"""Fetch fundamental + technical metrics for a universe of tickers.

Uses yfinance. All network access is wrapped so that a single failing ticker
never aborts the whole run.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "yfinance is required. Install deps with:\n"
        "  pip install -r requirements.txt"
    ) from exc


@dataclass
class StockMetrics:
    ticker: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    price: Optional[float] = None
    market_cap: Optional[float] = None         # in INR
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    peg: Optional[float] = None
    price_to_book: Optional[float] = None
    roe: Optional[float] = None                # return on equity (fraction)
    profit_margin: Optional[float] = None      # net margin (fraction)
    debt_to_equity: Optional[float] = None
    earnings_growth: Optional[float] = None    # yoy (fraction)
    revenue_growth: Optional[float] = None     # yoy (fraction)
    dividend_yield: Optional[float] = None     # fraction
    beta: Optional[float] = None
    ret_6m: Optional[float] = None             # 6-month price return (fraction)
    above_200dma: Optional[float] = None       # (price/200dma - 1)
    pct_of_52w_high: Optional[float] = None     # price / 52w high
    inst_hold_pct: Optional[float] = None       # institutional holding (fraction)
    insider_hold_pct: Optional[float] = None    # promoter / insider (fraction)
    vol_ratio: Optional[float] = None           # today vol ÷ average
    avg_volume: Optional[float] = None          # avg daily shares traded
    adv_value_cr: Optional[float] = None        # avg daily traded value (₹ crore)
    atr_pct: Optional[float] = None             # 14-day ATR as % of price (volatility)
    next_earnings_days: Optional[int] = None    # trading-ish days to next results
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


def _compute_technicals(hist: pd.DataFrame) -> Dict[str, Optional[float]]:
    out = {"ret_6m": None, "above_200dma": None, "pct_of_52w_high": None,
           "atr_pct": None}
    if hist is None or hist.empty or "Close" not in hist:
        return out
    close = hist["Close"].dropna()
    if close.empty:
        return out
    last = float(close.iloc[-1])

    # 14-day ATR (volatility) as a % of price — Wilder's true range
    try:
        if {"High", "Low"}.issubset(hist.columns) and len(close) >= 15:
            h = hist["High"].astype(float)
            l = hist["Low"].astype(float)
            c = hist["Close"].astype(float)
            prev_c = c.shift(1)
            tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()],
                           axis=1).max(axis=1)
            atr = tr.tail(14).mean()
            if last > 0 and atr == atr:  # not NaN
                out["atr_pct"] = round(float(atr) / last * 100.0, 2)
    except Exception:  # noqa: BLE001
        pass

    # 6-month (~126 trading days) return
    if len(close) > 126:
        ref = float(close.iloc[-127])
        if ref > 0:
            out["ret_6m"] = last / ref - 1.0
    else:
        ref = float(close.iloc[0])
        if ref > 0:
            out["ret_6m"] = last / ref - 1.0

    # distance above/below 200-DMA
    if len(close) >= 200:
        dma200 = float(close.tail(200).mean())
        if dma200 > 0:
            out["above_200dma"] = last / dma200 - 1.0

    # position vs 52-week high
    high_52w = float(close.tail(252).max()) if len(close) else None
    if high_52w and high_52w > 0:
        out["pct_of_52w_high"] = last / high_52w

    return out


def fetch_one(ticker: str, name: str, retries: int = 2) -> StockMetrics:
    last_err = None
    for attempt in range(retries + 1):
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}
            hist = tk.history(period="1y", auto_adjust=True)
            tech = _compute_technicals(hist)

            price = _safe(info, "currentPrice") or _safe(info, "regularMarketPrice")
            if price is None and hist is not None and not hist.empty:
                price = float(hist["Close"].dropna().iloc[-1])

            d2e = _safe(info, "debtToEquity")
            # yfinance sometimes reports D/E as a percentage (e.g. 45.0 = 45%)
            if isinstance(d2e, (int, float)) and d2e and d2e > 5:
                d2e = d2e / 100.0

            # Dividend yield: yfinance is inconsistent for the "dividendYield"
            # field (sometimes a fraction like 0.0496, sometimes a percent like
            # 4.96), which makes a simple heuristic unreliable for sub-1%
            # yields. Prefer unambiguous fields and always store a FRACTION.
            dy = _safe(info, "trailingAnnualDividendYield")  # reliably a fraction
            if dy is None:
                rate = _safe(info, "dividendRate")           # annual INR/share
                if isinstance(rate, (int, float)) and rate and price:
                    dy = rate / price
            if dy is None:
                raw = _safe(info, "dividendYield")
                if isinstance(raw, (int, float)) and raw:
                    dy = raw / 100.0 if raw > 1 else raw

            vol = _safe(info, "volume") or _safe(info, "regularMarketVolume")
            avg_vol = (
                _safe(info, "averageVolume")
                or _safe(info, "averageDailyVolume3Month")
                or _safe(info, "averageDailyVolume10Day")
            )
            vol_ratio = (vol / avg_vol) if vol and avg_vol and avg_vol > 0 else None

            # Liquidity: average daily traded value in ₹ crore (1 cr = 1e7)
            adv_value_cr = None
            if avg_vol and price and avg_vol > 0:
                adv_value_cr = round(avg_vol * price / 1e7, 1)

            # Days to next earnings (gap-risk window). yfinance is inconsistent;
            # best-effort, never fatal.
            next_earnings_days = None
            try:
                ets = (_safe(info, "earningsTimestamp")
                       or _safe(info, "earningsTimestampStart"))
                if isinstance(ets, (int, float)) and ets > 0:
                    days = (datetime.fromtimestamp(ets) - datetime.now()).days
                    if -3 <= days <= 120:
                        next_earnings_days = int(days)
            except Exception:  # noqa: BLE001
                pass

            return StockMetrics(
                ticker=ticker,
                name=name,
                sector=info.get("sector"),
                industry=info.get("industry"),
                price=price,
                market_cap=_safe(info, "marketCap"),
                trailing_pe=_safe(info, "trailingPE"),
                forward_pe=_safe(info, "forwardPE"),
                peg=_safe(info, "trailingPegRatio") or _safe(info, "pegRatio"),
                price_to_book=_safe(info, "priceToBook"),
                roe=_safe(info, "returnOnEquity"),
                profit_margin=_safe(info, "profitMargins"),
                debt_to_equity=d2e,
                earnings_growth=_safe(info, "earningsGrowth")
                or _safe(info, "earningsQuarterlyGrowth"),
                revenue_growth=_safe(info, "revenueGrowth"),
                dividend_yield=dy,
                beta=_safe(info, "beta"),
                ret_6m=tech["ret_6m"],
                above_200dma=tech["above_200dma"],
                pct_of_52w_high=tech["pct_of_52w_high"],
                inst_hold_pct=_safe(info, "heldPercentInstitutions"),
                insider_hold_pct=_safe(info, "heldPercentInsiders"),
                vol_ratio=vol_ratio,
                avg_volume=avg_vol,
                adv_value_cr=adv_value_cr,
                atr_pct=tech["atr_pct"],
                next_earnings_days=next_earnings_days,
            )
        except Exception as exc:  # noqa: BLE001 - keep the batch alive
            last_err = str(exc)
            time.sleep(1.0 + attempt)
    return StockMetrics(ticker=ticker, name=name, error=last_err or "fetch failed")


def fetch_universe(universe: Dict[str, str], workers: int = 6) -> pd.DataFrame:
    """Fetch metrics for the whole universe concurrently (keeps the batch
    alive even if individual tickers fail)."""
    rows: List[dict] = []
    total = len(universe)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fetch_one, ticker, name): ticker
            for ticker, name in universe.items()
        }
        for fut in as_completed(futures):
            ticker = futures[fut]
            done += 1
            try:
                m = fut.result()
            except Exception as exc:  # noqa: BLE001
                m = StockMetrics(ticker=ticker, name=universe[ticker], error=str(exc))
            flag = "" if not m.error else "  (FAILED)"
            print(f"  [{done:>2}/{total}] {ticker:<16}{flag}")
            rows.append(asdict(m))
    return pd.DataFrame(rows)


def fetch_news(ticker: str, limit: int = 6) -> List[dict]:
    """Return recent headlines for a ticker, tolerant of yfinance schema
    changes (old flat schema vs new nested ``content`` schema)."""
    out: List[dict] = []
    try:
        items = yf.Ticker(ticker).news or []
    except Exception:  # noqa: BLE001
        return out
    for it in items[: limit * 2]:
        title = it.get("title")
        publisher = it.get("publisher")
        link = it.get("link")
        ts = it.get("providerPublishTime")
        # new nested schema
        content = it.get("content") if isinstance(it.get("content"), dict) else None
        if content:
            title = title or content.get("title")
            prov = content.get("provider") or {}
            publisher = publisher or prov.get("displayName")
            cu = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
            link = link or (cu.get("url") if isinstance(cu, dict) else None)
            ts = ts or content.get("pubDate") or content.get("displayTime")
        if not title:
            continue
        date_str = None
        if isinstance(ts, (int, float)):
            try:
                date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            except Exception:  # noqa: BLE001
                date_str = None
        elif isinstance(ts, str):
            date_str = ts[:10]
        out.append({
            "title": title.strip(),
            "publisher": publisher or "",
            "date": date_str or "",
            "link": link or "",
        })
        if len(out) >= limit:
            break
    return out
