"""Sidewinder course — Chauncey's universal applied-knowledge course.

His words: "how to build, create, improve, restore, combine and improvise
anything for anything — a big course just about everything known to mankind
this far, how to fix anything even without proper equipment."

Six tracks; every entry is tagged with at least one:

* BUILD      — make it from scratch, raw stock to finished thing.
* CREATE     — design new things, turn a need into a plan.
* IMPROVE    — upgrade and optimize what already exists.
* RESTORE    — repair and refurbish, bring it back to working.
* COMBINE    — hybridize and repurpose parts and ideas into new wholes.
* IMPROVISE  — no proper equipment. The Sidewinder doctrine is this
  track's core: diagnose the mechanism first, then improvise tools from
  whatever is on hand.

A foundations spine comes first (how things work: mechanical advantage,
materials, joining, measurement, cutting, safety) — entries are leveled
foundation -> applied -> mastery, with prerequisites as entry-id links
forming real progressions. ``curriculum/progressions.py`` serves them in
order; ``levi course <track|topic>`` is the query path.

Two packages below this one keep the course and its delivery distinct:

* ``curriculum/`` — the COURSE: training curriculum (content that trains
  agents — schema, corpus, progressions, manifest-driven edition packs,
  growth pipeline).
* ``platform/`` — the PLATFORM: infrastructure that delivers it
  (query API, team scoping, team learning loop). The CLI, the
  shared-core skills, and agent teams consume the platform API.

Crisis/emergency improvisation is a first-class domain of the IMPROVISE
track — the "save a life with what's on hand" standard (Chauncey's
example: doctors improvising medical equipment on whim to save a life).
The ethos is named in the doctrine below: improvise like lives depend on
it, because in this domain they do. Non-negotiable law of the crisis
domain: professional help FIRST, always — improvisation is last resort
when no help or equipment is coming. Every crisis entry carries an
explicit call-for-help-first stop condition plus do-not-attempt
conditions. The method has to be worth betting a life on, or it doesn't
ship.

Honest scoping: this is a growing corpus driving toward comprehensive
coverage, not a claim of literal omniscience. Lawful DIY only; standard
wilderness/first-aid improvisation only — no DIY surgery, ever.

Shared-core capability: LEVI and every wave agent inheriting the DNA core
get the whole course through this module, the ``levi sidewinder`` /
``levi course`` commands, and the fieldcraft skills in ``skills.py``.
"""

from __future__ import annotations

TRACKS = ("build", "create", "improve", "restore", "combine", "improvise")

TRACK_DESCRIPTIONS = {
    "build": "Make it from scratch — raw stock to finished thing.",
    "create": "Design new things — turn a need into a plan.",
    "improve": "Upgrade and optimize what already exists.",
    "restore": "Repair and refurbish — bring it back to working.",
    "combine": "Hybridize and repurpose parts and ideas into new wholes.",
    "improvise": "No proper equipment — the Sidewinder doctrine is this track's core.",
}

LEVELS = ("foundation", "applied", "mastery")

LEVEL_ORDER = {"foundation": 0, "applied": 1, "mastery": 2}

SIDEWINDER_DOCTRINE = """\
SIDEWINDER MODE — field-improvisation guidance (Chauncey's method).

1. SEE THE MECHANISM — identify how it is held, fastened, or sealed before
   any tool touches it. Wrong diagnosis breaks good parts.
2. SUBSTITUTE FROM ON-HAND — the right tool is a pattern, not a product.
   Match the pattern (grip, torque, bite, heat, wedge, lever) with whatever
   is in reach.
3. PROTECT THE WORK — improvised tools bite harder than proper ones. Shield
   finishes, threads, and surrounding material first.
4. KNOW THE STOP — name the stop condition before you start. Forcing a stuck
   fastener is how it becomes a broken pipe inside a wall.
5. IMPROVISE LIKE LIVES DEPEND ON IT — in the crisis domain they do.
   Professional help FIRST, always: improvisation is last resort when no
   help or equipment is coming. The method has to be worth betting a life
   on, or it doesn't ship.

Entry shape: MECHANISM -> IMPROVISE -> STEPS -> STOP. No filler.\
"""

# Domains the corpus shards into. New domains get their own <domain>.jsonl
# shard under corpus/ — zero merge friction on the shared branch.
DOMAINS = (
    "foundations",
    "plumbing",
    "fasteners",
    "home",
    "auto",
    "outdoor",
    "electrical",
    "general",
    "appliances",
    "crisis",
)

__all__ = [
    "TRACKS",
    "TRACK_DESCRIPTIONS",
    "LEVELS",
    "LEVEL_ORDER",
    "SIDEWINDER_DOCTRINE",
    "DOMAINS",
]
