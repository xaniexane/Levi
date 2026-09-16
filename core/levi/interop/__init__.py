"""LEVI interpenetration glue.

Interpenetration is a binding law of the LEVI organism: modules compose
through a shared substrate with **strictest-risk-ceiling inheritance** —
when several modules participate in one composed action, the whole
composition is governed by the highest risk level among the participants.
Never the average, never the lowest.

This package is the wiring, not the organs:

- :mod:`levi.interop.risks` — strictest-risk-ceiling composition.
- :mod:`levi.interop.manifest` — static capability declarations for modules
  that cannot (or must not) be edited to declare their own.
- :mod:`levi.interop.registry` — capability registry; deny-closed validation
  of ``provides``/``requires`` wiring.
- :mod:`levi.interop.adapters` — pure connection functions between modules
  (assistant ↔ retrieval, bot ↔ rag, growth ↔ bot queue, academy → memory,
  bounty → knowledge).

Rules every adapter follows:

1. **Lazy imports everywhere.** Nothing in this package imports a sibling
   LEVI module at module-import time; connections are resolved when the
   function is called.
2. **Honest degradation.** When a connected module is unavailable, the
   adapter returns an explicit "unavailable" result. Data is never invented.
3. **Additive only.** Adapters never monkeypatch or edit the modules they
   connect; they sit beside them.
"""
