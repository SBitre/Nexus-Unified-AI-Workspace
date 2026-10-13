"""
Application logic tier — service synchronisation.

Version 3 queried the plugins on every question and discarded the results.
Version 4 pulls them into the database first, and the assistant answers
from stored rows.

That change is what makes the application dynamic rather than merely live.
Once an item is a database row the user can act on it — edit the title,
change the priority, mark it done, delete it — and those edits survive the
next sync, because a sync updates the provider's fields and leaves the
user's status alone.
"""

from dataclasses import dataclass
from datetime import date

from ..data_access import gateway
from ..data_access.plugins.base import PluginError
from ..data_access.repositories import users, work_items
from .registry import registry


@dataclass
class SyncReport:
    """What one synchronisation run did."""

    synced: list[str]
    failed: list[str]
    item_count: int
    cache_hits: int

    def to_dict(self) -> dict[str, object]:
        return {
            "synced": self.synced,
            "failed": self.failed,
            "item_count": self.item_count,
            "cache_hits": self.cache_hits,
        }


def sync_all(start: date, end: date, user_id: int | None = None) -> SyncReport:
    """Pull items from every registered plugin into the database.

    A plugin that fails is recorded and skipped, so one unavailable
    service does not prevent the others from syncing.
    """
    owner = user_id if user_id is not None else users.current_user_id()
    if owner is None:
        raise RuntimeError("No user configured; run database initialisation first")

    synced: list[str] = []
    failed: list[str] = []
    cache_hits = 0
    total = 0

    for plugin in registry.all_plugins():
        try:
            result = gateway.fetch(plugin, start, end)
        except PluginError:
            failed.append(plugin.display_name)
            continue

        if result.from_cache:
            cache_hits += 1

        for item in result.items:
            work_items.upsert_from_service(
                user_id=owner,
                source=item.source,
                external_id=item.item_id,
                title=item.title,
                due_at=item.due.isoformat() if item.due else None,
                priority=item.priority.value,
                url=item.url,
                extra=item.extra,
            )
            total += 1

        synced.append(plugin.name)

    return SyncReport(synced=synced, failed=failed, item_count=total, cache_hits=cache_hits)
