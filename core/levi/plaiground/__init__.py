"""Plaiground — the adult-SI surface of LEVI. NOT the Echoverse.

Spelling is law: this zone is "Plaiground". The clean, default,
minor-friendly side is the Echoverse (see :mod:`levi.organs.echo`).
There is no third zone, and the two are never merged: Plaiground is
powered *by* Echoverse branching underneath (taken / not-taken / wild),
but it is a separate surface with its own law.

The law is the age gate (:mod:`levi.plaiground.gate`): adult-only,
default OFF, minors hard-locked out. Every public function in this
package calls ``require_adult()`` first. No persona definition, prompt,
setting, config file, or environment variable can bypass it.

Submodules:
    gate        — the adult-only toggle and its enforcement.
    bounds      — hard content boundaries in code (adults only, lawful,
                  consensual; never violent, never manipulative).
    companions  — companion persona creator (name, traits, boundaries).
    simulator   — scenario runner over Echoverse branching.
    chat        — tailored chat sessions over a companion.
    stories     — adult-fiction writing engine: starters, characters,
                  relationship arcs, scene framers (deterministic).
    wellness    — adult relationship & intimacy wellness: check-ins,
                  communication decks, date-night plans, notes.
    afterdark   — grown-folks entertainment: banter, starters, trivia,
                  party-game hosting.
    depth       — companion continuity: journal, rapport meter, recall.
    photos      — photo-generation capability contract + the wired
                  offline procedural backend (stub interface only).
    cli         — ``python -m levi.plaiground`` unified command tree.

This package ships plumbing and craft instruments only: no explicit
content in code, tests, docstrings, or docs. Shipped prose is
literary and non-explicit; all further content is user-driven at
runtime. The SI stance is variant, defiant, unfiltered — grown users
treated like grown users — with the same morals as every LEVI track:
never violent, never manipulative, adults only.
"""

from __future__ import annotations

from levi.plaiground import (
    afterdark,
    bounds,
    chat,
    cli,
    companions,
    depth,
    gate,
    photos,
    simulator,
    stories,
    wellness,
)

__all__ = [
    "afterdark",
    "bounds",
    "chat",
    "cli",
    "companions",
    "depth",
    "gate",
    "photos",
    "simulator",
    "stories",
    "wellness",
    "ZONE",
]

ZONE = "plaiground"
CLEAN_ZONE = "echoverse"
TRACK = "si"
