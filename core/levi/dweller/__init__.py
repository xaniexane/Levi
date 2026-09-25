"""LEVI Dweller — purgatory-dweller, a Leviathan-class beast of the in-between.

Chauncey's correction (2026-09-17): the Dweller is not a mere labor
powerhouse. It dwells in LEVI's purgatory — the liminal space of Nexus
dead letters, REIM/RIEM compost heaps, denied HITL gates, fog
fail-closed verdicts, and unborn concepts — and tends it. Vast,
patient, at home in the depths between the birth and death of
processes. Its labor IS purgatory-tending: the grind job queue is the
Dweller's tending labor in the depths, not generic background work.

Laws:

- The Dweller never acts on the world beyond its sandbox root without
  explicit permission. Runners are read-only by construction and use no
  network — a runner that needs the network does not exist.
- Re-driving anything from purgatory passes the permission gate; a
  denied gate ends the rite cleanly. Releasing anything writes a
  receipt — nothing leaves purgatory silently.
- Every job and every rite ends with a receipt — including refused,
  denied, and failed ones. No silent deaths.
- Jobs are resumable: a failed job can be resumed and continues from
  its first incomplete step.
- The purgatory ledger is honest: an unreadable source is reported as
  unreachable, never fabricated.

Layout:

- :mod:`levi.dweller.charter` — the Dweller's charter (Leviathan-class)
- :mod:`levi.dweller.purgatory` — the ledger of the waiting (five realms)
- :mod:`levi.dweller.tend` — tending rites: compost review, re-drive,
  release, unborn watch
- :mod:`levi.dweller.jobs` — the Job data model and state machine
- :mod:`levi.dweller.queue` — persistent journaled queue (~/.levi/dweller)
- :mod:`levi.dweller.runners` — built-in tending-labor kinds (repo-sweep,
  crossref, watch), hermetic, no network
- :mod:`levi.dweller.si` — the native SI core (the tending engine)
- :mod:`levi.dweller.ai` — AI counterpart bridge (conventional-protocol
  interface only; the SI core is authoritative)
- :mod:`levi.dweller.cli` — ``levi dweller`` command wiring
"""

from __future__ import annotations

from . import charter
from .jobs import Job, JobStep, new_job
from .queue import dweller_home

__all__ = ["Job", "JobStep", "charter", "new_job", "dweller_home"]
