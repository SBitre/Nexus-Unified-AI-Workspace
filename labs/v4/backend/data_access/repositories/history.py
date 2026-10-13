"""
Data access tier — request history repository.

Wraps query_history. The application tier records each answered question
here without writing SQL.
"""

from datetime import datetime, timezone
from typing import Any

from ...db import adapter


def record(
    user_id: int | None,
    question: str,
    intent: str,
    parsed_by: str,
    sources_used: list[str],
    cache_hits: int,
    item_count: int,
    duration_ms: int,
) -> None:
    """Store one answered question."""
    adapter.execute(
        """
        INSERT INTO query_history
            (user_id, asked_at, question, intent, parsed_by,
             sources_used, cache_hits, item_count, duration_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
         question, intent, parsed_by, ",".join(sources_used),
         cache_hits, item_count, duration_ms),
    )


def recent(limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent questions, newest first."""
    rows = adapter.query(
        """
        SELECT id, asked_at, question, intent, parsed_by,
               sources_used, cache_hits, item_count, duration_ms
        FROM query_history
        ORDER BY asked_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [
        {**row, "sources_used": row["sources_used"].split(",") if row["sources_used"] else []}
        for row in rows
    ]
