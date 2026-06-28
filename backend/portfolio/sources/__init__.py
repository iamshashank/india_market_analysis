"""Holdings-source interface (live broker connectors)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class HoldingsSource(ABC):
    name = "base"

    def is_configured(self) -> bool:
        return False

    @abstractmethod
    def holdings(self) -> List[dict]:
        """Return live equity holdings as [{symbol, quantity, avg_price, broker, market}]."""
        ...
