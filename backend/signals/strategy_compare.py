"""A/B strategy comparison — score the SAME universe under each strategy and
rank their quality against realised returns.

For every registered strategy version we re-score the identical fetched
fundamentals, then evaluate how well each version's score separates winners from
losers using:

  * IC  — Spearman rank correlation of score vs return,
  * spread — top-quartile minus bottom-quartile average return,
  * hit_rate — share of the top-quartile that was positive.

Return source:
  * "forward" (preferred) — when point-in-time snapshots exist, compares an old
    snapshot date's scores to the realised price move since (true forward test).
  * "trailing" (proxy)    — otherwise uses each name's trailing return (ret_6m /
    ret_1y) as a sanity proxy on today's data, clearly labelled as such.

This lets us answer "does the new algo separate stocks better than core-v1?"
on real data today, and graduate to a true forward verdict as data accumulates.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from signals import strategy as strategy_mod
from signals.multibagger import score_universe
from signals.backtest_scores import spearman, quantile_spread


def _eval(pairs: List[tuple]) -> dict:
    """pairs = [(score, return_pct)] -> IC / spread / hit / counts."""
    pairs = [(s, r) for s, r in pairs if isinstance(s, (int, float)) and isinstance(r, (int, float))]
    n = len(pairs)
    if n < 5:
        return {"n": n, "ic": None, "spread_pct": None, "top_q_hit_pct": None,
                "top_q_avg_pct": None, "bottom_q_avg_pct": None}
    scores = [p[0] for p in pairs]
    rets = [p[1] for p in pairs]
    ic = spearman(scores, rets)
    spread = quantile_spread(pairs)
    s = sorted(pairs, key=lambda p: p[0])
    q = max(1, n // 4)
    top, bot = s[-q:], s[:q]
    top_hit = sum(1 for _, r in top if r > 0) / len(top) * 100
    return {
        "n": n,
        "ic": round(ic, 3) if ic is not None else None,
        "spread_pct": spread,
        "top_q_hit_pct": round(top_hit, 1),
        "top_q_avg_pct": round(sum(r for _, r in top) / len(top), 2),
        "bottom_q_avg_pct": round(sum(r for _, r in bot) / len(bot), 2),
    }


def _trailing_return(row: dict) -> Optional[float]:
    for k in ("ret_6m", "ret_1y"):
        v = row.get(k)
        if isinstance(v, (int, float)):
            return v * 100.0
    return None


def compare(funda_rows: Optional[List[dict]] = None,
            news_map: Optional[dict] = None,
            versions: Optional[List[str]] = None) -> dict:
    """Compare every registered strategy on the same data.

    If ``funda_rows`` is None, fetch the curated universe live (no news, fast).
    Returns per-strategy IC / spread / hit so they're directly comparable.
    """
    return_mode = "trailing"
    if funda_rows is None:
        import os
        os.environ.setdefault("INCLUDE_NEWS", "0")
        from data.feed import fetch_universe
        funda_rows = fetch_universe(snapshot=False)
    news_map = news_map or {}

    versions = versions or [s["version"] for s in strategy_mod.list_versions()]

    # realised return per ticker (trailing proxy on the fetched rows)
    ret_by_ticker: Dict[str, float] = {}
    for r in funda_rows:
        tr = _trailing_return(r)
        if r.get("ticker") and tr is not None:
            ret_by_ticker[r["ticker"]] = tr

    results = []
    for v in versions:
        scored = score_universe(funda_rows, news_map, strategy_version=v)
        pairs = [(s["score"], ret_by_ticker.get(s["ticker"]))
                 for s in scored if s["ticker"] in ret_by_ticker]
        ev = _eval([(a, b) for a, b in pairs if b is not None])
        strat = strategy_mod.get(v)
        results.append({"version": v, "label": strat.label, **ev})

    # rank strategies by IC (then spread) — higher = better separation
    def keyf(x):
        return (x["ic"] if x["ic"] is not None else -9,
                x["spread_pct"] if x["spread_pct"] is not None else -9)
    ranked = sorted(results, key=keyf, reverse=True)
    best = ranked[0]["version"] if ranked else None

    return {
        "available": bool(results),
        "return_mode": return_mode,
        "scored_universe": len(funda_rows),
        "results": results,
        "ranked": [r["version"] for r in ranked],
        "best_version": best,
        "method": ("Same universe scored under each strategy; quality = how well its "
                   "score separates realised returns (IC, top-minus-bottom-quartile "
                   "spread, top-quartile hit rate)."),
        "caveat": ("return_mode='trailing' uses each name's PAST return as a proxy — a "
                   "sanity signal, NOT proof of forward skill. A true forward verdict "
                   "needs accumulated point-in-time snapshots (graduates automatically)."),
    }
