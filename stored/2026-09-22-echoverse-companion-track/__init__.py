"""Echoverse — the SFW companion track (KFX² workstream 2 of 13).

The clean, default, minor-friendly side of the companion lane. Echoverse
and Plaiground are NEVER merged — binding law, enforced in code by
:mod:`levi.echoverse.separation`, not in prose.

What this package is today (Phase 0 — the separation audit):
  separation — the binding-gate audit engine: static proof that Echoverse
               entry points never touch the adult surface, plus a
               prover/verifier pair and a runtime audit with the gate OFF.
  entry      — the minimal SFW entry points the audit proves clean
               (the seed the Phase 1-8 milestones grow on).
  themes     — structured Myspace-style theming: safe by construction,
               no raw HTML/JS injection, working everywhere.
  voyage     — the fated-outcome engine: a sealed destined end, a voyage
               walked beat by beat on taken / not-taken / wild branches,
               a journal of lived beats, earned rapport, arrival as the
               destination. Built on Chauncey's original concepts and
               naming (docs/ECHOVERSE_KFX2_PRODUCTION.md); the earlier
               "doom" engine's invented framing was struck by his word.

Zone law (Chauncey, 2026-09-21):
  - Echoverse is SFW, always. Plaiground is the adult track.
  - No adult surface in this package: no gate-flipping, no PIN handling,
    no adult content paths. There is nothing to PIN-gate here, so adult
    gating is N/A — the separation audit proves the negative.
  - Local-first, opt-in, stdlib-only, no network, no analytics, no ads,
    no accounts. 127.0.0.1-safe: nothing here binds or calls out.
  - Records live under ``~/.levi/echoverse/`` with mode 0600, like the
    rest of the organism.

Known Phase 0 boundary (honest): the seven shared engines in
``levi.plaiground`` (companions, chat, depth, simulator, stories,
wellness, photos) are today fully adult-gated — every public function
calls ``require_adult`` first. They are classified GATE-REQUIRED, not
SFW-usable, so no Echoverse entry point imports them. Giving those
engines SFW cores is Phase 1/2 work and needs existing-file edits, which
this workstream cannot do alone (new-files-only rule) — reported as a
follow-up gated on review.
"""

from __future__ import annotations

from levi.echoverse import entry, separation, themes, voyage

ZONE = "echoverse"
CLEAN_ZONE = "echoverse"
ADULT_ZONE = "plaiground"
TRACK = "si"

__all__ = [
    "ADULT_ZONE",
    "CLEAN_ZONE",
    "TRACK",
    "ZONE",
    "entry",
    "separation",
    "themes",
    "voyage",
]
