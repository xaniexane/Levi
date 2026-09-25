"""levi.si: the assembled offline-first SI.

One coherent synthetic intelligence built only from design elements
Chauncey ruled reachable, foundation-first, maximum agency, zero network.

The assembly, in turn order (see ``levi.si.turn.run_turn``):

1. **Honest boundary** — every turn declares whether it can do the task
   honestly now or whether the task needs more training / live data.
   Standing law (Chauncey, 2026-09-22): the boundary is "can do now"
   vs. "needs more training" — never faked. Uncertainty resolves toward
   honesty, never toward faking.
2. **Judgment-based refusal** — the SI refuses only on its own better
   judgment, when the act would be more harmful than helpful (his
   doctrine, 2026-09-22). No policy lists, no topic bans. A refusal
   names the specific foreseeable harm in plain words and what would
   change the judgment.
3. **Deliberation** — propose -> critique -> verdict on the rules engine
   (``levi.alpha.si.deliberation``). The verdict always states which
   substrate reasoned.
4. **Native brain voice** — ``levi-native`` weights are exercised
   explicitly through ``levi.brain.runtime``: heard, never obeyed, never
   the verdict winner. When the brain cannot run, the turn says so and
   continues rules-only.
5. **Local memory** — the turn is recorded in the local memory store.
   Nothing leaves the machine.

Laws this package runs under:

- Offline-first: no network calls in the core path, proven by the
  blocked-network test (``tests/test_si_offline.py``).
- No external provider is ever seated ("None — I'm fully training it.",
  Chauncey 2026-09-22).
- SI and AI stores stay separate; this package never imports ``ai/``.
- Nothing here claims brain reasoning it didn't do, frontier fluency it
  doesn't have, or live knowledge it can't reach.
"""

from __future__ import annotations

ORIGIN = "levi/si"

__all__ = ["ORIGIN"]
