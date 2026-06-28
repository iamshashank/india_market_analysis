"""Zerodha Kite live holdings — activated when you add your own keys.

Setup (when ready): create a Kite Connect app (kite.trade) for your API key +
secret, run the daily login to get an access token, then set ``KITE_API_KEY``
and ``KITE_ACCESS_TOKEN`` in a git-ignored .env and ``pip install kiteconnect``.
Until then this source is inert. Never paste keys/tokens into chat — local .env only.
"""

from __future__ import annotations

import os
from typing import List

from portfolio.sources import HoldingsSource


class KiteSource(HoldingsSource):
    name = "Zerodha"

    def is_configured(self) -> bool:
        return bool(os.environ.get("KITE_API_KEY") and os.environ.get("KITE_ACCESS_TOKEN"))

    def holdings(self) -> List[dict]:
        if not self.is_configured():
            return []
        try:
            from kiteconnect import KiteConnect  # lazy
            kite = KiteConnect(api_key=os.environ["KITE_API_KEY"])
            kite.set_access_token(os.environ["KITE_ACCESS_TOKEN"])
            raw = kite.holdings() or []
        except Exception as e:  # noqa: BLE001
            print(f"[kite] holdings fetch failed: {e}")
            return []
        out = []
        for h in raw:
            sym = h.get("tradingsymbol")
            if not sym:
                continue
            out.append({"symbol": sym, "quantity": h.get("quantity"),
                        "avg_price": h.get("average_price"),
                        "broker": "Zerodha", "market": "IN"})
        return out
