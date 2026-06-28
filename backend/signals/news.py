"""News & event catalyst layer.

Fetches recent headlines (Yahoo Finance via yfinance — free, no API key) and
scores them with a transparent finance lexicon. Each headline is tagged with
the *events* it implies (order win, capacity expansion, upgrade, fraud, ...)
and a sentiment. We aggregate into a 0-100 catalyst score (50 = neutral) that
feeds the multibagger composite, and we surface the headlines themselves so the
agent's reasoning is auditable.

No external API key is required. To plug in a stronger provider later, implement
``_provider_headlines`` and set NEWS_PROVIDER.
"""

from __future__ import annotations

import datetime as _dt
import email.utils as _eut
import warnings
import xml.etree.ElementTree as ET
from urllib.parse import quote
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

import requests

try:
    from data.universe import UNIVERSE as _UNIVERSE
except Exception:  # noqa: BLE001
    _UNIVERSE = {}

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Indian financial outlets we especially trust (used to prioritise display).
PREFERRED_SOURCES = (
    "Moneycontrol", "Economic Times", "The Economic Times", "ET Markets", "Mint",
    "Livemint", "Business Standard", "Reuters", "Bloomberg", "CNBC", "Financial Express",
    "Hindu BusinessLine", "NDTV Profit", "Yahoo Finance",
)


# event keyword -> (weight, human label). Positive weights are bullish.
EVENT_LEXICON: Dict[str, Tuple[float, str]] = {
    # --- bullish catalysts ---
    "order win": (2.0, "Order win"),
    "bags order": (2.0, "Order win"),
    "wins order": (2.0, "Order win"),
    "new contract": (1.8, "New contract"),
    "contract": (1.0, "Contract"),
    "record": (1.5, "Record results"),
    "all-time high": (1.2, "All-time high"),
    "expansion": (1.5, "Capacity expansion"),
    "capacity": (1.2, "Capacity expansion"),
    "capex": (1.2, "Capex / investment"),
    "new plant": (1.6, "New plant"),
    "acquisition": (1.2, "Acquisition"),
    "acquire": (1.2, "Acquisition"),
    "merger": (1.0, "Merger"),
    "approval": (1.6, "Regulatory approval"),
    "approved": (1.5, "Regulatory approval"),
    "launch": (1.2, "Product launch"),
    "patent": (1.3, "Patent / IP"),
    "upgrade": (1.6, "Analyst upgrade"),
    "raises target": (1.5, "Target raised"),
    "buyback": (1.4, "Buyback"),
    "dividend": (0.8, "Dividend"),
    "beats": (1.8, "Earnings beat"),
    "beat estimates": (1.8, "Earnings beat"),
    "profit jumps": (1.8, "Profit surge"),
    "profit rises": (1.4, "Profit growth"),
    "profit surges": (2.0, "Profit surge"),
    "revenue jumps": (1.5, "Revenue growth"),
    "surges": (1.2, "Stock surge"),
    "tie-up": (1.2, "Partnership"),
    "partnership": (1.2, "Partnership"),
    "stake buy": (1.4, "Promoter/insider buying"),
    "promoter buy": (1.6, "Promoter buying"),
    "guidance raised": (1.8, "Guidance raised"),
    "multibagger": (1.0, "Multibagger mention"),
    # --- bearish flags ---
    "fraud": (-3.0, "Fraud allegation"),
    "probe": (-2.0, "Regulatory probe"),
    "investigation": (-2.0, "Investigation"),
    "downgrade": (-1.8, "Analyst downgrade"),
    "cuts target": (-1.5, "Target cut"),
    "lawsuit": (-1.5, "Litigation"),
    "litigation": (-1.5, "Litigation"),
    "default": (-2.5, "Default risk"),
    "debt": (-0.8, "Debt concern"),
    "loss widens": (-2.0, "Widening loss"),
    "profit falls": (-1.5, "Profit decline"),
    "profit drops": (-1.5, "Profit decline"),
    "misses": (-1.8, "Earnings miss"),
    "miss estimates": (-1.8, "Earnings miss"),
    "resigns": (-1.4, "Management exit"),
    "resignation": (-1.4, "Management exit"),
    "recall": (-1.5, "Product recall"),
    "penalty": (-1.6, "Penalty / fine"),
    "fine": (-1.2, "Penalty / fine"),
    "warning": (-1.2, "Warning"),
    "slump": (-1.3, "Slump"),
    "plunges": (-1.6, "Sharp fall"),
    "stake sale": (-1.0, "Promoter selling"),
    "pledge": (-1.2, "Promoter pledge"),
}


def _fetch_yf_news(ticker: str, limit: int = 8) -> List[dict]:
    out: List[dict] = []
    if yf is None:
        return out
    try:
        items = yf.Ticker(ticker).news or []
    except Exception:  # noqa: BLE001
        return out
    for it in items[: limit * 2]:
        title = it.get("title")
        publisher = it.get("publisher")
        link = it.get("link")
        ts = it.get("providerPublishTime")
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
        date_str = ""
        if isinstance(ts, (int, float)):
            try:
                date_str = _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            except Exception:  # noqa: BLE001
                date_str = ""
        elif isinstance(ts, str):
            date_str = ts[:10]
        out.append({"title": title.strip(), "publisher": publisher or "",
                    "date": date_str, "link": link or ""})
        if len(out) >= limit:
            break
    return out


def _parse_rss_date(s: str) -> str:
    try:
        return _eut.parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return (s or "")[:10]


def _fetch_google_news(query: str, region: str = "IN", limit: int = 12) -> List[dict]:
    """Google News RSS aggregates Moneycontrol, ET, Mint, Business Standard,
    Reuters, etc. — one feed, many trusted publishers. No API key."""
    hl, gl, ceid = ("en-IN", "IN", "IN:en") if region == "IN" else ("en-US", "US", "US:en")
    url = (f"https://news.google.com/rss/search?q={quote(query)}+when:45d"
           f"&hl={hl}&gl={gl}&ceid={ceid}")
    out: List[dict] = []
    try:
        r = requests.get(url, headers={"User-Agent": _UA}, timeout=8)
        if r.status_code != 200:
            return out
        root = ET.fromstring(r.content)
    except Exception:  # noqa: BLE001
        return out
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = item.findtext("link") or ""
        pub = item.findtext("pubDate") or ""
        src_el = item.find("source")
        publisher = (src_el.text if src_el is not None and src_el.text else "").strip()
        # Google News titles are usually "Headline - Publisher"
        if " - " in title:
            head, tail = title.rsplit(" - ", 1)
            if not publisher:
                publisher = tail.strip()
            if publisher and title.endswith(publisher):
                title = head.strip()
        if not title:
            continue
        out.append({"title": title, "publisher": publisher or "Google News",
                    "link": link, "date": _parse_rss_date(pub)})
        if len(out) >= limit:
            break
    return out


def _dedupe(items: List[dict]) -> List[dict]:
    seen = set()
    out = []
    for h in items:
        key = h["title"].lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def _source_rank(publisher: str) -> int:
    p = (publisher or "").lower()
    for i, src in enumerate(PREFERRED_SOURCES):
        if src.lower() in p:
            return i
    return len(PREFERRED_SOURCES)


def _score_headline(title: str) -> Tuple[float, List[str]]:
    t = " " + title.lower() + " "
    score = 0.0
    events: List[str] = []
    for kw, (w, label) in EVENT_LEXICON.items():
        if kw in t:
            score += w
            if label not in events:
                events.append(label)
    return score, events


def analyze(ticker: str, limit: int = 8) -> dict:
    """Return headlines (tagged) + an aggregate catalyst score for one ticker,
    aggregated across Google News (Moneycontrol/ET/Mint/Business Standard/…)
    plus Yahoo Finance."""
    meta = _UNIVERSE.get(ticker) or {}
    name = meta.get("name") or ticker.replace(".NS", "")
    region = "IN" if (meta.get("market") == "IN" or ticker.endswith(".NS")) else "US"

    google = _fetch_google_news(f'"{name}" stock', region=region, limit=limit + 4)
    yahoo = _fetch_yf_news(ticker, limit=limit)
    # prefer trusted-source ordering, then dedupe
    merged = sorted(google + yahoo, key=lambda h: _source_rank(h.get("publisher", "")))
    headlines = _dedupe(merged)[: limit + 4]
    total = 0.0
    pos = neg = 0
    enriched: List[dict] = []
    for h in headlines:
        s, events = _score_headline(h["title"])
        # recency weight: newer headlines count a little more
        weight = 1.0
        if h.get("date"):
            try:
                age = (_dt.date.today() - _dt.date.fromisoformat(h["date"])).days
                weight = 1.0 if age <= 7 else 0.7 if age <= 30 else 0.45
            except Exception:  # noqa: BLE001
                weight = 0.8
        total += s * weight
        if s > 0:
            pos += 1
        elif s < 0:
            neg += 1
        enriched.append({**h, "sentiment": round(s, 1),
                         "tone": "positive" if s > 0 else "negative" if s < 0 else "neutral",
                         "events": events})

    # squash total into 0-100 (50 neutral). tanh keeps extremes bounded.
    import math
    catalyst = round(50.0 + 50.0 * math.tanh(total / 5.0), 1)

    velocity, recent_count = _news_velocity(enriched)

    return {
        "ticker": ticker,
        "catalyst_score": catalyst,
        "news_count": len(headlines),
        "recent_count": recent_count,
        "velocity": velocity,
        "positive": pos,
        "negative": neg,
        "headlines": enriched,
        "top_events": _top_events(enriched),
    }


def _news_velocity(enriched: List[dict]) -> Tuple[Optional[float], int]:
    """Ratio of recent (<=10d) headline rate to the prior (11-45d) rate.
    >1 = coverage accelerating (attention waking up). None when no dated news."""
    recent = older = 0
    for h in enriched:
        d = h.get("date")
        if not d:
            continue
        try:
            age = (_dt.date.today() - _dt.date.fromisoformat(d)).days
        except Exception:  # noqa: BLE001
            continue
        if age <= 10:
            recent += 1
        elif age <= 45:
            older += 1
    if recent == 0 and older == 0:
        return None, 0
    older_rate = (older / 35.0) if older else 0.0
    if older_rate <= 0:
        return (1.5 if recent >= 2 else 1.1 if recent == 1 else None), recent
    return round((recent / 10.0) / older_rate, 2), recent


def _top_events(enriched: List[dict]) -> List[str]:
    seen: List[str] = []
    for h in enriched:
        for e in h.get("events", []):
            if e not in seen:
                seen.append(e)
    return seen[:5]


def analyze_many(tickers: List[str], limit: int = 8) -> Dict[str, dict]:
    """Sequential by design — yfinance news is light and rate-limited."""
    out: Dict[str, dict] = {}
    for tk in tickers:
        try:
            out[tk] = analyze(tk, limit=limit)
        except Exception:  # noqa: BLE001
            out[tk] = {"ticker": tk, "catalyst_score": 50.0, "news_count": 0,
                       "positive": 0, "negative": 0, "headlines": [], "top_events": []}
    return out
