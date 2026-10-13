"""
Data access tier — preferences repository.

Key/value settings, so the settings screen can add a field without a
schema change. Values are stored as text; callers convert.
"""

from datetime import datetime, timezone

from ...db import adapter

DEFAULTS = {
    "theme": "dark",
    "response_style": "technical",
    "default_model": "gemini-flash-lite",
}


def get(key: str) -> str | None:
    """Return a stored preference, falling back to the built-in default."""
    row = adapter.query_one("SELECT value FROM preferences WHERE key = ?", (key,))
    return row["value"] if row is not None else DEFAULTS.get(key)


def set_value(key: str, value: str) -> None:
    """Insert or update a preference."""
    adapter.execute(
        """
        INSERT INTO preferences (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value,
            updated_at = EXCLUDED.updated_at
        """,
        (key, value, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )


def all_values() -> dict[str, str]:
    """Return every preference, with defaults filled in for missing keys."""
    rows = adapter.query("SELECT key, value FROM preferences", ())
    merged = dict(DEFAULTS)
    merged.update({row["key"]: row["value"] for row in rows})
    return merged
