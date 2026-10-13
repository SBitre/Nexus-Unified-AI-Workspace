# Nexus — Version 4

Dynamic database integration. Lab Exercise 4.

## What changed from Version 3

Version 3 had a database, but the interface never touched it: items came
from fixture files on every request, and nothing could be created, edited
or removed. Version 4 makes the items themselves database rows.

- **New central table, `work_items`.** Everything the user can act on,
  whether synced from a connected service or created in Nexus.
- **Full CRUD.** Create, read, update and delete over the API and in the
  interface — add a task, edit it inline, mark it done, remove it.
- **Sync instead of live querying.** Connected services are pulled into
  the database and the assistant answers from stored rows. An item marked
  done stays done when the service is synced again.
- **Supabase (PostgreSQL)** replaces SQLite as the primary backend, with
  SQLite kept as a no-credentials fallback.

## Database backends

Chosen from the environment at import time.

| Setting | Backend |
|---|---|
| nothing set | SQLite, a local file at `backend/db/nexus.db` |
| `NEXUS_DB_BACKEND=supabase` plus `SUPABASE_DB_URL` | Supabase (PostgreSQL) |

Both work because every tier above reaches the database through the
repositories, and the repositories reach it through `backend/db/adapter.py`.
Moving from SQLite to Postgres touched those two places and nothing else —
no change in the application or presentation tiers. The two schema files
differ only in key and JSON column types.

### Connecting to Supabase

```bash
export NEXUS_DB_BACKEND=supabase
export SUPABASE_DB_URL="postgresql://postgres:<password>@<host>:5432/postgres"
pip install "psycopg[binary]"
```

Run `backend/db/schema_postgres.sql` once in the Supabase SQL editor, or
let the application create the tables on first start.

## Running it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Then open `frontend/index.html`. API documentation at
`http://127.0.0.1:8000/docs`.

### Server tiers only, no dependencies

```bash
python demo.py
```

Walks through plugin discovery, a sync, all four CRUD operations, input
validation, ownership scoping, cache behaviour on a repeat run, and the
request history — using only the standard library.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/items` | List items by window, status and source |
| `GET` | `/api/items/{id}` | One item |
| `POST` | `/api/items` | Create an item |
| `PATCH` | `/api/items/{id}` | Update supplied fields only |
| `DELETE` | `/api/items/{id}` | Delete an item |
| `POST` | `/api/sync` | Pull connected services into the database |
| `POST` | `/api/ask` | Answer a question from stored items |
| `GET` | `/api/history` | Recent questions, for the trace view |
| `GET`/`POST` | `/api/preferences` | Read or write settings |
| `GET` | `/api/plugins` | Plugins and their open item counts |
| `GET` | `/api/health` | Status, active database, model configuration |

## The four tiers

| Tier | Location | Responsibility |
|---|---|---|
| Presentation | `frontend/` | Render views, capture input. No business rules. |
| Application | `backend/services/` | Business logic, AI model calls, workflows. |
| Data access | `backend/data_access/` | API clients, authentication, caching, all SQL. |
| Database | `backend/db/` | Schema, connections, backend selection. |

Contracts A, B and C between them are unchanged from Version 3; see
`docs/architecture.pdf`. The schema is in `docs/schema.pdf`.

## Data integrity

- A unique constraint on `(user_id, source, external_id)` makes a repeated
  sync an upsert rather than a duplicate insert.
- `CHECK` constraints on `priority` and `status` reject invalid values at
  the database even if a caller skips validation. The repository checks
  them too, to give a clearer message than a constraint violation.
- Every read and write is scoped by `user_id`, so an item id alone cannot
  reach another user's row once sign-in is added.
- A sync updates the provider's fields and leaves `status` alone, because
  completion is the user's decision rather than the provider's.
- Only named columns can be written by `update()`, so an unexpected key
  cannot reach the SQL.

## Known limitations

- Plugins read fixtures rather than live APIs, and the token table holds
  placeholder values. What this release demonstrates is the database
  integration; moving a plugin to its real service means replacing one
  method and setting `requires_auth` to True.
- The interface pins its date window to the sample week so the fixture
  data stays meaningful.
- Tokens are stored in plain text and must be encrypted before any real
  credential is handled.
- No authentication on the API, and CORS is open so the front end can be
  opened as a local file. Both would be restricted before deployment.
- SQLite allows one writer at a time. Supabase removes that ceiling, which
  is part of why it is now the primary backend.

## Tools used

Supabase's AI Assistant was used for schema design and query generation.
Generative AI assistance was used during development. Details are recorded
in the accompanying documentation.
