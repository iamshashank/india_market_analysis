"""Persistence for paper-trading settings and trade logs.

Uses Postgres when ``MASTER_DB`` is set (dedicated ``paper_trades`` table plus
settings in ``app_store``). Falls back to ``cache/paper_store.json`` locally.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    from psycopg2.extras import Json, RealDictCursor
except ImportError:  # pragma: no cover
    psycopg2 = None
    Json = None
    RealDictCursor = None

MASTER_DB = os.environ.get("MASTER_DB", "").strip()
TABLE = os.environ.get("MASTER_DB_TABLE", "app_store")
SETTINGS_KEY = "paper_settings"
CACHE_DIR = os.environ.get("CACHE_DIR", "cache")
LOCAL_FILE = os.path.join(CACHE_DIR, "paper_store.json")

_lock = threading.Lock()
_local_cache: Optional[dict] = None
_paper_initialized = False
_next_id = 1


def is_pg_enabled() -> bool:
    return bool(MASTER_DB) and psycopg2 is not None


def _connect():
    return psycopg2.connect(MASTER_DB)


def _ensure_local_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _load_local() -> dict:
    global _local_cache
    if _local_cache is not None:
        return _local_cache
    _ensure_local_dir()
    if os.path.isfile(LOCAL_FILE):
        try:
            with open(LOCAL_FILE, encoding="utf-8") as f:
                _local_cache = json.load(f)
                return _local_cache
        except Exception:  # noqa: BLE001
            pass
    _local_cache = {"settings": {}, "trades": [], "skips": []}
    return _local_cache


def _save_local(data: dict) -> None:
    global _local_cache
    _local_cache = data
    _ensure_local_dir()
    with open(LOCAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def init_paper_db() -> bool:
    global _paper_initialized
    if _paper_initialized:
        return True
    if is_pg_enabled():
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
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS paper_trades (
                        id SERIAL PRIMARY KEY,
                        trade_date DATE NOT NULL,
                        ticker TEXT NOT NULL,
                        name TEXT,
                        confidence TEXT,
                        stock_score NUMERIC,
                        market_bias_score NUMERIC,
                        qty INT NOT NULL DEFAULT 0,
                        signal_entry_price NUMERIC,
                        stop_pct NUMERIC,
                        target_pct NUMERIC,
                        stop_price NUMERIC,
                        target_price NUMERIC,
                        budget_allocated NUMERIC,
                        actual_open NUMERIC,
                        actual_high NUMERIC,
                        actual_low NUMERIC,
                        actual_close NUMERIC,
                        entry_price NUMERIC,
                        exit_price NUMERIC,
                        exit_reason TEXT,
                        pnl_inr NUMERIC,
                        pnl_pct NUMERIC,
                        charges_inr NUMERIC,
                        status TEXT NOT NULL DEFAULT 'pending',
                        settings_snapshot JSONB,
                        signal_snapshot JSONB,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        settled_at TIMESTAMPTZ,
                        UNIQUE (trade_date, ticker)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS paper_skips (
                        id SERIAL PRIMARY KEY,
                        trade_date DATE NOT NULL UNIQUE,
                        reason TEXT NOT NULL,
                        market_bias_score NUMERIC,
                        settings_snapshot JSONB,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            conn.commit()
            _paper_initialized = True
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[paper_db] init failed: {e}")
            return False
        finally:
            if conn is not None:
                conn.close()
    _paper_initialized = True
    _load_local()
    return True


def load_settings() -> Optional[dict]:
    init_paper_db()
    if is_pg_enabled():
        conn = None
        try:
            conn = _connect()
            with conn.cursor() as cur:
                cur.execute(f"SELECT data FROM {TABLE} WHERE key = %s", (SETTINGS_KEY,))
                row = cur.fetchone()
            if not row:
                return None
            data = row[0]
            return json.loads(data) if isinstance(data, str) else data
        except Exception as e:  # noqa: BLE001
            print(f"[paper_db] load_settings failed: {e}")
            return None
        finally:
            if conn is not None:
                conn.close()
    return _load_local().get("settings") or None


def save_settings(settings: dict) -> bool:
    init_paper_db()
    if is_pg_enabled():
        conn = None
        try:
            conn = _connect()
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {TABLE} (key, data, updated_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, updated_at = now()
                    """,
                    (SETTINGS_KEY, Json(settings)),
                )
            conn.commit()
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[paper_db] save_settings failed: {e}")
            return False
        finally:
            if conn is not None:
                conn.close()
    with _lock:
        data = _load_local()
        data["settings"] = settings
        _save_local(data)
    return True


def has_session(trade_date: str) -> bool:
    init_paper_db()
    if is_pg_enabled():
        conn = None
        try:
            conn = _connect()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM paper_trades WHERE trade_date = %s LIMIT 1",
                    (trade_date,),
                )
                if cur.fetchone():
                    return True
                cur.execute(
                    "SELECT 1 FROM paper_skips WHERE trade_date = %s LIMIT 1",
                    (trade_date,),
                )
                return cur.fetchone() is not None
        except Exception:  # noqa: BLE001
            return False
        finally:
            if conn is not None:
                conn.close()
    data = _load_local()
    td = trade_date[:10]
    for t in data.get("trades", []):
        if str(t.get("trade_date", ""))[:10] == td:
            return True
    for s in data.get("skips", []):
        if str(s.get("trade_date", ""))[:10] == td:
            return True
    return False


def log_skip(trade_date: str, reason: str, market_bias: Optional[float], settings: dict) -> None:
    init_paper_db()
    row = {
        "trade_date": trade_date,
        "reason": reason,
        "market_bias_score": market_bias,
        "settings_snapshot": settings,
        "status": "skipped",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if is_pg_enabled():
        conn = None
        try:
            conn = _connect()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO paper_skips (trade_date, reason, market_bias_score, settings_snapshot)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (trade_date) DO UPDATE SET
                        reason = EXCLUDED.reason,
                        market_bias_score = EXCLUDED.market_bias_score,
                        settings_snapshot = EXCLUDED.settings_snapshot
                    """,
                    (trade_date, reason, market_bias, Json(settings)),
                )
            conn.commit()
        except Exception as e:  # noqa: BLE001
            print(f"[paper_db] log_skip failed: {e}")
        finally:
            if conn is not None:
                conn.close()
        return
    with _lock:
        data = _load_local()
        skips = [s for s in data.get("skips", []) if str(s.get("trade_date", ""))[:10] != trade_date[:10]]
        skips.append(row)
        data["skips"] = skips
        _save_local(data)


def insert_trades(rows: List[dict]) -> List[dict]:
    init_paper_db()
    inserted: List[dict] = []
    if is_pg_enabled():
        conn = None
        try:
            conn = _connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO paper_trades (
                            trade_date, ticker, name, confidence, stock_score, market_bias_score,
                            qty, signal_entry_price, stop_pct, target_pct, stop_price, target_price,
                            budget_allocated, status, settings_snapshot, signal_snapshot
                        ) VALUES (
                            %(trade_date)s, %(ticker)s, %(name)s, %(confidence)s, %(stock_score)s,
                            %(market_bias_score)s, %(qty)s, %(signal_entry_price)s, %(stop_pct)s,
                            %(target_pct)s, %(stop_price)s, %(target_price)s, %(budget_allocated)s,
                            %(status)s, %(settings_snapshot)s, %(signal_snapshot)s
                        )
                        RETURNING *
                        """,
                        {
                            **row,
                            "settings_snapshot": Json(row.get("settings_snapshot") or {}),
                            "signal_snapshot": Json(row.get("signal_snapshot") or {}),
                        },
                    )
                    inserted.append(dict(cur.fetchone()))
            conn.commit()
            return [_serialize_trade(t) for t in inserted]
        except Exception as e:  # noqa: BLE001
            print(f"[paper_db] insert_trades failed: {e}")
            return []
        finally:
            if conn is not None:
                conn.close()

    global _next_id
    with _lock:
        data = _load_local()
        existing = data.get("trades", [])
        if existing:
            _next_id = max(int(t.get("id", 0)) for t in existing) + 1
        for row in rows:
            tid = _next_id
            _next_id += 1
            full = {**row, "id": tid, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            data.setdefault("trades", []).append(full)
            inserted.append(full)
        _save_local(data)
    return inserted


def delete_session(trade_date: str) -> None:
    init_paper_db()
    td = trade_date[:10]
    if is_pg_enabled():
        conn = None
        try:
            conn = _connect()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM paper_trades WHERE trade_date = %s", (td,))
                cur.execute("DELETE FROM paper_skips WHERE trade_date = %s", (td,))
            conn.commit()
        except Exception as e:  # noqa: BLE001
            print(f"[paper_db] delete_session failed: {e}")
        finally:
            if conn is not None:
                conn.close()
        return
    with _lock:
        data = _load_local()
        data["trades"] = [t for t in data.get("trades", []) if str(t.get("trade_date", ""))[:10] != td]
        data["skips"] = [s for s in data.get("skips", []) if str(s.get("trade_date", ""))[:10] != td]
        _save_local(data)


def list_trades(
    status: Optional[str] = None,
    limit: int = 200,
) -> List[dict]:
    init_paper_db()
    if is_pg_enabled():
        conn = None
        try:
            conn = _connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if status:
                    cur.execute(
                        """
                        SELECT * FROM paper_trades
                        WHERE status = %s
                        ORDER BY trade_date DESC, id DESC
                        LIMIT %s
                        """,
                        (status, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT * FROM paper_trades
                        ORDER BY trade_date DESC, id DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                rows = [dict(r) for r in cur.fetchall()]
            return [_serialize_trade(r) for r in rows]
        except Exception as e:  # noqa: BLE001
            print(f"[paper_db] list_trades failed: {e}")
            return []
        finally:
            if conn is not None:
                conn.close()

    data = _load_local()
    trades = list(data.get("trades", []))
    if status:
        trades = [t for t in trades if t.get("status") == status]
    trades.sort(key=lambda x: (x.get("trade_date", ""), x.get("id", 0)), reverse=True)
    return [_serialize_trade(t) for t in trades[:limit]]


def list_skips(limit: int = 60) -> List[dict]:
    init_paper_db()
    if is_pg_enabled():
        conn = None
        try:
            conn = _connect()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM paper_skips ORDER BY trade_date DESC LIMIT %s",
                    (limit,),
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception:  # noqa: BLE001
            return []
        finally:
            if conn is not None:
                conn.close()
    data = _load_local()
    skips = sorted(data.get("skips", []), key=lambda x: x.get("trade_date", ""), reverse=True)
    return skips[:limit]


def update_trade(trade_id: int, fields: dict) -> bool:
    init_paper_db()
    if is_pg_enabled():
        conn = None
        try:
            sets = ", ".join(f"{k} = %s" for k in fields)
            vals = list(fields.values()) + [trade_id]
            conn = _connect()
            with conn.cursor() as cur:
                cur.execute(f"UPDATE paper_trades SET {sets} WHERE id = %s", vals)
            conn.commit()
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[paper_db] update_trade failed: {e}")
            return False
        finally:
            if conn is not None:
                conn.close()
    with _lock:
        data = _load_local()
        for t in data.get("trades", []):
            if t.get("id") == trade_id:
                t.update(fields)
                break
        _save_local(data)
    return True


def _serialize_trade(row: dict) -> dict:
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()[:10] if k == "trade_date" else v.isoformat()
        elif isinstance(v, dict):
            out[k] = v
        elif isinstance(v, (int, float, str, bool)) or v is None:
            out[k] = v
        else:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                out[k] = str(v)
    if "trade_date" in out and isinstance(out["trade_date"], str) and "T" in out["trade_date"]:
        out["trade_date"] = out["trade_date"][:10]
    return out
