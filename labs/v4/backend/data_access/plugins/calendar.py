"""Google Calendar plugin (data access tier)."""

from datetime import date

from .base import PluginError, ServiceKind, ServicePlugin, WorkItem
from .fixture_source import items_in_range


class CalendarPlugin(ServicePlugin):
    """Reads scheduled events in the requested window.

    Version 3 serves prepared fixture data. The event end time and
    attendee list are carried in WorkItem.extra rather than as top-level
    fields, so that no other service is forced to supply them.
    """

    @property
    def name(self) -> str:
        return "calendar"

    @property
    def kind(self) -> ServiceKind:
        return ServiceKind.CALENDAR

    @property
    def display_name(self) -> str:
        return "Google Calendar"

    def fetch_items(self, start: date, end: date, limit: int = 50) -> list[WorkItem]:
        try:
            return items_in_range("calendar.json", self.name, start, end, limit)
        except (OSError, ValueError, KeyError) as error:
            raise PluginError(self.name, f"could not read events ({error})") from error
