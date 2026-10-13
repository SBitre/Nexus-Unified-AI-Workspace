"""
Data access tier — work items repository.

Full CRUD over the central table. Every query lives here; no SQL appears
in the application or presentation tiers, which is why moving from SQLite
to Supabase changed this file's backend and not its callers.

Items arrive two ways. A sync pulls them from a connected service, keyed
by source and that service's own identifier, which makes a repeated sync
an upsert rather than a duplicate. A user can also create an item
directly, in which case source is 'nexus' and there is no external id.
"""

import json
from datetime import datetime, timezone
from typing import Any

from ...db import adapter

VALID_PRIORITIES = {"high", "medium", "low"}
VALID_STATUSES = {"open", "done", "archived"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _decode(row: dict[str, Any]) -> dict[str, Any]:
    """Normalise a row for callers.

    PostgreSQL returns JSONB already parsed; SQLite returns the text it
    was given. Both are handed back as a dictionary.
    """
    extra = row.get("extra")
    if isinstance(extra, str):
        try:
            extra = json.loads(extra)
        except (json.JSONDecodeError, TypeError):
            extra = {}
    row["extra"] = extra or {}
    return row


def _encode_extra(extra: dict[str, Any] | None) -> str:
    return json.dumps(extra or {})


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def create(
    user_id: int,
    title: str,
    due_at: str | None = None,
    priority: str = "medium",
    notes: str | None = None,
    url: str | None = None,
    source: str = "nexus",
    external_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert one item and return it.

    Raises:
        ValueError: If priority is outside the permitted set or the title
            is blank. The database enforces both as well; checking here
            gives a clearer message than a constraint violation.
    """
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"priority must be one of {sorted(VALID_PRIORITIES)}")
    if not title.strip():
        raise ValueError("title cannot be empty")

    stamp = _now()
    row = adapter.execute_returning(
        """
        INSERT INTO work_items
            (user_id, source, external_id, title, notes, due_at,
             priority, status, url, extra, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
        RETURNING *
        """,
        (user_id, source, external_id, title.strip(), notes, due_at,
         priority, url, _encode_extra(extra), stamp, stamp),
    )
    return _decode(row) if row else {}


def upsert_from_service(
    user_id: int,
    source: str,
    external_id: str,
    title: str,
    due_at: str | None,
    priority: str,
    url: str | None,
    extra: dict[str, Any] | None,
) -> None:
    """Insert or refresh one item synced from an external service.

    The user's status is preserved deliberately: an item marked done in
    Nexus stays done when the service is synced again, because completion
    is the user's decision rather than the provider's.
    """
    stamp = _now()
    adapter.execute(
        """
        INSERT INTO work_items
            (user_id, source, external_id, title, due_at, priority,
             status, url, extra, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
        ON CONFLICT (user_id, source, external_id) DO UPDATE SET
            title      = EXCLUDED.title,
            due_at     = EXCLUDED.due_at,
            priority   = EXCLUDED.priority,
            url        = EXCLUDED.url,
            extra      = EXCLUDED.extra,
            updated_at = EXCLUDED.updated_at
        """,
        (user_id, source, external_id, title, due_at, priority,
         url, _encode_extra(extra), stamp, stamp),
    )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def list_items(
    user_id: int,
    start: str | None = None,
    end: str | None = None,
    status: str | None = "open",
    source: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return items matching the filters, soonest first.

    Items with no due date are included and sort last, since a task
    without a date is still outstanding.
    """
    clauses = ["user_id = ?"]
    params: list[Any] = [user_id]

    if status and status != "all":
        clauses.append("status = ?")
        params.append(status)
    if source:
        clauses.append("source = ?")
        params.append(source)
    if start:
        clauses.append("(due_at IS NULL OR due_at >= ?)")
        params.append(start)
    if end:
        clauses.append("(due_at IS NULL OR due_at <= ?)")
        params.append(end)

    params.append(limit)
    rows = adapter.query(
        f"""
        SELECT * FROM work_items
        WHERE {' AND '.join(clauses)}
        ORDER BY (due_at IS NULL), due_at ASC,
                 CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                 title
        LIMIT ?
        """,
        params,
    )
    return [_decode(row) for row in rows]


def get(user_id: int, item_id: int) -> dict[str, Any] | None:
    """Return one item, scoped to its owner.

    The user_id condition is not decoration: without it, any id would
    expose any user's row once sign-in is added.
    """
    row = adapter.query_one(
        "SELECT * FROM work_items WHERE id = ? AND user_id = ?",
        (item_id, user_id),
    )
    return _decode(row) if row else None


def counts_by_source(user_id: int) -> dict[str, int]:
    """Open item totals per service, for the settings screen."""
    rows = adapter.query(
        """
        SELECT source, COUNT(*) AS total
        FROM work_items
        WHERE user_id = ? AND status = 'open'
        GROUP BY source
        """,
        (user_id,),
    )
    return {row["source"]: int(row["total"]) for row in rows}


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
def update(user_id: int, item_id: int, **fields: Any) -> dict[str, Any] | None:
    """Update whichever fields were supplied and return the stored row.

    Only named columns can be written, so an unexpected key cannot reach
    the SQL. Returns None if the item does not exist or is not owned by
    this user.
    """
    allowed = {"title", "notes", "due_at", "priority", "status", "url"}
    updates = {k: v for k, v in fields.items() if k in allowed}

    if "priority" in updates and updates["priority"] not in VALID_PRIORITIES:
        raise ValueError(f"priority must be one of {sorted(VALID_PRIORITIES)}")
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
    if "title" in updates and not str(updates["title"]).strip():
        raise ValueError("title cannot be empty")

    if not updates:
        return get(user_id, item_id)

    assignments = ", ".join(f"{column} = ?" for column in updates)
    params = list(updates.values()) + [_now(), item_id, user_id]

    row = adapter.execute_returning(
        f"""
        UPDATE work_items
        SET {assignments}, updated_at = ?
        WHERE id = ? AND user_id = ?
        RETURNING *
        """,
        params,
    )
    return _decode(row) if row else None


def set_status(user_id: int, item_id: int, status: str) -> dict[str, Any] | None:
    """Mark an item open, done or archived."""
    return update(user_id, item_id, status=status)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
def delete(user_id: int, item_id: int) -> bool:
    """Remove one item. Returns False if it was not there."""
    return adapter.execute(
        "DELETE FROM work_items WHERE id = ? AND user_id = ?",
        (item_id, user_id),
    ) > 0


def delete_by_source(user_id: int, source: str) -> int:
    """Remove every item from one service. Used when disconnecting it."""
    return adapter.execute(
        "DELETE FROM work_items WHERE user_id = ? AND source = ?",
        (user_id, source),
    )
