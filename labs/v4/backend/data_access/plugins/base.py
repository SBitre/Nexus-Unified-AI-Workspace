"""
Nexus — plugin interface (data access tier)

Every external service Nexus reads from is reached through a plugin that
implements ServicePlugin. The application logic tier depends only on this
interface: it asks each registered plugin for items and merges what comes
back, without knowing whether the data came from Gmail, Notion, a calendar,
or a fixture file.

This is the contract that keeps the tiers independent. It is frozen for
Version 3 — changing a method signature here means changing every plugin
and the logic tier that calls them, so raise it with the team first.

Adding a new service:
    1. Create data_access/plugins/<service>.py
    2. Subclass ServicePlugin and implement name, kind and fetch_items
    3. Register it in the plugin registry
No other tier needs to change.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Any


class Priority(str, Enum):
    """How urgent an item is.

    Stored as a string so it serialises straight to JSON for the API
    response without a conversion step.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ServiceKind(str, Enum):
    """The category of service a plugin talks to.

    The logic tier uses this to decide which plugins are worth querying
    for a given request — a question about meetings need not hit a mail
    service. Add a member here when a genuinely new category appears.
    """

    MAIL = "mail"
    CALENDAR = "calendar"
    NOTES = "notes"
    CHAT = "chat"
    CODE = "code"


@dataclass
class WorkItem:
    """One thing the user may need to act on, from any service.

    This is the common shape every plugin returns. It is deliberately
    small: fields that only one service provides belong in `extra`, not
    as new top-level fields, so that adding a service never changes this
    class and therefore never changes the tiers above it.

    Attributes:
        item_id:    Unique within the source service.
        source:     Which plugin produced this, matching ServicePlugin.name.
        title:      Short human-readable summary, shown as the row label.
        due:        When it needs attention. None if the service gives no date.
        priority:   Urgency, defaulting to medium when the source has no
                    concept of priority.
        url:        Deep link back into the source service, if one exists.
        extra:      Service-specific fields (sender, attendee list, database
                    id). The presentation tier may display these; the logic
                    tier does not depend on them.
    """

    item_id: str
    source: str
    title: str
    due: datetime | date | None = None
    priority: Priority = Priority.MEDIUM
    url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict for the API response.

        Dates become ISO strings and the enum becomes its value, so the
        route layer can hand the result straight to FastAPI.
        """
        payload = asdict(self)
        payload["priority"] = self.priority.value
        if self.due is not None:
            payload["due"] = self.due.isoformat()
        return payload


class PluginError(Exception):
    """A plugin could not complete a request.

    Plugins raise this instead of letting a provider-specific exception
    escape, so the logic tier can degrade gracefully — reporting that one
    service was unavailable while still returning results from the others.
    """

    def __init__(self, source: str, message: str):
        self.source = source
        super().__init__(f"{source}: {message}")


class ServicePlugin(ABC):
    """Base class every service integration implements.

    Subclasses are constructed by the registry and must not perform
    network calls in __init__ — connecting belongs in `connect`, so that
    a plugin can be registered and inspected without being authenticated.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier, lowercase, e.g. "gmail". Used as WorkItem.source."""

    @property
    @abstractmethod
    def kind(self) -> ServiceKind:
        """The category of service this plugin talks to."""

    @property
    def display_name(self) -> str:
        """Label shown in the interface. Defaults to a tidied `name`."""
        return self.name.replace("_", " ").title()

    def connect(self) -> None:
        """Establish credentials or a session.

        Called once by the registry before the first fetch. The default
        does nothing, which suits plugins backed by fixture data.
        """
        return None

    @property
    def requires_auth(self) -> bool:
        """Whether this plugin needs a stored credential to run.

        The gateway checks this before fetching. Fixture-backed plugins in
        Version 3 return False; a plugin calling a real service overrides
        it to True so the gateway enforces authorisation.
        """
        return False

    @property
    def is_connected(self) -> bool:
        """Whether this plugin is ready to serve requests.

        The settings screen uses this to show connection status.
        """
        return True

    @abstractmethod
    def fetch_items(
        self,
        start: date,
        end: date,
        limit: int = 50,
    ) -> list[WorkItem]:
        """Return items from this service falling between start and end.

        Args:
            start: First date to include, inclusive.
            end:   Last date to include, inclusive.
            limit: Maximum number of items to return. Plugins should
                   respect this to keep responses bounded.

        Returns:
            A list of WorkItem, possibly empty. Order is not guaranteed;
            the logic tier sorts after merging.

        Raises:
            PluginError: If the service is unreachable or rejects the
                request. Provider-specific exceptions must be caught and
                re-raised as PluginError.
        """

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r} kind={self.kind.value!r}>"
