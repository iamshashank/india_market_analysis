"""Paid market-data API provider — SCAFFOLD, wired in the pipeline stage.

A single robust paid API is the most reliable path to clean, point-in-time
fundamentals (esp. for India) and is the best feed for the longitudinal moat.
Supported targets (pick one at wiring time):

  * Financial Modeling Prep (FMP)  — ``DATA_API_PROVIDER=fmp``  + ``FMP_API_KEY``
  * EOD Historical Data (EODHD)    — ``DATA_API_PROVIDER=eodhd`` + ``EODHD_API_KEY``

Until ``DATA_API_PROVIDER`` + the matching key are set, ``is_configured()`` is
False and the provider is skipped (Yahoo remains the fallback).
"""

from __future__ import annotations

import os
from typing import Optional

from data.providers.base import DataProvider


class PaidAPIProvider(DataProvider):
    name = "paid_api"
    markets = ("IN", "BSE", "US")
    provides = ("fundamentals", "quote")

    def __init__(self) -> None:
        self.vendor = os.environ.get("DATA_API_PROVIDER", "").strip().lower()
        self.key = (os.environ.get("FMP_API_KEY") if self.vendor == "fmp"
                    else os.environ.get("EODHD_API_KEY") if self.vendor == "eodhd"
                    else None)

    def is_configured(self) -> bool:
        return bool(self.vendor) and bool(self.key)

    def fundamentals(self, ticker: str, meta: dict) -> Optional[dict]:
        # TODO(pipeline): call the selected vendor, map → fetch_one dict shape.
        return None
