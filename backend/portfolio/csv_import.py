"""Parse a holdings CSV exported from a broker (Groww / Zerodha / IndMoney / generic).

Tolerant of varied headers — matches common aliases for symbol / quantity /
average price. Returns a list of {symbol, quantity, avg_price} dicts.
"""

from __future__ import annotations

import csv
import io
from typing import List

_SYM = ["symbol", "tradingsymbol", "trading symbol", "stock", "scrip", "instrument",
        "ticker", "company", "stock name", "name"]
_QTY = ["quantity", "qty", "shares", "units", "holding qty", "holdings quantity", "net qty"]
_AVG = ["avg price", "average price", "avg cost", "avgprice", "buy average",
        "average_price", "avg_price", "avg. cost", "buy avg"]


def _find(headers: List[str], aliases: List[str]):
    low = {h.lower().strip(): h for h in headers}
    for a in aliases:
        if a in low:
            return low[a]
    for h in headers:                       # fuzzy contains
        hl = h.lower().strip()
        if any(a in hl for a in aliases):
            return h
    return None


def parse_csv(text: str) -> List[dict]:
    try:
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
    except Exception:  # noqa: BLE001
        return []
    sym_c = _find(headers, _SYM)
    if not sym_c:
        return []
    qty_c = _find(headers, _QTY)
    avg_c = _find(headers, _AVG)
    out: List[dict] = []
    for r in reader:
        sym = (r.get(sym_c) or "").strip()
        if not sym or sym.lower() in ("total", "grand total"):
            continue
        out.append({"symbol": sym,
                    "quantity": r.get(qty_c) if qty_c else None,
                    "avg_price": r.get(avg_c) if avg_c else None})
    return out
