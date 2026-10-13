"""
Data access tier — OAuth token repository.

The only module that reads or writes service credentials. Plugins ask for
a token by service name; nothing in the application or presentation tiers
can see one, which is why authentication sits in this tier.

Version 4 stores placeholder values because the plugins read fixtures.
Before deployment these must be encrypted at rest.
"""

from datetime import datetime, timezone
from typing import Any

from ...db import adapter


def save(
    user_id: int,
    service: str,
    access_token: str,
    refresh_token: str | None = None,
    expires_at: str | None = None,
    scopes: str | None = None,
) -> None:
    """Insert or replace the token for one user and service."""
    adapter.execute(
        """
        INSERT INTO oauth_tokens
            (user_id, service, access_token, refresh_token,
             expires_at, scopes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, service) DO UPDATE SET
            access_token  = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at    = EXCLUDED.expires_at,
            scopes        = EXCLUDED.scopes,
            updated_at    = EXCLUDED.updated_at
        """,
        (user_id, service, access_token, refresh_token, expires_at, scopes,
         datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )


def get(user_id: int, service: str) -> dict[str, Any] | None:
    """Return the stored token for one service, or None if absent."""
    return adapter.query_one(
        """
        SELECT service, access_token, refresh_token, expires_at, scopes
        FROM oauth_tokens
        WHERE user_id = ? AND service = ?
        """,
        (user_id, service),
    )


def connected_services(user_id: int) -> set[str]:
    """Names of services this user holds a token for."""
    rows = adapter.query(
        "SELECT service FROM oauth_tokens WHERE user_id = ? AND access_token IS NOT NULL",
        (user_id,),
    )
    return {row["service"] for row in rows}
