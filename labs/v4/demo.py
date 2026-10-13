"""
Command-line demonstration of the server-side tiers.

Exercises the application, data access and database layers without the API
or a browser: plugin discovery, a sync into the database, all four CRUD
operations, input validation, ownership scoping, cache behaviour on a
repeat run, and the request log.

Run from the project root:
    python demo.py

Runs against SQLite by default. For Supabase:
    export NEXUS_DB_BACKEND=supabase
    export SUPABASE_DB_URL=postgresql://postgres:<password>@<host>:5432/postgres
"""

from datetime import date

from backend.data_access.repositories import cache, history, users, work_items
from backend.db import adapter
from backend.services import ai_client, assistant, sync
from backend.services.registry import registry

REFERENCE_DAY = date(2026, 9, 29)
WEEK_START, WEEK_END = date(2026, 9, 28), date(2026, 10, 4)


def rule(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("-" * 72)


def main() -> None:
    adapter.initialise()
    cache.clear()

    user = users.current_user()
    print(f"Backend:  {adapter.backend_name()}")
    print(f"User:     {user['display_name']} <{user['email']}> (id={user['id']})")
    print(f"AI model: {'configured' if ai_client.is_configured() else 'not configured — rule-based fallback'}")

    rule("Plugins discovered at runtime")
    for plugin in registry.all_plugins():
        print(f"  {plugin.display_name:<18} kind={plugin.kind.value}")

    rule("SYNC — pulling connected services into the database")
    report = sync.sync_all(WEEK_START, WEEK_END, user["id"])
    print(f"  synced={report.synced} failed={report.failed} rows={report.item_count}")

    rule("CREATE — the user adds an item of their own")
    created = work_items.create(
        user_id=user["id"],
        title="Prepare Monday planning agenda",
        due_at="2026-09-30T09:00:00",
        priority="high",
        notes="Pull talking points from last week's retro",
    )
    print(f"  id={created['id']}  {created['title']}  [{created['priority']}] {created['status']}")

    rule("READ — open items for the week, soonest first")
    for item in work_items.list_items(user["id"], "2026-09-28", "2026-10-05"):
        when = (item["due_at"] or "no date")[:16].replace("T", " ")
        print(f"  [{item['priority']:<6}] {when:<17} {item['source']:<9} {item['title']}")

    rule("UPDATE — edit the item, then mark it done")
    work_items.update(user["id"], created["id"], priority="medium", title="Prepare planning agenda")
    done = work_items.set_status(user["id"], created["id"], "done")
    print(f"  id={done['id']}  {done['title']}  [{done['priority']}] {done['status']}")
    print(f"  still open this week: {len(work_items.list_items(user['id'], '2026-09-28', '2026-10-05'))}")

    rule("Validation — bad input is rejected before it reaches the database")
    for bad in ({"priority": "urgent"}, {"title": "   "}):
        try:
            work_items.update(user["id"], created["id"], **bad)
            print(f"  {bad} -> accepted (unexpected)")
        except ValueError as error:
            print(f"  {bad} -> rejected: {error}")
    print(f"  another user's id -> {work_items.get(999, created['id'])}")

    rule("DELETE")
    print(f"  delete id={created['id']} -> {work_items.delete(user['id'], created['id'])}")
    print(f"  delete again      -> {work_items.delete(user['id'], created['id'])}")

    rule("Re-sync is an upsert, not a duplicate")
    before = len(work_items.list_items(user["id"], status="all", limit=500))
    again = sync.sync_all(WEEK_START, WEEK_END, user["id"])
    after = len(work_items.list_items(user["id"], status="all", limit=500))
    print(f"  rows before={before}  after={after}  cache_hits={again.cache_hits}/{len(again.synced)}")

    rule("ASK — the assistant answers from stored rows")
    for question in ("What is due this week?", "Any Slack mentions this week?"):
        result = assistant.answer(question, today=REFERENCE_DAY)
        print(f"  Q: {question}")
        print(f"     {result.summary}")
        print(f"     intent={result.intent_label} sources={result.sources_used} {result.duration_ms}ms")

    rule("Request history (database tier)")
    for row in history.recent(limit=4):
        print(f"  {row['asked_at']}  {row['intent']:<18} items={row['item_count']}")


if __name__ == "__main__":
    main()
