"""
Data access tier — service gateway.

Sits between the application tier and the individual plugins, and is where
the two cross-cutting concerns shown in the data access layer of the
architecture diagram are applied: authentication and caching.

The application tier calls fetch(plugin, start, end) and receives items.
It does not know whether a network call happened, whether a cached copy
was used, or that a token was involved. Putting this here is what lets the
logic tier stay free of infrastructure concerns.
"""

from dataclasses import dataclass
from datetime import date

from .plugins.base import PluginError, ServicePlugin, WorkItem
from .plugins.fixture_source import to_work_item
from .repositories import cache, tokens, users


@dataclass
class FetchResult:
    """Items from one plugin, plus how they were obtained."""

    items: list[WorkItem]
    from_cache: bool
    authorised: bool


def _serialise(items: list[WorkItem]) -> list[dict]:
    """Convert items to cacheable records."""
    return [item.to_dict() for item in items]


def _deserialise(records: list[dict], source: str) -> list[WorkItem]:
    """Rebuild items from cached records."""
    return [to_work_item(record, source) for record in records]


def is_authorised(plugin: ServicePlugin) -> bool:
    """Whether a usable credential exists for this plugin.

    Version 3 plugins read fixtures and report themselves connected, so
    this returns True when either a stored token exists or the plugin
    declares it needs none. The lookup is written now so that enforcing
    real authorisation later is a change to this function alone.
    """
    if not plugin.requires_auth:
        return True
    user_id = users.current_user_id()
    if user_id is None:
        return False
    return plugin.name in tokens.connected_services(user_id)


def fetch(
    plugin: ServicePlugin,
    start: date,
    end: date,
    limit: int = 50,
    use_cache: bool = True,
) -> FetchResult:
    """Return items from one plugin, using the cache where possible.

    Raises:
        PluginError: If the plugin is unauthorised or its own fetch fails.
    """
    if not is_authorised(plugin):
        raise PluginError(plugin.name, "no valid credential stored")

    key = cache.build_key(plugin.name, start, end)

    if use_cache:
        cached = cache.get(key)
        if cached is not None:
            return FetchResult(_deserialise(cached, plugin.name), True, True)

    items = plugin.fetch_items(start, end, limit)

    if use_cache:
        try:
            cache.put(key, plugin.name, _serialise(items))
        except Exception:  # noqa: BLE001 - a cache write must never fail a request
            pass

    return FetchResult(items, False, True)
