"""Gmail plugin (data access tier)."""

from datetime import date

from .base import PluginError, ServiceKind, ServicePlugin, WorkItem
from .fixture_source import items_in_range


class GmailPlugin(ServicePlugin):
    """Reads messages that need a reply or an action.

    Version 3 serves prepared fixture data. To move to the live service,
    replace the body of fetch_items with a Gmail API call and set
    is_connected from the OAuth token state. Nothing outside this file
    changes, because the return type stays the same.
    """

    @property
    def name(self) -> str:
        return "gmail"

    @property
    def kind(self) -> ServiceKind:
        return ServiceKind.MAIL

    @property
    def display_name(self) -> str:
        return "Gmail"

    def fetch_items(self, start: date, end: date, limit: int = 50) -> list[WorkItem]:
        try:
            return items_in_range("gmail.json", self.name, start, end, limit)
        except (OSError, ValueError, KeyError) as error:
            # Provider-specific failures are re-raised as PluginError so the
            # logic tier can drop this source and still answer from the rest.
            raise PluginError(self.name, f"could not read messages ({error})") from error
