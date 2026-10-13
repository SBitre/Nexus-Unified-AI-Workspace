"""
Shared fixture loader for the Version 3 plugins.

Every plugin in this release reads from a JSON file rather than calling a
live service. Keeping that loading in one place means each plugin file
contains only what is specific to its service, and swapping a plugin over
to a real API later touches that one file and nothing else.
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .base import Priority, WorkItem

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> list[dict[str, Any]]:
    """Read a fixture file and return its raw records."""
    path = FIXTURE_DIR / filename
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def to_work_item(record: dict[str, Any], source: str) -> WorkItem:
    """Convert one fixture record into the shared WorkItem shape."""
    due_raw = record.get("due")
    return WorkItem(
        item_id=record["item_id"],
        source=source,
        title=record["title"],
        due=datetime.fromisoformat(due_raw) if due_raw else None,
        priority=Priority(record.get("priority", "medium")),
        url=record.get("url"),
        extra=record.get("extra", {}),
    )


def items_in_range(
    filename: str,
    source: str,
    start: date,
    end: date,
    limit: int,
) -> list[WorkItem]:
    """Load a fixture, convert it, and filter to the requested date range.

    Items with no date are always included, since a service that gives no
    due date still has something the user may need to see.
    """
    results: list[WorkItem] = []
    for record in load_fixture(filename):
        item = to_work_item(record, source)
        if item.due is None:
            results.append(item)
            continue
        item_date = item.due.date() if isinstance(item.due, datetime) else item.due
        if start <= item_date <= end:
            results.append(item)
    return results[:limit]
