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

BENCH = {"IN": "^NSEI", "BSE": "^NSEI", "US": "^GSPC"}


def _ranks(vals: List[float]) -> List[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _spearman(xs: List[float], ys: List[float]) -> Optional[float]:
    """Spearman rank correlation (Information Coefficient) of score vs return."""
    n = len(xs)
    if n < 5:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx <= 0 or vy <= 0:
        return None
    return cov / ((vx * vy) ** 0.5)


def _quantile_spread(pairs: List[tuple]) -> Optional[float]:
    """Top-quartile minus bottom-quartile average forward return (the tradeable edge)."""
    if len(pairs) < 8:
        return None
    s = sorted(pairs, key=lambda p: p[0])
    q = max(1, len(s) // 4)
    top, bot = s[-q:], s[:q]
    return round(sum(p[1] for p in top) / len(top) - sum(p[1] for p in bot) / len(bot), 2)


def _index_return(symbol: str, baseline_date: str) -> Optional[float]:
    """Benchmark index return from the baseline date to the latest close."""
    try:
        h = price_history.history(symbol, "1y")
    except Exception:  # noqa: BLE001
        return None
    if not h.get("available") or not h.get("candles"):
        return None
    candles = h["candles"]
    last = candles[-1].get("close")
    base = None
    for c in candles:
        if str(c.get("date", ""))[:10] >= baseline_date:
            base = c.get("close")
            break
    if not base or not last:
        return None
    return (last / base - 1.0) * 100.0


def _latest_price(ticker: str) -> Optional[float]:
    h = price_history.history(ticker, "3mo")
    if h.get("available") and h.get("candles"):
        return h["candles"][-1]["close"]
    return None


def _latest_prices(tickers: List[str]) -> Dict[str, float]:
    """Batch-fetch the latest close for many tickers in ONE network call
    (yfinance.download), falling back to the cached per-ticker path for any
    that the batch misses. Avoids 100+ sequential 3-month history fetches."""
    out: Dict[str, float] = {}
    uniq = [t for t in dict.fromkeys(tickers) if t]
    if not uniq:
        return out
    try:
        import yfinance as yf
        df = yf.download(uniq, period="5d", interval="1d", auto_adjust=True,
                         progress=False, threads=True, group_by="ticker")
        for t in uniq:
            try:
                if len(uniq) == 1:
                    series = df["Close"].dropna()
                else:
                    series = df[t]["Close"].dropna()
                if len(series):
                    out[t] = float(series.iloc[-1])
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    # fill any gaps from the cached single-ticker path
    for t in uniq:
        if t not in out:
            p = _latest_price(t)
            if p:
                out[t] = p
    return out


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
    latest = _latest_prices([r["ticker"] for r in base_rows])
    per_bucket: Dict[str, List[float]] = {b[0]: [] for b in BUCKETS}
    pairs: List[tuple] = []  # (score, fwd_pct, market)
    for r in base_rows:
        last = latest.get(r["ticker"])
        if not last or not r.get("price"):
            continue
        fwd = (last / r["price"] - 1.0) * 100.0
        pairs.append((r["score"], fwd, r.get("market")))
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

    scores = [p[0] for p in pairs]
    fwds = [p[1] for p in pairs]
    ic = _spearman(scores, fwds)
    spread = _quantile_spread([(p[0], p[1]) for p in pairs])
    overall_hit = round(sum(1 for f in fwds if f > 0) / len(fwds) * 100, 1) if fwds else None

    # benchmark-relative, per market present in the baseline
    by_market: Dict[str, List[float]] = {}
    for s, f, m in pairs:
        by_market.setdefault(m or "US", []).append(f)
    bench_rel = []
    for m, fs in sorted(by_market.items()):
        sym = BENCH.get(m, "^GSPC")
        br = _index_return(sym, baseline)
        avg = sum(fs) / len(fs)
        bench_rel.append({
            "market": m, "benchmark": sym, "count": len(fs),
            "portfolio_avg_pct": round(avg, 2),
            "benchmark_return_pct": round(br, 2) if br is not None else None,
            "excess_pct": round(avg - br, 2) if br is not None else None,
        })

    strat_versions = sorted({r.get("strategy_version") for r in base_rows if r.get("strategy_version")})

    return {
        "available": True,
        "baseline_date": baseline,
        "horizon_days": age_days,
        "snapshots": len(dates),
        "universe_priced": len(pairs),
        "strategy_versions": strat_versions,
        "ic": round(ic, 3) if ic is not None else None,
        "quantile_spread_pct": spread,
        "overall_hit_rate_pct": overall_hit,
        "benchmark_relative": bench_rel,
        "buckets": buckets_out,
        "method": (f"Stocks scored on {baseline} ({age_days}d ago) bucketed by score; "
                   "forward return = latest price ÷ snapshot price − 1. IC = Spearman rank "
                   "correlation of score vs forward return; spread = top-quartile minus "
                   "bottom-quartile average return. Strengthens as snapshots accumulate."),
        "caveat": ("Early results use a short history and a single baseline date. "
                   "Not survivorship-adjusted. Past performance ≠ future results."),
    }
