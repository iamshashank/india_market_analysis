"""Discovery-inflection signal — "hidden, but waking up".

Multibaggers often re-rate when an overlooked, fundamentally sound company
*starts* getting noticed. This signal blends three things:

  * **hidden**  — still under-covered (few analysts / little news / low inst.),
  * **waking**  — attention is rising now: news *velocity* (acceleration, not
    just count), a volume pickup vs its own base, and price breaking toward
    its 52-week high / above the 200-DMA,
  * **sound**   — only counts if the business quality/consistency is decent
    (so we catch real compounders being discovered, not pumps).

The full strength of "hidden vs *previously* hidden" sharpens as the
point-in-time moat (``core.data_cache`` / ``core.score_history``) accumulates;
this version already works on current data (news dates + volume + price).

Returns: {"score": 0-100, "waking": 0-100, "label": str}.
"""

from __future__ import annotations

from typing import Optional


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def assess(row: dict, news: dict, under_covered: float,
           quality: float, consistency: float) -> dict:
    news = news or {}

    # hidden: reuse the under-covered pillar (low analysts + little news + low inst.)
    hidden = under_covered if isinstance(under_covered, (int, float)) else 50.0

    # waking: attention + volume + price breakout, each 0-100
    waking_parts: list[float] = []
    vel = news.get("velocity")
    if isinstance(vel, (int, float)):
        waking_parts.append(_clip(50 + (vel - 1.0) * 50, 0, 100))
    vt = row.get("vol_trend")
    if isinstance(vt, (int, float)):
        waking_parts.append(_clip(50 + (vt - 1.0) * 60, 0, 100))
    near_high = row.get("pct_of_52w_high")
    if isinstance(near_high, (int, float)):
        waking_parts.append(_clip(near_high * 100, 0, 100))
    above_dma = row.get("above_200dma")
    if isinstance(above_dma, (int, float)):
        waking_parts.append(_clip(50 + above_dma * 120, 0, 100))
    waking = sum(waking_parts) / len(waking_parts) if waking_parts else 50.0

    # sound: gate on business quality (don't reward pumps in junk)
    sound = ((quality if isinstance(quality, (int, float)) else 50.0)
             + (consistency if isinstance(consistency, (int, float)) else 50.0)) / 2.0

    score = 0.40 * hidden + 0.40 * waking + 0.20 * sound
    label = ("Inflecting" if score >= 68 else "Stirring" if score >= 55 else "Quiet")
    return {"score": round(score, 1), "waking": round(waking, 1), "label": label}
