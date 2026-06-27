"""Fetch rich fundamentals + technicals for the multibagger screen.

For each ticker we pull (best-effort, never fatal):
  * size & price: market cap (converted to USD), price, liquidity
  * quality: ROE, margins, debt/equity, free cash flow
  * growth: revenue & earnings growth
  * valuation: trailing/forward P/E, PEG, P/B
  * coverage: number of analyst opinions, institutional holding
  * a quarterly Net-Income and Revenue series (for earnings-consistency scoring)

Uses yfinance. Every network call is wrapped so one bad ticker can't abort the
whole batch.
"""

from __future__ import annotations

import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError as exc:  # pragma: no cover
    raise SystemExit("yfinance is required: pip install -r requirements.txt") from exc

from core.config import FETCH_WORKERS, USD_PER
from data.universe import UNIVERSE


@dataclass
class Fundamentals:
    ticker: str
    name: str
    market: str = "US"
    currency: str = "USD"
    sector: Optional[str] = None
    industry: Optional[str] = None
    price: Optional[float] = None
    market_cap_usd: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    peg: Optional[float] = None
    price_to_book: Optional[float] = None
    roe: Optional[float] = None
    gross_margin: Optional[float] = None
    profit_margin: Optional[float] = None
    debt_to_equity: Optional[float] = None
    fcf_margin: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    num_analysts: Optional[int] = None
    inst_hold_pct: Optional[float] = None
    avg_volume: Optional[float] = None
    adv_value_usd: Optional[float] = None
    ret_6m: Optional[float] = None
    ret_1y: Optional[float] = None
    above_200dma: Optional[float] = None
    pct_of_52w_high: Optional[float] = None
    quarterly_ni: List[float] = field(default_factory=list)   # newest first
    quarterly_rev: List[float] = field(default_factory=list)  # newest first
    error: Optional[str] = None


def _safe(info: dict, key: str):
    val = info.get(key)
    if val in (None, "", "Infinity", float("inf")):
        return None
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return val


def _series_from(df: Optional[pd.DataFrame], names: List[str], limit: int = 8) -> List[float]:
    """Pull the first matching row from a financial statement as a clean list
    (newest period first), tolerant of yfinance label variations."""
    if df is None or getattr(df, "empty", True):
        return []
    idx_lower = {str(i).strip().lower(): i for i in df.index}
    row = None
    for cand in names:
        key = cand.strip().lower()
        if key in idx_lower:
            row = df.loc[idx_lower[key]]
            break
    if row is None:
        return []
    try:
        # columns are period-end dates; sort newest-first
        s = row.sort_index(ascending=False)
        vals = [float(x) for x in s.tolist() if x is not None and not pd.isna(x)]
        return vals[:limit]
    except Exception:  # noqa: BLE001
        return []


def _technicals(hist: pd.DataFrame) -> Dict[str, Optional[float]]:
    out = {"ret_6m": None, "ret_1y": None, "above_200dma": None, "pct_of_52w_high": None}
    if hist is None or hist.empty or "Close" not in hist:
        return out
    close = hist["Close"].dropna()
    if close.empty:
        return out
    last = float(close.iloc[-1])
    if len(close) > 126:
        ref = float(close.iloc[-127])
        if ref > 0:
            out["ret_6m"] = last / ref - 1.0
    if len(close) > 1:
        ref = float(close.iloc[0])
        if ref > 0:
            out["ret_1y"] = last / ref - 1.0
    if len(close) >= 200:
        dma = float(close.tail(200).mean())
        if dma > 0:
            out["above_200dma"] = last / dma - 1.0
    hi = float(close.tail(252).max()) if len(close) else None
    if hi and hi > 0:
        out["pct_of_52w_high"] = last / hi
    return out


def fetch_one(ticker: str, meta: dict, retries: int = 1) -> Fundamentals:
    name = meta.get("name", ticker)
    market = meta.get("market", "US")
    currency = meta.get("currency", "USD")
    fx = USD_PER.get(market, 1.0)
    last_err = None
    import time as _t

    for attempt in range(retries + 1):
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}
            hist = tk.history(period="1y", auto_adjust=True)
            tech = _technicals(hist)

            price = _safe(info, "currentPrice") or _safe(info, "regularMarketPrice")
            if price is None and hist is not None and not hist.empty:
                price = float(hist["Close"].dropna().iloc[-1])

            cap = _safe(info, "marketCap")
            market_cap_usd = cap * fx if isinstance(cap, (int, float)) else None

            d2e = _safe(info, "debtToEquity")
            if isinstance(d2e, (int, float)) and d2e and d2e > 5:
                d2e = d2e / 100.0

            avg_vol = (_safe(info, "averageVolume")
                       or _safe(info, "averageDailyVolume3Month")
                       or _safe(info, "averageDailyVolume10Day"))
            adv_usd = None
            if avg_vol and price:
                adv_usd = avg_vol * price * fx

            rev = _safe(info, "totalRevenue")
            fcf = _safe(info, "freeCashflow")
            fcf_margin = (fcf / rev) if (isinstance(fcf, (int, float))
                                         and isinstance(rev, (int, float)) and rev) else None

            # quarterly series for earnings-consistency scoring
            q_inc = None
            try:
                q_inc = tk.quarterly_income_stmt
            except Exception:  # noqa: BLE001
                q_inc = None
            if q_inc is None or getattr(q_inc, "empty", True):
                try:
                    q_inc = tk.quarterly_financials
                except Exception:  # noqa: BLE001
                    q_inc = None
            quarterly_ni = _series_from(q_inc, ["Net Income", "Net Income Common Stockholders",
                                                "NetIncome"])
            quarterly_rev = _series_from(q_inc, ["Total Revenue", "Operating Revenue",
                                                 "TotalRevenue"])

            return Fundamentals(
                ticker=ticker, name=name, market=market, currency=currency,
                sector=info.get("sector"), industry=info.get("industry"),
                price=price, market_cap_usd=market_cap_usd,
                trailing_pe=_safe(info, "trailingPE"), forward_pe=_safe(info, "forwardPE"),
                peg=_safe(info, "trailingPegRatio") or _safe(info, "pegRatio"),
                price_to_book=_safe(info, "priceToBook"),
                roe=_safe(info, "returnOnEquity"),
                gross_margin=_safe(info, "grossMargins"),
                profit_margin=_safe(info, "profitMargins"),
                debt_to_equity=d2e, fcf_margin=fcf_margin,
                revenue_growth=_safe(info, "revenueGrowth"),
                earnings_growth=_safe(info, "earningsGrowth")
                or _safe(info, "earningsQuarterlyGrowth"),
                num_analysts=int(_safe(info, "numberOfAnalystOpinions"))
                if _safe(info, "numberOfAnalystOpinions") is not None else None,
                inst_hold_pct=_safe(info, "heldPercentInstitutions"),
                avg_volume=avg_vol, adv_value_usd=adv_usd,
                ret_6m=tech["ret_6m"], ret_1y=tech["ret_1y"],
                above_200dma=tech["above_200dma"], pct_of_52w_high=tech["pct_of_52w_high"],
                quarterly_ni=quarterly_ni, quarterly_rev=quarterly_rev,
            )
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            _t.sleep(1.0 + attempt)
    return Fundamentals(ticker=ticker, name=name, market=market, currency=currency,
                        error=last_err or "fetch failed")


def fetch_universe(universe: Optional[Dict[str, dict]] = None,
                   workers: int = FETCH_WORKERS) -> List[dict]:
    universe = universe or UNIVERSE
    total = len(universe)
    rows: List[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fetch_one, tk, meta): tk for tk, meta in universe.items()}
        for fut in as_completed(futs):
            tk = futs[fut]
            done += 1
            try:
                f = fut.result()
            except Exception as exc:  # noqa: BLE001
                f = Fundamentals(ticker=tk, name=tk, error=str(exc))
            flag = "" if not f.error else "  (FAILED)"
            print(f"  [{done:>2}/{total}] {tk:<16}{flag}")
            rows.append(asdict(f))
    return rows


# ---------------------------------------------------------------------------
# Comprehensive per-stock fundamentals (on-demand drill-down)
# ---------------------------------------------------------------------------

# (info key, label, kind) — kind drives frontend formatting.
# kinds: money (large currency), price (per-share), pct (fraction), ratio
_RATIO_SPEC = [
    ("marketCap", "Market Cap", "money"),
    ("enterpriseValue", "Enterprise Value", "money"),
    ("trailingPE", "P/E (TTM)", "ratio"),
    ("forwardPE", "Forward P/E", "ratio"),
    ("__peg__", "PEG Ratio", "ratio"),
    ("priceToBook", "P/B Ratio", "ratio"),
    ("priceToSalesTrailing12Months", "Price/Sales (TTM)", "ratio"),
    ("enterpriseToEbitda", "EV/EBITDA", "ratio"),
    ("enterpriseToRevenue", "EV/Revenue", "ratio"),
    ("trailingEps", "EPS (TTM)", "price"),
    ("forwardEps", "Forward EPS", "price"),
    ("bookValue", "Book Value / Share", "price"),
    ("__divyield__", "Dividend Yield", "pct"),
    ("payoutRatio", "Payout Ratio", "pct"),
    ("returnOnEquity", "ROE", "pct"),
    ("returnOnAssets", "ROA", "pct"),
    ("grossMargins", "Gross Margin", "pct"),
    ("operatingMargins", "Operating Margin", "pct"),
    ("profitMargins", "Net Profit Margin", "pct"),
    ("ebitdaMargins", "EBITDA Margin", "pct"),
    ("__d2e__", "Debt to Equity", "ratio"),
    ("currentRatio", "Current Ratio", "ratio"),
    ("quickRatio", "Quick Ratio", "ratio"),
    ("totalRevenue", "Revenue (TTM)", "money"),
    ("ebitda", "EBITDA", "money"),
    ("netIncomeToCommon", "Net Income", "money"),
    ("totalCash", "Total Cash", "money"),
    ("totalDebt", "Total Debt", "money"),
    ("operatingCashflow", "Operating Cash Flow", "money"),
    ("freeCashflow", "Free Cash Flow", "money"),
    ("revenueGrowth", "Revenue Growth (YoY)", "pct"),
    ("earningsGrowth", "Earnings Growth (YoY)", "pct"),
    ("beta", "Beta", "ratio"),
    ("fiftyTwoWeekHigh", "52-Week High", "price"),
    ("fiftyTwoWeekLow", "52-Week Low", "price"),
]


def _divyield(info: dict, price) -> Optional[float]:
    dy = _safe(info, "trailingAnnualDividendYield")
    if isinstance(dy, (int, float)):
        return dy
    rate = _safe(info, "dividendRate")
    if isinstance(rate, (int, float)) and rate and price:
        return rate / price
    raw = _safe(info, "dividendYield")
    if isinstance(raw, (int, float)) and raw:
        return raw / 100.0 if raw > 1 else raw
    return None


def _stmt_to_dict(df, max_periods: int = 6, max_rows: int = 50) -> Optional[dict]:
    if df is None or getattr(df, "empty", True):
        return None
    try:
        cols = sorted(list(df.columns), reverse=True)[:max_periods]
    except Exception:  # noqa: BLE001
        cols = list(df.columns)[:max_periods]
    periods = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c)[:10] for c in cols]
    rows = []
    for idx in list(df.index)[:max_rows]:
        vals = []
        for c in cols:
            try:
                f = float(df.loc[idx, c])
                vals.append(None if (np.isnan(f) or np.isinf(f)) else f)
            except (TypeError, ValueError):
                vals.append(None)
        if any(v is not None for v in vals):
            rows.append({"label": str(idx), "values": vals})
    return {"periods": periods, "rows": rows}


def fetch_full(ticker: str) -> dict:
    """Comprehensive fundamentals for one ticker: all ratios + the three
    financial statements (annual + quarterly). On-demand drill-down."""
    if yf is None:
        return {"available": False, "reason": "yfinance not installed"}
    market = (UNIVERSE.get(ticker) or {}).get("market", "IN" if ticker.endswith(".NS") else "US")
    currency = "INR" if market == "IN" else "USD"
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        price = _safe(info, "currentPrice") or _safe(info, "regularMarketPrice")

        peg = _safe(info, "trailingPegRatio") or _safe(info, "pegRatio")
        d2e = _safe(info, "debtToEquity")
        if isinstance(d2e, (int, float)) and d2e and d2e > 5:
            d2e = d2e / 100.0
        special = {"__peg__": peg, "__divyield__": _divyield(info, price), "__d2e__": d2e}

        ratios = []
        for key, label, kind in _RATIO_SPEC:
            val = special[key] if key in special else _safe(info, key)
            if isinstance(val, (int, float)):
                ratios.append({"label": label, "value": val, "kind": kind})

        def grab(*names):
            for n in names:
                try:
                    df = getattr(tk, n)
                    if df is not None and not df.empty:
                        return df
                except Exception:  # noqa: BLE001
                    continue
            return None

        inc_a = grab("income_stmt", "financials")
        bal_a = grab("balance_sheet")
        cf_a = grab("cashflow", "cash_flow")

        statements = {
            "income_annual": _stmt_to_dict(inc_a),
            "income_quarterly": _stmt_to_dict(grab("quarterly_income_stmt", "quarterly_financials")),
            "balance_annual": _stmt_to_dict(bal_a),
            "balance_quarterly": _stmt_to_dict(grab("quarterly_balance_sheet")),
            "cashflow_annual": _stmt_to_dict(cf_a),
            "cashflow_quarterly": _stmt_to_dict(grab("quarterly_cashflow", "quarterly_cash_flow")),
        }

        try:
            from signals import quality_scores
            health = quality_scores.compute(inc_a, bal_a, cf_a, info, price)
        except Exception:  # noqa: BLE001
            health = {}

        return {
            "available": True,
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName") or (UNIVERSE.get(ticker) or {}).get("name", ticker),
            "market": market,
            "currency": currency,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "price": price,
            "summary": (info.get("longBusinessSummary") or "")[:600],
            "ratios": ratios,
            "health": health,
            "statements": statements,
            "source": "Yahoo Finance (yfinance)",
        }
    except Exception as e:  # noqa: BLE001
        return {"available": False, "ticker": ticker, "reason": str(e)}
