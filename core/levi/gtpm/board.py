"""The blackboard: coordination substrate for the multi-agentic loop.

GTPM (Chauncey): "Basically analyzing but pure deterministic. I call it
goal targeted predator mentality." This module is the GTPM technique's
shared working memory: minds act as knowledge sources (KSs) that post
*scored* hypotheses to a leveled blackboard, and the scan-mind in its
controller role runs deterministic scan cycles — compute the agenda,
pick the focus of attention, fire one KS, post its hypothesis. Repeat.

Formal spec: ``~/workspace/levi-unified-build/salvage-blackboard-formal-spec.md``
(sections 2-4). A LEVI-native recreation of the blackboard coordination
paradigm (Hearsay-II, researched as paradigm only — not a port).

**Working title and working names only — naming is Chauncey's.**
Hypotheses are scored data, not beliefs: a confidence number, a
provenance trail, and a lifecycle status. Nothing here claims
sentience or subjective experience.

Laws honored:
- Stdlib-only at import; zero network at runtime (verified by tests).
- Deterministic control: ``focus`` is a pure function of board state —
  fixed board -> identical scheduling decision, every run, every process.
  Never ``hash()`` on strings for ordering decisions: ``sorted()`` and
  name tie-breaks only.
- Board-mediated only: KSs never invoke each other; all coordination
  flows through posted hypotheses.
- Levels are honest (I3): a KS may only post to its registered
  competence levels; inflation is rejected and auditable.
- Diversity floor (I4): the controller never prunes to a single
  hypothesis before confirmation; refuted hypotheses are kept, never
  deleted (compost for the REIM engine).
- Every post is receipted: content, level, confidence, provenance,
  timestamp (I5).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

__all__ = [
    "DEFAULT_LEVELS",
    "new_board",
    "post",
    "register_ks",
    "agenda",
    "focus",
    "step",
    "corroborate",
    "contradict",
    "confirm",
    "arbitrate",
    "record_outcome",
    "on_transition",
    "diversity_ok",
    "audit_competence",
]

# Spec section 2: leveled structure, raw observation -> parsed -> planned
# -> verified -> receipted. Working names; Chauncey owns the taxonomy.
DEFAULT_LEVELS = ["raw", "parsed", "planned", "verified", "receipted"]

# Spec 3.2: hypothesis lifecycle statuses.
PROPOSED = "proposed"
ACTIVE = "active"
REFUTED = "refuted"
CONFIRMED = "confirmed"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ks_by_name(board: dict) -> dict:
    return {ks["name"]: ks for ks in board["ks"]}


def _find_hypothesis(board: dict, hyp_id: str):
    """Return (level, hypothesis) for hyp_id; ValueError if absent."""
    for level in board["levels"]:
        for hyp in board["cells"][level]:
            if hyp["id"] == hyp_id:
                return level, hyp
    raise ValueError(f"unknown hypothesis id: {hyp_id!r}")


def _emit(board: dict, event: dict) -> None:
    """Journal one lifecycle event and notify end-team listeners.

    Listeners are best-effort: a failing listener is recorded, never
    fatal (P4 failure isolation applies to the journaling hook too).
    """
    event = dict(event)
    event.setdefault("t", _utc_now())
    board["transitions"].append(event)
    for fn in list(board["_listeners"]):
        try:
            fn(dict(event))
        except Exception as exc:  # never let a listener kill the board
            board["transitions"].append(
                {"event": "listener_error", "t": _utc_now(), "error": repr(exc)}
            )


def new_board(levels: list[str] | None = None) -> dict:
    """Create an empty blackboard.

    Board = {"levels", "cells", "ks", "transitions", "_seq", "ks_stats"}.
    """
    if levels is None:
        levels = list(DEFAULT_LEVELS)
    levels = list(levels)
    if not levels:
        raise ValueError("board needs at least one level")
    if any(not isinstance(lv, str) or not lv for lv in levels):
        raise ValueError("levels must be non-empty strings")
    if len(set(levels)) != len(levels):
        raise ValueError("level names must be unique")
    return {
        "levels": levels,
        "cells": {lv: [] for lv in levels},
        "ks": [],
        "transitions": [],
        "ks_stats": {},
        "_seq": 0,
        "_listeners": [],
    }


def post(
    board: dict,
    level: str,
    content: dict,
    confidence: float,
    provenance: list,
    posted_by: str,
    supersedes=None,
) -> dict:
    """Post a hypothesis to a level; returns the hypothesis dict.

    Validates: level exists (ValueError), 0 <= confidence <= 1
    (ValueError), content is a dict (TypeError). I3: a registered KS
    posting above its competence levels is rejected (ValueError).
    Every post is appended to board["transitions"] as {"event":
    "posted", "id", ...} and delivered to transition listeners.
    """
    if level not in board["cells"]:
        raise ValueError(f"unknown level: {level!r}; levels={board['levels']}")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be a number in [0, 1]")
    if not 0.0 <= float(confidence) <= 1.0:
        raise ValueError(f"confidence {confidence!r} outside [0, 1]")
    if not isinstance(content, dict):
        raise TypeError(f"content must be a dict, got {type(content).__name__}")
    if not isinstance(provenance, list):
        raise ValueError("provenance must be a list of strings")
    if not isinstance(posted_by, str) or not posted_by:
        raise ValueError("posted_by must be a non-empty string")
    if supersedes is None:
        supersedes = []
    elif isinstance(supersedes, str):
        supersedes = [supersedes]
    else:
        supersedes = list(supersedes)

    # I3 — levels are honest: competence check for registered KSs.
    ks = _ks_by_name(board).get(posted_by)
    if ks is not None and level not in ks["levels"]:
        raise ValueError(
            f"level-inflation rejected: KS {posted_by!r} is competent for "
            f"{ks['levels']}, attempted to post at {level!r}"
        )

    hyp_id = f"h{board['_seq']}"
    board["_seq"] += 1
    hypothesis = {
        "id": hyp_id,
        "level": level,
        "content": dict(content),
        "confidence": float(confidence),
        "provenance": list(provenance),
        "status": PROPOSED,
        "posted_by": posted_by,
        "t": _utc_now(),
        "supersedes": list(supersedes),
        "refuted_by": None,
    }
    board["cells"][level].append(hypothesis)
    _emit(
        board,
        {
            "event": "posted",
            "id": hyp_id,
            "level": level,
            "posted_by": posted_by,
            "confidence": float(confidence),
        },
    )
    return hypothesis


def register_ks(
    board: dict,
    name: str,
    levels: list[str],
    trigger,
    contribute,
    priority: float = 0.0,
) -> dict:
    """Register a knowledge source (mind) on the board.

    ``levels`` are the competence levels the KS may post to — posting
    above competence is rejected (I3). ``trigger(board) -> bool`` and
    ``contribute(board) -> (level, content, confidence, provenance)``.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("KS name must be a non-empty string")
    if name in _ks_by_name(board):
        raise ValueError(f"KS {name!r} already registered")
    levels = list(levels)
    if not levels or any(lv not in board["cells"] for lv in levels):
        raise ValueError(
            f"KS competence levels must be board levels: {levels!r}"
        )
    if not callable(trigger):
        raise ValueError("trigger must be callable")
    if not callable(contribute):
        raise ValueError("contribute must be callable")
    ks = {
        "name": name,
        "levels": levels,
        "trigger": trigger,
        "contribute": contribute,
        "priority": float(priority),
    }
    board["ks"].append(ks)
    _emit(board, {"event": "ks_registered", "ks": name, "levels": levels})
    return ks


def _canonical_cells_summary(board: dict) -> str:
    """Deterministic canonical summary of board cells for snapshots."""
    summary = []
    for level in board["levels"]:
        hyps = sorted(board["cells"][level], key=lambda h: h["id"])
        for hyp in hyps:
            summary.append(
                [
                    level,
                    hyp["id"],
                    hyp["status"],
                    repr(hyp["confidence"]),
                    json.dumps(hyp["content"], sort_keys=True, separators=(",", ":")),
                    hyp["posted_by"],
                ]
            )
    return json.dumps(summary, sort_keys=True, separators=(",", ":"))


def _agenda_full(board: dict):
    """Internal: (triggered, skipped). triggered = [(ks_name, priority,
    snapshot)]; skipped = [{"ks", "reason"}]. A KS whose trigger raises
    is skipped — recorded in the journal, never fatal (P4)."""
    snapshot = hashlib.sha256(_canonical_cells_summary(board).encode("utf-8")).hexdigest()
    triggered = []
    skipped = []
    # Deterministic iteration: registration order is stable, and focus()
    # sorts by (priority desc, name asc) — never hash().
    for ks in board["ks"]:
        try:
            fires = ks["trigger"](board)
        except Exception as exc:
            skipped.append({"ks": ks["name"], "reason": f"trigger: {exc!r}"})
            _emit(board, {"event": "trigger_error", "ks": ks["name"], "error": repr(exc)})
            continue
        if fires:
            triggered.append((ks["name"], float(ks["priority"]), snapshot))
    return triggered, skipped


def agenda(board: dict) -> list:
    """[(ks_name, priority, snapshot)] for KSs whose trigger is true.

    ``snapshot`` is the sha256 of a canonical summary of the cells, so a
    consumer can tell whether the board changed since the agenda was
    computed. Trigger failures are skipped and journaled, never fatal.
    """
    triggered, _skipped = _agenda_full(board)
    return triggered


def focus(board: dict) -> str | None:
    """Deterministic focus of attention: argmax over the agenda.

    Ordering: priority descending, then KS name ascending. A pure
    function of board state — fixed board -> identical focus across
    runs and processes (I2, P3, T3). Returns the KS name or None.
    """
    heads = agenda(board)
    if not heads:
        return None
    # Sort, never hash: (priority desc, name asc). Registration order
    # never decides — only the declared priority and the name.
    heads.sort(key=lambda h: (-h[1], h[0]))
    return heads[0][0]


def step(board: dict, cycle: int = 0) -> tuple[dict, dict]:
    """One controller cycle: agenda -> focus -> fire one KS -> post.

    Runs the focused KS's ``contribute`` ONCE and posts its hypothesis
    (competence-validated). A KS whose contribute raises is skipped and
    the next agenda head fires — the board keeps working (P4). Returns
    (board, receipt); receipt = {"kind", "cycle", "focus", "posted",
    "skipped", "arbitrations"}.
    """
    triggered, skipped = _agenda_full(board)
    triggered.sort(key=lambda h: (-h[1], h[0]))

    fired = None
    posted = None
    for ks_name, _prio, _snap in triggered:
        ks = _ks_by_name(board)[ks_name]
        try:
            result = ks["contribute"](board)
            level, content, confidence, provenance = result
        except Exception as exc:
            skipped.append({"ks": ks_name, "reason": f"contribute: {exc!r}"})
            _emit(board, {"event": "contribute_error", "ks": ks_name, "error": repr(exc)})
            continue
        try:
            posted = post(
                board,
                level,
                content,
                confidence,
                provenance,
                posted_by=ks_name,
            )
        except Exception as exc:
            # Competence violation or bad payload: journaled, skipped,
            # never fatal.
            skipped.append({"ks": ks_name, "reason": f"post: {exc!r}"})
            _emit(board, {"event": "post_error", "ks": ks_name, "error": repr(exc)})
            continue
        fired = ks_name
        break

    receipt = {
        "kind": "board",
        "cycle": cycle,
        "focus": fired,
        "posted": posted,
        "skipped": skipped,
        "arbitrations": [],
    }
    _emit(
        board,
        {
            "event": "cycle",
            "cycle": cycle,
            "focus": fired,
            "posted": posted["id"] if posted else None,
            "skipped": [s["ks"] for s in skipped],
        },
    )
    return board, receipt


# -- Lifecycle (spec 3.2) -------------------------------------------------
# proposed --corroborated--> active --confirmed--> (WM fact for reflex layer)
#    |                            |
#    +--refuted <--contradicted----+   (refuted hypotheses are KEPT)


def corroborate(board: dict, hyp_id: str, by: str) -> dict:
    """Move a hypothesis proposed -> active. Anything else is an error."""
    level, hyp = _find_hypothesis(board, hyp_id)
    if hyp["status"] != PROPOSED:
        raise ValueError(
            f"cannot corroborate {hyp_id!r}: status is {hyp['status']!r}, "
            f"expected {PROPOSED!r}"
        )
    hyp["status"] = ACTIVE
    _emit(board, {"event": "corroborated", "id": hyp_id, "level": level, "by": by})
    return hyp


def contradict(board: dict, hyp_id: str, by: str, reason: str) -> dict:
    """Move a hypothesis proposed/active -> refuted (kept, with receipt).

    The hypothesis is NEVER deleted — the compost engine mines refuted
    hypotheses later. ``refuted_by`` records who refuted it and why.
    """
    level, hyp = _find_hypothesis(board, hyp_id)
    if hyp["status"] not in (PROPOSED, ACTIVE):
        raise ValueError(
            f"cannot contradict {hyp_id!r}: status is {hyp['status']!r}"
        )
    hyp["status"] = REFUTED
    hyp["refuted_by"] = {"by": by, "reason": reason}
    _emit(
        board,
        {
            "event": "refuted",
            "id": hyp_id,
            "level": level,
            "by": by,
            "reason": reason,
            "via": "contradict",
        },
    )
    return hyp


def confirm(board: dict, hyp_id: str) -> dict:
    """Move a hypothesis active -> confirmed. Requires active (ValueError)."""
    level, hyp = _find_hypothesis(board, hyp_id)
    if hyp["status"] != ACTIVE:
        raise ValueError(
            f"cannot confirm {hyp_id!r}: status is {hyp['status']!r}, "
            f"expected {ACTIVE!r}"
        )
    hyp["status"] = CONFIRMED
    _emit(board, {"event": "confirmed", "id": hyp_id, "level": level})
    return hyp


# -- Provenance-track-record weights (spec 3.3) ----------------------------


def record_outcome(board: dict, ks_name: str, correct: bool) -> dict:
    """Record whether a KS's hypothesis checked out.

    Maintains the measured per-KS precision the arbitration weights
    come from — never a hand-tuned constant. Returns the stats dict.
    """
    stats = board["ks_stats"].setdefault(ks_name, {"correct": 0, "total": 0, "precision": 1.0})
    stats["total"] += 1
    if correct:
        stats["correct"] += 1
    stats["precision"] = stats["correct"] / stats["total"]
    return stats


def _combined_weight(board: dict, hyp: dict) -> float:
    """w = historical precision of the posting KS (default 1.0)."""
    return float(board["ks_stats"].get(hyp["posted_by"], {}).get("precision", 1.0))


def arbitrate(board: dict, level: str, key_fn) -> dict:
    """Scored arbitration over competing ACTIVE hypotheses on a level.

    Groups by ``key_fn(hypothesis) -> str``; per group promotes the
    argmax of (confidence * KS precision) to confirmed and demotes the
    rest to refuted (receipted). Ties break by hypothesis id ascending.
    Returns {"winner", "losers", "weights", "level"}.
    """
    if level not in board["cells"]:
        raise ValueError(f"unknown level: {level!r}")
    groups: dict[str, list] = {}
    for hyp in board["cells"][level]:
        if hyp["status"] == ACTIVE:
            key = key_fn(hyp)
            groups.setdefault(key, []).append(hyp)

    winner = None
    losers: list = []
    weights: dict = {}
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda h: h["id"])
        for hyp in members:
            weights[hyp["id"]] = _combined_weight(board, hyp)
        # argmax(combined) with id tie-break — sorted(), never hash().
        best = min(
            members,
            key=lambda h: (-(h["confidence"] * weights[h["id"]]), h["id"]),
        )
        if winner is None:
            winner = best
            losers.extend(m for m in members if m is not best)
        else:
            losers.extend(members)

    if winner is None:
        return {"winner": None, "losers": [], "weights": {}, "level": level}

    # Confirm the winner FIRST so the journal shows confirmation before
    # any demotion — diversity_ok() reads that ordering.
    confirm(board, winner["id"])
    for hyp in sorted(losers, key=lambda h: h["id"]):
        hyp["status"] = REFUTED
        hyp["refuted_by"] = {
            "by": "arbitration",
            "reason": f"superseded by {winner['id']} in arbitration on {level!r}",
        }
        _emit(
            board,
            {
                "event": "refuted",
                "id": hyp["id"],
                "level": level,
                "by": "arbitration",
                "reason": f"lost to {winner['id']}",
                "via": "arbitrate",
            },
        )

    return {
        "winner": winner,
        "losers": losers,
        "weights": weights,
        "level": level,
    }


# -- Hooks, audit ----------------------------------------------------------


def on_transition(board: dict, fn) -> None:
    """Subscribe ``fn(event_dict)`` to every lifecycle event.

    End-team hook for journaling (ITS discipline): every post,
    corroboration, contradiction, confirmation, refutation, KS
    registration/error, and cycle is delivered. Listener failures are
    journaled, never fatal.
    """
    if not callable(fn):
        raise ValueError("listener must be callable")
    board["_listeners"].append(fn)


def diversity_ok(board: dict, level: str | None = None) -> bool:
    """True if no hypothesis was pruned before any confirm on the level.

    I4 support: replays the transition journal per level; if any
    refutation (contradict or arbitration demotion) precedes the first
    confirmation on that level, the diversity floor was violated and
    this returns False. Arbitration confirms its winner first, so
    sanctioned arbitration never trips this.
    """
    levels = [level] if level is not None else list(board["levels"])
    if level is not None and level not in board["cells"]:
        raise ValueError(f"unknown level: {level!r}")
    for lv in levels:
        confirmed_seen = False
        for ev in board["transitions"]:
            if ev.get("level") != lv:
                continue
            if ev["event"] == "confirmed":
                confirmed_seen = True
            elif ev["event"] == "refuted" and not confirmed_seen:
                return False
    return True


def audit_competence(board: dict) -> list:
    """Scan all hypotheses for I3 violations (KS posting above competence).

    Returns a list of violation dicts; empty means clean. The live
    ``post`` path rejects violations outright, so a non-empty result
    means something bypassed the API (hand-edited board, legacy data).
    """
    ks_names = _ks_by_name(board)
    violations = []
    for level in board["levels"]:
        for hyp in board["cells"][level]:
            ks = ks_names.get(hyp["posted_by"])
            if ks is not None and level not in ks["levels"]:
                violations.append(
                    {
                        "hypothesis": hyp["id"],
                        "posted_by": hyp["posted_by"],
                        "level": level,
                        "competence": list(ks["levels"]),
                    }
                )
    return violations
