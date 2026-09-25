"""Nexus revival: mode-aware, confidence-scored provider routing, LEVI-native.

Omega's Nexus was the chat/inference layer: several models, several modes,
and a confidence score explaining *why* a given model was chosen for a
task. This module is that routing policy from scratch — pure decision
logic, no network calls, no provider SDKs.

SOURCING LAW (the one law of Nexus):

LEVI routes only through what is LEVI's own. Two operational sources
exist, and nothing else will ever be one:

- ``"levi-local"`` — LEVI-native on-device capability. This is the
  headliner; it never shares the spotlight.
- ``"levi-si-cloud"`` — LEVI SI Cloud, the only remote source, out of
  the spotlight, never the default.

Anything else is ``"reference"``: studied, compared against, never
served through. Reference providers are NEVER eligible in any mode —
they are echoes, not voices.

Public surface:

- ``Provider`` — ``name``, ``source`` (one of the three lawful values),
  ``kinds`` (frozenset of capability tags like ``"chat"``, ``"code"``,
  ``"vision"``), ``cost`` (lower is cheaper), ``quality`` (0.0–1.0,
  operator-assessed, never asserted as fact). ``local`` is a read-only
  property: True iff ``source == "levi-local"``.
- ``MODES`` — ``fast``, ``balanced``, ``deep``, ``offline``: each a
  documented weighting policy.
- ``route(task, providers, mode="balanced")`` — ranks providers for a
  task, returning ``Route`` entries with ``confidence`` (0.0–1.0) and
  human-readable ``reasons``.
- ``assess_task_risk(task)`` — documented heuristic mapping a task dict's
  ``"kinds"`` to a risk tier (``"standard"`` / ``"elevated"`` /
  ``"critical"``); an explicit ``"risk"`` wins when it is a valid tier.
- ``route_guarded(substrate, task, providers, mode="balanced",
  approved_by=None)`` — ``route()`` under the shared risk ceiling:
  sourcing-law eligibility, the approval gate, the HITL gate for
  critical tasks, and a recorded receipt for every outcome. A refusal
  is a receipt, not silence — the Nexus→refuses→route interrogation
  path.

SYMBIOTIC INVARIANT (the Nexus law in the shared bloodstream):

"Nexus never routes through a source LEVI doesn't own, and never routes
above the approved ceiling. A refusal is a receipt, not silence."

Guarded in code by ``route_guarded`` and proven (behaviorally, honestly
named) in ``tests/test_omega_nexus_symbiotic.py``.

``Task`` is ``{"kinds": {...}, "needs_local": bool}`` — what the job needs,
not how to do it.

Defensive notes:

- ``offline`` mode is deny-closed: only ``levi-local`` providers are
  eligible, and if none exist the result says so explicitly instead of
  leaking the task to a remote provider.
- Confidence is a *policy score*, labeled as such — it ranks options, it
  does not measure real-world accuracy.
- Unknown modes and empty provider lists raise ``ValueError`` loudly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence

from levi.revival.omega import substrate as sub

ORIGIN = "levi-revival-omega/nexus"

# The only lawful operational sources. Everything else is reference-only.
SOURCE_LOCAL = "levi-local"  # LEVI-native on-device capability
SOURCE_CLOUD = "levi-si-cloud"  # LEVI SI Cloud — the only remote source
SOURCE_REFERENCE = "reference"  # any other system: comparison only, never operational
SOURCES = frozenset({SOURCE_LOCAL, SOURCE_CLOUD, SOURCE_REFERENCE})

REFERENCE_DENY_REASON = (
    "reference-only: I study this one, I never serve through it — "
    "never an operational source"
)

# mode -> {description, weights}
MODES: Dict[str, Dict[str, object]] = {
    "fast": {
        "description": "Cheapest eligible provider that covers the task kinds.",
        "kind_weight": 3.0,
        "cost_weight": 2.0,
        "quality_weight": 0.5,
        "local_bonus": 0.2,
    },
    "balanced": {
        "description": "Trade cost against quality; prefer kind coverage.",
        "kind_weight": 3.0,
        "cost_weight": 1.0,
        "quality_weight": 1.5,
        "local_bonus": 0.3,
    },
    "deep": {
        "description": "Best quality for the task kinds; cost is secondary.",
        "kind_weight": 3.0,
        "cost_weight": 0.3,
        "quality_weight": 3.0,
        "local_bonus": 0.1,
    },
    "offline": {
        "description": "LEVI-local only. Nothing leaves the machine.",
        "kind_weight": 3.0,
        "cost_weight": 0.5,
        "quality_weight": 1.5,
        "local_bonus": 2.0,
    },
}


@dataclass(frozen=True)
class Provider:
    name: str
    source: str = SOURCE_REFERENCE
    kinds: FrozenSet[str] = field(default_factory=frozenset)
    cost: int = 5  # 1 (cheapest) .. 10
    quality: float = 0.5  # operator-assessed 0.0..1.0

    @property
    def local(self) -> bool:
        """True iff this provider is LEVI-native on-device capability."""
        return self.source == SOURCE_LOCAL

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("provider name must be non-empty")
        if self.source not in SOURCES:
            raise ValueError(
                f"source must be one of {sorted(SOURCES)}; got {self.source!r}"
            )
        if not 1 <= self.cost <= 10:
            raise ValueError("cost must be 1..10")
        if not 0.0 <= self.quality <= 1.0:
            raise ValueError("quality must be 0.0..1.0")


@dataclass
class Task:
    kinds: FrozenSet[str] = field(default_factory=frozenset)
    needs_local: bool = False
    label: str = ""


@dataclass
class Route:
    provider: str
    confidence: float
    reasons: List[str]
    eligible: bool = True


def _score(provider: Provider, task: Task, weights: Dict[str, object]) -> Route:
    reasons: List[str] = []
    if task.needs_local and not provider.local:
        return Route(
            provider=provider.name,
            confidence=0.0,
            reasons=["excluded: task needs LEVI-local, provider is not on-device"],
            eligible=False,
        )
    kinds = set(task.kinds)
    covered = kinds & set(provider.kinds)
    missing = kinds - set(provider.kinds)
    kind_frac = (len(covered) / len(kinds)) if kinds else 1.0
    if missing:
        reasons.append(f"missing kinds: {sorted(missing)}")
    else:
        reasons.append(f"covers kinds: {sorted(covered) or 'any'}")
    # cost component: cheaper -> higher (cost 1..10 mapped to 1.0..0.0)
    cost_comp = 1.0 - (provider.cost - 1) / 9.0
    score = (
        float(weights["kind_weight"]) * kind_frac
        + float(weights["cost_weight"]) * cost_comp
        + float(weights["quality_weight"]) * provider.quality
        + (float(weights["local_bonus"]) if provider.local else 0.0)
    )
    max_score = (
        float(weights["kind_weight"])
        + float(weights["cost_weight"])
        + float(weights["quality_weight"])
        + float(weights["local_bonus"])
    )
    confidence = round(score / max_score, 3) if max_score else 0.0
    if provider.local:
        reasons.append("runs on-device (LEVI-native)")
    elif provider.source == SOURCE_CLOUD:
        reasons.append("via LEVI SI Cloud (the only remote source)")
    reasons.append(f"cost {provider.cost}/10, quality {provider.quality}")
    return Route(provider=provider.name, confidence=confidence, reasons=reasons)


def route(
    task: Task,
    providers: Sequence[Provider],
    mode: str = "balanced",
) -> List[Route]:
    """Rank providers for ``task`` under ``mode``; best first.

    Reference providers are NEVER eligible in any mode: they are
    studied, never served through. Ineligible providers (references,
    remotes under ``offline`` mode, or remotes for a ``needs_local``
    task) sort last with ``eligible=False``.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode!r} (expected one of {sorted(MODES)})")
    if not providers:
        raise ValueError("providers must be non-empty")
    names = [p.name for p in providers]
    if len(set(names)) != len(names):
        raise ValueError("provider names must be unique")
    weights = MODES[mode]
    ranked: List[Route] = []
    for p in providers:
        if p.source == SOURCE_REFERENCE:
            # sourcing law: references never route, in any mode
            ranked.append(
                Route(
                    provider=p.name,
                    confidence=0.0,
                    reasons=[REFERENCE_DENY_REASON],
                    eligible=False,
                )
            )
        elif mode == "offline" and not p.local:
            # deny-closed: nothing leaves the machine
            ranked.append(
                Route(
                    provider=p.name,
                    confidence=0.0,
                    reasons=["excluded: offline mode allows LEVI-local only"],
                    eligible=False,
                )
            )
        else:
            ranked.append(_score(p, task, weights))
    ranked.sort(key=lambda r: (r.eligible, r.confidence), reverse=True)
    return ranked


# ---------------------------------------------------------------------------
# Symbiotic layer: guarded routing on the shared substrate
# ---------------------------------------------------------------------------
# NEXUS INVARIANT: "Nexus never routes through a source LEVI doesn't own,
# and never routes above the approved ceiling. A refusal is a receipt,
# not silence."

ORGAN = "nexus"  # origin tag on every receipt Nexus writes

# Task-kind tags that raise a task's risk tier. Honest documented
# heuristic: these are labels read from the task's own declaration, not
# measured real-world danger. When in doubt, the caller declares higher.
RISK_CRITICAL_KINDS = frozenset({"hitl", "irreversible", "external-send"})
RISK_ELEVATED_KINDS = frozenset(
    {"payment", "money", "browser", "write", "deploy", "network", "exec", "shell"}
)

# Nexus holds standing authority to refuse: the Nexus→refuses→route
# interrogation path needs no external approval to be *recorded*. A
# refusal is never an execution of the risky action, so it is written
# under the organ's own hand and says so in the payload.
SELF_APPROVAL = "nexus:self"


def assess_task_risk(task: Dict[str, Any]) -> str:
    """Map a task dict to a risk tier: ``"standard"`` / ``"elevated"`` /
    ``"critical"``.

    ``task`` carries ``"kinds"`` (a set of capability tags) and may carry
    an explicit ``"risk"``, which wins when it is a valid tier; an
    invalid or absent ``"risk"`` falls through to the heuristic:

    - kinds ∩ {"hitl", "irreversible", "external-send"} → "critical"
    - kinds ∩ {"payment", "money", "browser", "write", "deploy",
      "network", "exec", "shell"} → "elevated"
    - else → "standard"

    This is a label from the task's self-declaration, not a measurement
    of real-world danger.
    """
    if not isinstance(task, dict):
        raise ValueError(
            f"task must be a dict with 'kinds'; got {type(task).__name__}"
        )
    explicit = task.get("risk")
    if explicit in sub.RISK_ORDER:
        return explicit
    kinds = set(task.get("kinds") or set())
    if kinds & RISK_CRITICAL_KINDS:
        return sub.RISK_CRITICAL
    if kinds & RISK_ELEVATED_KINDS:
        return sub.RISK_ELEVATED
    return sub.RISK_STANDARD


def _guarded_eligible(
    task_kinds: FrozenSet[str],
    providers: Sequence[Provider],
    mode: str,
) -> tuple:
    """Lawful eligibility for a guarded route: LEVI-owned sources only,
    full kind coverage, and offline mode deny-closed to on-device."""
    eligible: List[Provider] = []
    reasons: List[str] = []
    for p in providers:
        if p.source == SOURCE_REFERENCE:
            reasons.append(
                f"{p.name}: excluded — reference-only, never an operational source"
            )
        elif not task_kinds <= set(p.kinds):
            missing = sorted(task_kinds - set(p.kinds))
            reasons.append(f"{p.name}: excluded — missing kinds {missing}")
        elif mode == "offline" and not p.local:
            reasons.append(f"{p.name}: excluded — offline mode allows LEVI-local only")
        else:
            eligible.append(p)
    return eligible, reasons


def route_guarded(
    substrate: "sub.SharedSubstrate",
    task: Dict[str, Any],
    providers: Sequence[Provider],
    mode: str = "balanced",
    approved_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Route ``task`` under the shared risk ceiling, with receipts.

    ``task`` is a dict with ``"kinds"`` (a set of capability tags) and an
    optional explicit ``"risk"``. Steps, in order:

    1. ``task_risk = assess_task_risk(task)``; ``ceiling =
       sub.ceiling_for("nexus", action_risk=task_risk)`` — the strictest
       tier governs, trust never flows downhill.
    2. The ceiling gate: if the ceiling requires approval (elevated+) and
       no ``approved_by`` was recorded, Nexus REFUSES — and records a
       ``route_refusal`` receipt under its own standing refusal authority.
    3. The HITL gate: a critical task routes only on an explicit human
       approval — ``approved_by`` must start with ``"hitl:"``. Anything
       else is refused, loudly.
    4. Sourcing-law eligibility: only ``levi-local`` / ``levi-si-cloud``
       providers covering every task kind; offline mode additionally
       deny-closed to on-device. No eligible provider → ``route_refusal``
       receipt, never silence.
    5. Otherwise the existing ``route()`` ranks the eligible providers,
       the top route is recorded as a ``route`` receipt (``"hitl": True``
       in the payload for critical tasks), and the decision returns.

    Returns ``{"ok": True, "provider", "confidence", "reasons",
    "ceiling", "receipt_id"}`` on a route, or ``{"ok": False,
    "refusal", "ceiling", "receipt_id", ...}`` on a refusal. Unknown
    modes and non-dict tasks raise ``ValueError`` loudly; the existing
    ``route()`` signature is untouched.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode!r} (expected one of {sorted(MODES)})")
    if not isinstance(task, dict):
        raise ValueError(
            f"task must be a dict with 'kinds'; got {type(task).__name__}"
        )
    task_kinds = frozenset(task.get("kinds") or set())
    task_risk = assess_task_risk(task)
    ceiling = sub.ceiling_for(ORGAN, action_risk=task_risk)

    def _refuse(reason: str, extra: Dict[str, Any]) -> "sub.Receipt":
        # A refusal is a receipt, not silence. Nexus records it under its
        # own standing refusal authority — refusing needs no external
        # approval; executing would have.
        return substrate.record_receipt(
            organ=ORGAN,
            kind="route_refusal",
            payload={
                "reason": reason,
                "task_kinds": sorted(task_kinds),
                "ceiling": ceiling,
                "recorded_under": SELF_APPROVAL + " — standing refusal authority",
                **extra,
            },
            risk=ceiling,
            approved_by=SELF_APPROVAL,
        )

    # --- the ceiling gate: elevated+ needs a recorded approval ---
    if sub.requires_approval(ceiling) and not approved_by:
        receipt = _refuse(
            f"approval required for ceiling {ceiling}",
            {"approval": "missing"},
        )
        return {
            "ok": False,
            "refusal": "approval required",
            "ceiling": ceiling,
            "receipt_id": receipt.id,
        }

    # --- the HITL gate: critical tasks need an explicit human hand ---
    if task_risk == sub.RISK_CRITICAL and not (
        approved_by and approved_by.startswith("hitl:")
    ):
        receipt = _refuse(
            "critical task: human-in-the-loop approval required "
            "(approved_by must start with 'hitl:')",
            {"hitl": True, "approval": approved_by or "missing"},
        )
        return {
            "ok": False,
            "refusal": "approval required",
            "ceiling": ceiling,
            "receipt_id": receipt.id,
        }

    # --- sourcing-law eligibility (deny-closed, never silent) ---
    eligible, reasons = _guarded_eligible(task_kinds, providers, mode)
    if not eligible:
        receipt = substrate.record_receipt(
            organ=ORGAN,
            kind="route_refusal",
            payload={
                "reason": "no eligible provider",
                "task_kinds": sorted(task_kinds),
                "ceiling": ceiling,
                "mode": mode,
                "exclusions": reasons or ["no providers were offered"],
            },
            risk=ceiling,
            approved_by=approved_by,  # present whenever ceiling needs one
        )
        return {
            "ok": False,
            "refusal": "no eligible provider",
            "reasons": reasons,
            "ceiling": ceiling,
            "receipt_id": receipt.id,
        }

    # --- route: the existing policy brain decides among the eligible ---
    routes = route(Task(kinds=task_kinds), eligible, mode=mode)
    top = routes[0]
    payload: Dict[str, Any] = {
        "provider": top.provider,
        "confidence": top.confidence,
        "ceiling": ceiling,
        "mode": mode,
    }
    if task_risk == sub.RISK_CRITICAL:
        payload["hitl"] = True  # loud: a human hand was on this route
    receipt = substrate.record_receipt(
        organ=ORGAN,
        kind="route",
        payload=payload,
        risk=ceiling,
        approved_by=approved_by,  # required by the substrate at elevated+
    )
    return {
        "ok": True,
        "provider": top.provider,
        "confidence": top.confidence,
        "reasons": top.reasons,
        "ceiling": ceiling,
        "receipt_id": receipt.id,
    }


def explain(routes: Sequence[Route]) -> str:
    """One-line-per-route human summary of a routing decision."""
    lines = []
    for r in routes:
        status = "OK " if r.eligible else "SKIP"
        lines.append(
            f"[{status}] {r.provider} conf={r.confidence:.3f} — " + "; ".join(r.reasons)
        )
    return "\n".join(lines)
