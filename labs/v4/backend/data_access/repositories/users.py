"""
Data access tier — users repository.

Version 4 operates as one local user; this module is where multi-user
lookup goes when sign-in is added, so the tiers above already ask for
"the current user" rather than assuming one exists.
"""

from typing import Any

from ...db import adapter
from ...db.adapter import DEFAULT_USER_EMAIL


def current_user() -> dict[str, Any] | None:
    """Return the active user."""
    return adapter.query_one(
        "SELECT id, email, display_name FROM users WHERE email = ?",
        (DEFAULT_USER_EMAIL,),
    )


def current_user_id() -> int | None:
    user = current_user()
    return user["id"] if user else None
