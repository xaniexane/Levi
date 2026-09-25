"""Eden — the forbidden-zone experimental sandbox (Execution Layer organ).

Canon: Eden is the forbidden-zone experiments organ of the SER
architecture, attested in the founder corpus alongside GenEX (ledger),
SupraStreet (commerce), Vector (sandbox), and the Execution Layer
table. Revived as docs-level only in the dead-software inventory
(§16); confirmed still absent from the tree by the 2026-09-22 hunt
audit.

LEVI-native build from scratch. It is NOT :mod:`core.levi.sandbox`
(the general sandbox runner): Eden is the *forbidden zone* — a
quarantined experimental area with explicit zones, containment, and
clearance semantics. Experiments run inside a zone; nothing leaves a
zone without recorded clearance; every run writes a receipt.

Law (declared up front; tests are the proof):
1. CONTAINMENT — all writes during a run land inside the zone's root
   directory. Absolute-path and ``..`` escapes are refused.
2. QUARANTINE BY DEFAULT — a run's outputs are quarantined; release
   requires an explicit ``clear`` call recording who authorized it.
3. RECEIPTS — every run writes a sealed run receipt (ok/failed,
   outputs, clearance state). A run without a receipt didn't happen.
4. ISOLATION — zones are disjoint; one zone's runs cannot read or
   write another zone's root.

Stdlib only. Runs execute plain Python callables inside the zone
context — no subprocesses, no network.
"""

from .zone import ClearanceError, Eden, EdenRun, EdenZone, ZoneError

__all__ = ["Eden", "EdenZone", "EdenRun", "ZoneError", "ClearanceError"]
