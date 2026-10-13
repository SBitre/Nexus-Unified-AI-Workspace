"""
Application logic tier — the assistant workflow.

Version 4 answers from the database rather than from the plugins directly.
The sequence is: classify the question, make sure the relevant services
have been synced into storage, query the stored items for the requested
window, and summarise.

Reading from storage is what lets an answer include items the user created
in Nexus alongside items from Gmail or Notion, and lets an item the user
marked done drop out of the answer without the provider knowing anything
about it.
"""

import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from ..data_access.repositories import history, users, work_items
from . import ai_client
from . import sync as sync_module
from .registry import registry


@dataclass
class AssistantAnswer:
    """Everything the presentation tier needs to render one answer."""

    question: str
    summary: str
    items: list[dict[str, Any]]
    intent_label: str
    parsed_by: str
    sources_used: list[str]
    sources_failed: list[str] = field(default_factory=list)
    cache_hits: int = 0
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "summary": self.summary,
            "items": self.items,
            "trace": {
                "intent": self.intent_label,
                "parsed_by": self.parsed_by,
                "sources_used": self.sources_used,
                "sources_failed": self.sources_failed,
                "cache_hits": self.cache_hits,
                "item_count": len(self.items),
                "duration_ms": self.duration_ms,
            },
        }


def _display_names(sources: list[str]) -> list[str]:
    """Map plugin names to labels, leaving unknown sources as-is."""
    lookup = {p.name: p.display_name for p in registry.all_plugins()}
    lookup["nexus"] = "Nexus"
    return [lookup.get(name, name.title()) for name in sources]


def _summarise(items: list[dict[str, Any]], sources: list[str], failed: list[str]) -> str:
    """Build the overview sentence shown above the results."""
    if not items:
        return "Nothing is scheduled or outstanding in that period across your connected apps."

    high = sum(1 for item in items if item.get("priority") == "high")
    labels = _display_names(sources)

    if len(labels) > 1:
        source_text = f"{', '.join(labels[:-1])} and {labels[-1]}"
    else:
        source_text = labels[0] if labels else "your connected apps"

    sentence = f"You have {len(items)} item{'s' if len(items) != 1 else ''} across {source_text}."
    if high:
        sentence += f" {high} {'is' if high == 1 else 'are'} marked as high priority."
    if failed:
        sentence += f" {', '.join(failed)} could not be reached, so those results are missing."
    return sentence


def answer(question: str, today: date | None = None, do_sync: bool = True) -> AssistantAnswer:
    """Answer one question from stored items.

    Args:
        question: The user's text.
        today:    Reference date, injectable for reproducible demonstrations.
        do_sync:  Whether to refresh from the connected services first. The
                  cache means a repeated question rarely re-queries a
                  provider even with this left on.
    """
    started = time.perf_counter()
    user_id = users.current_user_id()

    parsed = ai_client.parse_intent(question, today=today)
    failed: list[str] = []
    cache_hits = 0

    if do_sync:
        report = sync_module.sync_all(parsed.intent.start, parsed.intent.end, user_id)
        failed = report.failed
        cache_hits = report.cache_hits

    # The window extends to the start of the following day so an item due
    # at 5pm on the last day is not cut off by a midnight boundary.
    start_text = parsed.intent.start.isoformat()
    end_text = (parsed.intent.end + timedelta(days=1)).isoformat()

    items = work_items.list_items(
        user_id=user_id, start=start_text, end=end_text, status="open"
    )

    # Intent may name particular service categories; filter to those.
    if parsed.intent.kinds:
        wanted = {p.name for p in registry.by_kinds(parsed.intent.kinds)}
        wanted.add("nexus")  # the user's own items always count
        items = [item for item in items if item["source"] in wanted]

    sources_used = sorted({item["source"] for item in items})
    duration_ms = int((time.perf_counter() - started) * 1000)

    result = AssistantAnswer(
        question=question,
        summary=_summarise(items, sources_used, failed),
        items=items,
        intent_label=parsed.intent.label,
        parsed_by=parsed.parsed_by,
        sources_used=sources_used,
        sources_failed=failed,
        cache_hits=cache_hits,
        duration_ms=duration_ms,
    )

    # Recording the request is a side effect of answering, so a storage
    # failure must never lose the user's result.
    try:
        history.record(
            user_id=user_id,
            question=question,
            intent=parsed.intent.label,
            parsed_by=parsed.parsed_by,
            sources_used=sources_used,
            cache_hits=cache_hits,
            item_count=len(items),
            duration_ms=duration_ms,
        )
    except Exception:  # noqa: BLE001
        pass

    return result
