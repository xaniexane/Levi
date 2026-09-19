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
from typing import Dict, FrozenSet, List, Sequence

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


def explain(routes: Sequence[Route]) -> str:
    """One-line-per-route human summary of a routing decision."""
    lines = []
    for r in routes:
        status = "OK " if r.eligible else "SKIP"
        lines.append(
            f"[{status}] {r.provider} conf={r.confidence:.3f} — " + "; ".join(r.reasons)
        )
    return "\n".join(lines)
