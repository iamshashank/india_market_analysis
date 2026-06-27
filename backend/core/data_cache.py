"""Point-in-time fundamentals cache — the longitudinal data moat.

Every screen build snapshots the fundamentals we fetched (one row per
date+ticker) into ``fundamentals_snapshots``. Over time this becomes a
proprietary panel dataset: what each stock's fundamentals looked like on each
date — the raw material for true forward backtests and the discovery-inflection
signal. Complements ``core.score_history`` (which stores the derived scores).

Uses the shared MySQL engine from ``core.store``; degrades to a local JSON file
so dev/demo works without a database.
"""

from __future__ import annotations

import json
import os
import time
from typing import List, Optional

from core.config import CACHE_DIR
from core import store

_LOCAL = os.path.join(CACHE_DIR, "fundamentals_snapshots.json")
_initialized = False
_SNAPSHOT_ON = os.environ.get("SNAPSHOT_FUNDAMENTALS", "1") not in ("0", "false", "False")

# keep the per-row JSON lean — the fields worth preserving point-in-time
_KEEP = (
    "ticker", "name", "market", "currency", "sector", "industry", "price",
    "market_cap_usd", "trailing_pe", "forward_pe", "peg", "price_to_book",
    "roe", "gross_margin", "profit_margin", "debt_to_equity", "fcf_margin",
    "revenue_growth", "earnings_growth", "num_analysts", "inst_hold_pct",
    "adv_value_usd", "ret_6m", "ret_1y", "quarterly_ni", "quarterly_rev", "_source",
)


def is_enabled() -> bool:
    return store.get_engine() is not None


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
                CREATE TABLE IF NOT EXISTS fundamentals_snapshots (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    snapshot_date DATE NOT NULL,
                    ticker VARCHAR(32) NOT NULL,
                    source VARCHAR(24),
                    market VARCHAR(8),
                    price DECIMAL(18,4),
                    market_cap_usd DECIMAL(20,2),
                    data JSON,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_fsnap (snapshot_date, ticker),
                    KEY idx_fticker (ticker),
                    KEY idx_fdate (snapshot_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            ))
        _initialized = True
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[data_cache] init failed: {e}")
        _initialized = True
        return False


def _slim(row: dict) -> dict:
    return {k: row.get(k) for k in _KEEP if k in row}


def snapshot(rows: List[dict], snapshot_date: Optional[str] = None) -> int:
    """Persist today's fundamentals rows (priced, non-error). Idempotent per
    (date, ticker). Returns rows written. Controlled by SNAPSHOT_FUNDAMENTALS."""
    if not _SNAPSHOT_ON:
        return 0
    snapshot_date = snapshot_date or time.strftime("%Y-%m-%d")
    clean = [r for r in rows if r.get("ticker") and r.get("price") and not r.get("error")]
    if not clean:
        return 0

    if _init():
        try:
            from sqlalchemy import text
            eng = store.get_engine()
            with eng.begin() as conn:
                for r in clean:
                    conn.execute(text(
                        """
                        INSERT INTO fundamentals_snapshots
                          (snapshot_date, ticker, source, market, price, market_cap_usd, data)
                        VALUES (:d,:t,:s,:m,:p,:c,:j)
                        ON DUPLICATE KEY UPDATE source=VALUES(source), price=VALUES(price),
                          market_cap_usd=VALUES(market_cap_usd), data=VALUES(data)
                        """
                    ), {"d": snapshot_date, "t": r["ticker"], "s": r.get("_source"),
                        "m": r.get("market"), "p": r.get("price"),
                        "c": r.get("market_cap_usd"), "j": json.dumps(_slim(r), default=str)})
            return len(clean)
        except Exception as e:  # noqa: BLE001
            print(f"[data_cache] snapshot failed: {e}")

    # local fallback (keyed date|ticker)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        blob = {}
        if os.path.exists(_LOCAL):
            with open(_LOCAL, encoding="utf-8") as fh:
                blob = json.load(fh)
        for r in clean:
            blob[f"{snapshot_date}|{r['ticker']}"] = _slim(r)
        with open(_LOCAL, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, default=str)
        return len(clean)
    except Exception:  # noqa: BLE001
        return 0
