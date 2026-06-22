"""Postgres persistence for the predictor.

Connection string comes from the ``MASTER_DB`` environment variable. All app
data is stored as JSON in a single key/value table (``app_store``), so the
whole prediction payload lives under one key for easy access:

    SELECT data FROM app_store WHERE key = 'premarket_latest';

Everything degrades gracefully: if ``MASTER_DB`` is unset or the database is
unreachable, the app keeps working from its in-memory cache and these helpers
become no-ops (so local dev needs no database).
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

try:
    import psycopg2
    from psycopg2.extras import Json
except ImportError:  # pragma: no cover
    psycopg2 = None
    Json = None

MASTER_DB = os.environ.get("MASTER_DB", "").strip()
TABLE = os.environ.get("MASTER_DB_TABLE", "app_store")
DEFAULT_KEY = "premarket_latest"

_initialized = False


def is_enabled() -> bool:
    return bool(MASTER_DB) and psycopg2 is not None


def _connect():
    """Open a short-lived connection. Caller is responsible for closing."""
    return psycopg2.connect(MASTER_DB)


def init_db() -> bool:
    """Create the single-key JSON store table if needed. Safe to call often."""
    global _initialized
    if not is_enabled():
        return False
    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    key        TEXT PRIMARY KEY,
                    data       JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        conn.commit()
        _initialized = True
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[db] init failed: {e}")
        return False
    finally:
        if conn is not None:
            conn.close()


def save(data: Any, key: str = DEFAULT_KEY) -> bool:
    """Upsert the entire payload as JSON under a single key."""
    if not is_enabled():
        return False
    if not _initialized and not init_db():
        return False
    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {TABLE} (key, data, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (key)
                DO UPDATE SET data = EXCLUDED.data, updated_at = now()
                """,
                (key, Json(data)),
            )
        conn.commit()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[db] save failed: {e}")
        return False
    finally:
        if conn is not None:
            conn.close()


def load(key: str = DEFAULT_KEY) -> Optional[Any]:
    """Return the JSON payload stored under ``key`` (or None)."""
    if not is_enabled():
        return None
    if not _initialized and not init_db():
        return None
    conn = None
    try:
        conn = _connect()
        with conn.cursor() as cur:
            cur.execute(f"SELECT data FROM {TABLE} WHERE key = %s", (key,))
            row = cur.fetchone()
        if not row:
            return None
        data = row[0]
        # psycopg2 returns JSONB as a dict already; tolerate str too.
        return json.loads(data) if isinstance(data, str) else data
    except Exception as e:  # noqa: BLE001
        print(f"[db] load failed: {e}")
        return None
    finally:
        if conn is not None:
            conn.close()
