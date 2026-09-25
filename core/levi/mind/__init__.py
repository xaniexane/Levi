"""``levi.mind`` — the runner interface for LEVI's native brain (BRAINUX workstream).

One organism, not a pipe: ``python -m levi.mind start`` wakes the runner,
``stop`` puts it down, ``status`` reports its state honestly, ``guard``
shows the offline-mandatory verdict before anything moves.

KFX² shapes baked in:
- Ternary guard verdicts: ``local`` / ``refused`` / ``uncertain`` — the
  skipped third state is ``uncertain`` (can't verify → fail closed, with
  a named reason, not a silent refusal and not an assumed go).
- Ternary daemon states: ``running`` / ``stopped`` / ``stale`` — a pidfile
  with no living process is reported as its own state instead of being
  rounded into either of the binary ones.
- Paired mind: start is a proposer/verifier pair (request → guard verdict
  → only then spawn); ``status`` only calls the daemon ``running`` when
  two independent records — the pidfile AND the worker's heartbeat — agree.
- Local is law: the guard refuses to start with any network inference
  path enabled. No telemetry, no accounts, no cloud door exists in this
  package. Nothing phones home; there is no code path that could.

Config lives at ``~/.levi/mind/`` (override with ``LEVI_MIND_HOME``).
Stdlib only. Deterministic where it counts (atomic state writes).
"""
