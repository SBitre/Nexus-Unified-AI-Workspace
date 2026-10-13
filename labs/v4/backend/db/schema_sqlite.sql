-- Nexus — Version 4 schema (SQLite)
--
-- Six tables. work_items is the centre: everything the user can act on,
-- whether synced from an external service or created in Nexus itself.
-- The rest support it — identity, credentials, caching, history, settings.

CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    email        TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

-- OAuth credentials, one row per user per service. Only the data access
-- tier reads these; no token is visible to the layers above.
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    service       TEXT NOT NULL,
    access_token  TEXT,
    refresh_token TEXT,
    expires_at    TEXT,
    scopes        TEXT,
    updated_at    TEXT NOT NULL,
    UNIQUE (user_id, service)
);

-- The core entity. An item either came from a connected service, where
-- source names the plugin and external_id is that service's own
-- identifier, or it was created in Nexus, where source is 'nexus' and
-- external_id is null.
--
-- The unique constraint on (user_id, source, external_id) is what makes a
-- re-sync an upsert rather than a duplicate: syncing twice updates the
-- existing rows instead of inserting a second copy.
CREATE TABLE IF NOT EXISTS work_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    external_id TEXT,
    title       TEXT NOT NULL,
    notes       TEXT,
    due_at      TEXT,
    priority    TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('high', 'medium', 'low')),
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'done', 'archived')),
    url         TEXT,
    extra       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (user_id, source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_items_due ON work_items (user_id, due_at);
CREATE INDEX IF NOT EXISTS idx_items_status ON work_items (user_id, status);
CREATE INDEX IF NOT EXISTS idx_items_source ON work_items (user_id, source);

-- Short-lived cache of what each service returned, keyed by service and
-- date window, so a repeated sync does not re-query the provider.
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key  TEXT PRIMARY KEY,
    service    TEXT NOT NULL,
    payload    TEXT NOT NULL,
    stored_at  TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_expires ON response_cache (expires_at);

-- Every answered question, with which parser handled it and which
-- services contributed. Backs the agent trace view.
CREATE TABLE IF NOT EXISTS query_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER REFERENCES users (id) ON DELETE SET NULL,
    asked_at     TEXT NOT NULL,
    question     TEXT NOT NULL,
    intent       TEXT NOT NULL,
    parsed_by    TEXT NOT NULL,
    sources_used TEXT NOT NULL,
    cache_hits   INTEGER NOT NULL DEFAULT 0,
    item_count   INTEGER NOT NULL,
    duration_ms  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_asked_at ON query_history (asked_at DESC);

CREATE TABLE IF NOT EXISTS preferences (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
