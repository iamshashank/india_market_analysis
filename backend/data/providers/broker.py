"""Broker API provider (India) — SCAFFOLD, wired in the pipeline stage.

For reliable real-time India quotes, F&O and (your own) holdings where scraping
is too fragile. Targets:

  * Zerodha Kite — ``BROKER_PROVIDER=kite`` + ``KITE_API_KEY`` / ``KITE_ACCESS_TOKEN``
  * Groww        — ``BROKER_PROVIDER=groww`` + ``GROWW_API_KEY`` / token

Kite needs a daily access-token login flow; tokens are read from env / a
git-ignored file, never committed. ``is_configured()`` stays False until set,
so the provider is skipped and Yahoo remains the fallback.
"""

from __future__ import annotations

import os
from typing import Optional

from data.providers.base import DataProvider


class BrokerProvider(DataProvider):
    name = "broker"
    markets = ("IN", "BSE")
    provides = ("quote", "fundamentals")

    def __init__(self) -> None:
        self.vendor = os.environ.get("BROKER_PROVIDER", "").strip().lower()

    def is_configured(self) -> bool:
        if self.vendor == "kite":
            return bool(os.environ.get("KITE_API_KEY") and os.environ.get("KITE_ACCESS_TOKEN"))
        if self.vendor == "groww":
            return bool(os.environ.get("GROWW_API_KEY"))
        return False

    def fundamentals(self, ticker: str, meta: dict) -> Optional[dict]:
        # TODO(pipeline): brokers are quote/F&O-first; fundamentals optional.
        return None
