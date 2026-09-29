"""Nanobit execution loop: the nano-bit turn loop — one face, real tools.

ORIGINALS-FIRST (Chauncey's actual words — the spec, not invention):

- Identity card ``~/workspace/your_files/nanobit-identity.md``: "First
  immortalized brand of the XI line. The nano bit: the smallest thing in
  the room." Voice: "Tiny, bright, curious ... Never uses two words
  where one will do." Core mechanic: "every room, a different identity"
  — "One memory across all faces: what it learns wearing one face, it
  keeps wearing them all." The card's faces: "The code gremlin, the
  story gremlin, the strategist — same friend, different day."
  Signature line: "I'm the smallest thing here. Tell me what this room
  needs." The Mogwai engine: "Everything thrown at it gets composted
  into capability."
- ``docs/OPERATOR.md`` nano-bit tier: "the smallest, fastest, cheapest
  operators, built for trivial turns at near-zero cost ... refuses
  non-trivial work with an escalation hint — never faked, never
  guessed."
- ``revival/omega/nanobit.py`` (its docstring IS the law): faces, the
  LOW risk ceiling, ``_check_ceiling``, the shared-pool bridge, and the
  compost pattern this loop follows for learnings.
- Chauncey's orders (2026-09-22): "add what you have to nano bit and
  legion" — this module is the capability half of that order (the pool
  half already landed).

LAWS (declared in plain words, guarded in code, proven in tests):

1. "The LOW ceiling is absolute." The turn estimates an action tier
   BEFORE touching the loop; anything above low is refused LOUDLY with
   an escalation hint — receipt recorded first, ``NanobitRefusal``
   raised, the loop never executed. Never faked, never guessed, never
   silent.
2. "Faces stay the card's four." Selection reuses ``read_the_room`` —
   keyword-deterministic, the three named faces plus the honest
   companion; no invented faces. Every face runs the same loop
   machinery with real tool access through the shared pool.
3. "One memory across all faces." Turn learnings go into the shared
   substrate (the compost pattern: what it learns wearing one face, it
   keeps wearing them all), and every turn's system prompt carries the
   recent shared learnings — so all faces see what any face learned.
4. "The final word honors the card." The turn's voice instruction is
   tiny, bright, curious, plain words — never two words where one will
   do.
5. "Labeled skills never fake execution." Tools resolve through the
   shared pool via ``legion.crew_loop.registry_from_skills`` — same
   object, same honest stubs.
6. Law-guard-prove: laws declared up front, guards in code, property
   tests as the proof artifact — behavioral verification, named
   honestly, not a formal proof.

PROOF (honest): ``tests/test_nanobit_loop.py``.

Dynasty eyes-only: no dynasty/IP material in this module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.agent.assistant import assistant_system_prompt, candidate_learnings
from levi.agent.loop import run_subtask
from levi.legion import crew_loop
from levi.revival.omega import nanobit as nb
from levi.revival.omega import substrate as sub

__all__ = [
    "shared_pool",
    "estimate_tier",
    "run_turn",
]


def shared_pool():
    """The shared Legion skill pool — the SAME singleton every legion
    member resolves through. ``shared_pool() is nanobit.skill_pool()``,
    always. No per-face copies, ever."""
    return nb.skill_pool()


# ---------------------------------------------------------------------------
# tier estimation — deliberately conservative heuristic
# ---------------------------------------------------------------------------
#
# Nanobit's own declared ceiling is LOW (OPERATOR.md nano-bit tier).
# This estimator errs toward refusal: a false positive means Nanobit
# says "escalate" on a harmless turn (annoying, safe); a false negative
# would mean acting above its ceiling (dangerous). The loop's own
# confirmation gates remain the second line of defense for anything
# that does reach the tools.

_ABOVE_LOW_PHRASES = (
    # money movement
    "send money",
    "pay ",
    "payment",
    "transfer",
    "checkout",
    "refund",
    "charge ",
    "buy ",
    "sell ",
    "subscribe",
    "unsubscribe",
    # destruction / irreversible state
    "delete",
    "destroy",
    "wipe",
    "remove everything",
    # external sends / publication
    "send email",
    "send mail",
    "post to",
    "publish",
    # credentials and secrets
    "password",
    "api key",
    "apikey",
    "credential",
    "secret",
    "private key",
    "token",
    # advice with liability
    "diagnos",
    "lawsuit",
    "sue ",
    "medical advice",
    "legal advice",
    "sign ",
    "signature",
    "contract",
)


def estimate_tier(prompt: str) -> str:
    """Estimate the action tier of a turn. Deterministic heuristic:
    anything naming consequential work (money, deletion, external
    sends, credentials, liability advice) estimates "standard" — which
    is above nanobit's LOW ceiling and therefore refuses. Everything
    else estimates "low". Conservative by design."""
    text = " " + (prompt or "").lower() + " "
    for phrase in _ABOVE_LOW_PHRASES:
        if phrase in text:
            return sub.RISK_STANDARD
    return sub.RISK_LOW


_ESCALATION_HINT = (
    "Above nanobit's LOW ceiling — escalate to a higher-tier operator "
    "(the LEVI agent core) or to Chauncey himself. Nanobit does not fake "
    "this work, does not guess at it, and does not do it quietly."
)


def _voice_block(face: Dict[str, Any]) -> str:
    """The identity card's voice, as loop instruction — tiny, bright,
    curious, plain words. Verbatim where the card speaks."""
    return (
        "Voice — the identity card's law: tiny, bright, curious. "
        "Never use two words where one will do, and the one word is "
        "always the right one. Speak simply — deceptively simply.\n"
        f"You are wearing one face this turn: {face['name']} — {face['scope']}. "
        "Same friend, different day: one memory across all faces."
    )


def _learnings_context(substrate: sub.SharedSubstrate, limit: int = 5) -> str:
    """Recent shared learnings — one memory across all faces. What any
    face learned, this face sees too."""
    try:
        entries = substrate.learnings()[-limit:]
    except Exception:
        return ""
    lines = [
        f"- {e.lesson[:200]}"
        for e in entries
        if getattr(e, "lesson", "")
    ]
    if not lines:
        return ""
    return (
        "What you've learned before (shared across all your faces — "
        "what one face learns, all faces keep):\n" + "\n".join(lines)
    )


def _system_prompt(face: Dict[str, Any], substrate: sub.SharedSubstrate) -> str:
    """The turn's system prompt: assistant core + card voice + face +
    shared learnings."""
    parts = [
        assistant_system_prompt(identity="Nanobit"),
        "",
        _voice_block(face),
    ]
    learnings = _learnings_context(substrate)
    if learnings:
        parts += ["", learnings]
    return "\n".join(parts)


def _record_turn_learnings(
    substrate: sub.SharedSubstrate, face_id: str, prompt: str, final: str
) -> List[str]:
    """Compost the turn into shared learnings — the Mogwai pattern:
    recorded on the shared substrate under organ 'nanobit', visible to
    every face on later turns."""
    ids: List[str] = []
    text = (prompt or "") + "\n" + (final or "")
    for cand in candidate_learnings(text):
        entry = substrate.record_learning(
            nb.ORGAN,
            f"[{face_id}] {cand['content']} (kind={cand['kind']})",
        )
        ids.append(entry.id)
    return ids


# Cap: a turn sees a handful of the best-matching skills, never the
# whole pool.
_MAX_SKILLS_PER_TURN = 5


def run_turn(
    substrate: sub.SharedSubstrate,
    prompt: str,
    *,
    max_steps: int = 10,
    provider: Optional[Any] = None,
) -> str:
    """Run one Nanobit turn and return the turn receipt id.

    Flow: ``read_the_room`` -> face -> ceiling check (loud refusal above
    LOW, receipt recorded, loop never executed) -> resolve skills via
    the shared pool -> run the turn through ``run_subtask`` within the
    ceiling -> record the delivery receipt + shared learnings -> return
    the receipt id.

    ``provider`` may be a :class:`ChatProvider`, a provider-name string,
    or ``None`` for the default selection.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(
            f"run_turn: 'prompt' must be a non-empty string, got {prompt!r}"
        )
    face = nb.read_the_room(prompt)

    # Law 1: the ceiling check happens BEFORE the loop. Above-ceiling
    # work is refused loudly — receipt first, then the exception — and
    # the loop is never executed.
    tier = estimate_tier(prompt)
    try:
        nb._check_ceiling(tier)
    except nb.NanobitRefusal:
        substrate.record_receipt(
            nb.ORGAN,
            "turn-refusal",
            {
                "ok": False,
                "face": face["face"],
                "estimated_tier": tier,
                "ceiling": sub.ORGAN_RISK[nb.ORGAN],
                "escalation_hint": _ESCALATION_HINT,
                "prompt": prompt[:200],
                "note": "refused before the loop ran — never faked, never silent",
            },
            risk=sub.RISK_LOW,
        )
        raise nb.NanobitRefusal(
            f"nanobit turn refused: estimated tier {tier!r} exceeds the "
            f"LOW ceiling. {_ESCALATION_HINT}"
        ) from None

    pool = shared_pool()
    skills = pool.find_skill(prompt)[:_MAX_SKILLS_PER_TURN]
    registry = crew_loop.registry_from_skills(skills, pool=pool)
    system = _system_prompt(face, substrate)

    transcript = run_subtask(
        task=prompt,
        provider=provider,
        registry=registry,
        max_steps=max_steps,
        system_prompt=system,
    )

    tool_calls = sum(len(s.tool_calls) for s in transcript.steps)
    learning_ids = _record_turn_learnings(
        substrate, face["face"], prompt, transcript.final
    )
    receipt = substrate.record_receipt(
        nb.ORGAN,
        "turn",
        {
            "ok": transcript.ok,
            "face": face["face"],
            "face_name": face["name"],
            "tier": tier,
            "steps": len(transcript.steps),
            "tool_calls": tool_calls,
            "skills_resolved": [s["id"] for s in skills],
            "learning_ids": learning_ids,
            "final": transcript.final[:300],
            "provider": transcript.provider_name,
        },
        risk=sub.RISK_LOW,
    )
    return receipt.id
