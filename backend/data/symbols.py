"""Dynamic symbol masters — the *full* listed universe, fetched live (cached).

Instead of a hardcoded list, this pulls the official symbol directories:

  * NSE  — EQUITY_L.csv (~2,000 equities)            → ``SYMBOL.NS``
  * US   — Nasdaq Trader symbol files (~5,000–6,000) → plain ticker
  * BSE  — best-effort scrip list (often blocked)    → ``<code>.BO``

Each market is cached to ``cache/symbols_<mkt>.json`` for ``SYMBOLS_TTL_DAYS``.
Everything degrades gracefully: if a source is unreachable we fall back to the
cache, then to the curated list, so the app never hard-fails.
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from typing import Dict, List

import requests

from core.config import CACHE_DIR

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_TTL = float(os.environ.get("SYMBOLS_TTL_DAYS", 7)) * 86400.0


def _cache_path(mkt: str) -> str:
    return os.path.join(CACHE_DIR, f"symbols_{mkt}.json")


def _load_cache(mkt: str) -> List[dict]:
    try:
        p = _cache_path(mkt)
        if time.time() - os.path.getmtime(p) < _TTL:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:  # noqa: BLE001
        pass
    return []


def _save_cache(mkt: str, rows: List[dict]) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(mkt), "w", encoding="utf-8") as fh:
            json.dump(rows, fh)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# NSE
# ---------------------------------------------------------------------------
def nse_equities(force: bool = False) -> List[dict]:
    if not force:
        cached = _load_cache("nse")
        if cached:
            return cached
    urls = [
        "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
        "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
    ]
    for url in urls:
        try:
            s = requests.Session()
            s.headers.update({"User-Agent": _UA, "Accept": "text/csv,*/*"})
            s.get("https://www.nseindia.com", timeout=10)
            r = s.get(url, timeout=15)
            if r.status_code != 200 or not r.text:
                continue
            rows = []
            for row in csv.DictReader(io.StringIO(r.text)):
                sym = (row.get("SYMBOL") or "").strip()
                series = (row.get(" SERIES") or row.get("SERIES") or "").strip()
                name = (row.get("NAME OF COMPANY") or "").strip()
                if not sym or (series and series not in ("EQ", "BE")):
                    continue
                rows.append({"ticker": f"{sym}.NS", "name": name, "market": "IN", "currency": "INR"})
            if rows:
                _save_cache("nse", rows)
                return rows
        except Exception:  # noqa: BLE001
            continue
    return _load_cache("nse")


# ---------------------------------------------------------------------------
# US (Nasdaq Trader symbol directory)
# ---------------------------------------------------------------------------
def _parse_pipe(text: str, sym_col: str, name_col: str) -> List[dict]:
    rows = []
    reader = csv.DictReader(io.StringIO(text), delimiter="|")
    for r in reader:
        sym = (r.get(sym_col) or "").strip()
        if not sym or "File Creation Time" in sym:
            continue
        if (r.get("Test Issue") or "").strip() == "Y":
            continue
        if (r.get("ETF") or "").strip() == "Y":
            continue
        if not sym.isalpha():  # skip warrants/units/preferred/class shares
            continue
        rows.append({"ticker": sym, "name": (r.get(name_col) or "").strip(),
                     "market": "US", "currency": "USD"})
    return rows


def us_equities(force: bool = False) -> List[dict]:
    if not force:
        cached = _load_cache("us")
        if cached:
            return cached
    out: Dict[str, dict] = {}
    # Primary: SEC official ticker directory (reliable, no bot wall).
    try:
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers={"User-Agent": "market-intelligence research tool (contact: admin@example.com)"},
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            for v in (data.values() if isinstance(data, dict) else []):
                sym = str(v.get("ticker") or "").strip().upper()
                if sym and sym.isalpha():
                    out.setdefault(sym, {"ticker": sym, "name": (v.get("title") or "").strip(),
                                         "market": "US", "currency": "USD"})
    except Exception:  # noqa: BLE001
        pass
    # Fallback: Nasdaq Trader pipe files (may be bot-blocked from some hosts).
    if not out:
        for url, sym_col, name_col in [
            ("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", "Symbol", "Security Name"),
            ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", "ACT Symbol", "Security Name"),
        ]:
            try:
                r = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
                if r.status_code == 200 and r.text and not r.text.lstrip().startswith("<"):
                    for row in _parse_pipe(r.text, sym_col, name_col):
                        out.setdefault(row["ticker"], row)
            except Exception:  # noqa: BLE001
                continue
    rows = list(out.values())
    if rows:
        _save_cache("us", rows)
        return rows
    return _load_cache("us")


# ---------------------------------------------------------------------------
# BSE (best-effort — frequently blocks non-browser traffic)
# ---------------------------------------------------------------------------
def bse_equities(force: bool = False) -> List[dict]:
    if not force:
        cached = _load_cache("bse")
        if cached:
            return cached
    try:
        s = requests.Session()
        s.headers.update({"User-Agent": _UA, "Accept": "application/json",
                          "Referer": "https://www.bseindia.com/"})
        url = ("https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?"
               "Group=&Scripcode=&industry=&segment=Equity&status=Active")
        r = s.get(url, timeout=15)
        if r.status_code != 200:
            return _load_cache("bse")
        data = r.json()
        rows = []
        for x in (data if isinstance(data, list) else []):
            code = str(x.get("SCRIP_CD") or x.get("Scrip_Cd") or "").strip()
            name = (x.get("Scrip_Name") or x.get("SCRIP_NAME") or "").strip()
            if code:
                rows.append({"ticker": f"{code}.BO", "name": name, "market": "BSE", "currency": "INR"})
        if rows:
            _save_cache("bse", rows)
        return rows
    except Exception:  # noqa: BLE001
        return _load_cache("bse")


_FETCHERS = {"IN": nse_equities, "US": us_equities, "BSE": bse_equities}

_SEARCH_CACHE: List[dict] = []


def _all_symbols_for_search() -> List[dict]:
    """Flat list of {ticker,name,market} across markets, from cache or curated.
    Used by the typeahead. Tries cached masters first; never blocks on network."""
    global _SEARCH_CACHE
    if _SEARCH_CACHE:
        return _SEARCH_CACHE
    out: List[dict] = []
    for mkt in ("IN", "US", "BSE"):
        out.extend(_load_cache(mkt))
    if not out:
        from data.universe import UNIVERSE
        out = [{"ticker": t, "name": v["name"], "market": v["market"]} for t, v in UNIVERSE.items()]
    _SEARCH_CACHE = out
    return out


def search(query: str, limit: int = 12) -> List[dict]:
    """Typeahead: match a query against ticker or company name, ranked by
    relevance (exact > word-start > starts-with > contains), NSE preferred."""
    q = (query or "").strip().lower()
    if not q:
        return []
    rows = _all_symbols_for_search()
    mkt_rank = {"IN": 0, "US": 1, "BSE": 2}
    scored = []
    for r in rows:
        tk = (r.get("ticker") or "").lower()
        base = tk.split(".")[0]
        nm = (r.get("name") or "").lower()
        words = nm.split()
        if base == q or nm == q:
            rel = 0
        elif base.startswith(q) or any(w.startswith(q) for w in words):
            rel = 1
        elif nm.startswith(q):
            rel = 2
        elif q in base or q in nm:
            rel = 3
        else:
            continue
        scored.append((rel, mkt_rank.get(r.get("market"), 3), len(nm), r))
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    return [r for *_, r in scored[:limit]]


def _norm_name(name: str) -> str:
    """Normalise a company name for cross-exchange matching (NSE vs BSE)."""
    import re
    n = (name or "").lower()
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    # drop common corporate suffixes/noise so 'Reliance Industries Ltd' == 'Reliance Industries Limited'
    stop = {"ltd", "limited", "the", "india", "indian", "corp", "corporation",
            "co", "company", "and", "&", "plc", "inc"}
    toks = [t for t in n.split() if t and t not in stop]
    return " ".join(toks)


def nse_twin(bse_ticker: str, name_hint: str = "") -> Optional[str]:
    """Given a BSE (.BO) ticker (or a company name), find the matching NSE (.NS)
    ticker by company-name match. Yahoo serves far better data for .NS, so the
    analyzer falls back to the twin when a .BO listing has no price."""
    nse = nse_equities()
    nse_by_name = {_norm_name(r.get("name")): r.get("ticker") for r in nse if r.get("name")}

    # try the BSE master's official name for this code first (most reliable),
    # then the caller's name hint (skip placeholder codes like "532667").
    candidates = []
    for r in _load_cache("bse"):
        if r.get("ticker") == bse_ticker and r.get("name"):
            candidates.append(_norm_name(r["name"]))
            break
    if name_hint and not name_hint.replace(".", "").isdigit():
        candidates.append(_norm_name(name_hint))

    for c in candidates:
        if c and c in nse_by_name:
            return nse_by_name[c]
    return None


def build_dynamic_universe(markets=("IN", "BSE", "US"), force: bool = False,
                           dedupe_in=True) -> Dict[str, dict]:
    """Merge the requested markets into a {ticker: {name, market, currency}} dict.

    NSE is the canonical India market (deeper liquidity + better data on Yahoo).
    When ``dedupe_in`` is True, any BSE name that also lists on NSE is dropped in
    favour of the ``.NS`` ticker — so we keep only BSE-EXCLUSIVE names and never
    double-count (e.g. Reliance as both RELIANCE.NS and 500325.BO).

    Falls back to the curated universe if nothing could be fetched at all.
    """
    uni: Dict[str, dict] = {}
    counts = {}
    fetched = {}
    for mkt in markets:
        fn = _FETCHERS.get(mkt)
        if not fn:
            continue
        fetched[mkt] = fn(force=force)
        counts[mkt] = len(fetched[mkt])

    nse_names = {_norm_name(r["name"]) for r in fetched.get("IN", []) if r.get("name")}
    dropped = 0
    for mkt in markets:
        for row in fetched.get(mkt, []):
            if dedupe_in and mkt == "BSE" and _norm_name(row.get("name")) in nse_names:
                dropped += 1
                continue  # prefer the NSE listing of the same company
            uni[row["ticker"]] = {"name": row["name"], "market": row["market"],
                                  "currency": row["currency"]}
    print(f"[symbols] fetched: {counts} · BSE↔NSE dups dropped: {dropped} -> {len(uni)} total")
    if not uni:
        from data.universe import UNIVERSE
        print("[symbols] all sources empty — falling back to curated universe")
        return dict(UNIVERSE)
    return uni
