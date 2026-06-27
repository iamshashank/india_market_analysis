"""Options / F&O analytics.

US: full option-chain analytics via yfinance (works out of the box).
India (NSE): best-effort fetch of the NSE option-chain API. NSE aggressively
rate-limits/blocks non-browser traffic, so this can fail from servers — in that
case we return a clear, honest "unavailable" payload (and you can later wire a
broker API like Kite for reliable Indian F&O data).

For a chosen expiry we compute: spot, put/call ratio (OI & volume), max pain,
ATM implied volatility, the biggest OI strikes (support/resistance), and a plain
sentiment read — all explainable.
"""

from __future__ import annotations

import time
import warnings
from typing import Dict, List, Optional

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

import requests

_CACHE: Dict[str, dict] = {}
_TTL = 300  # seconds


def _pcr_sentiment(pcr: Optional[float]) -> str:
    if pcr is None:
        return "Unknown"
    if pcr < 0.7:
        return "Bullish positioning (calls dominate)"
    if pcr < 1.0:
        return "Mildly bullish"
    if pcr <= 1.3:
        return "Mildly bearish"
    return "Bearish positioning (puts dominate)"


def _max_pain(strikes: List[float], call_oi: Dict[float, float],
              put_oi: Dict[float, float]) -> Optional[float]:
    if not strikes:
        return None
    best_strike = None
    best_loss = None
    for s in strikes:
        loss = 0.0
        for k in strikes:
            if k < s:
                loss += (s - k) * call_oi.get(k, 0.0)   # ITM calls
            elif k > s:
                loss += (k - s) * put_oi.get(k, 0.0)    # ITM puts
        if best_loss is None or loss < best_loss:
            best_loss = loss
            best_strike = s
    return best_strike


def _summarise(spot, expiry, strikes, call_oi, put_oi, call_vol, put_vol,
               call_iv, put_iv) -> dict:
    tot_call_oi = sum(call_oi.values())
    tot_put_oi = sum(put_oi.values())
    tot_call_vol = sum(call_vol.values())
    tot_put_vol = sum(put_vol.values())
    pcr_oi = round(tot_put_oi / tot_call_oi, 2) if tot_call_oi else None
    pcr_vol = round(tot_put_vol / tot_call_vol, 2) if tot_call_vol else None
    mp = _max_pain(sorted(strikes), call_oi, put_oi)

    # ATM IV: nearest strike to spot
    atm_iv = None
    if spot and strikes:
        atm = min(strikes, key=lambda k: abs(k - spot))
        ivs = [v for v in (call_iv.get(atm), put_iv.get(atm)) if isinstance(v, (int, float))]
        if ivs:
            atm_iv = round(sum(ivs) / len(ivs) * 100, 1)

    top_calls = sorted(call_oi.items(), key=lambda x: x[1], reverse=True)[:3]
    top_puts = sorted(put_oi.items(), key=lambda x: x[1], reverse=True)[:3]

    return {
        "expiry": expiry,
        "spot": round(spot, 2) if spot else None,
        "pcr_oi": pcr_oi,
        "pcr_volume": pcr_vol,
        "sentiment": _pcr_sentiment(pcr_oi),
        "max_pain": mp,
        "atm_iv_pct": atm_iv,
        "total_call_oi": int(tot_call_oi),
        "total_put_oi": int(tot_put_oi),
        "resistance_strikes": [{"strike": k, "call_oi": int(v)} for k, v in top_calls],
        "support_strikes": [{"strike": k, "put_oi": int(v)} for k, v in top_puts],
    }


def analyze_us(ticker: str) -> dict:
    if yf is None:
        return {"available": False, "reason": "yfinance not installed"}
    try:
        tk = yf.Ticker(ticker)
        expiries = list(tk.options or [])
        if not expiries:
            return {"available": False, "market": "US", "ticker": ticker,
                    "reason": "No listed options for this symbol"}
        expiry = expiries[0]
        chain = tk.option_chain(expiry)
        calls, puts = chain.calls, chain.puts
        info = tk.fast_info if hasattr(tk, "fast_info") else {}
        spot = None
        try:
            spot = float(info["lastPrice"])
        except Exception:  # noqa: BLE001
            h = tk.history(period="1d")
            spot = float(h["Close"].iloc[-1]) if h is not None and not h.empty else None

        def col(df, c):
            return df[c].fillna(0).tolist() if c in df else [0] * len(df)

        strikes = set()
        call_oi, put_oi, call_vol, put_vol, call_iv, put_iv = {}, {}, {}, {}, {}, {}
        for _, r in calls.iterrows():
            k = float(r["strike"]); strikes.add(k)
            call_oi[k] = float(r.get("openInterest") or 0)
            call_vol[k] = float(r.get("volume") or 0)
            call_iv[k] = float(r.get("impliedVolatility") or 0)
        for _, r in puts.iterrows():
            k = float(r["strike"]); strikes.add(k)
            put_oi[k] = float(r.get("openInterest") or 0)
            put_vol[k] = float(r.get("volume") or 0)
            put_iv[k] = float(r.get("impliedVolatility") or 0)

        summary = _summarise(spot, expiry, strikes, call_oi, put_oi,
                             call_vol, put_vol, call_iv, put_iv)
        return {"available": True, "market": "US", "ticker": ticker,
                "expiries": expiries[:8], **summary}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "market": "US", "ticker": ticker, "reason": str(e)}


_NSE_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/option-chain",
}


def analyze_in(ticker: str) -> dict:
    sym = ticker.replace(".NS", "").upper()
    try:
        s = requests.Session()
        s.headers.update(_NSE_HEADERS)
        s.get("https://www.nseindia.com/option-chain", timeout=10)
        r = s.get(f"https://www.nseindia.com/api/option-chain-equities?symbol={sym}", timeout=10)
        if r.status_code != 200:
            return {"available": False, "market": "IN", "ticker": ticker,
                    "reason": f"NSE returned HTTP {r.status_code} (often blocked for non-browser traffic). "
                              "Wire a broker API (e.g. Kite) for reliable Indian F&O."}
        data = r.json()
        records = data.get("records", {})
        spot = records.get("underlyingValue")
        all_exp = records.get("expiryDates", [])
        expiry = all_exp[0] if all_exp else None
        rows = [x for x in records.get("data", []) if x.get("expiryDate") == expiry]

        strikes = set()
        call_oi, put_oi, call_vol, put_vol, call_iv, put_iv = {}, {}, {}, {}, {}, {}
        for x in rows:
            k = float(x.get("strikePrice"))
            strikes.add(k)
            ce, pe = x.get("CE"), x.get("PE")
            if ce:
                call_oi[k] = float(ce.get("openInterest") or 0)
                call_vol[k] = float(ce.get("totalTradedVolume") or 0)
                call_iv[k] = float(ce.get("impliedVolatility") or 0) / 100.0
            if pe:
                put_oi[k] = float(pe.get("openInterest") or 0)
                put_vol[k] = float(pe.get("totalTradedVolume") or 0)
                put_iv[k] = float(pe.get("impliedVolatility") or 0) / 100.0

        if not strikes:
            return {"available": False, "market": "IN", "ticker": ticker,
                    "reason": "NSE reachable but returned no option data (likely throttled). "
                              "Wire a broker API (e.g. Kite) for reliable Indian F&O."}

        summary = _summarise(spot, expiry, strikes, call_oi, put_oi,
                             call_vol, put_vol, call_iv, put_iv)
        return {"available": True, "market": "IN", "ticker": ticker,
                "expiries": all_exp[:8], **summary}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "market": "IN", "ticker": ticker,
                "reason": f"Could not reach NSE ({e}). Wire a broker API (e.g. Kite) for Indian F&O."}


def analyze(ticker: str, market: Optional[str] = None) -> dict:
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return {"available": False, "reason": "No ticker given"}
    if market is None:
        market = "IN" if ticker.endswith(".NS") else "US"

    key = f"{market}:{ticker}"
    now = time.time()
    cached = _CACHE.get(key)
    if cached and (now - cached["_ts"] < _TTL):
        return cached["data"]

    data = analyze_in(ticker) if market == "IN" else analyze_us(ticker)
    _CACHE[key] = {"data": data, "_ts": now}
    return data
