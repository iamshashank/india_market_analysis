"""Parse an NSDL/CDSL Consolidated Account Statement (e-CAS) PDF → equity holdings.

Equities only: we keep ISINs that resolve to an NSE-listed equity (ISIN→ticker
via the NSE master) and skip everything else (mutual funds = ISIN starting INF,
bonds, unlisted). The CAS groups holdings by demat account / DP, so each holding
is tagged with its broker where we can detect it.

Password: used only to decrypt in-memory; never stored or logged. The app runs
locally, so the statement never leaves the machine. Never raises — returns a
structured result so the UI can show a friendly message.
"""

from __future__ import annotations

import io
import re
from typing import Dict, List, Optional

ISIN_RE = re.compile(r"\bIN[EF0-9][0-9A-Z]{9}\b")
_NUM = re.compile(r"-?\d[\d,]*\.?\d*")
# standalone numeric token — not glued to letters (avoids the '3' in '3i Infotech')
_QTY_TOK = re.compile(r"(?<![A-Za-z0-9.])\d[\d,]*(?:\.\d+)?(?![A-Za-z])")

# DP / broker detection — keyword in an account header → display name
_DP_HINTS = [
    ("zerodha", "Zerodha"), ("nextbillion", "Groww"), ("groww", "Groww"),
    ("angel", "Angel One"), ("upstox", "Upstox"), ("rksv", "Upstox"),
    ("icici", "ICICI Direct"), ("hdfc", "HDFC Securities"), ("kotak", "Kotak"),
    ("motilal", "Motilal Oswal"), ("5paisa", "5paisa"), ("dhan", "Dhan"),
    ("paytm", "Paytm Money"), ("iifl", "IIFL"), ("sbicap", "SBI Securities"),
    ("axis", "Axis Direct"), ("sharekhan", "Sharekhan"), ("nuvama", "Nuvama"),
]


def _detect_dp(line: str) -> Optional[str]:
    """Detect a broker/DP from an account *header* line only — never from a
    holding row (which carries an ISIN and may contain a bank name)."""
    if ISIN_RE.search(line):
        return None
    low = line.lower()
    header = any(k in low for k in ("dp name", "depository participant", "dp id",
                                    "demat account", "boid", "client id"))
    if not header:
        return None
    known = next((disp for kw, disp in _DP_HINTS if kw in low), None)
    if known:
        return known
    m = re.search(r"(?:dp name|depository participant)\s*[:\-]\s*(.+)", line, re.I)
    if m:
        name = m.group(1).strip().split("  ")[0][:40].strip()
        if name:
            return name.title()
    return None


def _nums(s: str) -> List[float]:
    out: List[float] = []
    for t in _QTY_TOK.findall(s):
        try:
            v = float(t.replace(",", ""))
        except ValueError:
            continue
        if v > 0:
            out.append(v)
    return out


def _extract_qty(line: str, isin: str) -> Optional[float]:
    """Best-effort quantity from a CAS equity row. Looks at the numeric columns
    after the ISIN (typically qty, market price, value), then before it; ignores
    digits glued to a name (e.g. '3i'). Returns None if uncertain."""
    before, _, after = line.partition(isin)
    nums = _nums(after) or _nums(before)
    if not nums:
        return None
    cand = nums[-3] if len(nums) >= 3 else nums[0]
    if cand <= 0 or cand >= 1e8:
        return None
    return float(int(cand)) if cand == int(cand) else round(cand, 3)


def parse_text(full_text: str, isin_map: Dict[str, str]) -> List[dict]:
    """Extract equity holdings from already-decrypted CAS text (testable core)."""
    by_ticker: Dict[str, dict] = {}
    cur_dp = "Demat (CAS)"
    for line in full_text.split("\n"):
        dp = _detect_dp(line)
        if dp:
            cur_dp = dp
        m = ISIN_RE.search(line)
        if not m:
            continue
        isin = m.group(0)
        if not isin.startswith("INE"):      # equities only (INF = mutual fund, etc.)
            continue
        tk = isin_map.get(isin)
        if not tk:                          # not an NSE-listed equity → skip
            continue
        qty = _extract_qty(line, isin)
        rec = by_ticker.get(tk)
        if rec:
            if qty:
                rec["quantity"] = (rec.get("quantity") or 0) + qty
        else:
            by_ticker[tk] = {"symbol": tk, "ticker": tk, "market": "IN",
                             "broker": cur_dp, "quantity": qty, "avg_price": None}
    return list(by_ticker.values())


def _extract_all(reader) -> str:
    """Concatenate page text. Uses the default (fast) extractor — layout mode is
    far slower and on a multi-page CAS can exceed the request timeout."""
    parts = []
    for p in reader.pages:
        try:
            parts.append(p.extract_text() or "")
        except Exception:  # noqa: BLE001
            parts.append("")
    return "\n".join(parts)


def _sample_isin_lines(full_text: str, limit: int = 4) -> List[str]:
    out: List[str] = []
    for line in full_text.split("\n"):
        if ISIN_RE.search(line) and line.strip():
            out.append(" ".join(line.split())[:200])
            if len(out) >= limit:
                break
    return out


def parse_cas(data: bytes, password: str = "") -> dict:
    """Decrypt + parse a CAS PDF. Returns {available, holdings, note} | {available:False, reason}."""
    try:
        from pypdf import PdfReader
    except Exception:  # noqa: BLE001
        return {"available": False, "reason": "PDF support isn't installed (pip install pypdf pycryptodome)."}

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            if not reader.decrypt(password or ""):
                return {"available": False, "reason": "Wrong PDF password."}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": f"Couldn't open the PDF ({type(e).__name__})."}

    try:
        full_text = _extract_all(reader)
        pages = len(reader.pages)
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": f"Couldn't read the PDF text ({type(e).__name__})."}

    from data.symbols import isin_to_ticker_map
    holdings = parse_text(full_text, isin_to_ticker_map())
    sample = _sample_isin_lines(full_text)
    if not holdings:
        return {"available": True, "holdings": [], "pages": pages, "sample": sample,
                "note": "No NSE-listed equities matched in this statement (mutual funds are skipped)."}
    valued = sum(1 for h in holdings if h.get("quantity"))
    note = f"Matched {len(holdings)} equities to NSE listings"
    note += (f"; quantities read for {valued}." if valued
             else "; couldn't read quantities from this layout — analysis still works (value/P&L need quantity).")
    return {"available": True, "holdings": holdings, "pages": pages, "sample": sample, "note": note}
