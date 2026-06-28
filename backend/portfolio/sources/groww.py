"""Groww live holdings (own + imported) — activated when you add your access token.

Setup: https://groww.in/trade-api/docs/python-sdk

TOTP Flow (Recommended - no daily approval):
  1. Go to https://groww.in/trade-api/api-keys → Generate TOTP token
  2. Copy TOTP_TOKEN and TOTP_SECRET
  3. Add to .env: GROWW_AUTH_METHOD=totp, GROWW_TOTP_TOKEN=..., GROWW_TOTP_SECRET=...

API Key Flow (requires daily approval):
  1. Go to https://groww.in/trade-api/api-keys → Generate API key
  2. Copy API_KEY and API_SECRET
  3. Add to .env: GROWW_AUTH_METHOD=apikey, GROWW_API_KEY=..., GROWW_API_SECRET=...

Never paste tokens in chat — only in local .env file.
"""

from __future__ import annotations

import os
from typing import List

from portfolio.sources import HoldingsSource


class GrowwSource(HoldingsSource):
    name = "Groww"

    def is_configured(self) -> bool:
        auth_method = os.environ.get("GROWW_AUTH_METHOD", "").lower()
        if auth_method == "totp":
            return bool(os.environ.get("GROWW_TOTP_TOKEN"))
        elif auth_method == "apikey":
            return bool(os.environ.get("GROWW_API_KEY"))
        return False

    def _get_access_token(self) -> str | None:
        """Generate access token using configured auth method."""
        try:
            from growwapi import GrowwAPI
            import pyotp
        except ImportError:
            print("[groww] growwapi or pyotp not installed")
            return None

        auth_method = os.environ.get("GROWW_AUTH_METHOD", "").lower()

        if auth_method == "totp":
            totp_token = os.environ.get("GROWW_TOTP_TOKEN")
            totp_secret = os.environ.get("GROWW_TOTP_SECRET")
            if not (totp_token and totp_secret):
                return None
            try:
                totp_gen = pyotp.TOTP(totp_secret)
                totp = totp_gen.now()
                access_token = GrowwAPI.get_access_token(api_key=totp_token, totp=totp)
                return access_token
            except Exception as e:
                print(f"[groww] TOTP auth failed: {e}")
                return None

        elif auth_method == "apikey":
            api_key = os.environ.get("GROWW_API_KEY")
            api_secret = os.environ.get("GROWW_API_SECRET")
            if not (api_key and api_secret):
                return None
            try:
                access_token = GrowwAPI.get_access_token(api_key=api_key, secret=api_secret)
                return access_token
            except Exception as e:
                print(f"[groww] API key auth failed: {e}")
                return None

        return None

    def holdings(self) -> List[dict]:
        if not self.is_configured():
            return []

        try:
            from growwapi import GrowwAPI
        except ImportError:
            print("[groww] growwapi not installed")
            return []

        access_token = self._get_access_token()
        if not access_token:
            print("[groww] failed to get access token")
            return []

        try:
            api = GrowwAPI(access_token)
            out = []

            # Fetch all holdings (own + imported)
            try:
                raw = api.get_holdings_for_user() or []
                holdings_list = raw.get("holdings", raw) if isinstance(raw, dict) else raw
                
                for h in holdings_list:
                    sym = h.get("trading_symbol") or h.get("tradingsymbol") or h.get("symbol")
                    if not sym:
                        continue
                    out.append({
                        "symbol": sym, "quantity": h.get("quantity"),
                        "avg_price": h.get("average_price") or h.get("avg_price") or h.get("averagePrice"),
                        "broker": "Groww", "market": "IN"
                    })
            except Exception as e:
                print(f"[groww] holdings fetch failed: {e}")

            return out
        except Exception as e:  # noqa: BLE001
            print(f"[groww] API initialization failed: {e}")
            return []

