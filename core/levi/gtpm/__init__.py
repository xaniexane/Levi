"""The flagship GTPM minds layer (Phase 2).

Working package name — **naming is Chauncey's**.

GTPM (Chauncey): "Basically analyzing but pure deterministic. I call it
goal targeted predator mentality." This package is the predator's build:
minds that lock a goal and pursue it with unfailing deterministic
analysis — no drift, no probabilistic wandering.

Components (each per its formal spec in ``~/workspace/levi-unified-build/``):

- :mod:`levi.gtpm.predicates` — the closed contact-predicate language.
- :mod:`levi.gtpm.scanmind` — the scan-mind: deterministic scan cycles
  over a frozen process image (the flagship GTPM mind, the reliable
  witness).
- :mod:`levi.gtpm.board` — the blackboard: coordination substrate for
  the multi-agentic loop (scan-mind as controller).
- :mod:`levi.gtpm.reflex` — the rule-reflex layer: Rete-compiled
  production rules, self-maintained by the growth loop (the honest
  rules-engine fallback, grown up).
- :mod:`levi.gtpm.words` — the dictionary: Forth-like threaded muscle
  language, grown by the SI, replayed bit-identically.
- :mod:`levi.gtpm.flagship` — the flagship demo: scan-mind + blackboard
  + rule-reflex running one task.
- :mod:`levi.gtpm.adapters` — thin adapters over Phase 1's synthesis
  interfaces. The beginning team owns ``core/levi/synthesis/*``; this
  package never edits their files.

Laws: stdlib-only at import; zero required network at runtime; no
sentience or subjective-experience claims; finance paper/simulated-only;
cyber defensive-only; dynasty/canon/IP materials eyes-only.
"""

from __future__ import annotations

ORIGIN = "levi-gtpm"

__all__ = [
    "ORIGIN",
    "predicates",
    "scanmind",
    "board",
    "reflex",
    "words",
    "flagship",
    "adapters",
]
