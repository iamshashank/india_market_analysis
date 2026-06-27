"""Pluggable market-data providers.

A thin abstraction so the screen can draw fundamentals / shareholding / insider
data from the best available source per market, with graceful fallback to
Yahoo. Today only Yahoo is active; Moneycontrol, a paid API (FMP/EODHD) and a
broker (Kite/Groww) are scaffolded and become live once configured via env
(planned for the data-pipeline stage).

Use ``data.feed`` as the front door — it routes through ``registry`` and writes
a point-in-time snapshot to ``core.data_cache`` (the longitudinal data moat).
"""

from __future__ import annotations
