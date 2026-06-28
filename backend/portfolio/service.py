"""Portfolio analysis: gather holdings → score with the full engine → group by broker.

Runs the same multibagger scoring (composite, health, inflection, emerging) used
by the screen, but on *your* holdings. Holdings are scored against the curated
universe so the percentile-ranked pillars stay meaningful. Built in the
background and cached (it re-fetches fundamentals), like the screen.
"""

from __future__ import annotations

from typing import Dict, List

from core.config import USD_PER
from portfolio import holdings_store
from portfolio.sources.groww import GrowwSource
from portfolio.sources.kite import KiteSource

_SOURCES = [GrowwSource(), KiteSource()]


def _live_holdings() -> List[dict]:
    rows: List[dict] = []
    for s in _SOURCES:
        if not s.is_configured():
            continue
        for h in s.holdings():
            mkt = h.get("market", "IN")
            rows.append({
                "id": f"live-{s.name}-{h.get('symbol')}",
                "broker": h.get("broker", s.name),
                "symbol": h.get("symbol"), "market": mkt,
                "ticker": holdings_store.norm_ticker(h.get("symbol"), mkt),
                "quantity": holdings_store._num(h.get("quantity")),
                "avg_price": holdings_store._num(h.get("avg_price")),
                "live": True,
            })
    return rows


def gather_holdings() -> List[dict]:
    return list(holdings_store.list_holdings()) + _live_holdings()


def build(force: bool = False) -> dict:
    holdings = gather_holdings()
    configured = [s.name for s in _SOURCES if s.is_configured()]
    if not holdings:
        return {"available": True, "holdings": [], "by_broker": [], "stats": {},
                "sources_configured": configured}

    tickers = sorted({h["ticker"] for h in holdings if h.get("ticker")})
    analysis = _analyze(tickers)

    enriched: List[dict] = []
    for h in holdings:
        a = analysis.get(h["ticker"]) or {}
        price = a.get("price")
        qty = h.get("quantity")
        mkt = h.get("market", "IN")
        ccy = "USD" if mkt == "US" else "INR"
        value = (qty * price) if (qty and price) else None
        value_usd = (value * USD_PER.get(mkt, 1.0)) if value else None
        invested = (qty * h["avg_price"]) if (qty and h.get("avg_price")) else None
        pnl_pct = ((price / h["avg_price"] - 1.0) * 100.0
                   if (price and h.get("avg_price")) else None)
        enriched.append({
            **h,
            "name": a.get("name") or h.get("symbol"),
            "sector": a.get("sector"), "cap_tier": a.get("cap_tier"),
            "ccy": ccy,
            "price": price, "value": round(value, 2) if value else None,
            "value_usd": round(value_usd, 2) if value_usd else None,
            "invested": round(invested, 2) if invested else None,
            "pnl_pct": round(pnl_pct, 1) if pnl_pct is not None else None,
            "score": a.get("score"), "conviction": a.get("conviction"),
            "compounder_score": a.get("compounder_score"),
            "catalyst_score": a.get("catalyst_score"),
            "health": a.get("health"), "inflection": a.get("inflection"),
            "emerging_compounder": a.get("emerging_compounder"),
            "pillars": a.get("pillars"),
            "unanalysed": not bool(a),
        })

    groups: Dict[str, List[dict]] = {}
    for h in enriched:
        groups.setdefault(h["broker"], []).append(h)
    by_broker = [{
        "broker": b,
        "holdings": hs,
        "value": round(sum(x["value"] or 0 for x in hs), 2),
        "count": len(hs),
    } for b, hs in sorted(groups.items())]

    return {"available": True, "holdings": enriched, "by_broker": by_broker,
            "stats": _stats(enriched), "sources_configured": configured}


def _analyze(tickers: List[str]) -> Dict[str, dict]:
    from data.feed import fetch_universe
    from data.universe import UNIVERSE
    from signals import news as news_mod
    from signals.multibagger import score_universe
    from core.config import INCLUDE_NEWS

    uni: Dict[str, dict] = {}
    for t in tickers:
        mkt = "IN" if t.endswith(".NS") else "BSE" if t.endswith(".BO") else "US"
        uni[t] = {"name": t, "market": mkt,
                  "currency": "INR" if mkt in ("IN", "BSE") else "USD"}
    context = {k: v for k, v in UNIVERSE.items() if k not in uni}
    rows = fetch_universe({**context, **uni}, snapshot=False)
    news_map = news_mod.analyze_many(tickers) if INCLUDE_NEWS else {}
    scored = score_universe(rows, news_map, force_include=set(tickers))
    want = set(tickers)
    return {s["ticker"]: s for s in scored if s["ticker"] in want}


def _stats(enriched: List[dict]) -> dict:
    scored = [h for h in enriched if h.get("score") is not None]
    total_by_ccy: Dict[str, float] = {}
    for h in enriched:
        if h.get("value"):
            total_by_ccy[h["ccy"]] = round(total_by_ccy.get(h["ccy"], 0.0) + h["value"], 2)
    valued_count = sum(1 for h in enriched if h.get("value"))

    # value-weighted score (USD-normalised so ₹ and $ holdings weight fairly)
    wpairs = [(h["score"], h["value_usd"]) for h in scored if h.get("value_usd")]
    if wpairs:
        wavg = sum(s * v for s, v in wpairs) / sum(v for _, v in wpairs)
    elif scored:
        wavg = sum(h["score"] for h in scored) / len(scored)
    else:
        wavg = None

    health_counts: Dict[str, int] = {}
    for h in enriched:
        lab = (h.get("health") or {}).get("label")
        if lab and lab != "Unknown":
            health_counts[lab] = health_counts.get(lab, 0) + 1

    flagged = [{"ticker": h["ticker"], "name": h.get("name"),
                "flags": (h.get("health") or {}).get("flags", [])}
               for h in enriched if (h.get("health") or {}).get("flags")]
    emerging = [{"ticker": h["ticker"], "name": h.get("name")}
                for h in enriched if h.get("emerging_compounder")]
    weakest = [{"ticker": h["ticker"], "name": h.get("name"), "score": h["score"]}
               for h in sorted(scored, key=lambda x: x["score"])[:3]]

    return {
        "total_by_ccy": total_by_ccy,
        "count": len(enriched),
        "valued_count": valued_count,
        "analysed": len(scored),
        "weighted_avg_score": round(wavg, 1) if wavg is not None else None,
        "health_counts": health_counts,
        "flagged": flagged,
        "emerging": emerging,
        "weakest": weakest,
    }
