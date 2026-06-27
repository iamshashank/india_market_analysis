"""Central configuration for the multibagger screener.

Everything tunable lives here so the strategy is explainable and reproducible.
All values can be overridden by environment variables for deployment.
"""

from __future__ import annotations

import os


def _f(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _i(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


# ---- Multibagger composite weights (must roughly sum to 1.0) -------------
# Each pillar is percentile-ranked within the universe, then weighted.
WEIGHTS = {
    "room_to_grow": _f("W_ROOM_TO_GROW", 0.16),   # size-relative headroom WITHIN the cap tier
    "consistency": _f("W_CONSISTENCY", 0.20),   # criterion 2: low earnings volatility, rising
    "under_covered": _f("W_UNDER_COVERED", 0.15),  # criterion 3: hidden / low coverage
    "growth": _f("W_GROWTH", 0.16),             # revenue / earnings growth runway
    "quality": _f("W_QUALITY", 0.15),           # ROE, margins, low debt, FCF
    "valuation": _f("W_VALUATION", 0.08),       # not absurdly expensive (PEG/PB)
    "catalyst": _f("W_CATALYST", 0.10),         # news / event momentum
}

# ---- Market-cap tiers (per market) ---------------------------------------
# Scoring is now SIZE-NEUTRAL: instead of penalising large caps, we bucket each
# stock into a cap tier and rank "room to grow" WITHIN its tier. Thresholds are
# upper bounds in USD (a name belongs to the first tier whose ceiling it's under).
# India uses 3 tiers; US uses 5. Edit freely.
CAP_TIERS = {
    "IN": [
        ("Small", 3e9),       # < ~₹25,000 cr
        ("Mid", 12e9),        # ~₹25k–1,00,000 cr
        ("Large", float("inf")),
    ],
    "US": [
        ("Micro", 3e8),       # < $300M
        ("Small", 2e9),       # $300M–2B
        ("Mid", 10e9),        # $2B–10B
        ("Large", 2e11),      # $10B–200B
        ("Mega", float("inf")),  # > $200B
    ],
    "BSE": [
        ("Small", 3e9),
        ("Mid", 12e9),
        ("Large", float("inf")),
    ],
}

# Absolute lower bound to be screenable at all (filters listed-but-dead shells).
MIN_CAP_USD = _f("MIN_CAP_USD", 25e6)

# ---- Liquidity floor (average daily traded value, USD) -------------------
MIN_ADV_USD = _f("MIN_ADV_USD", 3e5)   # ~$300k/day so a position can be built

# ---- Portfolio construction (criterion 4: conviction + concentration) ----
PORTFOLIO_SIZE = _i("PORTFOLIO_SIZE", 7)      # number of high-conviction names
MAX_WEIGHT_PCT = _f("MAX_WEIGHT_PCT", 25.0)   # cap any single name
MIN_WEIGHT_PCT = _f("MIN_WEIGHT_PCT", 5.0)    # floor so it stays meaningful
MAX_PER_SECTOR = _i("MAX_PER_SECTOR", 3)      # diversification guardrail
MIN_SCORE = _f("MIN_SCORE", 55.0)             # don't include weak ideas

# ---- Coverage thresholds (criterion 3) -----------------------------------
LOW_ANALYST_COUNT = _i("LOW_ANALYST_COUNT", 6)   # <= this = under-covered
LOW_NEWS_COUNT = _i("LOW_NEWS_COUNT", 3)         # few recent headlines = hidden

# ---- Runtime / caching ---------------------------------------------------
CACHE_DIR = os.environ.get("CACHE_DIR", "cache")
SCREEN_TTL_HOURS = _f("SCREEN_TTL_HOURS", 12.0)
FETCH_WORKERS = _i("FETCH_WORKERS", 6)
INCLUDE_NEWS = os.environ.get("INCLUDE_NEWS", "1") not in ("0", "false", "False")

# Approx USD per 1 unit of local currency, for cross-market cap comparison.
# Coarse on purpose (only used to bucket "small base"); refine via env if needed.
USD_PER = {
    "IN": _f("USD_PER_INR", 1.0 / 86.0),
    "BSE": _f("USD_PER_INR", 1.0 / 86.0),
    "US": 1.0,
}

def cap_tier(market: str, cap_usd) -> str:
    """Return the cap-tier name for a market + USD market cap."""
    if not isinstance(cap_usd, (int, float)) or cap_usd <= 0:
        return "Unknown"
    tiers = CAP_TIERS.get(market) or CAP_TIERS["US"]
    for name, ceil in tiers:
        if cap_usd < ceil:
            return name
    return tiers[-1][0]


DISCLAIMER = (
    "Educational research tool — NOT investment advice. This is an automated, "
    "rules-based screen of public data (Yahoo Finance). Small-cap and "
    "low-coverage stocks are illiquid and high-risk; you can lose money. "
    "Do your own research and consult a SEBI/SEC-registered adviser."
)
