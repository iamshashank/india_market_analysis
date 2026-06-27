"""Moneycontrol provider (India) — SCAFFOLD, wired in the pipeline stage.

Why it matters: Moneycontrol has far cleaner Indian fundamentals than Yahoo —
consolidated & standalone financials, quarterly results, ratios, shareholding
pattern, promoter pledging, and broker calls. This is the primary India unlock.

Auth options (finalised at wiring time; nothing is stored in code):
  1. PUBLIC JSON endpoints (no login) — priceapi.moneycontrol.com and the
     financials/shareholding widget APIs cover most data. Default approach.
  2. PRO session cookie — set ``MC_COOKIE`` in a git-ignored .env to unlock
     Pro-gated research/screeners.
  3. Headless login (Playwright) — auto-refresh cookies from ``MC_USER`` /
     ``MC_PASS``. Heaviest; only if needed.

Enable by setting ``MC_ENABLED=1`` (+ optional ``MC_COOKIE``). Until then this
provider reports ``is_configured() == False`` and is skipped, so the screen
falls back to Yahoo with zero behaviour change.
"""

from __future__ import annotations

import os
from typing import Optional

from data.providers.base import DataProvider


class MoneycontrolProvider(DataProvider):
    name = "moneycontrol"
    markets = ("IN", "BSE")
    provides = ("fundamentals", "shareholding", "insider", "news")

    def is_configured(self) -> bool:
        return os.environ.get("MC_ENABLED", "0") in ("1", "true", "True")

    # --- to implement in the pipeline stage ---
    def fundamentals(self, ticker: str, meta: dict) -> Optional[dict]:
        # TODO(pipeline): map MC financials/ratios → the fetch_one dict shape.
        return None

    def shareholding(self, ticker: str, meta: dict) -> Optional[dict]:
        # TODO(pipeline): promoter / FII / DII / public % + pledging trend.
        return None

    def insider(self, ticker: str, meta: dict) -> Optional[dict]:
        # TODO(pipeline): insider/promoter buy-sell from MC.
        return None
