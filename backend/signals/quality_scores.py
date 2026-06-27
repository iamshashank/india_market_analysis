"""Battle-tested fundamental scores, computed from the financial statements.

  * Piotroski F-Score (0-9)  — financial-strength checklist.
  * Altman Z-Score           — bankruptcy / distress risk.
  * Graham Number            — Benjamin Graham's fair-value ceiling.
  * Magic Formula (Greenblatt) — earnings yield + return on capital.
  * Beneish M-Score          — earnings-manipulation flag (best-effort).

All are explainable (stated formulas/checks) and degrade gracefully: when the
required line items aren't reported, the score returns None instead of guessing.
Inputs are the raw yfinance statement DataFrames + the ``info`` dict.
"""

from __future__ import annotations

import math
from typing import List, Optional


def _cols(df):
    if df is None or getattr(df, "empty", True):
        return []
    try:
        return sorted(list(df.columns), reverse=True)
    except Exception:  # noqa: BLE001
        return list(df.columns)


def _get(df, cols, names: List[str], i: int = 0) -> Optional[float]:
    if df is None or getattr(df, "empty", True) or i >= len(cols):
        return None
    low = {str(ix).strip().lower(): ix for ix in df.index}
    for n in names:
        ix = low.get(n.strip().lower())
        if ix is not None:
            try:
                v = float(df.loc[ix, cols[i]])
                if not (math.isnan(v) or math.isinf(v)):
                    return v
            except (TypeError, ValueError):
                continue
    return None


NI = ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"]
TA = ["Total Assets"]
OCF = ["Operating Cash Flow", "Total Cash From Operating Activities",
       "Cash Flow From Continuing Operating Activities"]
LTD = ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]
CA = ["Current Assets", "Total Current Assets"]
CL = ["Current Liabilities", "Total Current Liabilities"]
SHARES = ["Share Issued", "Ordinary Shares Number", "Common Stock Shares Outstanding"]
GP = ["Gross Profit"]
REV = ["Total Revenue", "Operating Revenue"]
RE = ["Retained Earnings"]
EBIT = ["EBIT", "Operating Income", "Total Operating Income As Reported"]
TL = ["Total Liabilities Net Minority Interest", "Total Liabilities"]
PPE = ["Net PPE", "Net Property Plant And Equipment", "Property Plant And Equipment Net"]


def _piotroski(inc, bal, cf) -> Optional[dict]:
    ci, cb, cc = _cols(inc), _cols(bal), _cols(cf)
    ni0 = _get(inc, ci, NI, 0); ta0 = _get(bal, cb, TA, 0); ta1 = _get(bal, cb, TA, 1)
    ocf0 = _get(cf, cc, OCF, 0)
    if ni0 is None or ta0 is None or not ta0 or ocf0 is None:
        return None
    roa0 = ni0 / ta0
    checks = {}
    pts = 0
    # profitability
    checks["positive_roa"] = roa0 > 0; pts += checks["positive_roa"]
    checks["positive_ocf"] = ocf0 > 0; pts += checks["positive_ocf"]
    checks["ocf_gt_ni"] = ocf0 > ni0; pts += checks["ocf_gt_ni"]
    # comparative (needs prior year)
    ni1 = _get(inc, ci, NI, 1)
    roa1 = (ni1 / ta1) if (ni1 is not None and ta1) else None
    if roa1 is not None:
        checks["rising_roa"] = roa0 > roa1; pts += checks["rising_roa"]
    ltd0 = _get(bal, cb, LTD, 0); ltd1 = _get(bal, cb, LTD, 1)
    if ltd0 is not None and ltd1 is not None and ta0 and ta1:
        checks["lower_leverage"] = (ltd0 / ta0) < (ltd1 / ta1); pts += checks["lower_leverage"]
    ca0 = _get(bal, cb, CA, 0); cl0 = _get(bal, cb, CL, 0)
    ca1 = _get(bal, cb, CA, 1); cl1 = _get(bal, cb, CL, 1)
    if all(x is not None and x for x in (cl0, cl1)) and ca0 is not None and ca1 is not None:
        checks["higher_current_ratio"] = (ca0 / cl0) > (ca1 / cl1); pts += checks["higher_current_ratio"]
    sh0 = _get(bal, cb, SHARES, 0); sh1 = _get(bal, cb, SHARES, 1)
    if sh0 is not None and sh1 is not None:
        checks["no_dilution"] = sh0 <= sh1 * 1.01; pts += checks["no_dilution"]
    gp0 = _get(inc, ci, GP, 0); gp1 = _get(inc, ci, GP, 1)
    rev0 = _get(inc, ci, REV, 0); rev1 = _get(inc, ci, REV, 1)
    if all(x is not None and x for x in (rev0, rev1)) and gp0 is not None and gp1 is not None:
        checks["higher_gross_margin"] = (gp0 / rev0) > (gp1 / rev1); pts += checks["higher_gross_margin"]
    if all(x is not None and x for x in (ta0, ta1, rev0, rev1)):
        checks["higher_asset_turnover"] = (rev0 / ta0) > (rev1 / ta1); pts += checks["higher_asset_turnover"]

    max_pts = len(checks)
    label = "Strong" if pts >= 7 else "Moderate" if pts >= 4 else "Weak"
    return {"score": int(pts), "max": max_pts, "label": label,
            "checks": {k: bool(v) for k, v in checks.items()}}


def _altman_z(inc, bal, info) -> Optional[dict]:
    cb, ci = _cols(bal), _cols(inc)
    ta = _get(bal, cb, TA, 0)
    if not ta:
        return None
    ca = _get(bal, cb, CA, 0); cl = _get(bal, cb, CL, 0)
    re = _get(bal, cb, RE, 0); ebit = _get(inc, ci, EBIT, 0)
    tl = _get(bal, cb, TL, 0); rev = _get(inc, ci, REV, 0)
    mcap = info.get("marketCap")
    wc = (ca - cl) if (ca is not None and cl is not None) else None
    parts = []
    if wc is not None: parts.append(1.2 * wc / ta)
    if re is not None: parts.append(1.4 * re / ta)
    if ebit is not None: parts.append(3.3 * ebit / ta)
    if mcap and tl: parts.append(0.6 * mcap / tl)
    if rev is not None: parts.append(1.0 * rev / ta)
    if len(parts) < 4:
        return None
    z = round(sum(parts), 2)
    zone = "Safe" if z > 2.99 else "Grey" if z >= 1.81 else "Distress"
    return {"value": z, "zone": zone}


def _graham(info, price) -> Optional[dict]:
    eps = info.get("trailingEps"); bvps = info.get("bookValue")
    if not isinstance(eps, (int, float)) or not isinstance(bvps, (int, float)):
        return None
    if eps <= 0 or bvps <= 0:
        return None
    num = round(math.sqrt(22.5 * eps * bvps), 2)
    out = {"number": num}
    if isinstance(price, (int, float)) and price:
        out["price"] = round(price, 2)
        out["upside_pct"] = round((num / price - 1) * 100, 1)
        out["verdict"] = "Below Graham number — margin of safety" if price < num else "Above Graham number — no margin of safety"
    return out


def _magic_formula(inc, info) -> Optional[dict]:
    ci = _cols(inc)
    ebit = _get(inc, ci, EBIT, 0)
    ev = info.get("enterpriseValue")
    out = {}
    if isinstance(ebit, (int, float)) and isinstance(ev, (int, float)) and ev:
        out["earnings_yield_pct"] = round(ebit / ev * 100, 1)
    roic = info.get("returnOnAssets")
    if isinstance(roic, (int, float)):
        out["roc_pct"] = round(roic * 100, 1)
    return out or None


def _beneish_m(inc, bal, cf) -> Optional[dict]:
    ci, cb, cc = _cols(inc), _cols(bal), _cols(cf)
    if len(ci) < 2 or len(cb) < 2:
        return None
    REC = ["Receivables", "Accounts Receivable", "Net Receivables"]
    COGS = ["Cost Of Revenue", "Cost Of Goods Sold", "Reconciled Cost Of Revenue"]
    DEP = ["Reconciled Depreciation", "Depreciation And Amortization", "Depreciation"]
    SGA = ["Selling General And Administration", "Selling General Administrative"]
    rev0, rev1 = _get(inc, ci, REV, 0), _get(inc, ci, REV, 1)
    rec0, rec1 = _get(bal, cb, REC, 0), _get(bal, cb, REC, 1)
    ta0, ta1 = _get(bal, cb, TA, 0), _get(bal, cb, TA, 1)
    gp0, gp1 = _get(inc, ci, GP, 0), _get(inc, ci, GP, 1)
    ni0 = _get(inc, ci, NI, 0); ocf0 = _get(cf, cc, OCF, 0)
    if None in (rev0, rev1, rec0, rec1, ta0, ta1, gp0, gp1) or not rev0 or not rev1 or not ta0:
        return None
    try:
        dsri = (rec0 / rev0) / (rec1 / rev1)
        gmi = (gp1 / rev1) / (gp0 / rev0)
        sgi = rev0 / rev1
        tata = ((ni0 - ocf0) / ta0) if (ni0 is not None and ocf0 is not None) else 0.0
        # simplified 4-factor Beneish (AQI/DEPI/SGAI/LVGI ≈ 1 when unavailable)
        m = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.892 * sgi + 4.679 * tata)
        m = round(m, 2)
        flag = "Elevated manipulation risk" if m > -1.78 else "Low manipulation risk"
        return {"value": m, "flag": flag, "approx": True}
    except Exception:  # noqa: BLE001
        return None


def compute(inc, bal, cf, info: dict, price) -> dict:
    info = info or {}
    return {
        "piotroski": _piotroski(inc, bal, cf),
        "altman_z": _altman_z(inc, bal, info),
        "graham": _graham(info, price),
        "magic_formula": _magic_formula(inc, info),
        "beneish_m": _beneish_m(inc, bal, cf),
    }
