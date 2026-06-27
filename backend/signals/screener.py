"""Multibagger screen orchestration.

Pipeline:  fetch fundamentals (India + US)  ->  fetch news/catalysts  ->
score every name on the strategy pillars  ->  concentrate into a
conviction-weighted portfolio  ->  return a JSON-serialisable payload.

The web layer caches this (it takes ~1-2 min live) and persists it to MySQL.
"""

from __future__ import annotations

import time
from typing import List

from core.config import WEIGHTS, INCLUDE_NEWS, DISCLAIMER, PORTFOLIO_SIZE
from data.universe import UNIVERSE
from data.feed import fetch_universe
from signals import news as news_mod
from data import candles as candles_mod
from signals import themes as themes_mod
from signals.multibagger import score_universe, build_portfolio, build_portfolios_by_tier

STRATEGY = {
    "title": "Multibagger compounders across cap tiers (India + US)",
    "criteria": [
        {"key": "room_to_grow", "label": "Room to grow",
         "desc": "Headroom to compound, ranked within each cap tier — size-neutral."},
        {"key": "consistency", "label": "Consistent earnings",
         "desc": "Steady or rising earnings, not lumpy quarter-to-quarter swings."},
        {"key": "under_covered", "label": "Limited coverage",
         "desc": "Few analysts / little media — overlooked, more likely mispriced."},
        {"key": "catalyst", "label": "News & event catalysts",
         "desc": "Recent events (orders, approvals, expansion) that can re-rate the stock."},
        {"key": "concentration", "label": "High conviction",
         "desc": "Meaningful, concentrated weights in the very best ideas, per cap tier."},
    ],
}


def build_screen(force: bool = False, universe: dict | None = None) -> dict:
    """Run the full screen and return the report payload.

    ``universe`` defaults to the curated UNIVERSE; the nightly scan passes a
    much larger dict for broad-market coverage.
    """
    t0 = time.time()
    uni = universe or UNIVERSE
    funda_rows = fetch_universe(uni)

    eligible_tickers = [r["ticker"] for r in funda_rows if not r.get("error") and r.get("price")]

    news_map = {}
    if INCLUDE_NEWS:
        news_map = news_mod.analyze_many(eligible_tickers)

    return assemble_payload(funda_rows, news_map, universe_size=len(uni), t0=t0)


def assemble_payload(funda_rows: List[dict], news_map: dict | None = None,
                     universe_size: int | None = None, t0: float | None = None) -> dict:
    """Score rows → portfolio + themes + payload. Shared by the live screen and
    the nightly broad scan (which passes an empty news_map for speed)."""
    import time as _t
    t0 = t0 or _t.time()
    news_map = news_map or {}
    scored = score_universe(funda_rows, news_map)

    # Industry P/E proxy: median trailing P/E within each sector of the universe.
    import statistics
    sector_pes: dict = {}
    for s in scored:
        pe = (s.get("metrics") or {}).get("trailing_pe")
        sec = s.get("sector")
        if isinstance(pe, (int, float)) and pe > 0 and sec:
            sector_pes.setdefault(sec, []).append(pe)
    industry_pe = {sec: round(statistics.median(v), 1) for sec, v in sector_pes.items() if v}
    for s in scored:
        s["industry_pe"] = industry_pe.get(s.get("sector"))

    # Light validation: avg trailing return by composite-score bucket. This is a
    # contemporaneous association check (NOT a true forward backtest — we lack
    # point-in-time history), shown with that caveat.
    buckets = [("75+", 75, 999), ("65–75", 65, 75), ("55–65", 55, 65), ("<55", 0, 55)]
    score_validation = []
    for label, lo, hi in buckets:
        grp = [s for s in scored if lo <= s["score"] < hi]
        r1 = [(s.get("metrics") or {}).get("ret_1y") for s in grp]
        r1 = [x for x in r1 if isinstance(x, (int, float))]
        if grp:
            score_validation.append({
                "bucket": label, "count": len(grp),
                "avg_ret_1y_pct": round(sum(r1) / len(r1) * 100, 1) if r1 else None,
            })

    portfolio = build_portfolio(scored)
    tier_portfolios = build_portfolios_by_tier(scored)

    failed = [r["ticker"] for r in funda_rows if r.get("error")]
    shortlist = scored[: max(120, PORTFOLIO_SIZE * 3)]

    # Candlestick timing overlay for the names we actually surface (portfolio +
    # per-tier portfolios + shortlist), deduped.
    overlay_tickers = {s["ticker"] for s in shortlist} | {p["ticker"] for p in portfolio}
    for grp in tier_portfolios:
        overlay_tickers |= {p["ticker"] for p in grp["portfolio"]}
    candle_map = candles_mod.detect_many(list(overlay_tickers))
    for s in shortlist:
        s["candle"] = candle_map.get(s["ticker"])
    for p in portfolio:
        p["candle"] = candle_map.get(p["ticker"])
    for grp in tier_portfolios:
        for p in grp["portfolio"]:
            p["candle"] = candle_map.get(p["ticker"])

    by_market = {"IN": [s for s in shortlist if s.get("market") in ("IN", "BSE")],
                 "US": [s for s in shortlist if s.get("market") == "US"]}

    # tier counts (for UI filters), per market
    tier_counts: dict = {}
    for s in scored:
        tier_counts.setdefault(s.get("market"), {}).setdefault(s.get("cap_tier"), 0)
        tier_counts[s.get("market")][s.get("cap_tier")] += 1

    theme_heatmap = themes_mod.build_heatmap(scored)
    # Per-market heatmaps so the global market selector can show a region view.
    themes_by_market = {
        "IN": themes_mod.build_heatmap([s for s in scored if s.get("market") in ("IN", "BSE")]),
        "US": themes_mod.build_heatmap([s for s in scored if s.get("market") == "US"]),
    }

    # Persist today's scores so we accumulate a real time series for the
    # forward-return backtest + per-stock score-history sparklines.
    try:
        from core import score_history
        score_history.snapshot(scored)
    except Exception:  # noqa: BLE001
        pass

    return {
        "as_of": time.strftime("%Y-%m-%d %H:%M IST", time.localtime()),
        "build_seconds": round(time.time() - t0, 1),
        "universe_size": universe_size if universe_size is not None else len(funda_rows),
        "scored_count": len(scored),
        "failed_tickers": failed,
        "weights": {k: round(v, 3) for k, v in WEIGHTS.items()},
        "strategy": STRATEGY,
        "portfolio": portfolio,
        "tier_portfolios": tier_portfolios,
        "tier_counts": tier_counts,
        "shortlist": shortlist,
        "by_market": by_market,
        "themes": theme_heatmap,
        "themes_by_market": themes_by_market,
        "industry_pe": industry_pe,
        "score_validation": score_validation,
        "disclaimer": DISCLAIMER,
    }


def analyze_ticker(ticker: str) -> dict:
    """Run the full multibagger algorithm on a SINGLE stock and return its
    score breakdown — for the 'analyze any company' search.

    Note: pillars like room-to-grow / quality / growth / valuation are normally
    percentile-ranked within the scanned universe. For a lone stock we score it
    against the curated UNIVERSE so the percentiles are still meaningful, then
    pull out just the requested ticker.
    """
    from data.feed import fetch_one
    from data.universe import UNIVERSE
    import data.candles as candles_mod

    ticker = (ticker or "").strip()
    if not ticker:
        return {"available": False, "reason": "No ticker given"}

    meta = UNIVERSE.get(ticker) or {
        "name": ticker.replace(".NS", "").replace(".BO", ""),
        "market": "IN" if ticker.endswith(".NS") else "BSE" if ticker.endswith(".BO") else "US",
        "currency": "INR" if (ticker.endswith(".NS") or ticker.endswith(".BO")) else "USD",
    }

    # fetch the target + the curated universe (for percentile context), dedup target
    target = asdict_safe(fetch_one(ticker, meta))

    # BSE (.BO) listings frequently return no price from Yahoo — fall back to the
    # NSE (.NS) twin (same company, far better data) so Indian stocks just work.
    switched_from = None
    if (target.get("error") or not target.get("price")) and ticker.endswith(".BO"):
        from data.symbols import nse_twin
        twin = nse_twin(ticker, meta.get("name"))
        if twin:
            alt = asdict_safe(fetch_one(twin, {"name": meta.get("name"), "market": "IN", "currency": "INR"}))
            if alt.get("price"):
                switched_from, ticker, target = ticker, twin, alt
                meta = {"name": alt.get("name") or meta.get("name"), "market": "IN", "currency": "INR"}

    if target.get("error") or not target.get("price"):
        return {"available": False, "ticker": ticker,
                "reason": target.get("error") or "No price data (symbol may be delisted or unsupported)."}

    context = fetch_universe({k: v for k, v in UNIVERSE.items() if k != ticker}, snapshot=False)
    rows = context + [target]

    news = news_mod.analyze(ticker) if INCLUDE_NEWS else {}
    news_map = {ticker: news} if news else {}

    # User explicitly asked for this stock → never hard-reject it on the
    # portfolio liquidity/cap floors; flag concerns as warnings instead.
    scored = score_universe(rows, news_map, force_include={ticker})
    me = next((s for s in scored if s["ticker"] == ticker), None)
    if not me:
        return {"available": False, "ticker": ticker,
                "reason": "Could not score this stock (insufficient data from the data provider)."}

    from core.config import MIN_ADV_USD, MIN_CAP_USD
    warnings = []
    if switched_from:
        warnings.append(f"{switched_from} (BSE) has no Yahoo price data — showing the NSE listing {ticker} (same company, better data).")
    adv = (me.get("metrics") or {}).get("adv_value_usd")
    if isinstance(adv, (int, float)) and adv < MIN_ADV_USD:
        warnings.append(f"Low liquidity (~${adv/1e3:.0f}k/day traded) — below the {MIN_ADV_USD/1e3:.0f}k portfolio floor; hard to build a position.")
    if not isinstance(me.get("market_cap_usd"), (int, float)):
        warnings.append("Market cap unavailable from the data provider for this listing.")
    if ticker.endswith(".BO"):
        warnings.append("BSE listing — most volume/coverage is usually on the NSE (.NS) twin; try that symbol for richer data.")
    me["warnings"] = warnings

    me["candle"] = candles_mod.detect_for_ticker(ticker)
    # peer context: where it ranks among everything scored
    me["rank"] = scored.index(me) + 1
    me["scored_total"] = len(scored)
    me["weights"] = {k: round(v, 3) for k, v in WEIGHTS.items()}
    me["available"] = True
    return me


def asdict_safe(obj):
    from dataclasses import asdict, is_dataclass
    return asdict(obj) if is_dataclass(obj) else dict(obj)


if __name__ == "__main__":
    import json
    print(json.dumps(build_screen(force=True), default=str)[:2000])