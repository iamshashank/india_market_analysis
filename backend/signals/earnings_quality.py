"""Earnings-consistency scoring (criterion 2).

The thesis: durable wealth comes from businesses whose earnings compound
*steadily*, not ones that lurch up and down each quarter. We reward:

  * low volatility of the quarterly series (small coefficient of variation),
  * a positive trend (earnings rising over time),
  * few/no negative quarters (consistently profitable).

Works on whatever quarterly history yfinance gives us (typically 4-8 quarters).
Returns a 0-100 consistency score plus transparent components, so a name with
"small but steadily rising" earnings beats one with "big but erratic" earnings.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _trend_slope(vals: List[float]) -> Optional[float]:
    """Normalised slope of oldest->newest series (per-quarter growth fraction)."""
    n = len(vals)
    if n < 3:
        return None
    series = list(reversed(vals))  # oldest first
    x = np.arange(n, dtype=float)
    y = np.array(series, dtype=float)
    denom = np.mean(np.abs(y))
    if denom == 0:
        return None
    slope = np.polyfit(x, y, 1)[0]
    return float(slope / denom)


def _cv(vals: List[float]) -> Optional[float]:
    """Coefficient of variation on the magnitudes (lower = steadier)."""
    if len(vals) < 3:
        return None
    arr = np.array(vals, dtype=float)
    mean_abs = np.mean(np.abs(arr))
    if mean_abs == 0:
        return None
    return float(np.std(arr) / mean_abs)


def consistency(quarterly_ni: List[float],
                quarterly_rev: List[float]) -> Tuple[Optional[float], dict]:
    """Return (score 0-100 or None, detail dict).

    Blends net-income steadiness (primary) with revenue steadiness (secondary).
    None when we simply don't have enough history to judge.
    """
    detail: dict = {"quarters": len(quarterly_ni), "components": {}}

    if len(quarterly_ni) < 3:
        return None, {**detail, "reason": "insufficient quarterly history"}

    ni = quarterly_ni
    cv_ni = _cv(ni)
    slope_ni = _trend_slope(ni)
    neg_share = sum(1 for v in ni if v < 0) / len(ni)

    # 1) steadiness from CV: cv 0 -> 100, cv >= 1.0 -> ~0
    if cv_ni is None:
        steady = 50.0
    else:
        steady = _clip(100.0 * (1.0 - _clip(cv_ni, 0.0, 1.2) / 1.2), 0.0, 100.0)

    # 2) trend: rising earnings rewarded, falling penalised (centered at 50)
    if slope_ni is None:
        trend = 50.0
    else:
        trend = _clip(50.0 + slope_ni * 220.0, 0.0, 100.0)

    # 3) profitability consistency: penalise loss-making quarters hard
    profit = _clip(100.0 * (1.0 - neg_share), 0.0, 100.0)

    # revenue steadiness as a lighter confirmation
    cv_rev = _cv(quarterly_rev) if len(quarterly_rev) >= 3 else None
    rev_steady = (_clip(100.0 * (1.0 - _clip(cv_rev, 0.0, 0.8) / 0.8), 0.0, 100.0)
                  if cv_rev is not None else None)

    parts = [(steady, 0.40), (trend, 0.30), (profit, 0.20)]
    if rev_steady is not None:
        parts.append((rev_steady, 0.10))
    wsum = sum(w for _, w in parts)
    score = sum(v * w for v, w in parts) / wsum

    detail["components"] = {
        "cv_net_income": round(cv_ni, 3) if cv_ni is not None else None,
        "trend_per_q": round(slope_ni, 3) if slope_ni is not None else None,
        "negative_quarter_share": round(neg_share, 2),
        "steadiness_score": round(steady, 1),
        "trend_score": round(trend, 1),
        "profitability_score": round(profit, 1),
        "revenue_steadiness_score": round(rev_steady, 1) if rev_steady is not None else None,
    }
    return round(score, 1), detail


def label(score: Optional[float]) -> str:
    if score is None:
        return "Unknown (limited history)"
    if score >= 75:
        return "Very consistent compounder"
    if score >= 60:
        return "Consistent / rising"
    if score >= 45:
        return "Mixed"
    return "Erratic earnings"
