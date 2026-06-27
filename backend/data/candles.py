"""Candlestick pattern detection from OHLC — pure pandas/numpy, no TA-Lib.

Detects the classic single- and multi-candle patterns and returns the most
recent one for a ticker, with the date it occurred and a bullish/bearish/neutral
bias. Used to add a technical-timing overlay to the multibagger picks and (later)
a dedicated candles view.

Every pattern is defined by transparent geometric rules on body/shadow sizes and
short-term trend context, so the output is explainable.
"""

from __future__ import annotations

import warnings
from typing import List, Optional

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

import pandas as pd

# pattern name -> bias
BULLISH = {"Hammer", "Bullish Engulfing", "Morning Star", "Piercing Line",
           "Three White Soldiers", "Bullish Harami", "Bullish Marubozu",
           "Inverted Hammer"}
BEARISH = {"Hanging Man", "Bearish Engulfing", "Evening Star", "Dark Cloud Cover",
           "Three Black Crows", "Bearish Harami", "Bearish Marubozu",
           "Shooting Star"}


def _bias(name: str) -> str:
    if name in BULLISH:
        return "bullish"
    if name in BEARISH:
        return "bearish"
    return "neutral"


def _parts(o: float, h: float, l: float, c: float):
    rng = max(h - l, 1e-9)
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return rng, body, upper, lower


def _trend(closes: List[float]) -> str:
    """Crude short-term trend from the candles preceding the pattern."""
    if len(closes) < 3:
        return "flat"
    first, last = closes[0], closes[-1]
    if last > first * 1.01:
        return "up"
    if last < first * 0.99:
        return "down"
    return "flat"


def _detect_at(df: pd.DataFrame, i: int) -> Optional[str]:
    """Return a pattern name ending at row i, or None."""
    if i < 0 or i >= len(df):
        return None
    o, h, l, c = (float(df["Open"].iloc[i]), float(df["High"].iloc[i]),
                  float(df["Low"].iloc[i]), float(df["Close"].iloc[i]))
    rng, body, upper, lower = _parts(o, h, l, c)
    bull = c >= o
    pre = [float(df["Close"].iloc[j]) for j in range(max(0, i - 4), i)]
    trend = _trend(pre)

    # ---- three-candle patterns (strongest) ----
    if i >= 2:
        o1, c1 = float(df["Open"].iloc[i - 2]), float(df["Close"].iloc[i - 2])
        o2, c2 = float(df["Open"].iloc[i - 1]), float(df["Close"].iloc[i - 1])
        b1 = abs(c1 - o1); b2 = abs(c2 - o2)
        avg_body = (b1 + body) / 2 or 1e-9
        # Morning Star: down, small body, strong up closing into first body
        if c1 < o1 and b2 < 0.5 * b1 and bull and body > 0.6 * avg_body and c > (o1 + c1) / 2:
            return "Morning Star"
        # Evening Star
        if c1 > o1 and b2 < 0.5 * b1 and not bull and body > 0.6 * avg_body and c < (o1 + c1) / 2:
            return "Evening Star"
        # Three White Soldiers
        if (c > o and c2 > o2 and c1 > o1 and c > c2 > c1
                and b1 > 0.3 * rng and b2 > 0.3 * rng and body > 0.3 * rng):
            return "Three White Soldiers"
        # Three Black Crows
        if (c < o and c2 < o2 and c1 < o1 and c < c2 < c1
                and b1 > 0.3 * rng and b2 > 0.3 * rng and body > 0.3 * rng):
            return "Three Black Crows"

    # ---- two-candle patterns ----
    if i >= 1:
        po, ph, pl, pc = (float(df["Open"].iloc[i - 1]), float(df["High"].iloc[i - 1]),
                          float(df["Low"].iloc[i - 1]), float(df["Close"].iloc[i - 1]))
        pbody = abs(pc - po)
        # Engulfing
        if bull and pc < po and c >= po and o <= pc and body > pbody:
            return "Bullish Engulfing"
        if (not bull) and pc > po and o >= pc and c <= po and body > pbody:
            return "Bearish Engulfing"
        # Harami (small body inside previous large body)
        if pbody > 0 and body < 0.6 * pbody and max(o, c) <= max(po, pc) and min(o, c) >= min(po, pc):
            if pc < po and bull:
                return "Bullish Harami"
            if pc > po and not bull:
                return "Bearish Harami"
        # Piercing / Dark Cloud
        mid_prev = (po + pc) / 2
        if bull and pc < po and o < pl and c > mid_prev and c < po:
            return "Piercing Line"
        if (not bull) and pc > po and o > ph and c < mid_prev and c > po:
            return "Dark Cloud Cover"

    # ---- single-candle patterns ----
    if body < 0.1 * rng:
        return "Doji"
    if body > 0.9 * rng:
        return "Bullish Marubozu" if bull else "Bearish Marubozu"
    # Hammer family: long lower shadow, small body near top
    if lower >= 2 * body and upper <= 0.3 * rng and body > 0:
        return "Hammer" if trend == "down" else "Hanging Man"
    # Shooting star / inverted hammer: long upper shadow, small body near bottom
    if upper >= 2 * body and lower <= 0.3 * rng and body > 0:
        return "Shooting Star" if trend == "up" else "Inverted Hammer"
    return None


def detect_series(df: pd.DataFrame, lookback: int = 6) -> Optional[dict]:
    """Scan the last ``lookback`` bars and return the most recent pattern."""
    if df is None or df.empty or not {"Open", "High", "Low", "Close"}.issubset(df.columns):
        return None
    n = len(df)
    for i in range(n - 1, max(-1, n - 1 - lookback), -1):
        name = _detect_at(df, i)
        if name:
            ts = df.index[i]
            date = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
            return {"pattern": name, "bias": _bias(name), "date": date,
                    "bars_ago": (n - 1 - i)}
    return None


def detect_for_ticker(ticker: str, period: str = "3mo") -> Optional[dict]:
    """Fetch recent daily bars and return the latest candlestick pattern."""
    if yf is None:
        return None
    try:
        h = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        return detect_series(h)
    except Exception:  # noqa: BLE001
        return None


def detect_many(tickers: List[str]) -> dict:
    out = {}
    for tk in tickers:
        try:
            out[tk] = detect_for_ticker(tk)
        except Exception:  # noqa: BLE001
            out[tk] = None
    return out
