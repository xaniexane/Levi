"""LEVI OS v0.1 — the always-on OS layer. Chat is a client of the daemon,
not vice versa (Chauncey's canon).

.. note::
    Provisional module name — Chauncey's word on the final name later.
    ``levi.os`` never shadows the stdlib: every import inside this package
    is absolute, so ``import os`` still resolves to the standard library.

LAWS (invariants, guarded in code, proven in tests/test_levi_os.py):

1. Every plan step is backed by a real pool skill, or planning fails
   loudly — no invented steps.
2. No step executes without a receipt. Receipts are hash-chained,
   genesis-anchored, and verifiable end-to-end.
3. The memory/context path is network-free — machine-checked by a guard
   test that blocks all sockets, not asserted.
4. Held files are untouched: ``core/levi/model/abstraction.py`` and
   ``core/levi/model/ministral_cloud.py``. The provider seam documents
   where it will plug in; it never edits them.
5. Devices are honest: steps route only to devices with declared
   capabilities; stubbed surfaces are labeled stubbed.

ORIGIN LINEAGE (originals-first): daemon-as-OS-layer from docs/DAEMON.md
and core/levi/daemon/ (foreground supervisor; chat is a client);
Alpha-builds / Omega-executes from core/levi/alpha/ and
core/levi/revival/omega/; receipt chain convention from
core/levi/mood/receipts.py; skills from the Legion shared pool
(core/levi/legion/skill_pool/).
"""

from __future__ import annotations

from levi.os.client import ChatClient
from levi.os.devices import (
    Device,
    builtin_devices,
    enumerate_devices,
    required_capabilities,
    route_step,
)
from levi.os.outcome import (
    DEFAULT_RANK,
    OSPlanError,
    Plan,
    PlanStep,
    state_outcome,
)
from levi.os.provider import (
    OSContext,
    LocalRulesProvider,
    ModelProvider,
    swap_provider,
)
from levi.os.receipts import (
    GENESIS_HEAD,
    Receipt,
    ReceiptWriter,
    os_dir,
    verify,
)
from levi.os.runner import RunReport, execute

__all__ = [
    "ChatClient",
    "DEFAULT_RANK",
    "Device",
    "GENESIS_HEAD",
    "LocalRulesProvider",
    "ModelProvider",
    "OSContext",
    "OSPlanError",
    "Plan",
    "PlanStep",
    "Receipt",
    "ReceiptWriter",
    "RunReport",
    "builtin_devices",
    "enumerate_devices",
    "execute",
    "os_dir",
    "required_capabilities",
    "route_step",
    "state_outcome",
    "swap_provider",
    "verify",
]
