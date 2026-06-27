"""Yahoo Finance provider — the default, always-available source.

Wraps the existing, battle-tested ``data.fundamentals.fetch_one`` so behaviour
is identical to V1. It's the universal fallback: configured everywhere, every
market, so the screen always has data even when richer providers are offline.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from data.providers.base import DataProvider


class YahooProvider(DataProvider):
    name = "yahoo"
    markets = ("IN", "BSE", "US")
    provides = ("fundamentals", "quote")

    def is_configured(self) -> bool:
        return True

    def fundamentals(self, ticker: str, meta: dict) -> Optional[dict]:
        from data.fundamentals import fetch_one
        f = fetch_one(ticker, meta)
        d = asdict(f)
        d["_source"] = self.name
        return d
