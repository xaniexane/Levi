"""LEVI UniForge — the forge that unifies HYBRID builds.

UniForge is a named system in Chauncey's recovered Drive/OneDrive corpus
(``UniForge_Hybrid_Pro.py``, ``UniForge_Prime_Founder.py`` in the Drive
inventory). Those originals are not accessible — Drive access is revoked
and no local copy exists — so this module claims nothing about their
contents. It is built from the name and the role alone, LEVI-native and
original: **one build plan across heterogeneous targets**.

A forge run assembles steps for each requested target (python package,
static site, android apk scaffold), then walks the standing law:

    Plan -> Preview -> Permission -> Execute -> Verify -> Receipt

Dry-run is the default: preview shows every step and nothing executes.
A target whose tools are absent refuses cleanly with a receipt naming
what is missing — UniForge never fakes a build.

Layout:

- :mod:`levi.uniforge.plan` — the :class:`BuildPlan` data model
- :mod:`levi.uniforge.targets` — target definitions and tool declarations
- :mod:`levi.uniforge.si` — the native SI core (planner + executor)
- :mod:`levi.uniforge.ai` — AI counterpart bridge (conventional-protocol
  interface only; the SI core is authoritative)
- :mod:`levi.uniforge.cli` — ``levi uniforge`` command wiring
- :mod:`levi.uniforge.surgeon` — the code-surgeon instruments (forensics,
  emergency error response, code refinement): a faithful Python port of
  the Omega Triple Threat Elite Acode plugin's surgeon/converter logic,
  plus diagnose -> fix -> verify. The Acode plugin is the phone-side
  field instrument; this module is the deep instrument.
"""

from __future__ import annotations

from .plan import BuildPlan, Step
from .surgeon import diagnose, operate, quick_cleanup, stamp_header, surgeon_file
from .targets import TARGETS, target_ids

__all__ = [
    "BuildPlan",
    "Step",
    "TARGETS",
    "target_ids",
    "diagnose",
    "operate",
    "quick_cleanup",
    "stamp_header",
    "surgeon_file",
]
