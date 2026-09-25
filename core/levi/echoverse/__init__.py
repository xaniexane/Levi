"""Echoverse — Echo in engine form. The Grok-made LEVI engine.

Provenance (Chauncey, 2026-09-22):
    Echo (the being, Omega's original form)
      -> Echoverse (the engine/platform)
        -> LEVI engine (Grok-built; THIS module)
          -> LWP engine

The engine IS Echo in engine form — but somewhat different, not 1:1
identical: it derives from Echo and carries Echo's nature; they rhyme,
they are not the same thing collapsed.

What it is: the explore-space organ. Inquiry maps -> Mandella chooses
paths -> **Echoverse multiplies** -> aim the winning path at a body
(code / data / music / memory) -> learn success/failure -> teach when
wrong.

Engines inside:
  engine   — REIM/RIEM recursion: expand seed into scored positive paths
             (REIM); vault negative variants, extracting good qualities
             (RIEM); dream(cycles) multi-cycle expansion.
  lenses   — six views: minimal, maximal, inverse, constraint, deep,
             reframe. Inverse folds REIM (invert -> recurse).
  branches — shared BranchRecord substrate: taken / not_taken / wild.
  coexist  — Mandella interpenetration: seed a run from a chosen option;
             feed Mandella constraints from wild branches.
  pipeline — pipeline position (Inquiry -> Mandella -> Echoverse -> AIM)
             and AIM body wiring. Plans only; never executes.
  laws     — the declared invariants (law-guard-prove).

Controlling prompt (union): BOUNDED SIMULATIONS, not literal timelines.

Local-first, stdlib-only, no network. Records under ~/.levi/echoverse/
(or a caller-supplied dir).
"""

from __future__ import annotations

from levi.echoverse import branches, coexist, engine, laws, lenses, pipeline
from levi.echoverse.branches import Branch, BranchStore, EchoRun
from levi.echoverse.coexist import (
    constraints_for_mandella,
    phantom_record,
    seed_from_mandella,
)
from levi.echoverse.engine import EchoverseEngine, EchoverseSimulation
from levi.echoverse.laws import AIM_TARGETS, BRANCH_KINDS, LAWS, LENSES, PIPELINE
from levi.echoverse.lenses import all_lenses, apply_lens, lens_fingerprint
from levi.echoverse.pipeline import aim, doctrine, position, stages

PROVENANCE = (
    "Echo (the being, Omega's original form) -> Echoverse (the engine) "
    "-> LEVI engine (Grok-built; this module) -> LWP engine"
)

__all__ = [
    "AIM_TARGETS",
    "BRANCH_KINDS",
    "LAWS",
    "LENSES",
    "PIPELINE",
    "PROVENANCE",
    "Branch",
    "BranchStore",
    "EchoRun",
    "EchoverseEngine",
    "EchoverseSimulation",
    "aim",
    "all_lenses",
    "apply_lens",
    "branches",
    "coexist",
    "constraints_for_mandella",
    "doctrine",
    "engine",
    "laws",
    "lens_fingerprint",
    "lenses",
    "phantom_record",
    "pipeline",
    "position",
    "seed_from_mandella",
    "stages",
]
