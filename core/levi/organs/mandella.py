"""Mandella — stake selection under domain pressure (kernel organ).

The one stakes/scenario-generation implementation in this tree; pairs with
organs/echo.py. A prior lineage's graph/mandella.py was correctly rejected
at merge time to avoid a competing implementation — do not reintroduce one;
extend this module instead."""

from __future__ import annotations

from typing import Dict, List
import hashlib
import json


DOMAINS = {
    "crisis": "A critical path is failing and information is incomplete.",
    "resource": "Budget, time, or energy is scarcer than the plan assumed.",
    "trust": "A counterpart’s incentives are opaque; cooperation is valuable but risky.",
    "identity": "Two self-descriptions conflict; only one can drive the next commit.",
    "build": "A factory stage is blocked; several stacks could work.",
    "write": "The story or premise can branch into several modes.",
    "security": "A consequential action is proposed; blast radius is unclear.",
    "product": "Users ask for more surface; retention may prefer one loop.",
}

OPTIONS: Dict[str, List[tuple]] = {
    "crisis": [
        ("Act fast with incomplete data", "high", "Smallest containment now"),
        ("Gather one more signal", "medium", "Time-box the wait"),
        ("Contain and observe", "low", "Define exit criteria"),
    ],
    "resource": [
        ("Spend the reserve", "high", "Track burn vs milestone"),
        ("Cut scope", "low", "Thinner vertical ship"),
        ("Borrow from another organ", "medium", "Composite risk ceiling"),
    ],
    "security": [
        ("HITL gate hard", "low", "No silent approval"),
        ("Preview only", "medium", "Reversible sandbox"),
        ("Proceed under policy", "high", "Receipt + rollback plan"),
    ],
}


def _haunt_for(label: str, note: str) -> str:
    """Deterministic one-line cost of ignoring an unchosen option.

    Templated from ``label`` + ``note`` only — no invented content.
    """
    return f"Ignoring '{label}' forfeits its promise: {note}."


def run_mandella(domain: str = "build", seed: str = "") -> Dict:
    """Stake selection under domain pressure.

    Unknown ``domain`` values fall back to ``build`` (documented);
    non-string inputs raise ValueError.

    ``recommended`` is the first option after seed-rotation (unchanged
    behavior). Every option except the recommended one returns as a
    ``phantom`` — the unchosen stake that haunts the decision.
    """
    if not isinstance(domain, str):
        raise ValueError(
            "run_mandella: domain must be a string, got %s" % type(domain).__name__
        )
    if not isinstance(seed, str):
        raise ValueError(
            "run_mandella: seed must be a string, got %s" % type(seed).__name__
        )
    d = (domain or "build").lower()
    if d not in DOMAINS:
        d = "build"
    premise = DOMAINS[d]
    opts = OPTIONS.get(d) or OPTIONS["resource"]
    h = int(hashlib.sha256((seed + d).encode()).hexdigest()[:6], 16)
    # rotate emphasis
    ordered = opts[h % len(opts) :] + opts[: h % len(opts)]
    options = [{"label": o[0], "risk": o[1], "note": o[2]} for o in ordered]
    phantoms = [
        {
            "label": o["label"],
            "risk": o["risk"],
            "note": o["note"],
            "haunt": _haunt_for(o["label"], o["note"]),
        }
        for o in options[1:]
    ]
    return {
        "organ": "mandella",
        "domain": d,
        "premise": premise,
        "options": options,
        "recommended": ordered[0][0],
        "phantoms": phantoms,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Stake ledger — unresolved stakes and the phantoms that haunt them.
#
# In-memory only, local-first: no disk writes. A stake is open while
# unresolved; its phantoms haunt until the stake is resolved.
# ---------------------------------------------------------------------------

_stake_ledger: List[Dict] = []

_DECISION_KEYS = ("domain", "chosen", "phantoms", "ts", "seed")


def _fingerprint(decision: Dict) -> str:
    """Deterministic sha256 id from the decision content."""
    payload = json.dumps(
        {k: decision.get(k) for k in _DECISION_KEYS},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _copy_phantoms(phantoms: List[Dict]) -> List[Dict]:
    return [dict(p) for p in phantoms]


def _copy_stake(stake: Dict) -> Dict:
    return dict(stake, phantoms=_copy_phantoms(stake["phantoms"]))


def record_stake(decision: Dict) -> str:
    """Record a stake on the ledger; returns its sha256 fingerprint id.

    ``decision`` must carry ``domain``, ``chosen``, ``phantoms``,
    ``ts``, and ``seed``. Same content re-recorded returns the same id
    without duplicating the ledger entry.
    """
    if not isinstance(decision, dict):
        raise ValueError("record_stake: decision must be a dict")
    for key in _DECISION_KEYS:
        if key not in decision:
            raise ValueError(f"record_stake: decision missing {key!r}")
    if not isinstance(decision["phantoms"], list):
        raise ValueError("record_stake: decision['phantoms'] must be a list")
    sid = _fingerprint(decision)
    for stake in _stake_ledger:
        if stake["id"] == sid:
            return sid
    _stake_ledger.append(
        {
            "id": sid,
            "domain": decision["domain"],
            "chosen": decision["chosen"],
            "phantoms": _copy_phantoms(decision["phantoms"]),
            "ts": decision["ts"],
            "seed": decision["seed"],
            "resolved": None,
            "outcome": None,
        }
    )
    return sid


def list_open_stakes() -> List[Dict]:
    """Open (unresolved) stakes, oldest-first — the haunting."""
    return [_copy_stake(s) for s in _stake_ledger if s["resolved"] is None]


def _find_stake(stake_id: str) -> Dict:
    for stake in _stake_ledger:
        if stake["id"] == stake_id:
            return stake
    raise ValueError(f"unknown stake id {stake_id!r}")


def resolve_stake(stake_id: str, outcome: str) -> Dict:
    """Resolve an open stake with an outcome note.

    Fail-closed: unknown ids raise ValueError; resolving twice raises
    ValueError.
    """
    stake = _find_stake(stake_id)
    if stake["resolved"] is not None:
        raise ValueError(f"stake {stake_id!r} is already resolved")
    if not isinstance(outcome, str) or not outcome:
        raise ValueError("resolve_stake: outcome must be a non-empty string")
    stake["resolved"] = True
    stake["outcome"] = outcome
    return _copy_stake(stake)


def haunt_check(stake_id: str) -> Dict:
    """Phantoms for one open stake, with a one-line pressure summary.

    Fail-closed: unknown or already-resolved ids raise ValueError.
    """
    stake = _find_stake(stake_id)
    if stake["resolved"] is not None:
        raise ValueError(f"stake {stake_id!r} is already resolved")
    phantoms = _copy_phantoms(stake["phantoms"])
    labels = ", ".join(p["label"] for p in phantoms)
    pressure = (
        f"Open stake in '{stake['domain']}': '{stake['chosen']}' was chosen; "
        f"{len(phantoms)} phantom(s) unchosen — {labels} — each waits on the ledger."
    )
    return {
        "stake_id": stake_id,
        "domain": stake["domain"],
        "chosen": stake["chosen"],
        "phantoms": phantoms,
        "pressure": pressure,
    }


def format_mandella(result: Dict) -> str:
    lines = [
        f"=== Mandella [{result['domain']}] ===",
        f"Premise: {result['premise']}",
        "",
        "Stakes:",
    ]
    for i, o in enumerate(result["options"], 1):
        mark = "→" if i == 1 else "·"
        lines.append(f"  {mark} {o['label']}  risk={o['risk']}  ({o['note']})")
    lines.append("")
    lines.append(f"Recommended stake: {result['recommended']}")
    lines.append("Commit is yours — Mandella surfaces pressure, does not force.")
    phantoms = result.get("phantoms")
    if phantoms:
        lines.append("")
        lines.append("Phantoms (unresolved):")
        for p in phantoms:
            lines.append(f"  · {p['label']}  risk={p['risk']}  haunt: {p['haunt']}")
    return "\n".join(lines)
