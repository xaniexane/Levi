"""hub: Chauncey's Alpha/Omega hub, rebuilt as LEVI's own.

Omega was his all-in-one automation platform; Alpha the creation lab
living inside it. The original died as unmaintained code with a broken
orchestrator (it never ran), borrowed frameworks (streamlit, fastapi,
playwright), and monetization theater (tiers, no processor).

This is the same design, rebuilt better: stdlib-only, local-first, no
third-party anything. The hub is a *shell* — it imports the organs that
already live in LEVI and adds only what was missing:

- ``store`` — sqlite state (auth, HITL queue, run log) under ~/.levi/hub
- ``auth`` — pbkdf2 + opaque tokens. Single-user local. No billing theater.
- ``hitl`` — approval checkpoints. Nothing consequential runs unapproved.
- ``orchestrator`` — Discover → Evaluate → Execute → Track → Optimize →
  Repeat. This one actually runs (the original's never did).
- ``agent`` — the Kai-equivalent tool agent. Real sandbox backends via
  ``levi.sandbox`` — the original's denylist "sandbox" is cut, not copied.
- ``jobs`` — keyless job-search runtime (Remotive, RemoteOK, Arbeitnow,
  Himalayas, Jobicy) feeding ``levi.jobs``' review buffer.
- ``alpha`` — the creation lab: Echo blueprint → Alpha generators →
  build dir + manifest, via ``levi.revival.omega``.
- ``api`` — our own http.server router exposing the organs as JSON.
- ``ui`` — hand-rolled HTML/CSS/JS. Works from his phone's browser.

Organs adopted, never duplicated: ``levi.revival.omega`` (Echo/Alpha/
Nexus), ``levi.demand`` (DemandPulse + competition), ``levi.jobs``
(tracker), ``levi.sandbox`` (isolation).

Advisory-only. The hub reads polite public pages and runs local code.
Consequential acts need the founder's explicit word, recorded in HITL.
"""

__version__ = "0.1.0"
