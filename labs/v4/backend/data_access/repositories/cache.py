"""
Data access tier — response cache repository.

Stores serialised plugin results against a key built from the plugin name
and date window. A repeated sync inside the time-to-live is served from
here rather than re-querying the provider.

Caching lives in this tier, not above: the logic tier asks for items and
should not know whether a network call happened.
"""

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ...db import adapter

DEFAULT_TTL_SECONDS = 300


def build_key(service: str, start: date, end: date) -> str:
    """Deterministic cache key for one service and date window."""
    return f"{service}:{start.isoformat()}:{end.isoformat()}"


def get(cache_key: str) -> list[dict[str, Any]] | None:
    """Return cached records, or None if absent or expired."""
    row = adapter.query_one(
        "SELECT payload FROM response_cache WHERE cache_key = ? AND expires_at > ?",
        (cache_key, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    if row is None:
        return None
    try:
        return json.loads(row["payload"])
    except (json.JSONDecodeError, TypeError):
        # A corrupt entry is treated as a miss rather than an error.
        return None


def put(
    cache_key: str,
    service: str,
    records: list[dict[str, Any]],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Store records under a key with a time-to-live."""
    now = datetime.now(timezone.utc)
    adapter.execute(
        """
        INSERT INTO response_cache (cache_key, service, payload, stored_at, expires_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (cache_key) DO UPDATE SET
            payload    = EXCLUDED.payload,
            stored_at  = EXCLUDED.stored_at,
            expires_at = EXCLUDED.expires_at
        """,
        (cache_key, service, json.dumps(records),
         now.isoformat(timespec="seconds"),
         (now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")),
    )


def purge_expired() -> int:
    """Delete entries past their expiry."""
    return adapter.execute(
        "DELETE FROM response_cache WHERE expires_at <= ?",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"),),
    )


def clear() -> None:
    """Empty the cache entirely."""
    adapter.execute("DELETE FROM response_cache", ())
