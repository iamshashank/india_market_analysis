"""Next-day market-open predictor (educational, NOT a guarantee).

Single purpose: estimate which NSE stocks are most likely to OPEN HIGHER
tomorrow, from overnight / pre-open global cues:

  * US index futures (S&P / Nasdaq) — closest live proxy for GIFT Nifty
  * US cash indices (prior session)
  * Asian markets trading during the IST morning (Nikkei, Hang Seng, Shanghai)
  * Commodities (crude, gold), US Dollar Index, USD/INR
  * India VIX (fear gauge)
  * Overnight ADR moves for cross-listed names (direct next-day gap signal)

Each stock is tilted by its sector's sensitivity to those cues, its beta,
recent momentum, and (for ADR names) the overnight ADR move.

IMPORTANT: Markets are not predictable. Nothing here is "sure" to rise. This
is a transparent rules engine that estimates ODDS, for education only.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import time
import warnings
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

from urllib.parse import quote

from predictor.stock_universe import UNIVERSE
from data.metrics import fetch_universe
from predictor.backtest import run_backtest


# ---- Global cue symbols ---------------------------------------------------
CUE_SYMBOLS: Dict[str, Tuple[str, str]] = {
    "sp_fut": ("ES=F", "S&P 500 futures"),
    "nq_fut": ("NQ=F", "Nasdaq futures"),
    "sp500": ("^GSPC", "S&P 500"),
    "nasdaq": ("^IXIC", "Nasdaq Composite"),
    "dow": ("^DJI", "Dow Jones"),
    "nikkei": ("^N225", "Nikkei 225"),
    "hangseng": ("^HSI", "Hang Seng"),
    "shanghai": ("000001.SS", "Shanghai Composite"),
    "crude": ("CL=F", "Crude oil (WTI)"),
    "brent": ("BZ=F", "Brent crude"),
    "gold": ("GC=F", "Gold"),
    "dxy": ("DX-Y.NYB", "US Dollar Index"),
    "usdinr": ("INR=X", "USD / INR"),
    "vix_india": ("^INDIAVIX", "India VIX"),
}

# NSE gold ETFs. INR gold-ETF price ≈ international gold (USD) × USD/INR,
# so overnight gold-futures + rupee moves drive the next-day gap directly.
GOLD_ETFS: Dict[str, str] = {
    "GOLDBEES.NS": "Nippon India Gold BeES",
    "GOLDIETF.NS": "ICICI Prudential Gold ETF",
    "SETFGOLD.NS": "SBI Gold ETF",
    "AXISGOLD.NS": "Axis Gold ETF",
    "HDFCGOLD.NS": "HDFC Gold ETF",
}

# ADR (US-listed) → NSE ticker. Overnight ADR move = strong next-day gap cue.
ADR_TO_NSE: Dict[str, str] = {
    "INFY": "INFY.NS",
    "WIT": "WIPRO.NS",
    "HDB": "HDFCBANK.NS",
    "IBN": "ICICIBANK.NS",
    "RDY": "DRREDDY.NS",
}

# Sector sensitivity to cues. +ve = cue-up helps the sector.
SECTOR_SENSITIVITY: Dict[str, Dict[str, float]] = {
    "Technology": {"risk": 0.5, "us_tech": 1.0, "inr_weak": 0.5},
    "Communication Services": {"risk": 0.6, "us_tech": 0.4},
    "Financial Services": {"risk": 1.0, "inr_weak": -0.3},
    "Energy": {"risk": 0.4, "crude": 0.9},
    "Utilities": {"risk": 0.3, "crude": -0.2},
    "Basic Materials": {"risk": 0.7, "china": 1.0},
    "Industrials": {"risk": 0.8, "china": 0.3},
    "Consumer Cyclical": {"risk": 0.7, "inr_weak": -0.2},
    "Consumer Defensive": {"risk": -0.2, "gold": 0.1},
    "Healthcare": {"risk": 0.1, "inr_weak": 0.4},
}

_CACHE: Dict[str, object] = {}
_CUE_TTL = 600  # seconds

CACHE_DIR = os.environ.get("CACHE_DIR", "cache")
_UNIV_CACHE_FILE = os.path.join(CACHE_DIR, "universe.json")
_UNIV_TTL = float(os.environ.get("UNIVERSE_TTL_HOURS", 8)) * 3600


def _f(v) -> Optional[float]:
    try:
        import math
        if v is None:
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except (TypeError, ValueError):
        return None


def _last_change(symbol: str) -> Optional[dict]:
    if yf is None:
        return None
    try:
        h = yf.Ticker(symbol).history(period="5d", auto_adjust=True)
        c = h["Close"].dropna()
        if len(c) < 2:
            return None
        last, prev = float(c.iloc[-1]), float(c.iloc[-2])
        return {
            "last": round(last, 2),
            "change_pct": round((last / prev - 1.0) * 100, 2) if prev else None,
        }
    except Exception:  # noqa: BLE001
        return None


def global_cues(force: bool = False) -> Dict[str, dict]:
    """Fetch (and short-cache) the global cue snapshot."""
    now = time.time()
    if not force and _CACHE.get("cues") and (now - float(_CACHE.get("cues_ts", 0)) < _CUE_TTL):
        return _CACHE["cues"]  # type: ignore[return-value]

    out: Dict[str, dict] = {}
    for key, (sym, label) in CUE_SYMBOLS.items():
        d = _last_change(sym)
        if d is not None:
            d["label"] = label
            d["symbol"] = sym
            out[key] = d

    _CACHE["cues"] = out
    _CACHE["cues_ts"] = now
    return out


def gold_etf_outlook(cues: Dict[str, dict]) -> dict:
    """Next-day direction for NSE gold ETFs.

    Indian gold-ETF NAV ≈ international gold (USD) × USD/INR. The overnight
    move in gold futures plus the rupee gives a direct estimate of tomorrow's
    open gap for each ETF.
    """
    gold = cues.get("gold") or {}
    usdinr = cues.get("usdinr") or {}
    dxy = cues.get("dxy") or {}

    gold_chg = gold.get("change_pct")
    inr_chg = usdinr.get("change_pct")   # +ve = rupee weaker → INR gold up

    # Implied INR gold move = USD gold move + rupee depreciation
    implied = 0.0
    have = False
    drivers: List[dict] = []
    if gold_chg is not None:
        implied += gold_chg
        have = True
        drivers.append({"label": "International gold (USD)", "change_pct": gold_chg,
                        "effect": "supports higher" if gold_chg > 0 else "drags lower"})
    if inr_chg is not None:
        implied += inr_chg
        have = True
        drivers.append({"label": "USD/INR (rupee)",
                        "change_pct": inr_chg,
                        "effect": "rupee weaker → lifts INR gold" if inr_chg > 0
                        else "rupee stronger → caps INR gold"})
    if dxy.get("change_pct") is not None:
        drivers.append({"label": "US Dollar Index", "change_pct": dxy["change_pct"],
                        "effect": "context (strong USD usually pressures gold)"})

    implied = round(implied, 2) if have else None

    # Uncertainty band: tracking/discount noise + move-size uncertainty
    band = None
    if implied is not None:
        band = round(max(0.4, 0.25 * abs(implied)), 2)
    lo = round(implied - band, 2) if implied is not None else None
    hi = round(implied + band, 2) if implied is not None else None

    if implied is None:
        direction = "Unknown (no overnight gold/FX data)"
    elif implied > 0.3:
        direction = "Likely to open HIGHER"
    elif implied < -0.3:
        direction = "Likely to open LOWER"
    else:
        direction = "Likely flat at open"

    etfs: List[dict] = []
    for sym, name in GOLD_ETFS.items():
        d = _last_change(sym)
        if not d:
            continue
        last = d.get("last")
        est_lo = round(last * (1 + lo / 100.0), 2) if (last and lo is not None) else None
        est_hi = round(last * (1 + hi / 100.0), 2) if (last and hi is not None) else None
        etfs.append({
            "ticker": sym,
            "name": name,
            "last_close": last,
            "last_change_pct": d.get("change_pct"),
            "implied_next_pct": implied,
            "est_low": est_lo,
            "est_high": est_hi,
        })

    return {
        "direction": direction,
        "implied_move_pct": implied,
        "range_low_pct": lo,
        "range_high_pct": hi,
        "drivers": drivers,
        "etfs": etfs,
        "method": (
            "Estimate = overnight international gold (GC=F) move + USD/INR move. "
            "Indian gold-ETF price tracks gold priced in rupees. A range (not a "
            "point) is shown because ETFs can open at a premium/discount to NAV."
        ),
        "caveat": (
            "Directional estimate only — NOT guaranteed. Gold is volatile and can "
            "reverse on US data, Fed commentary or risk sentiment intraday."
        ),
    }


def _get_universe(force: bool = False) -> List[dict]:
    """Lightweight universe (ticker, name, sector, beta, ret_6m) with caching."""
    now = time.time()
    u = _CACHE.get("universe")
    if not force and u and (now - float(_CACHE.get("universe_ts", 0)) < _UNIV_TTL):
        return u  # type: ignore[return-value]

    if not force:
        try:
            if now - os.path.getmtime(_UNIV_CACHE_FILE) < _UNIV_TTL:
                with open(_UNIV_CACHE_FILE) as fh:
                    data = json.load(fh)
                _CACHE["universe"] = data
                _CACHE["universe_ts"] = now
                return data
        except Exception:  # noqa: BLE001
            pass

    df = fetch_universe(UNIVERSE)
    rows: List[dict] = []
    for _, r in df.iterrows():
        rows.append({
            "ticker": r.get("ticker"),
            "name": r.get("name"),
            "sector": r.get("sector"),
            "beta": _f(r.get("beta")),
            "ret_6m": _f(r.get("ret_6m")),
            "price": _f(r.get("price")),
            "atr_pct": _f(r.get("atr_pct")),
            "adv_value_cr": _f(r.get("adv_value_cr")),
            "next_earnings_days": _f(r.get("next_earnings_days")),
        })
    rows = [x for x in rows if x.get("ticker") and x.get("price")]

    _CACHE["universe"] = rows
    _CACHE["universe_ts"] = now
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_UNIV_CACHE_FILE, "w") as fh:
            json.dump(rows, fh)
    except Exception:  # noqa: BLE001
        pass
    return rows


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def market_bias(cues: Dict[str, dict]) -> dict:
    """Aggregate overnight cues into a 0-100 risk-on score (50 = neutral)."""
    def chg(key: str) -> Optional[float]:
        d = cues.get(key)
        return d.get("change_pct") if d else None

    score = 0.0
    weight = 0.0
    drivers: List[dict] = []

    def add(label: str, value: Optional[float], w: float, invert: bool = False):
        nonlocal score, weight
        if value is None:
            return
        v = -value if invert else value
        score += v * w
        weight += w
        drivers.append({"label": label, "change_pct": value, "effect": round(v * w, 3)})

    add("S&P 500 futures", chg("sp_fut"), 2.0)
    add("Nasdaq futures", chg("nq_fut"), 2.0)
    add("S&P 500 (prev close)", chg("sp500"), 0.8)
    add("Nasdaq (prev close)", chg("nasdaq"), 0.8)
    add("Nikkei 225", chg("nikkei"), 1.0)
    add("Hang Seng", chg("hangseng"), 1.0)
    add("Shanghai", chg("shanghai"), 0.6)
    add("India VIX (inverted)", chg("vix_india"), 0.6, invert=True)
    add("USD/INR (inverted)", chg("usdinr"), 0.6, invert=True)

    avg = (score / weight) if weight else 0.0
    score_100 = round(_clip(50.0 + avg * 23.0, 0.0, 100.0), 1)

    if score_100 >= 65:
        label = "Risk-on — positive open likely"
    elif score_100 >= 55:
        label = "Mildly positive open"
    elif score_100 > 45:
        label = "Flat / mixed open"
    elif score_100 > 35:
        label = "Mildly negative open"
    else:
        label = "Risk-off — weak open likely"

    drivers.sort(key=lambda d: abs(d["effect"]), reverse=True)
    return {"score": score_100, "avg_move_pct": round(avg, 2), "label": label, "drivers": drivers[:6]}


def _cue_group_values(cues: Dict[str, dict]) -> Dict[str, float]:
    def chg(key: str) -> float:
        d = cues.get(key)
        v = d.get("change_pct") if d else None
        return float(v) if v is not None else 0.0

    return {
        "risk": 0.0,
        "us_tech": (chg("nq_fut") + chg("nasdaq")) / 2.0,
        "crude": chg("crude"),
        "china": (chg("hangseng") + chg("shanghai")) / 2.0,
        "inr_weak": chg("usdinr"),
        "gold": chg("gold"),
    }


def stock_next_day_bias(row: dict, cues: Dict[str, dict], bias: dict) -> Optional[dict]:
    """Per-stock next-day directional bias (0-100, 50 = neutral) with risk plan."""
    ticker = row.get("ticker")
    sector = row.get("sector") or ""
    if not ticker:
        return None

    groups = _cue_group_values(cues)
    groups["risk"] = bias.get("avg_move_pct", 0.0)

    sens = SECTOR_SENSITIVITY.get(sector, {"risk": 0.6})
    beta = row.get("beta")
    beta = float(beta) if isinstance(beta, (int, float)) else 1.0
    beta = _clip(beta, 0.4, 2.0)

    reasons: List[str] = []

    tilt = sum(w * groups.get(grp, 0.0) for grp, w in sens.items())
    tilt_beta = tilt * (0.6 + 0.4 * beta)

    ret_6m = row.get("ret_6m")
    mom = _clip(ret_6m * 100 * 0.02, -1.0, 1.0) if isinstance(ret_6m, (int, float)) else 0.0

    net = tilt_beta + mom
    score = round(_clip(50.0 + net * 8.5, 0.0, 100.0), 1)

    contrib = sorted(((grp, w * groups.get(grp, 0.0)) for grp, w in sens.items()),
                     key=lambda x: abs(x[1]), reverse=True)
    label_map = {"risk": "broad market", "us_tech": "US tech", "crude": "crude oil",
                 "china": "China markets", "inr_weak": "rupee", "gold": "gold"}
    for grp, val in contrib[:2]:
        if abs(val) < 0.05:
            continue
        direction = "supportive" if val > 0 else "a headwind"
        reasons.append(f"{label_map.get(grp, grp)} cue {direction} for {sector or 'this name'}")

    if score >= 62:
        verdict = "Strong up bias"
    elif score >= 54:
        verdict = "Lean up"
    elif score > 46:
        verdict = "Flat"
    elif score > 38:
        verdict = "Lean down"
    else:
        verdict = "Down bias"

    # --- Risk plan (ATR-based, intraday) ---
    atr_pct = row.get("atr_pct")
    atr_f = (atr_pct / 100.0) if isinstance(atr_pct, (int, float)) and atr_pct > 0 else 0.015
    price = row.get("price")
    rr = 1.5
    stop_pct = round(atr_f * 100, 2)
    target_pct = round(atr_f * 100 * rr, 2)
    stop_price = round(price * (1 - atr_f), 2) if price else None
    target_price = round(price * (1 + atr_f * rr), 2) if price else None

    # --- Liquidity & confidence ---
    adv = row.get("adv_value_cr")
    earn = row.get("next_earnings_days")
    if adv is not None and adv >= 200 and sector and abs(score - 50) >= 4:
        confidence = "High"
    elif adv is not None and adv >= 50:
        confidence = "Medium"
    else:
        confidence = "Low"
    # Earnings within the window is a gap-risk downgrade
    earnings_warn = isinstance(earn, (int, float)) and 0 <= earn <= 3
    if earnings_warn and confidence == "High":
        confidence = "Medium"
        reasons.append("Earnings due within ~3 days — higher gap risk")

    return {
        "ticker": ticker,
        "name": row.get("name"),
        "sector": sector,
        "score": score,
        "verdict": verdict,
        "confidence": confidence,
        "adv_cr": round(adv, 1) if isinstance(adv, (int, float)) else None,
        "atr_pct": atr_pct if isinstance(atr_pct, (int, float)) else None,
        "stop_pct": stop_pct,
        "target_pct": target_pct,
        "stop_price": stop_price,
        "target_price": target_price,
        "rr": rr,
        "price": price,
        "earnings_warn": bool(earnings_warn),
        "reasons": reasons[:3],
    }


def _yahoo_quote_url(symbol: str) -> str:
    return f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}"


def _sources() -> dict:
    """Every external data feed used to curate the prediction, with links."""
    global_cues = [
        {"label": label, "symbol": sym, "url": _yahoo_quote_url(sym)}
        for key, (sym, label) in CUE_SYMBOLS.items()
    ]
    gold = [
        {"label": name, "symbol": sym, "url": _yahoo_quote_url(sym)}
        for sym, name in GOLD_ETFS.items()
    ]
    return {
        "provider": {"name": "Yahoo Finance", "url": "https://finance.yahoo.com"},
        "global_cues": global_cues,
        "gold_etfs": gold,
        "fundamentals": {
            "label": "Per-stock sector, beta & 6-month return (NSE universe)",
            "note": "Fetched via the yfinance library from Yahoo Finance.",
            "url": "https://finance.yahoo.com",
        },
        "note": (
            "All market data is sourced from Yahoo Finance (delayed/indicative). "
            "GIFT Nifty is not available there, so US index futures are used as "
            "the closest live pre-open proxy."
        ),
    }


_MIN_ADV_CR = float(os.environ.get("MIN_ADV_CR", 25))  # liquidity floor for intraday


def _next_trading_day(now: Optional[_dt.datetime] = None) -> _dt.date:
    """The next NSE session this prediction targets.

    NSE trades Mon-Fri and closes at 15:30 IST. Once today's session is over
    (or it's the weekend) the prediction is for the next weekday; otherwise it
    targets today's upcoming open. Holidays aren't modelled — weekends only.
    """
    now = now or _dt.datetime.now()
    d = now.date()
    # After the session closes, roll to the next calendar day.
    if now.hour > 15 or (now.hour == 15 and now.minute >= 30):
        d = d + _dt.timedelta(days=1)
    # Skip Saturday (5) and Sunday (6).
    while d.weekday() >= 5:
        d = d + _dt.timedelta(days=1)
    return d


def build_premarket(force: bool = False) -> dict:
    """Build the next-day open prediction: stocks most likely to open higher."""
    cues = global_cues(force=force)
    bias = market_bias(cues)
    universe = _get_universe(force=force)

    excluded = set(ADR_TO_NSE.values())  # ADR-linked names hidden by request
    ranked: List[dict] = []
    for row in universe:
        if row.get("ticker") in excluded:
            continue
        adv = row.get("adv_value_cr")
        if adv is not None and adv < _MIN_ADV_CR:
            continue  # too illiquid to trade intraday
        b = stock_next_day_bias(row, cues, bias)
        if b:
            ranked.append(b)
    ranked.sort(key=lambda x: x["score"], reverse=True)

    likely_up = [x for x in ranked if x["score"] >= 54]
    high_conf = [x for x in likely_up if x["confidence"] == "High"][:10]
    watchlist = [x for x in likely_up if x["confidence"] != "High"][:10]

    def cue_card(key: str) -> Optional[dict]:
        d = cues.get(key)
        if not d:
            return None
        return {"label": d.get("label"), "change_pct": d.get("change_pct"), "last": d.get("last")}

    cue_strip = [c for c in (
        cue_card("sp_fut"), cue_card("nq_fut"), cue_card("nikkei"),
        cue_card("hangseng"), cue_card("crude"), cue_card("gold"),
        cue_card("usdinr"), cue_card("vix_india"),
    ) if c]

    predict_for = _next_trading_day()
    return {
        "as_of": time.strftime("%Y-%m-%d %H:%M IST", time.localtime()),
        "predict_for": predict_for.strftime("%Y-%m-%d"),
        "predict_for_label": predict_for.strftime("%a, %d %b %Y"),
        "market_bias": bias,
        "cue_strip": cue_strip,
        "gift_nifty_note": (
            "GIFT Nifty isn't available from this data source; US index futures "
            "(S&P / Nasdaq) are used as the closest live pre-open proxy."
        ),
        "high_confidence": high_conf,
        "watchlist": watchlist,
        "liquidity_floor_cr": _MIN_ADV_CR,
        "gold_etf": gold_etf_outlook(cues),
        "validation": run_backtest(force=force),
        "sources": _sources(),
        "disclaimer": (
            "Educational pre-open prediction from overnight global cues — NOT a "
            "guarantee. No stock is 'sure' to rise. Opening gaps can reverse "
            "within minutes; intraday trading carries a high risk of loss. "
            "Always use the stop-loss shown."
        ),
    }
