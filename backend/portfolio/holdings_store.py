"""Persisted user-entered holdings (manual + CSV) — JSON via core.store."""

from __future__ import annotations

import time
import uuid
from typing import List, Optional

from core import store

KEY = "portfolio_holdings"


def norm_ticker(symbol: str, market: str) -> str:
    """Normalise a raw symbol to a yfinance ticker (.NS for India, plain for US)."""
    s = (symbol or "").strip().upper()
    if not s:
        return s
    if s.endswith(".NS") or s.endswith(".BO"):
        return s
    if market in ("IN", "BSE"):
        return s + (".BO" if market == "BSE" else ".NS")
    return s


def list_holdings() -> List[dict]:
    return store.load(KEY) or []


def save_all(rows: List[dict]) -> None:
    store.save(rows, KEY)


def add(broker: str, symbol: str, market: str,
        quantity: Optional[float] = None, avg_price: Optional[float] = None) -> dict:
    rows = list_holdings()
    h = {
        "id": uuid.uuid4().hex[:12],
        "broker": (broker or "Manual").strip() or "Manual",
        "symbol": (symbol or "").strip().upper(),
        "market": market if market in ("IN", "BSE", "US") else "IN",
        "ticker": norm_ticker(symbol, market),
        "quantity": _num(quantity),
        "avg_price": _num(avg_price),
        "added": time.strftime("%Y-%m-%d"),
    }
    rows.append(h)
    save_all(rows)
    return h


def add_many(items: List[dict]) -> int:
    rows = list_holdings()
    n = 0
    for it in items:
        sym = (it.get("symbol") or "").strip().upper()
        if not sym:
            continue
        mkt = it.get("market") if it.get("market") in ("IN", "BSE", "US") else "IN"
        rows.append({
            "id": uuid.uuid4().hex[:12],
            "broker": (it.get("broker") or "CSV").strip() or "CSV",
            "symbol": sym, "market": mkt, "ticker": norm_ticker(sym, mkt),
            "quantity": _num(it.get("quantity")), "avg_price": _num(it.get("avg_price")),
            "added": time.strftime("%Y-%m-%d"),
        })
        n += 1
    save_all(rows)
    return n


def remove(hid: str) -> None:
    save_all([r for r in list_holdings() if r.get("id") != hid])


def clear() -> None:
    save_all([])


def _num(v):
    try:
        return float(str(v).replace(",", "").strip()) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
