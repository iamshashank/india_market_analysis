"""Financial-health / forensic gate (criterion: clean books + sound balance sheet).

A fast, statement-light health score computed from fields we already fetch in
``data.fundamentals.fetch_one`` (no extra API calls), so it runs on every
screened name. It captures the *safety* dimension that the percentile pillars
miss — liquidity, leverage, cash-backed earnings (accruals) and distress — and
raises red flags that down-rank value traps and possible manipulation.

The *full* forensic suite (Piotroski F, Altman Z, Beneish M) needs the complete
financial statements and stays in ``data.fundamentals.fetch_full`` (the drill-
down dialog). This gate is the always-on, lightweight complement.

Returns: {"score": 0-100 | None, "label": str, "flags": [str]}.
"""

from __future__ import annotations

from typing import Optional


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def assess(row: dict) -> dict:
    d2e = row.get("debt_to_equity")
    cr = row.get("current_ratio")
    roa = row.get("return_on_assets")
    pm = row.get("profit_margin")
    fcfm = row.get("fcf_margin")
    ocf = row.get("operating_cashflow")
    ni = row.get("net_income")

    parts: list[tuple[float, float]] = []   # (sub-score 0-100, weight)
    flags: list[str] = []

    # liquidity — current ratio (≈2 healthy, <1 a worry)
    if isinstance(cr, (int, float)):
        parts.append((_clip(50 + (cr - 1.0) * 40, 0, 100), 0.18))
        if cr < 1.0:
            flags.append("Weak liquidity (current ratio < 1)")

    # leverage — debt/equity (lower better)
    if isinstance(d2e, (int, float)):
        parts.append((_clip(100 - d2e * 45, 0, 100), 0.22))
        if d2e > 1.5:
            flags.append(f"High leverage (D/E ~{d2e:.1f})")

    # profitability
    if isinstance(pm, (int, float)):
        parts.append((_clip(50 + pm * 250, 0, 100), 0.18))
        if pm < 0:
            flags.append("Loss-making (negative net margin)")
    if isinstance(roa, (int, float)):
        parts.append((_clip(50 + roa * 300, 0, 100), 0.12))

    # cash quality — free cash flow + accruals (OCF vs reported earnings)
    if isinstance(fcfm, (int, float)):
        parts.append((_clip(50 + fcfm * 250, 0, 100), 0.15))
        if fcfm < 0:
            flags.append("Negative free cash flow")
    if isinstance(ocf, (int, float)) and isinstance(ni, (int, float)) and ni != 0:
        ratio = (ocf / ni) if ni > 0 else (1.0 if ocf > 0 else 0.0)
        parts.append((_clip(ratio * 70, 0, 100), 0.15))
        if ni > 0 and ocf < 0.5 * ni:
            flags.append("Low cash conversion (earnings not backed by cash)")

    if not parts:
        return {"score": None, "label": "Unknown", "flags": []}

    wsum = sum(w for _, w in parts)
    score = sum(s * w for s, w in parts) / wsum
    label = ("Strong" if score >= 70 else "Sound" if score >= 55
             else "Watch" if score >= 40 else "Distress")
    return {"score": round(score, 1), "label": label, "flags": flags}
