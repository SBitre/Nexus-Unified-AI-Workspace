"""Notion plugin (data access tier)."""

from datetime import date

from .base import PluginError, ServiceKind, ServicePlugin, WorkItem
from .fixture_source import items_in_range


class NotionPlugin(ServicePlugin):
    """Reads database pages that carry a due date.

    Version 3 serves prepared fixture data. Notion's own database name,
    status and assignee travel in WorkItem.extra.
    """

    @property
    def name(self) -> str:
        return "notion"

    @property
    def kind(self) -> ServiceKind:
        return ServiceKind.NOTES

    @property
    def display_name(self) -> str:
        return "Notion"

    def fetch_items(self, start: date, end: date, limit: int = 50) -> list[WorkItem]:
        try:
            return items_in_range("notion.json", self.name, start, end, limit)
        except (OSError, ValueError, KeyError) as error:
            raise PluginError(self.name, f"could not read pages ({error})") from error
