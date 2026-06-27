"""Back-compat shim for the next-day predictor's persistence.

Historically this module spoke to Postgres directly. Persistence now lives in
``store.py`` (MySQL with a local-JSON fallback); these helpers just delegate so
existing callers (web.py, cron_refresh.py) keep working unchanged.
"""

from __future__ import annotations

from typing import Any, Optional

from core import store

PREMARKET_KEY = "premarket_latest"


def is_enabled() -> bool:
    return store.is_enabled()


def init_db() -> bool:
    return store.is_enabled()


def save(data: Any, key: str = PREMARKET_KEY) -> bool:
    return store.save(data, key)


def load(key: str = PREMARKET_KEY) -> Optional[Any]:
    return store.load(key)
