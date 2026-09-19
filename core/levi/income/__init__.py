"""Income Factory — economic execution capability (one subsystem, not LEVI's purpose).

Also hosts the income portfolio engine: the 100-slot generator registry
(``levi.income.engine``) — automated income generators, 70/30 split, the
reinvestment pool, Cybrus-gateway-only money paths.
"""

from __future__ import annotations

from levi.income.factory import IncomeFactory

__all__ = ["IncomeFactory"]
