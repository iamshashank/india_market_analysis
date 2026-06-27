"""Price history (OHLC) for charting — yfinance, cached.

Returns daily OHLC candles for a ticker over a selectable range, plus simple
moving averages, for the price/candlestick charts in the UI.
"""

from __future__ import annotations

import time
import warnings
from typing import Dict, List, Optional

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

# range key -> (yfinance period, interval)
_RANGES = {
    "1mo": ("1mo", "1d"),
    "3mo": ("3mo", "1d"),
    "6mo": ("6mo", "1d"),
    "1y": ("1y", "1d"),
    "2y": ("2y", "1wk"),
    "5y": ("5y", "1wk"),
    "max": ("max", "1mo"),
}

_CACHE: Dict[str, dict] = {}
_TTL = 600.0  # 10 min


def _sma(vals: List[Optional[float]], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    acc: List[float] = []
    for v in vals:
        if v is None:
            out.append(None)
            continue
        acc.append(v)
        if len(acc) > window:
            acc.pop(0)
        out.append(round(sum(acc) / len(acc), 2) if len(acc) == window else None)
    return out


def history(ticker: str, rng: str = "1y") -> dict:
    ticker = (ticker or "").strip()
    if not ticker:
        return {"available": False, "reason": "No ticker given"}
    if yf is None:
        return {"available": False, "reason": "yfinance not installed"}
    rng = rng if rng in _RANGES else "1y"
    key = f"{ticker}:{rng}"
    now = time.time()
    c = _CACHE.get(key)
    if c and now - c["ts"] < _TTL:
        return c["data"]

    period, interval = _RANGES[rng]
    try:
        h = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
        if h is None or h.empty:
            return {"available": False, "ticker": ticker, "reason": "No price history available."}
        candles = []
        closes = []
        for idx, row in h.iterrows():
            try:
                o, hi, lo, c2 = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
            except (TypeError, ValueError, KeyError):
                continue
            d = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            vol = None
            try:
                vol = int(row["Volume"])
            except (TypeError, ValueError, KeyError):
                pass
            candles.append({"date": d, "open": round(o, 2), "high": round(hi, 2),
                            "low": round(lo, 2), "close": round(c2, 2), "volume": vol})
            closes.append(c2)

        sma50 = _sma(closes, 50)
        sma200 = _sma(closes, 200)
        for i, cd in enumerate(candles):
            cd["sma50"] = sma50[i]
            cd["sma200"] = sma200[i]

        first, last = (closes[0], closes[-1]) if closes else (None, None)
        change_pct = round((last / first - 1) * 100, 2) if (first and last) else None
        data = {
            "available": True, "ticker": ticker, "range": rng, "interval": interval,
            "candles": candles,
            "last": round(last, 2) if last else None,
            "change_pct": change_pct,
            "high": round(max(closes), 2) if closes else None,
            "low": round(min(closes), 2) if closes else None,
        }
        _CACHE[key] = {"data": data, "ts": now}
        return data
    except Exception as e:  # noqa: BLE001
        return {"available": False, "ticker": ticker, "reason": str(e)}
