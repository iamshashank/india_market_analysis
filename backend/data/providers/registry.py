"""Provider registry + router.

Picks the best *configured* provider per market for a capability, always with
Yahoo as the final fallback. Today only Yahoo is configured, so behaviour equals
V1; as Moneycontrol / paid-API / broker come online they slot in ahead of Yahoo
for the markets they serve — no change needed in the scoring layer.
"""

from __future__ import annotations

from typing import List, Optional

from data.providers.base import DataProvider
from data.providers.yahoo import YahooProvider
from data.providers.moneycontrol import MoneycontrolProvider
from data.providers.paid_api import PaidAPIProvider
from data.providers.broker import BrokerProvider

_PROVIDERS: Optional[List[DataProvider]] = None

# Preference order per market (first configured wins; Yahoo always last = fallback).
_PREFERENCE = {
    "IN": ("moneycontrol", "paid_api", "broker", "yahoo"),
    "BSE": ("moneycontrol", "paid_api", "broker", "yahoo"),
    "US": ("paid_api", "yahoo"),
}


def providers() -> List[DataProvider]:
    global _PROVIDERS
    if _PROVIDERS is None:
        _PROVIDERS = [YahooProvider(), MoneycontrolProvider(),
                      PaidAPIProvider(), BrokerProvider()]
    return _PROVIDERS


def _chain(market: str, capability: str) -> List[DataProvider]:
    by_name = {p.name: p for p in providers()}
    order = _PREFERENCE.get(market, ("paid_api", "yahoo"))
    chain = [by_name[n] for n in order if n in by_name]
    # any other provider that supports this market/capability, then ensure yahoo
    for p in providers():
        if p not in chain and p.supports(market, capability):
            chain.append(p)
    return [p for p in chain if p.supports(market, capability)]


def active_sources() -> List[str]:
    """Names of providers currently configured (for diagnostics/UI)."""
    return [p.name for p in providers() if p.is_configured()]


def fundamentals(ticker: str, meta: dict) -> Optional[dict]:
    """Return a fundamentals dict from the best configured source (+ ``_source``).
    Falls back through the chain; Yahoo is always the last resort."""
    market = meta.get("market", "US")
    base: Optional[dict] = None
    for p in _chain(market, "fundamentals"):
        if not p.is_configured():
            continue
        try:
            data = p.fundamentals(ticker, meta)
        except Exception:  # noqa: BLE001 — never let one provider break the batch
            data = None
        if data and data.get("price") and not data.get("error"):
            data.setdefault("_source", p.name)
            base = data
            break
    if base is not None:
        _enrich(base, ticker, meta, market)
    return base


def _enrich(base: dict, ticker: str, meta: dict, market: str) -> None:
    """Attach optional shareholding / insider data from any configured provider
    that offers it (no-op until MC/broker are wired)."""
    for cap, key in (("shareholding", "shareholding"), ("insider", "insider")):
        for p in _chain(market, cap):
            if not p.is_configured():
                continue
            try:
                extra = getattr(p, cap)(ticker, meta)
            except Exception:  # noqa: BLE001
                extra = None
            if extra:
                base[key] = extra
                base.setdefault("_enriched", []).append(f"{p.name}:{cap}")
                break
