"""
Database tier — backend adapter.

Nexus Version 4 runs against either Supabase (hosted PostgreSQL) or a local
SQLite file. The backend is chosen at import time from the environment:

    NEXUS_DB_BACKEND=supabase
    SUPABASE_DB_URL=postgresql://postgres:<password>@<host>:5432/postgres

With nothing set, SQLite is used, so the application runs with no account
and no network. That matters for review and for automated testing.

Supporting both is cheap because every tier above this one reaches the
database through the repositories, and the repositories reach it through
this module. Neither the application nor the presentation tier contains a
line that changes when the backend does.

SQL is written once in SQLite's "?" placeholder style and translated for
PostgreSQL here. The two schema files differ only in key and JSON types.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

BACKEND = os.environ.get("NEXUS_DB_BACKEND", "sqlite").lower()
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")

SQLITE_PATH = Path(__file__).parent / "nexus.db"
SCHEMA_SQLITE = Path(__file__).parent / "schema_sqlite.sql"
SCHEMA_POSTGRES = Path(__file__).parent / "schema_postgres.sql"

DEFAULT_USER_EMAIL = "local@nexus.app"
DEFAULT_USER_NAME = "Local User"


def using_supabase() -> bool:
    """Whether the Postgres backend is active and configured."""
    return BACKEND == "supabase" and bool(SUPABASE_DB_URL)


def backend_name() -> str:
    """Human-readable backend name, surfaced by the health endpoint."""
    return "Supabase (PostgreSQL)" if using_supabase() else "SQLite (local file)"


def _to_postgres(sql: str) -> str:
    """Translate "?" placeholders to the "%s" style psycopg expects.

    Question marks inside quoted literals would be damaged by a plain
    replace, so the string is walked and quoted regions are skipped.
    """
    out: list[str] = []
    in_single = in_double = False
    for char in sql:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        out.append("%s" if (char == "?" and not in_single and not in_double) else char)
    return "".join(out)


@contextmanager
def connect() -> Iterator[Any]:
    """Yield a connection, committing on success and rolling back on error."""
    if using_supabase():
        import psycopg
        from psycopg.rows import dict_row

        connection = psycopg.connect(SUPABASE_DB_URL, row_factory=dict_row)
    else:
        connection = sqlite3.connect(SQLITE_PATH)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def query(sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """Run a SELECT and return rows as dictionaries."""
    with connect() as connection:
        if using_supabase():
            with connection.cursor() as cursor:
                cursor.execute(_to_postgres(sql), tuple(params))
                return [dict(row) for row in cursor.fetchall()]
        return [dict(row) for row in connection.execute(sql, tuple(params)).fetchall()]


def query_one(sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    """Run a SELECT and return the first row, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    """Run a write and return the number of rows affected."""
    with connect() as connection:
        if using_supabase():
            with connection.cursor() as cursor:
                cursor.execute(_to_postgres(sql), tuple(params))
                return cursor.rowcount
        return connection.execute(sql, tuple(params)).rowcount


def execute_returning(sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    """Run a write with a RETURNING clause and give back the row.

    RETURNING is supported by PostgreSQL and by SQLite from 3.35, so one
    statement serves both backends.
    """
    with connect() as connection:
        if using_supabase():
            with connection.cursor() as cursor:
                cursor.execute(_to_postgres(sql), tuple(params))
                row = cursor.fetchone()
                return dict(row) if row else None
        row = connection.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None


def initialise() -> None:
    """Create tables if absent and ensure the default user exists.

    Idempotent: every statement is guarded with IF NOT EXISTS, and the
    user insert is guarded by its uniqueness constraint.
    """
    from datetime import datetime, timezone

    schema_path = SCHEMA_POSTGRES if using_supabase() else SCHEMA_SQLITE
    script = schema_path.read_text(encoding="utf-8")

    with connect() as connection:
        if using_supabase():
            with connection.cursor() as cursor:
                                cursor.execute(script)
        else:
            connection.executescript(script)

    execute(
        """
        INSERT INTO users (email, display_name, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT (email) DO NOTHING
        """,
        (
            DEFAULT_USER_EMAIL,
            DEFAULT_USER_NAME,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
    )
