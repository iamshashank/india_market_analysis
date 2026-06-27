"""Multibagger composite scoring + high-conviction portfolio construction.

Turns raw fundamentals + news into an explainable 0-100 score built from the
strategy's pillars, then concentrates the best ideas into a conviction-weighted
portfolio. Every number traces back to a stated rule.

Pillars (weights live in config.WEIGHTS):
  room_to_grow   - headroom to compound, ranked WITHIN the stock's cap tier
  consistency    - steady / rising earnings (criterion 2, from earnings_quality)
  under_covered  - few analysts + little news = hidden gem (criterion 3)
  growth         - revenue / earnings growth runway
  quality        - ROE, margins, FCF, low debt
  valuation      - not paying an absurd price for the growth
  catalyst       - recent news / event momentum (from news.py)

Scoring is SIZE-NEUTRAL: every stock is bucketed into a per-market cap tier
(India 3, US 5) and ranked against its tier peers, so a great large-cap is no
longer penalised just for being large. Concentration (criterion 4) is enforced
in build_portfolio: a handful of names, weights tilted toward the
highest-conviction ideas, with a per-sector cap.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from core.config import (
    WEIGHTS, MIN_ADV_USD, MIN_CAP_USD, cap_tier,
    PORTFOLIO_SIZE, MAX_WEIGHT_PCT, MIN_WEIGHT_PCT, MAX_PER_SECTOR,
    MIN_SCORE, LOW_ANALYST_COUNT, LOW_NEWS_COUNT,
)
from signals.earnings_quality import consistency as earnings_consistency, label as consistency_label


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _pctile_scores(values: Dict[str, Optional[float]], higher_is_better: bool = True
                   ) -> Dict[str, float]:
    """Percentile-rank a ticker->value map into 0-100. None -> 50 (neutral)."""
    have = {k: v for k, v in values.items() if isinstance(v, (int, float))}
    out: Dict[str, float] = {}
    if not have:
        return {k: 50.0 for k in values}
    ordered = sorted(have.values())
    n = len(ordered)

    def rank(v: float) -> float:
        below = sum(1 for x in ordered if x < v)
        equal = sum(1 for x in ordered if x == v)
        pct = (below + 0.5 * equal) / n * 100.0
        return pct if higher_is_better else 100.0 - pct

    for k, v in values.items():
        out[k] = round(rank(v), 1) if isinstance(v, (int, float)) else 50.0
    return out


def _room_to_grow_pillar(rows: List[dict]) -> Dict[str, float]:
    """Headroom to compound, ranked WITHIN each (market, cap tier) group.

    Within a tier, a smaller cap and a stronger growth runway = more room. This
    replaces the old global small-cap penalty, so large caps compete fairly
    against other large caps instead of against micro-caps.
    """
    groups: Dict[tuple, List[dict]] = {}
    for r in rows:
        groups.setdefault((r.get("market"), r.get("_tier")), []).append(r)

    out: Dict[str, float] = {}
    for _, grp in groups.items():
        # smaller-within-tier (40%) + growth runway (60%), percentile-ranked in-group
        smaller = _pctile_scores({r["ticker"]: r.get("market_cap_usd") for r in grp},
                                  higher_is_better=False)
        def runway(r):
            vals = [v for v in (r.get("revenue_growth"), r.get("earnings_growth"))
                    if isinstance(v, (int, float))]
            return sum(_clip(v, -0.5, 2.0) for v in vals) / len(vals) if vals else None
        grow = _pctile_scores({r["ticker"]: runway(r) for r in grp})
        for r in grp:
            t = r["ticker"]
            out[t] = round(smaller[t] * 0.4 + grow[t] * 0.6, 1)
    return out


def _under_covered_score(num_analysts: Optional[float], news_count: Optional[float],
                         inst_hold: Optional[float]) -> float:
    # few analysts -> hidden
    if num_analysts is None:
        analyst = 65.0  # genuinely no coverage data often = uncovered
    else:
        analyst = _clip(100.0 * (1.0 - num_analysts / 20.0), 0.0, 100.0)
    # little news flow -> hidden
    nc = news_count if isinstance(news_count, (int, float)) else 2
    news = _clip(100.0 * (1.0 - nc / 12.0), 0.0, 100.0)
    # lower institutional ownership -> less discovered
    if isinstance(inst_hold, (int, float)):
        inst = _clip(100.0 * (1.0 - inst_hold), 0.0, 100.0)
    else:
        inst = 50.0
    return round(analyst * 0.5 + news * 0.3 + inst * 0.2, 1)


def _quality_pillar(rows: List[dict]) -> Dict[str, float]:
    roe = _pctile_scores({r["ticker"]: r.get("roe") for r in rows})
    pm = _pctile_scores({r["ticker"]: r.get("profit_margin") for r in rows})
    fcf = _pctile_scores({r["ticker"]: r.get("fcf_margin") for r in rows})
    d2e = _pctile_scores({r["ticker"]: r.get("debt_to_equity") for r in rows},
                         higher_is_better=False)
    out = {}
    for r in rows:
        t = r["ticker"]
        out[t] = round(roe[t] * 0.32 + pm[t] * 0.28 + fcf[t] * 0.22 + d2e[t] * 0.18, 1)
    return out


def _growth_pillar(rows: List[dict]) -> Dict[str, float]:
    def blended(r):
        vals = [v for v in (r.get("revenue_growth"), r.get("earnings_growth"))
                if isinstance(v, (int, float))]
        if not vals:
            return None
        return sum(_clip(v, -0.5, 2.0) for v in vals) / len(vals)
    return _pctile_scores({r["ticker"]: blended(r) for r in rows})


def _valuation_pillar(rows: List[dict]) -> Dict[str, float]:
    # cheapness: low PEG and low P/B are good; we percentile-rank "lowness"
    peg = _pctile_scores({r["ticker"]: r.get("peg") for r in rows}, higher_is_better=False)
    pb = _pctile_scores({r["ticker"]: r.get("price_to_book") for r in rows},
                        higher_is_better=False)
    out = {}
    for r in rows:
        t = r["ticker"]
        out[t] = round(peg[t] * 0.6 + pb[t] * 0.4, 1)
    return out


def score_universe(funda_rows: List[dict], news_map: Dict[str, dict],
                   force_include: Optional[set] = None) -> List[dict]:
    """Score every eligible name; return list sorted by composite desc.

    ``force_include`` is a set of tickers that bypass the liquidity/min-cap
    floors (used by the single-stock analyzer, where a user explicitly asked for
    that stock and should always get a result + a warning instead of rejection).
    """
    force_include = force_include or set()
    # eligibility: priced, has a real market cap, clears liquidity + min-cap floors
    rows = []
    for r in funda_rows:
        if r.get("error") or not r.get("price"):
            continue
        forced = r.get("ticker") in force_include
        cap = r.get("market_cap_usd")
        # Reject only when cap is KNOWN and below the floor; an unknown cap on an
        # otherwise-liquid name shouldn't auto-fail (yfinance sometimes omits it).
        if not forced and isinstance(cap, (int, float)) and cap < MIN_CAP_USD:
            continue
        adv = r.get("adv_value_usd")
        if not forced and isinstance(adv, (int, float)) and adv < MIN_ADV_USD:
            continue
        r["_tier"] = cap_tier(r.get("market"), cap)
        rows.append(r)
    if not rows:
        return []

    quality = _quality_pillar(rows)
    growth = _growth_pillar(rows)
    valuation = _valuation_pillar(rows)
    room = _room_to_grow_pillar(rows)

    scored: List[dict] = []
    for r in rows:
        t = r["ticker"]
        news = news_map.get(t, {})
        cons_score, cons_detail = earnings_consistency(
            r.get("quarterly_ni") or [], r.get("quarterly_rev") or [])

        pillars = {
            "room_to_grow": room[t],
            "consistency": cons_score if cons_score is not None else 40.0,
            "under_covered": _under_covered_score(
                r.get("num_analysts"), news.get("news_count"), r.get("inst_hold_pct")),
            "growth": growth[t],
            "quality": quality[t],
            "valuation": valuation[t],
            "catalyst": news.get("catalyst_score", 50.0),
        }
        wsum = sum(WEIGHTS.values())
        composite = sum(WEIGHTS[k] * pillars[k] for k in WEIGHTS) / wsum

        conviction = _conviction(composite, pillars, cons_score, news, r)
        scored.append({
            "ticker": t,
            "name": r.get("name"),
            "market": r.get("market"),
            "currency": r.get("currency"),
            "cap_tier": r.get("_tier"),
            "sector": r.get("sector") or "Unknown",
            "industry": r.get("industry"),
            "price": r.get("price"),
            "market_cap_usd": r.get("market_cap_usd"),
            "score": round(composite, 1),
            "pillars": {k: round(v, 1) for k, v in pillars.items()},
            "conviction": conviction,
            "consistency_label": consistency_label(cons_score),
            "consistency_detail": cons_detail,
            "num_analysts": r.get("num_analysts"),
            "metrics": {
                "trailing_pe": r.get("trailing_pe"),
                "forward_pe": r.get("forward_pe"),
                "peg": r.get("peg"),
                "price_to_book": r.get("price_to_book"),
                "roe": r.get("roe"),
                "profit_margin": r.get("profit_margin"),
                "fcf_margin": r.get("fcf_margin"),
                "debt_to_equity": r.get("debt_to_equity"),
                "revenue_growth": r.get("revenue_growth"),
                "earnings_growth": r.get("earnings_growth"),
                "ret_6m": r.get("ret_6m"),
                "ret_1y": r.get("ret_1y"),
                "inst_hold_pct": r.get("inst_hold_pct"),
                "adv_value_usd": r.get("adv_value_usd"),
            },
            "news": {
                "catalyst_score": news.get("catalyst_score", 50.0),
                "news_count": news.get("news_count", 0),
                "top_events": news.get("top_events", []),
                "headlines": news.get("headlines", [])[:5],
            },
            "thesis": _thesis(pillars, cons_score, news, r),
            "risks": _risks(pillars, cons_score, news, r),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _conviction(composite: float, pillars: dict, cons_score: Optional[float],
                news: dict, r: dict) -> str:
    if composite >= 70 and cons_score is not None and news.get("negative", 0) == 0:
        base = "High"
    elif composite >= 60:
        base = "Medium"
    else:
        base = "Speculative"
    # downgrade on red flags
    if news.get("negative", 0) >= 2 or (pillars["quality"] < 30):
        if base == "High":
            base = "Medium"
        elif base == "Medium":
            base = "Speculative"
    return base


def _fmt_pct(v: Optional[float]) -> str:
    return f"{v * 100:.0f}%" if isinstance(v, (int, float)) else "n/a"


def _thesis(pillars: dict, cons_score: Optional[float], news: dict, r: dict) -> List[str]:
    out: List[str] = []
    tier = r.get("_tier")
    if pillars.get("room_to_grow", 0) >= 65:
        out.append(f"Strong runway for its size — ranks high on room-to-grow among {tier or 'its'}-cap peers.")
    if cons_score is not None and cons_score >= 60:
        out.append("Earnings have been steady/rising, not lumpy — the compounding profile we want.")
    if pillars["under_covered"] >= 65:
        na = r.get("num_analysts")
        out.append(f"Under the radar — {('only ' + str(na)) if na is not None else 'few'} analysts cover it; mispricing is more likely.")
    if pillars["growth"] >= 65:
        out.append(f"Growth runway intact (rev {_fmt_pct(r.get('revenue_growth'))}, EPS {_fmt_pct(r.get('earnings_growth'))}).")
    if pillars["quality"] >= 65:
        out.append(f"Quality balance sheet/returns (ROE {_fmt_pct(r.get('roe'))}, margin {_fmt_pct(r.get('profit_margin'))}).")
    if news.get("top_events"):
        out.append("Recent catalysts: " + ", ".join(news["top_events"][:3]) + ".")
    return out[:5] or ["Passes the screen on a blend of size-relative growth, quality and value."]


def _risks(pillars: dict, cons_score: Optional[float], news: dict, r: dict) -> List[str]:
    out: List[str] = []
    tier = r.get("_tier")
    if tier in ("Micro", "Small"):
        out.append(f"{tier}-cap: more volatile and less liquid; size positions carefully.")
    if cons_score is not None and cons_score < 45:
        out.append("Earnings have been erratic quarter to quarter.")
    if pillars["valuation"] < 35:
        out.append("Valuation is rich — limited margin of safety if growth slows.")
    d2e = r.get("debt_to_equity")
    if isinstance(d2e, (int, float)) and d2e > 1.0:
        out.append(f"Leverage is elevated (D/E ~{d2e:.1f}).")
    if news.get("negative", 0):
        out.append("Recent negative headlines — verify before acting.")
    if not out:
        out.append("Standard equity risk; even quality compounders can de-rate.")
    return out[:4]


def build_portfolio(scored: List[dict], size: int = PORTFOLIO_SIZE,
                    max_per_sector: int = MAX_PER_SECTOR) -> List[dict]:
    """Concentrate the best ideas into a conviction-weighted portfolio
    (criterion 4), with a per-sector cap for sanity."""
    picks: List[dict] = []
    per_sector: Dict[str, int] = {}
    for s in scored:
        if s["score"] < MIN_SCORE:
            continue
        sec = s.get("sector") or "Unknown"
        if per_sector.get(sec, 0) >= max_per_sector:
            continue
        picks.append(s)
        per_sector[sec] = per_sector.get(sec, 0) + 1
        if len(picks) >= size:
            break

    if not picks:
        return []

    # weight ∝ score^2 to concentrate in the best ideas, then clip & renormalise
    raw = {p["ticker"]: (p["score"] ** 2) for p in picks}
    total = sum(raw.values())
    weights = {t: (v / total) * 100.0 for t, v in raw.items()}

    # clip into [MIN_WEIGHT, MAX_WEIGHT] then renormalise once
    for t in weights:
        weights[t] = _clip(weights[t], MIN_WEIGHT_PCT, MAX_WEIGHT_PCT)
    s = sum(weights.values())
    weights = {t: round(v / s * 100.0, 1) for t, v in weights.items()}

    conv_tier = {"High": "Core", "Medium": "Half", "Speculative": "Starter"}
    out = []
    for p in picks:
        out.append({
            **p,
            "weight_pct": weights[p["ticker"]],
            "size_tier": conv_tier.get(p["conviction"], "Starter"),
            "entry_note": ("Stagger entry in 2-3 tranches — smaller/low-coverage names "
                           "gap on low volume."),
        })
    return out


# Tier display order per market (largest → smallest reads naturally as headers).
_TIER_ORDER = {
    "IN": ["Large", "Mid", "Small"],
    "BSE": ["Large", "Mid", "Small"],
    "US": ["Mega", "Large", "Mid", "Small", "Micro"],
}


def build_portfolios_by_tier(scored: List[dict], per_tier: int = 5) -> List[dict]:
    """A separate concentrated portfolio for each (market, cap tier), so you get
    the best compounders in every size class — not just small-caps."""
    groups: Dict[tuple, List[dict]] = {}
    for s in scored:
        groups.setdefault((s.get("market"), s.get("cap_tier")), []).append(s)

    out: List[dict] = []
    for market in ("IN", "BSE", "US"):
        for tier in _TIER_ORDER.get(market, []):
            grp = sorted(groups.get((market, tier), []), key=lambda x: x["score"], reverse=True)
            pf = build_portfolio(grp, size=per_tier, max_per_sector=per_tier)
            if pf:
                out.append({"market": market, "cap_tier": tier,
                            "count": len(grp), "portfolio": pf})
    return out
