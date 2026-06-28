"""Versioned, curated strategy definitions — the proprietary core.

A ``Strategy`` bundles three things:
  * ``weights``            — the composite pillar weights (what ranks names),
  * ``compounder_pillars`` — the long-term wealth lens (own-for-years quality),
  * ``catalyst_pillars``   — the near-term entry-timing lens (news + momentum).

Versions are registered here and selected via the ``STRATEGY_VERSION`` env var
(default ``core-v1`` = original V1 behaviour). This lets you curate your own
variants and A/B them on the accumulating point-in-time data without touching
the scoring code — every snapshot is stamped with the version that produced it,
so each can be backtested independently.

To add a strategy: define a ``Strategy`` and ``register`` it (or append to the
defaults below), then set ``STRATEGY_VERSION`` to its version string.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

from core.config import WEIGHTS as _CFG_WEIGHTS


@dataclass(frozen=True)
class Strategy:
    version: str
    label: str
    description: str
    weights: Dict[str, float]              # composite pillar weights (sum ~1.0)
    compounder_pillars: Dict[str, float]   # long-term lens (pillar/momentum -> weight)
    catalyst_pillars: Dict[str, float]     # entry-timing lens
    min_score: float = 55.0


# ---- core-v1: the original V1 behaviour (default, no change) ---------------
CORE_V1 = Strategy(
    version="core-v1",
    label="Core Multibagger v1",
    description=("Original 7-pillar, size-neutral composite. Targets hidden "
                 "small/mid-cap compounders (small base + low coverage)."),
    weights=dict(_CFG_WEIGHTS),
    compounder_pillars={
        "room_to_grow": 0.18, "consistency": 0.24, "under_covered": 0.16,
        "growth": 0.18, "quality": 0.18, "valuation": 0.06,
    },
    catalyst_pillars={"catalyst": 0.6, "momentum": 0.4},
)

# ---- quality-compounder-v1: a demonstrator variant -------------------------
# Tilts toward proven, high-quality, consistent compounders and de-emphasises
# being undiscovered. Well-covered quality names (e.g. AIA Engineering) rank
# higher here than under core-v1 — illustrating why versioning matters.
QUALITY_COMPOUNDER_V1 = Strategy(
    version="quality-compounder-v1",
    label="Quality Compounder v1",
    description=("Tilts to proven, high-quality, consistent compounders; less "
                 "emphasis on being undiscovered. Surfaces well-known quality."),
    weights={
        "room_to_grow": 0.12, "consistency": 0.24, "under_covered": 0.06,
        "growth": 0.16, "quality": 0.22, "valuation": 0.10, "catalyst": 0.10,
    },
    compounder_pillars={
        "room_to_grow": 0.12, "consistency": 0.26, "under_covered": 0.06,
        "growth": 0.18, "quality": 0.28, "valuation": 0.10,
    },
    catalyst_pillars={"catalyst": 0.6, "momentum": 0.4},
)


_REGISTRY: Dict[str, Strategy] = {
    s.version: s for s in (CORE_V1, QUALITY_COMPOUNDER_V1)
}


def get(version: str) -> Strategy:
    return _REGISTRY.get(version) or CORE_V1


def active() -> Strategy:
    """The strategy selected by ``STRATEGY_VERSION`` (default core-v1)."""
    return get(os.environ.get("STRATEGY_VERSION", "core-v1"))


def register(strategy: Strategy) -> None:
    _REGISTRY[strategy.version] = strategy


def list_versions() -> List[dict]:
    return [{"version": s.version, "label": s.label, "description": s.description}
            for s in _REGISTRY.values()]
