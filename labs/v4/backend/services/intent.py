"""
Application logic tier — intent parsing.

Decides what the user is asking for and therefore which categories of
service are worth querying. Version 3 uses keyword matching, which is
deliberate: it keeps the tier boundary testable without a network call
or an API key. In the final project this function is replaced by a model
call, and because the return type stays the same, nothing else changes.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from ..data_access.plugins.base import ServiceKind


@dataclass
class Intent:
    """The parsed meaning of one question."""

    label: str
    kinds: set[ServiceKind]
    start: date
    end: date

    @property
    def kind_names(self) -> list[str]:
        return sorted(kind.value for kind in self.kinds)


_MAIL_WORDS = {"email", "emails", "mail", "inbox", "message", "messages", "reply"}
_CALENDAR_WORDS = {"meeting", "meetings", "calendar", "event", "events", "schedule"}
_NOTES_WORDS = {"note", "notes", "doc", "docs", "document", "page", "roadmap"}
_CHAT_WORDS = {"slack", "channel", "mention", "mentions", "dm", "thread"}
_TODAY_WORDS = {"today", "now", "currently"}
_WEEK_WORDS = {"week", "weekly", "this week", "upcoming"}


def window_for(days_ahead: int, today: date | None = None) -> tuple[date, date]:
    """Turn a forward-looking day count into a start and end date.

    Shared with the model-backed parser so both produce windows the same way.
    """
    reference = today or date.today()
    if days_ahead <= 0:
        return reference, reference
    if days_ahead == 7:
        monday = reference - timedelta(days=reference.weekday())
        return monday, monday + timedelta(days=6)
    return reference, reference + timedelta(days=days_ahead)


def parse(question: str, today: date | None = None) -> Intent:
    """Turn a natural-language question into an Intent.

    Args:
        question: The user's raw text.
        today:    Reference date, injectable so tests are deterministic.

    Returns:
        An Intent naming the service categories to query and the date
        window to ask them for. When no category is recognised, the set is
        left empty, which the registry treats as "query everything".
    """
    reference = today or date.today()
    words = set(question.lower().replace("?", " ").replace(",", " ").split())

    kinds: set[ServiceKind] = set()
    if words & _MAIL_WORDS:
        kinds.add(ServiceKind.MAIL)
    if words & _CALENDAR_WORDS:
        kinds.add(ServiceKind.CALENDAR)
    if words & _NOTES_WORDS:
        kinds.add(ServiceKind.NOTES)
    if words & _CHAT_WORDS:
        kinds.add(ServiceKind.CHAT)

    if words & _TODAY_WORDS:
        label = "today_overview" if not kinds else "today_filtered"
        return Intent(label, kinds, reference, reference)

    if words & _WEEK_WORDS:
        monday = reference - timedelta(days=reference.weekday())
        label = "week_overview" if not kinds else "week_filtered"
        return Intent(label, kinds, monday, monday + timedelta(days=6))

    # Default window: the next seven days.
    label = "general_overview" if not kinds else "general_filtered"
    return Intent(label, kinds, reference, reference + timedelta(days=7))
