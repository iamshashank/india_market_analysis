"""MySQL-backed JSON persistence (SQLAlchemy + PyMySQL).

A single key/value table (``app_store``) holds JSON payloads — the latest
screen, the next-day prediction, settings, etc. — each under its own key.

Connection comes from ``MYSQL_URL`` (SQLAlchemy URL), e.g.
    mysql+pymysql://root@127.0.0.1:3306/market_intelligence

Everything degrades gracefully: if MySQL is unreachable, the app keeps working
from a local JSON file (``cache/store.json``), so local dev / demos need no DB.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Optional

from core.config import CACHE_DIR

MYSQL_URL = os.environ.get(
    "MYSQL_URL", "mysql+pymysql://root@127.0.0.1:3306/market_intelligence"
).strip()
TABLE = os.environ.get("STORE_TABLE", "app_store")

_engine = None
_engine_ready = False
_lock = threading.Lock()
_local_file = os.path.join(CACHE_DIR, "store.json")


def _get_engine():
    """Lazily build (and verify) the SQLAlchemy engine. Returns None on failure."""
    global _engine, _engine_ready
    if _engine_ready:
        return _engine
    with _lock:
        if _engine_ready:
            return _engine
        _engine_ready = True
        if not MYSQL_URL:
            return None
        try:
            from sqlalchemy import create_engine, text

            eng = create_engine(MYSQL_URL, pool_pre_ping=True, pool_recycle=1800)
            with eng.begin() as conn:
                conn.execute(text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {TABLE} (
                        `key`       VARCHAR(191) PRIMARY KEY,
                        `data`      JSON NOT NULL,
                        `updated_at` TIMESTAMP NOT NULL
                            DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                ))
            _engine = eng
            return _engine
        except Exception as e:  # noqa: BLE001
            print(f"[store] MySQL unavailable, using local JSON fallback: {e}")
            _engine = None
            return None


def is_enabled() -> bool:
    return _get_engine() is not None


def get_engine():
    """Public accessor for the shared SQLAlchemy engine (or None). Lets sibling
    modules (e.g. score-history) reuse the same MySQL connection + fallback."""
    return _get_engine()


# ---- local JSON fallback --------------------------------------------------

def _load_local() -> dict:
    try:
        with open(_local_file, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return {}


def _save_local(blob: dict) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_local_file, "w", encoding="utf-8") as fh:
        json.dump(blob, fh, default=str)


# ---- public API -----------------------------------------------------------

def save(data: Any, key: str) -> bool:
    """Upsert a JSON payload under ``key``."""
    eng = _get_engine()
    if eng is not None:
        try:
            from sqlalchemy import text

            with eng.begin() as conn:
                conn.execute(
                    text(
                        f"""
                        INSERT INTO {TABLE} (`key`, `data`) VALUES (:k, :d)
                        ON DUPLICATE KEY UPDATE `data` = VALUES(`data`)
                        """
                    ),
                    {"k": key, "d": json.dumps(data, default=str)},
                )
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[store] save failed ({key}): {e}")
            # fall through to local
    with _lock:
        blob = _load_local()
        blob[key] = data
        _save_local(blob)
    return True


def load(key: str) -> Optional[Any]:
    """Return the JSON payload under ``key`` (or None)."""
    eng = _get_engine()
    if eng is not None:
        try:
            from sqlalchemy import text

            with eng.connect() as conn:
                row = conn.execute(
                    text(f"SELECT `data` FROM {TABLE} WHERE `key` = :k"), {"k": key}
                ).fetchone()
            if not row:
                return None
            data = row[0]
            return json.loads(data) if isinstance(data, (str, bytes, bytearray)) else data
        except Exception as e:  # noqa: BLE001
            print(f"[store] load failed ({key}): {e}")
            # fall through to local
    return _load_local().get(key)
