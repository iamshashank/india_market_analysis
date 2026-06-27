"""Forward-return backtest from accumulated score snapshots.

Genuine forward look (not contemporaneous): for a chosen lookback horizon, take
each stock's score on the snapshot date and its price change to *now*, then
bucket forward returns by the original score. If the screen works, higher-score
buckets should show higher average forward returns + hit-rates.

Requires accumulated `score_history` (one snapshot per screen build / nightly
job). With only one day of history it reports "insufficient history".
"""

from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional

from core import score_history
from data import history as price_history

BUCKETS = [("75+", 75, 999), ("65–75", 65, 75), ("55–65", 55, 65), ("<55", 0, 55)]


def _latest_price(ticker: str) -> Optional[float]:
    h = price_history.history(ticker, "3mo")
    if h.get("available") and h.get("candles"):
        return h["candles"][-1]["close"]
    return None


def run(min_days: int = 20, max_tickers: int = 120) -> dict:
    """Backtest using the oldest snapshot that is at least ``min_days`` old as
    the baseline; measure return to the latest price for each ticker."""
    rows = score_history.all_snapshots()
    if not rows:
        return {"available": False, "reason": "No score history yet — snapshots accumulate as the screen runs."}

    by_date: Dict[str, List[dict]] = {}
    for r in rows:
        if r.get("price") and r.get("score") is not None:
            by_date.setdefault(r["snapshot_date"], []).append(r)
    dates = sorted(by_date.keys())
    if len(dates) < 2:
        return {"available": False, "reason": "Only one snapshot so far — the backtest needs at least two dated runs. "
                                              "It will populate automatically as the screen runs over coming days.",
                "snapshots": len(dates)}

    today = _dt.date.today()
    # pick the oldest baseline that is >= min_days old; else the oldest available
    baseline = None
    for d in dates:
        try:
            age = (today - _dt.date.fromisoformat(d)).days
        except Exception:  # noqa: BLE001
            continue
        if age >= min_days:
            baseline = d
            break
    if baseline is None:
        baseline = dates[0]
    age_days = (today - _dt.date.fromisoformat(baseline)).days

    base_rows = by_date[baseline][:max_tickers]
    results = []
    per_bucket: Dict[str, List[float]] = {b[0]: [] for b in BUCKETS}
    for r in base_rows:
        last = _latest_price(r["ticker"])
        if not last or not r.get("price"):
            continue
        fwd = (last / r["price"] - 1.0) * 100.0
        for label, lo, hi in BUCKETS:
            if lo <= r["score"] < hi:
                per_bucket[label].append(fwd)
                break

    buckets_out = []
    for label, _, _ in BUCKETS:
        vals = per_bucket[label]
        if vals:
            buckets_out.append({
                "bucket": label, "count": len(vals),
                "avg_fwd_return_pct": round(sum(vals) / len(vals), 2),
                "hit_rate_pct": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
            })

    return {
        "available": True,
        "baseline_date": baseline,
        "horizon_days": age_days,
        "snapshots": len(dates),
        "universe_priced": sum(len(v) for v in per_bucket.values()),
        "buckets": buckets_out,
        "method": (f"Stocks scored on {baseline} ({age_days}d ago) bucketed by score; "
                   "forward return = latest price ÷ snapshot price − 1. A real forward "
                   "test that strengthens as more snapshots accumulate."),
        "caveat": ("Early results use a short history and a single baseline date. "
                   "Not survivorship-adjusted. Past performance ≠ future results."),
    }
