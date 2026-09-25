"""Consult flow — ask a crew role, get an honest receipt."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from levi.si_team import roles, substrate
from levi.si_team.si import get_core


@dataclass(frozen=True)
class Counsel:
    """The receipt for one consult: who answered, with what, and the limits."""

    role: str
    substrate_used: str
    answer: str
    limits: List[str] = field(default_factory=list)
    refused: bool = False


def _refuse(role: str) -> Counsel:
    return Counsel(
        role=role or "",
        substrate_used="none",
        refused=True,
        answer=(
            f"No such role in the SI team roster: {role!r}. The crew is "
            f"levi, alpha, omega, dweller. Roster membership only — this "
            f"is a clean refusal, not an error."
        ),
        limits=["roster membership"],
    )


def consult(role: str, task: str) -> Counsel:
    """Ask a crew role about *task*; return a Counsel receipt.

    Unknown roles are refused cleanly (refused=True) — never an exception.
    """
    charter = roles.get_role(role)
    if charter is None:
        return _refuse(role)
    core = get_core(charter.name)
    if core is None:
        return Counsel(
            role=charter.name,
            substrate_used="none",
            refused=True,
            answer=f"The {charter.name} SI core is not wired yet — honest gap.",
            limits=["core wiring"],
        )

    def _fallback(t: str):
        result = core.reason(t)
        return result["answer"], result["rule_tag"]

    substrate_used, answer = substrate.reason(charter.name, task, _fallback)

    limits: List[str] = []
    if substrate_used == "rules-engine":
        limits.append(
            "answered by the native rules engine — trainable SI weights not finished yet"
        )
    limits.append("per-consult reasoning; no memory of past consults")

    return Counsel(
        role=charter.name,
        substrate_used=substrate_used,
        answer=answer,
        limits=limits,
    )


def capability_report(role: str) -> Dict[str, object]:
    """What this role can/can't do YET — honest, per current wiring."""
    charter = roles.get_role(role)
    if charter is None:
        return {
            "role": role,
            "known": False,
            "known_roles": roles.role_names(),
        }
    core = get_core(charter.name)
    weights_dir = str(core.weights_dir()) if core else None
    can = [
        "deterministic rules-engine reasoning, offline, stdlib-only",
        "honest substrate reporting — every consult says what answered",
        f"{charter.epithet} mandate per charter",
    ]
    cannot_yet = [
        "trainable SI weights (no weights at the weights dir yet)",
        "native-brain inference hook (levi.brain has no probe API today)",
        "persistent per-role memory across consults",
    ]
    if charter.name == "alpha":
        cannot_yet.insert(
            0,
            "dedicated levi.alpha substrate (sibling build in flight; rules fallback active)",
        )
    return {
        "role": charter.name,
        "known": True,
        "epithet": charter.epithet,
        "can": can,
        "cannot_yet": cannot_yet,
        "weights_dir": weights_dir,
        "weights_present": core.weights_present() if core else False,
        "substrates_available": [
            "rules-engine",
            "registered probes via register_substrate()",
            "levi.alpha (alpha only, if importable and it yields a reasoner)",
            "native-brain (hook reserved; not wired today)",
        ],
    }
