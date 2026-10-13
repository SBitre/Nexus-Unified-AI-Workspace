"""Slack plugin (data access tier)."""

from datetime import date

from .base import PluginError, ServiceKind, ServicePlugin, WorkItem
from .fixture_source import items_in_range


class SlackPlugin(ServicePlugin):
    """Reads messages and mentions that need a response.

    Note for the live implementation: Slack rate-limits history-reading
    methods for apps distributed outside its marketplace, so Nexus is
    built as an internal workspace app, which is exempt. Free workspaces
    also retain only 90 days of history.
    """

    @property
    def name(self) -> str:
        return "slack"

    @property
    def kind(self) -> ServiceKind:
        return ServiceKind.CHAT

    @property
    def display_name(self) -> str:
        return "Slack"

    def fetch_items(self, start: date, end: date, limit: int = 50) -> list[WorkItem]:
        try:
            return items_in_range("slack.json", self.name, start, end, limit)
        except (OSError, ValueError, KeyError) as error:
            raise PluginError(self.name, f"could not read messages ({error})") from error
