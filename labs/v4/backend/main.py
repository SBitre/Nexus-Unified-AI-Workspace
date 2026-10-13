"""
Nexus — API boundary (Contract A).

The interface between the presentation tier in the browser and the
application tier on the server. Deliberately thin: each route validates
its input, calls one function in the tier below, and returns the result.
No business rules and no SQL appear here.

Version 4 adds full CRUD over work items, plus a sync endpoint that pulls
connected services into the database.

Run from the project root:
    uvicorn backend.main:app --reload
"""

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .data_access import gateway
from .data_access.repositories import cache, history, preferences, users, work_items
from .db import adapter
from .services import ai_client, assistant, sync
from .services.registry import registry

app = FastAPI(
    title="Nexus API",
    version="4.0.0",
    description="Unified AI workspace assistant — dynamic database release.",
)

# The front end is opened as a local file during development, which the
# browser treats as a null origin. Acceptable for a local prototype; would
# be restricted to known hosts before deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    adapter.initialise()
    cache.purge_expired()


def _user_id() -> int:
    """The active user, or a 500 if the database was never initialised."""
    user_id = users.current_user_id()
    if user_id is None:
        raise HTTPException(status_code=500, detail="No user configured")
    return user_id


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "database": adapter.backend_name(),
        "plugins": len(registry.all_plugins()),
        "ai_model": "configured" if ai_client.is_configured() else "rule-based fallback",
    }


@app.get("/api/plugins")
def list_plugins() -> list[dict[str, Any]]:
    """Registered plugins with open item counts, for the settings screen."""
    counts = work_items.counts_by_source(_user_id())
    return [
        {
            "name": plugin.name,
            "display_name": plugin.display_name,
            "kind": plugin.kind.value,
            "connected": gateway.is_authorised(plugin) and plugin.is_connected,
            "open_items": counts.get(plugin.name, 0),
        }
        for plugin in registry.all_plugins()
    ]


@app.get("/api/me")
def me() -> dict[str, Any]:
    user = users.current_user()
    if user is None:
        raise HTTPException(status_code=404, detail="No user configured")
    return user


# ---------------------------------------------------------------------------
# Work items — CRUD
# ---------------------------------------------------------------------------
class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_at: str | None = None
    priority: str = Field(default="medium", pattern="^(high|medium|low)$")
    notes: str | None = Field(default=None, max_length=2000)
    url: str | None = None


class ItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    due_at: str | None = None
    priority: str | None = Field(default=None, pattern="^(high|medium|low)$")
    status: str | None = Field(default=None, pattern="^(open|done|archived)$")
    notes: str | None = Field(default=None, max_length=2000)
    url: str | None = None


@app.get("/api/items")
def read_items(
    start: str | None = None,
    end: str | None = None,
    status: str = Query(default="open", pattern="^(open|done|archived|all)$"),
    source: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """List items, filtered by date window, status and service."""
    return work_items.list_items(
        user_id=_user_id(), start=start, end=end,
        status=status, source=source, limit=limit,
    )


@app.get("/api/items/{item_id}")
def read_item(item_id: int) -> dict[str, Any]:
    item = work_items.get(_user_id(), item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/api/items", status_code=201)
def create_item(payload: ItemCreate) -> dict[str, Any]:
    """Create an item owned by the user rather than synced from a service."""
    try:
        return work_items.create(
            user_id=_user_id(),
            title=payload.title,
            due_at=payload.due_at,
            priority=payload.priority,
            notes=payload.notes,
            url=payload.url,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.patch("/api/items/{item_id}")
def update_item(item_id: int, payload: ItemUpdate) -> dict[str, Any]:
    """Update whichever fields were supplied. Omitted fields are untouched."""
    try:
        item = work_items.update(_user_id(), item_id, **payload.model_dump(exclude_unset=True))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.delete("/api/items/{item_id}", status_code=204)
def delete_item(item_id: int) -> None:
    if not work_items.delete(_user_id(), item_id):
        raise HTTPException(status_code=404, detail="Item not found")


# ---------------------------------------------------------------------------
# Sync and ask
# ---------------------------------------------------------------------------
class SyncRequest(BaseModel):
    start: date
    end: date


@app.post("/api/sync")
def run_sync(request: SyncRequest) -> dict[str, Any]:
    """Pull every connected service into the database for a date window."""
    if request.end < request.start:
        raise HTTPException(status_code=422, detail="end must not precede start")
    return sync.sync_all(request.start, request.end, _user_id()).to_dict()


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    today: date | None = None
    sync: bool = True


@app.post("/api/ask")
def ask(request: AskRequest) -> dict[str, Any]:
    """Answer one natural-language question from stored items."""
    try:
        result = assistant.answer(request.question, today=request.today, do_sync=request.sync)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Assistant failed: {error}") from error
    return result.to_dict()


@app.get("/api/history")
def read_history(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    return history.recent(limit=limit)


# ---------------------------------------------------------------------------
# Preferences and cache
# ---------------------------------------------------------------------------
@app.get("/api/preferences")
def read_preferences() -> dict[str, str]:
    return preferences.all_values()


class PreferenceUpdate(BaseModel):
    key: str = Field(min_length=1, max_length=50)
    value: str = Field(max_length=200)


@app.post("/api/preferences")
def write_preference(update: PreferenceUpdate) -> dict[str, str]:
    preferences.set_value(update.key, update.value)
    return preferences.all_values()


@app.post("/api/cache/clear")
def clear_cache() -> dict[str, str]:
    cache.clear()
    return {"status": "cleared"}
