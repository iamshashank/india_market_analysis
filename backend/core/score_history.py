"""Score-history persistence + forward-return backtest store.

Every screen build snapshots each scored stock (composite + pillars + price +
cap tier) into ``score_history``. Over time this accumulates a real time series
so we can:

  * show how a stock's composite score has evolved (sparkline), and
  * run a genuine FORWARD-return backtest: did stocks that scored high on date D
    actually outperform over the following N days? (We re-price the snapshot's
    ticker as-of later dates and bucket returns by the original score.)

Uses the shared MySQL engine from ``core.store``; degrades to a local JSON file
so dev/demo works without a database.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

from core.config import CACHE_DIR
from core import store

_LOCAL = os.path.join(CACHE_DIR, "score_history.json")
_initialized = False


def _init() -> bool:
    global _initialized
    if _initialized:
        return store.get_engine() is not None
    eng = store.get_engine()
    if eng is None:
        _initialized = True
        return False
    try:
        from sqlalchemy import text
        with eng.begin() as conn:
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS score_history (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    snapshot_date DATE NOT NULL,
                    ticker VARCHAR(32) NOT NULL,
                    market VARCHAR(8),
                    cap_tier VARCHAR(16),
                    sector VARCHAR(64),
                    score DECIMAL(6,2),
                    price DECIMAL(18,4),
                    pillars JSON,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_snap (snapshot_date, ticker),
                    KEY idx_ticker (ticker),
                    KEY idx_date (snapshot_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            ))
        _initialized = True
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[score_history] init failed: {e}")
        _initialized = True
        return False


# ---- local fallback -------------------------------------------------------

def _load_local() -> List[dict]:
    try:
        with open(_LOCAL, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return []


def _save_local(rows: List[dict]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_LOCAL, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, default=str)


# ---- snapshot writer ------------------------------------------------------

def snapshot(scored: List[dict], snapshot_date: Optional[str] = None) -> int:
    """Persist today's scores. One row per (date, ticker); re-running a day
    upserts. Returns the number of rows written."""
    snapshot_date = snapshot_date or time.strftime("%Y-%m-%d")
    rows = [{
        "snapshot_date": snapshot_date,
        "ticker": s.get("ticker"),
        "market": s.get("market"),
        "cap_tier": s.get("cap_tier"),
        "sector": s.get("sector"),
        "score": s.get("score"),
        "price": (s.get("metrics") or {}).get("price") or s.get("price"),
        "pillars": s.get("pillars") or {},
    } for s in scored if s.get("ticker")]
    if not rows:
        return 0

    if _init():
        try:
            from sqlalchemy import text
            eng = store.get_engine()
            with eng.begin() as conn:
                for r in rows:
                    conn.execute(text(
                        """
                        INSERT INTO score_history
                          (snapshot_date, ticker, market, cap_tier, sector, score, price, pillars)
                        VALUES (:snapshot_date,:ticker,:market,:cap_tier,:sector,:score,:price,:pillars)
                        ON DUPLICATE KEY UPDATE score=VALUES(score), price=VALUES(price),
                          pillars=VALUES(pillars), cap_tier=VALUES(cap_tier), sector=VALUES(sector)
                        """
                    ), {**r, "pillars": json.dumps(r["pillars"])})
            return len(rows)
        except Exception as e:  # noqa: BLE001
            print(f"[score_history] snapshot failed: {e}")

    # local fallback: keep last ~400 days of rows
    data = _load_local()
    existing = {(d["snapshot_date"], d["ticker"]) for d in data}
    for r in rows:
        if (r["snapshot_date"], r["ticker"]) not in existing:
            data.append(r)
    _save_local(data[-200000:])
    return len(rows)


# ---- queries --------------------------------------------------------------

def history_for(ticker: str, limit: int = 180) -> List[dict]:
    """Score time series for one ticker (oldest→newest)."""
    if _init():
        try:
            from sqlalchemy import text
            eng = store.get_engine()
            with eng.connect() as conn:
                res = conn.execute(text(
                    """
                    SELECT snapshot_date, score, price FROM score_history
                    WHERE ticker = :t ORDER BY snapshot_date DESC LIMIT :n
                    """
                ), {"t": ticker, "n": limit}).fetchall()
            rows = [{"date": str(r[0])[:10], "score": float(r[1]) if r[1] is not None else None,
                     "price": float(r[2]) if r[2] is not None else None} for r in res]
            return list(reversed(rows))
        except Exception as e:  # noqa: BLE001
            print(f"[score_history] history_for failed: {e}")
    rows = [d for d in _load_local() if d.get("ticker") == ticker]
    rows.sort(key=lambda d: d.get("snapshot_date", ""))
    return [{"date": d["snapshot_date"], "score": d.get("score"), "price": d.get("price")} for d in rows][-limit:]


def all_snapshots() -> List[dict]:
    """Every snapshot row (for the backtest join). Heavy — use server-side."""
    if _init():
        try:
            from sqlalchemy import text
            eng = store.get_engine()
            with eng.connect() as conn:
                res = conn.execute(text(
                    "SELECT snapshot_date, ticker, score, price FROM score_history"
                )).fetchall()
            return [{"snapshot_date": str(r[0])[:10], "ticker": r[1],
                     "score": float(r[2]) if r[2] is not None else None,
                     "price": float(r[3]) if r[3] is not None else None} for r in res]
        except Exception as e:  # noqa: BLE001
            print(f"[score_history] all_snapshots failed: {e}")
    return _load_local()


def distinct_dates() -> List[str]:
    rows = all_snapshots()
    return sorted({r["snapshot_date"] for r in rows if r.get("snapshot_date")})
