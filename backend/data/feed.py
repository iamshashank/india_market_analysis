"""Data feed — the single front door for fundamentals.

Routes each fetch through the provider registry (best configured source, Yahoo
fallback) and snapshots the batch into the point-in-time cache (the moat). The
screener and analyzer call this instead of yfinance directly, so swapping /
adding data sources never touches the scoring layer.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from core.config import FETCH_WORKERS
from core import data_cache
from data.providers import registry
from data.universe import UNIVERSE


def fetch_one(ticker: str, meta: dict) -> dict:
    """Fundamentals for one ticker via the best configured provider."""
    data = registry.fundamentals(ticker, meta)
    if data is None:
        return {"ticker": ticker, "name": meta.get("name", ticker),
                "market": meta.get("market", "US"),
                "currency": meta.get("currency", "USD"),
                "error": "no data from any provider"}
    return data


def fetch_universe(universe: Optional[Dict[str, dict]] = None,
                   workers: int = FETCH_WORKERS, snapshot: bool = True) -> List[dict]:
    """Fetch a whole universe in parallel; snapshot the result point-in-time.

    ``snapshot=False`` for transient context fetches (e.g. the single-stock
    analyzer) so we don't write redundant rows.
    """
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
                row = fut.result()
            except Exception as exc:  # noqa: BLE001
                row = {"ticker": tk, "name": tk, "error": str(exc)}
            src = row.get("_source", "")
            flag = "  (FAILED)" if row.get("error") else (f"  [{src}]" if src else "")
            print(f"  [{done:>2}/{total}] {tk:<16}{flag}")
            rows.append(row)

    if snapshot:
        try:
            data_cache.snapshot(rows)
        except Exception:  # noqa: BLE001
            pass
    return rows
