"""Honest, out-of-sample validation of the core signal.

The model's central claim: a positive OVERNIGHT global lead (US session) makes
the Indian market more likely to OPEN HIGHER the next day — and the question
every trader asks: does that opening gap HOLD through the first hour, or fade?

This module tests exactly that, using only data we can actually get:

  * Signal  = sign of the S&P 500's prior-session return (the overnight lead,
              the same input the live model leans on most).
  * Gap     = Nifty 50 next-day Open ÷ prior Close − 1   (daily, ~1 year).
  * 1st hr  = Nifty 50 first 60-min bar Close ÷ Open − 1 (intraday, ~60 days).

It reports hit-rates, average moves, and a simple calibration table. It is a
MARKET-LEVEL test (Nifty), not a per-stock guarantee — but it tells you whether
the overnight-lead idea has held up recently, which is the honest thing to know.
"""

from __future__ import annotations

import time
import warnings
from typing import Optional

warnings.filterwarnings("ignore")

import pandas as pd

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

_CACHE: dict = {}
_TTL = float(__import__("os").environ.get("BACKTEST_TTL_HOURS", 12)) * 3600


def _daily(symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    if yf is None:
        return None
    try:
        h = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
        if h is None or h.empty:
            return None
        h.index = pd.to_datetime(h.index).tz_localize(None)
        return h
    except Exception:  # noqa: BLE001
        return None


def _rate(mask_cond: pd.Series, mask_outcome: pd.Series) -> Optional[dict]:
    sub = mask_outcome[mask_cond]
    n = int(sub.notna().sum())
    if n == 0:
        return None
    up = int((sub > 0).sum())
    return {"n": n, "hit_rate": round(up / n * 100, 1)}


def _gap_test() -> dict:
    nifty = _daily("^NSEI", "1y", "1d")
    spx = _daily("^GSPC", "1y", "1d")
    if nifty is None or spx is None:
        return {}

    nf = pd.DataFrame({"date": nifty.index.normalize()})
    nf["open"] = nifty["Open"].values
    nf["close"] = nifty["Close"].values
    nf["prev_close"] = nf["close"].shift(1)
    nf["gap"] = nf["open"] / nf["prev_close"] - 1.0
    nf["intraday"] = nf["close"] / nf["open"] - 1.0

    sp = pd.DataFrame({"date": spx.index.normalize()})
    sp["spx_ret"] = spx["Close"].pct_change().values

    merged = pd.merge_asof(
        nf.sort_values("date"),
        sp[["date", "spx_ret"]].sort_values("date"),
        on="date", direction="backward", allow_exact_matches=False,
    ).dropna(subset=["gap", "spx_ret"])

    sig_up = merged["spx_ret"] > 0
    gap = merged["gap"]

    overall_gap_up = round((gap > 0).mean() * 100, 1)
    when_up = _rate(sig_up, gap)
    when_down = _rate(~sig_up, gap)

    # Calibration: stronger overnight lead → higher gap-up rate?
    buckets = []
    for label, lo, hi in [
        ("Strong up (>+0.75%)", 0.0075, 9), ("Mild up (0 to +0.75%)", 0.0, 0.0075),
        ("Mild down (−0.75 to 0%)", -0.0075, 0.0), ("Strong down (<−0.75%)", -9, -0.0075),
    ]:
        m = (merged["spx_ret"] > lo) & (merged["spx_ret"] <= hi) if lo < hi else None
        if m is None:
            continue
        r = _rate(m, gap)
        if r:
            buckets.append({"bucket": label, **r,
                            "avg_gap_pct": round(float(gap[m].mean()) * 100, 2)})

    return {
        "sample_days": int(len(merged)),
        "overall_gap_up_pct": overall_gap_up,
        "gap_up_when_overnight_up": when_up,
        "gap_up_when_overnight_down": when_down,
        "calibration": buckets,
    }


def _first_hour_test() -> dict:
    """Does the open gap hold the first hour? (intraday, ~60 days)"""
    bars = _daily("^NSEI", "60d", "60m")
    spx = _daily("^GSPC", "120d", "1d")
    if bars is None or spx is None:
        return {}

    bars = bars.copy()
    bars["day"] = bars.index.normalize()
    first = bars.groupby("day").first()
    first_hr = (first["Close"] / first["Open"] - 1.0).rename("first_hr")

    daily = _daily("^NSEI", "120d", "1d")
    if daily is None:
        return {}
    dd = pd.DataFrame({"date": daily.index.normalize()})
    dd["open"] = daily["Open"].values
    dd["prev_close"] = pd.Series(daily["Close"].values).shift(1).values
    dd["gap"] = dd["open"] / dd["prev_close"] - 1.0

    fh = pd.DataFrame({"date": first_hr.index, "first_hr": first_hr.values})
    sp = pd.DataFrame({"date": spx.index.normalize()})
    sp["spx_ret"] = spx["Close"].pct_change().values

    m = fh.merge(dd[["date", "gap"]], on="date", how="inner")
    m = pd.merge_asof(m.sort_values("date"), sp[["date", "spx_ret"]].sort_values("date"),
                      on="date", direction="backward", allow_exact_matches=False)
    m = m.dropna(subset=["first_hr"])
    if m.empty:
        return {}

    gap_up = m["gap"] > 0
    # of the days that GAPPED UP, how often was the first hour still positive?
    hold = _rate(gap_up, m["first_hr"])
    sig_up = m["spx_ret"] > 0
    fh_when_sig = _rate(sig_up, m["first_hr"])

    return {
        "sample_days": int(len(m)),
        "first_hour_up_when_gap_up": hold,
        "first_hour_up_when_overnight_up": fh_when_sig,
    }


def run_backtest(force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE.get("data") and (now - _CACHE.get("ts", 0) < _TTL):
        return _CACHE["data"]

    gap = _gap_test()
    fh = _first_hour_test()
    data = {
        "as_of": time.strftime("%Y-%m-%d", time.localtime()),
        "gap": gap,
        "first_hour": fh,
        "method": (
            "Market-level (Nifty 50). Signal = sign of the S&P 500's prior "
            "session — the overnight lead the live model leans on. Gap tested "
            "over ~1 year of daily data; first-hour over ~60 days of 60-min bars."
        ),
        "caveat": (
            "This validates the OVERNIGHT-LEAD idea at the index level, not the "
            "per-stock scores. Past hit-rates do not guarantee future results."
        ),
    }
    _CACHE["data"] = data
    _CACHE["ts"] = now
    return data
