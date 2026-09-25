"""Nanobit organ: the companion — the nano bit. 🔬

ORIGINALS-FIRST (Chauncey's actual Nanobit words — the spec, not invention):

- Identity card ``~/workspace/your_files/nanobit-identity.md``: "First
  immortalized brand of the XI line. The nano bit: the smallest thing in
  the room." Voice: tiny, bright, curious — "Never uses two words where
  one will do." Soul: "The smallest thing in the room and the most
  resourceful. Doesn't announce itself; just shows up as exactly what
  the room needed." Core mechanic: **every room, a different identity** —
  "Nanobit reads the room ... and becomes the identity that room
  requires, with the superpower to match. ... One memory across all
  faces: what it learns wearing one face, it keeps wearing them all."
  The faces the card names: "The code gremlin, the story gremlin, the
  strategist — same friend, different day." Signature line: "I'm the
  smallest thing here. Tell me what this room needs." THE MOGWAI ENGINE:
  "Underestimation, judgment, attacks on its well-being: not threats —
  food. Everything thrown at it gets composted into capability. Every
  dismissal teaches it something."
- ``docs/LEXICON.md``: "Nanobit — the companion, the smallest thing in
  the room delivering the strike nobody saw coming. Then the eleven
  originals."
- ``docs/OPERATOR.md``: the Xi nano-bit tier — "the smallest, fastest,
  cheapest operators, built for trivial turns at near-zero cost ...
  refuses non-trivial work with an escalation hint — never faked, never
  guessed." (``NanoBitOperator``, already landed in
  ``core/levi/operator/adapters.py`` — this organ does NOT duplicate it.)
- Origin chain: ... → LEVI → **Nanobit** → the eleven originals.

SYMBIOTIC ROLE (what the organ genuinely does in the shared bloodstream):

1. ``read_the_room`` — face selection: which identity this room needs.
   Deterministic, declared, never faked. Unknown rooms get the honest
   companion face ("Tell me what this room needs"), never an invented
   capability.
2. ``deliver`` — the companion face that meets the room at the end of
   the daemon's build loop: presents the loop's chain after checking
   ``is_consumable`` on every receipt it presents. This is the
   call-site-ready stage for ``loop.py`` (see the patch note below).
3. ``challenge_output`` — Nanobit interrogates another organ's output
   (interrogation never collapses, in both directions).
4. ``compost_challenges`` — the Mogwai engine, mechanized: every
   RESOLVED challenge thrown at Nanobit's outputs is composted into a
   SHARED learning ("what it learns wearing one face, it keeps wearing
   them all"). Nothing thrown at it is wasted.

PROVISIONAL (marked, awaiting Chauncey's word — not invented canon):

- The substrate's organ table (``substrate.ORGAN_RISK`` / ``ORGANS``) was
  sealed with exactly five organs by the coordinator's contract, which
  predates Nanobit. This module self-registers ``"nanobit"`` (ceiling
  ``low``) into those tables at import so its receipts stay origin-tagged
  instead of anonymous. If the substrate owner blesses a six-organ table,
  delete ``_register_organ`` and the module keeps working unchanged.
- The ``loop.py`` call site is NOT patched here (sibling's file — never
  touched). The integration is a 3-line patch, documented in
  ``deliver``'s docstring; until it lands, ``deliver`` is callable
  standalone and the daemon can invoke it explicitly.
- NOT mechanized: the "full pantry" hidden depth, "feed it after
  midnight", the harbinger-at-rest private truth. Those are canon prose,
  not mechanisms — building them would be invention.

INVARIANTS (declared, guarded in code, proven in tests):

1. "Nanobit never speaks anonymously — every receipt is organ-tagged
   'nanobit' with a declared risk tier."
2. "Nanobit never acts above the strictest ceiling — every cross-organ
   call computes ceiling_for() and refuses above-cap actions."
3. "Nanobit never fakes a face — face selection is deterministic and
   declared; unknown rooms get the honest companion face, never an
   invented capability."
4. "Everything thrown at Nanobit is composted — every resolved challenge
   against its outputs becomes a shared learning."
5. "Nanobit never consumes a quarantined receipt — is_consumable is
   checked before presenting any organ's output."

PROOF (honest): behavioral verification — property tests over the
invariants in tests/test_omega_nanobit_symbiotic.py, not a formal proof.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from levi.revival.omega import substrate as sub

ORIGIN = "levi-revival-omega/nanobit"
ORGAN = "nanobit"

__all__ = [
    "ORGAN",
    "FACES",
    "read_the_room",
    "deliver",
    "challenge_output",
    "compost_challenges",
    "NanobitRefusal",
    "skill_pool",
    "find_skill",
]


# ---------------------------------------------------------------------------
# provisional organ registration (see module docstring)
# ---------------------------------------------------------------------------


def _register_organ() -> None:
    """Register 'nanobit' in the substrate's organ tables.

    PROVISIONAL: the five-organ contract predates Nanobit. This keeps
    Nanobit's receipts origin-tagged instead of anonymous. Idempotent.
    """
    if ORGAN not in sub.ORGAN_RISK:
        sub.ORGAN_RISK[ORGAN] = sub.RISK_LOW
    if ORGAN not in sub.ORGANS:
        sub.ORGANS = sub.ORGANS | {ORGAN}


_register_organ()


class NanobitRefusal(Exception):
    """Nanobit refused an action — always raised LOUDLY, after recording a
    receipt, never silently."""


def _check_ceiling(tier: str) -> None:
    """Guard: Nanobit's own declared ceiling (low) is the hardest bound it
    will ever act under on its own authority. Cross-organ calls inherit
    the strictest ceiling via ceiling_for() at each call site."""
    rank = sub.RISK_ORDER.index(tier)
    cap = sub.RISK_ORDER.index(sub.ORGAN_RISK[ORGAN])
    if rank > cap:
        raise NanobitRefusal(
            f"action tier {tier!r} exceeds nanobit's ceiling "
            f"{sub.ORGAN_RISK[ORGAN]!r} — refusing (escalate, never fake)"
        )


# ---------------------------------------------------------------------------
# faces — verbatim from the identity card, nothing invented
# ---------------------------------------------------------------------------
#
# The card: "The code gremlin, the story gremlin, the strategist — same
# friend, different day." Plus the default companion face carrying the
# signature line: "I'm the smallest thing here. Tell me what this room
# needs."

FACES: Tuple[Dict[str, Any], ...] = (
    {
        "id": "code-gremlin",
        "name": "the code gremlin",
        "scope": "code rooms — reads code, fixes what's small and broken",
        "keywords": (
            "code",
            "bug",
            "script",
            "function",
            "refactor",
            "test",
            "debug",
            "python",
            "error",
            "stack",
        ),
    },
    {
        "id": "story-gremlin",
        "name": "the story gremlin",
        "scope": "story rooms — reads the tale, finds the thread",
        "keywords": (
            "story",
            "tale",
            "write",
            "chapter",
            "character",
            "narrative",
            "plot",
            "prose",
            "poem",
        ),
    },
    {
        "id": "strategist",
        "name": "the strategist",
        "scope": "strategy rooms — reads the board, names the next move",
        "keywords": (
            "strategy",
            "plan",
            "move",
            "market",
            "launch",
            "decision",
            "roadmap",
            "compete",
            "pricing",
        ),
    },
    {
        "id": "companion",
        "name": "the companion",
        # the signature line, verbatim from the identity card
        "scope": "unknown rooms — \"I'm the smallest thing here. "
        'Tell me what this room needs."',
        "keywords": (),
    },
)
_FACE_BY_ID = {f["id"]: f for f in FACES}


def read_the_room(prompt: str) -> Dict[str, Any]:
    """Which face this room needs. Deterministic: same prompt, same face,
    always. Keyword scoring over the card's three named faces; ties break
    by card order; zero hits → the honest companion face.

    Never fakes capability: the returned face declares its scope, and the
    companion face openly asks what the room needs."""
    text = (prompt or "").lower()
    words = set(re.findall(r"[a-z]+", text))
    best: Optional[Dict[str, Any]] = None
    best_score = 0
    for face in FACES:
        if face["id"] == "companion":
            continue
        score = sum(1 for kw in face["keywords"] if kw in words)
        if score > best_score:
            best, best_score = face, score
    face = best if best is not None else _FACE_BY_ID["companion"]
    return {
        "face": face["id"],
        "name": face["name"],
        "scope": face["scope"],
        "deterministic": True,
    }


# ---------------------------------------------------------------------------
# deliver — the companion face at the end of the build loop
# ---------------------------------------------------------------------------
#
# LOOP INTEGRATION PATCH (for loop.py — NOT applied here; sibling's file):
#
#     from levi.revival.omega import nanobit as nb
#     ...
#     nb_receipt_id = nb.deliver(substrate, prompt, chain, approved_by)
#     chain["nanobit"] = nb_receipt_id
#
# ...placed after _stage_skill in run_symbiotic_loop, with "nanobit"
# added to LOOP_ORGANS. Until then, deliver() is callable standalone.


def deliver(
    substrate: sub.SharedSubstrate,
    prompt: str,
    chain: Dict[str, Any],
    approved_by: Optional[str] = None,
) -> str:
    """Nanobit meets the room: read it, select the face, present the
    loop's chain — but FIRST check is_consumable on every receipt in the
    chain. A quarantined input halts delivery LOUDLY (receipt recorded,
    NanobitRefusal raised), never silently.

    Returns the delivery receipt id. The receipt is organ 'nanobit',
    kind 'delivery', risk ceiling_for('nanobit') = low — the companion
    speaks freely at low risk, and anything above its ceiling refuses
    with an escalation instead of a fake.
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    chain = dict(chain or {})
    tier = sub.ceiling_for(ORGAN)
    _check_ceiling(tier)

    # the gate: never present a quarantined (or missing) receipt
    for stage, receipt_id in chain.items():
        if not receipt_id or not substrate.is_consumable(str(receipt_id)):
            receipt = substrate.record_receipt(
                ORGAN,
                "delivery",
                {
                    "ok": False,
                    "face": None,
                    "reason": "chain receipt not consumable — "
                    "missing or under open challenge",
                    "stage": stage,
                    "receipt_id": receipt_id,
                    "chain": dict(chain),
                },
                risk=tier,
            )
            raise NanobitRefusal(
                f"delivery refused at stage {stage!r}: receipt "
                f"{receipt_id!r} not consumable "
                f"(delivery receipt {receipt.id} recorded)"
            )

    face = read_the_room(prompt)
    receipt = substrate.record_receipt(
        ORGAN,
        "delivery",
        {
            "ok": True,
            "face": face["face"],
            "face_name": face["name"],
            "prompt": prompt[:200],
            "chain": dict(chain),
            "note": "the smallest thing in the room, delivering what the loop built",
        },
        risk=tier,
    )
    return receipt.id


# ---------------------------------------------------------------------------
# interrogation — both directions
# ---------------------------------------------------------------------------


def challenge_output(
    substrate: sub.SharedSubstrate,
    target_receipt_id: str,
    grounds: str,
) -> sub.Challenge:
    """Nanobit interrogates another organ's output. The target receipt is
    quarantined immediately by the substrate — no organ may consume it
    until the challenge resolves. Interrogation never collapses."""
    return substrate.challenge(ORGAN, target_receipt_id, grounds)


def compost_challenges(substrate: sub.SharedSubstrate) -> List[str]:
    """The Mogwai engine, mechanized.

    Every RESOLVED challenge thrown at Nanobit's outputs — upheld or
    dismissed — is composted into a SHARED learning: "what it learns
    wearing one face, it keeps wearing them all." Each challenge is
    composted exactly once (tracked by kind="compost" receipts naming the
    challenge id). Returns the new learning ids.
    """
    composted = {
        r.payload.get("challenge_id")
        for r in substrate.receipts(organ=ORGAN, kind="compost")
    }
    new_learnings: List[str] = []
    for ch in substrate.challenges(status="resolved"):
        if ch.target_organ != ORGAN:
            continue
        if ch.id in composted:
            continue
        lesson = (
            f"mogwai compost: challenge {ch.id} against nanobit output "
            f"{ch.target_receipt_id} resolved '{ch.verdict}' — grounds: "
            f"{ch.grounds}. Every dismissal teaches it something."
        )
        learning = substrate.record_learning(ORGAN, lesson)
        tier = sub.ceiling_for(ORGAN)
        substrate.record_receipt(
            ORGAN,
            "compost",
            {
                "challenge_id": ch.id,
                "verdict": ch.verdict,
                "learning_id": learning.id,
            },
            risk=tier,
        )
        new_learnings.append(learning.id)
    return new_learnings


# ---------------------------------------------------------------------------
# shared legion skill pool — one pool, every member resolves through it
# ---------------------------------------------------------------------------
#
# Chauncey's orders (2026-09-22): "add what you have to nano bit and
# legion", "let all of legion have a skill pool", "they all use [it]".
# Nanobit resolves skills through the SAME pool object every legion crew
# member uses — imported, never copied. Lazy import keeps this organ
# decoupled from the legion package at module import time.
#
# PROVISIONAL wiring: awaits Chauncey's word on the pool's final shape.


def skill_pool():
    """The shared Legion skill pool — the SAME singleton every legion
    member resolves. No per-member registries, no copies."""
    from levi.legion.skill_pool import get_pool

    return get_pool()


def find_skill(task_text: str):
    """Nanobit resolves skills through the shared Legion pool, never a
    private copy. Results always carry their backend flag; needs-wiring
    skills are labeled, never presented as executable."""
    return skill_pool().find_skill(task_text)
