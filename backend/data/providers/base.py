"""Provider interface.

A provider implements one or more *capabilities*. ``fundamentals`` is the only
required one; the rest (shareholding, insider/promoter activity, news) are
optional and default to ``None`` so partial providers compose cleanly.

Contract for ``fundamentals``: return a dict matching the shape produced by
``data.fundamentals.fetch_one`` (so the scoring layer is source-agnostic), or
``None``/``{"error": ...}`` when the source can't serve the ticker. Always be
fault-tolerant — never raise; one bad ticker must not abort a batch.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class DataProvider(ABC):
    name: str = "base"
    # markets this provider can serve ("IN", "BSE", "US"); empty = any.
    markets: tuple = ()
    # capabilities offered, e.g. ("fundamentals", "shareholding", "insider", "news")
    provides: tuple = ()

    def is_configured(self) -> bool:
        """True when the provider has what it needs to run (keys/cookies/etc.).
        Scaffolded providers return False until configured via env."""
        return True

    def supports(self, market: str, capability: str) -> bool:
        market_ok = (not self.markets) or (market in self.markets)
        return market_ok and (capability in self.provides)

    # ---- capabilities (override what you support) ----
    @abstractmethod
    def fundamentals(self, ticker: str, meta: dict) -> Optional[dict]:
        ...

    def shareholding(self, ticker: str, meta: dict) -> Optional[dict]:
        """Promoter / FII / DII / public holding + pledging, when available."""
        return None

    def insider(self, ticker: str, meta: dict) -> Optional[dict]:
        """Insider / promoter buy-sell activity, when available."""
        return None

    def news(self, ticker: str, meta: dict) -> Optional[list]:
        return None
