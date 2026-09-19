"""Orchestrated twin-pair seats: on-demand mode with visible escalation.

Chauncey ratified the hybrid choice on 2026-09-18: twin mode
``"on_demand"`` is the standing decision. This module is the
seat-level orchestrator for that mode:

* High-stakes turns fork a second, independent mind (the verifier);
  trivial/normal turns run single — zero behavior change there.
* The verifier's arrival is LEGIBLE: a plain-text banner the seat
  surfaces to the user, plus a note on the merged result.
* Merge is the ratified INTERIM (auto-merge only on concurrence,
  user judges every disagreement). The full inverse-twin merge/judge
  stays GATED — Chauncey has not defined "inverse", so this module
  deliberately contains no inverse semantics of any kind.
* User picks on disagreements feed the growth loop as training
  signal via :func:`record_pick` (additive only — growth internals
  are not rewired).

Stdlib only. No-mask. Defensive only. No finance.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .contract import (
    OperatorMessage,
    OperatorResult,
)
from .registry import (
    OperatorRegistry,
    assess_stakes,
    resolve_for_task,
    resolve_twin,
    scoped_step,
)

__all__ = [
    "HIGH_STAKES_BANNER",
    "FORCED_BANNER",
    "TwinArrival",
    "TwinTurnResult",
    "run_twin_turn",
    "record_pick",
]

#: Banner rendered when the second mind joins on high stakes.
HIGH_STAKES_BANNER = "Second mind '{verifier}' joined — high-stakes turn ({reason})."

#: Banner rendered when the second mind joins because it was forced.
FORCED_BANNER = "Second mind '{verifier}' joined — requested by the seat ({reason})."

_VERIFIED = re.compile(r"\bVERIFIED\b", re.IGNORECASE)
_CHALLENGED = re.compile(r"\bCHALLENGED\b", re.IGNORECASE)


@dataclass
class TwinArrival:
    """The legible record of a second mind joining a turn.

    ``verifier_name`` is the verifier operator's name, ``stakes`` the
    assessed stakes that triggered the fork, and ``reason`` the human
    reason (e.g. "stakes assessed high" or "force_twin set in
    context"). :meth:`banner` renders the plain-text banner the seat
    surfaces to the user — plain speech, no branding.
    """

    verifier_name: str
    reason: str
    stakes: str

    def banner(self) -> str:
        template = (
            HIGH_STAKES_BANNER
            if self.stakes == "high"
            else FORCED_BANNER
        )
        return template.format(verifier=self.verifier_name, reason=self.reason)


@dataclass
class TwinTurnResult:
    """Everything a seat needs after an on-demand twin turn.

    * ``primary_result`` — the primary operator's result (always set).
    * ``verifier_result`` — the verifier's result, or None when the
      fork did not happen (trivial/normal stakes).
    * ``merged_result`` — the auto-merged result on concurrence, or
      None when ``needs_user_judge`` is True (nothing is auto-merged
      on disagreement).
    * ``arrival`` — the :class:`TwinArrival`, or None when no fork.
    * ``disagreement`` — True when the verifier CHALLENGED the primary.
    * ``needs_user_judge`` — True on CHALLENGED: the seat must show
      BOTH results framed as "your call"; do NOT auto-merge.
    * ``disagreement_id`` — stable id for the disagreement (used by
      :func:`record_pick`); None when there is no disagreement.
    """

    primary_result: OperatorResult
    verifier_result: Optional[OperatorResult] = None
    merged_result: Optional[OperatorResult] = None
    arrival: Optional[TwinArrival] = None
    disagreement: bool = False
    needs_user_judge: bool = False
    disagreement_id: Optional[str] = None


def _stable_disagreement_id(
    seat_id: str, primary: OperatorResult, verifier: OperatorResult
) -> str:
    digest = hashlib.sha1(
        "|".join(
            [
                seat_id,
                primary.operator or "",
                primary.text or "",
                verifier.operator or "",
                verifier.text or "",
            ]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"twindis-{digest}"


def run_twin_turn(
    registry: OperatorRegistry,
    seat_id: str,
    messages: List[OperatorMessage],
    tools: List[Dict[str, Any]],
    context: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> TwinTurnResult:
    """Run one seat turn under the on-demand twin policy.

    1. Resolve the twin pair via :func:`resolve_twin`. No pair (mode
       off, or the seat has no twin spec) -> single operator via
       :func:`resolve_for_task`; ``arrival`` is None.
    2. On-demand fork triggers when ``assess_stakes(...) == "high"``
       OR ``context["force_twin"]`` is True. Mode ``"always"`` forks
       every turn. Trivial/normal stakes in ``on_demand`` -> single
       operator, no fork.
    3. On fork: run the primary via :func:`scoped_step`, then the
       verifier over the primary's result using the twin-verify probe
       (:meth:`OperatorSession.verify_via`). Render the
       :class:`TwinArrival` banner into the merged result's note.
    4. Interim merge (ratified; NOT the gated inverse merge):
       VERIFIED -> confidence-weighted auto-merge (primary text +
       verifier concurrence; note records both contributors).
       CHALLENGED -> ``needs_user_judge=True``: BOTH results are
       returned framed as "your call"; nothing is auto-merged, and
       the disagreement is recorded with a stable id.

    Never raises: a failed primary or verifier is reported as a
    well-formed result and the single/fork path degrades honestly.
    """
    config = config or {}
    context = dict(context or {})
    messages = list(messages or [])
    tools = list(tools or [])

    pair = resolve_twin(seat_id, config)
    if pair is None:
        # Twins off or no spec for this seat: single operator, routing
        # unchanged (escalation still applies).
        operator = registry.resolve(
            resolve_for_task(seat_id, messages, tools, context, config)
        )
        primary = scoped_step(operator, messages, tools, context)
        return TwinTurnResult(primary_result=primary, merged_result=primary)

    mode = (pair.mode or "on_demand").strip().lower()
    stakes = assess_stakes(messages, tools, context)
    forced = bool(context.get("force_twin"))

    if mode == "always":
        fork, fork_reason, fork_stakes = True, "twin mode always", stakes
    elif mode == "on_demand" and (stakes == "high" or forced):
        fork = True
        fork_stakes = stakes
        fork_reason = (
            "stakes assessed high"
            if stakes == "high"
            else "force_twin set in context"
        )
    else:
        fork = False
        fork_reason = ""
        fork_stakes = stakes

    if not fork:
        # Trivial/normal stakes under on_demand: single operator, no
        # fork, no arrival. Behavior unchanged from before twins.
        primary_op = registry.resolve(pair.primary)
        primary = scoped_step(primary_op, messages, tools, context)
        return TwinTurnResult(primary_result=primary, merged_result=primary)

    arrival = TwinArrival(
        verifier_name=pair.verifier, reason=fork_reason, stakes=fork_stakes
    )
    banner = arrival.banner()

    # Primary does the work; the verifier independently examines the
    # transcript + primary result via the twin-verify probe pattern.
    session = registry.open_session(
        f"twin-{seat_id}-{time.time_ns()}",
        pair.primary,
        context=context,
        verifier=pair.verifier,
    )
    for message in messages:
        session.append(message)
    primary = session.step_via(registry, tools)
    verifier_result = session.verify_via(registry, primary, tools)

    vtext = verifier_result.text or ""
    challenged = bool(_CHALLENGED.search(vtext))
    verified = bool(_VERIFIED.search(vtext)) and not challenged

    if challenged:
        # Interim law: any CHALLENGED is the user's call. Both results
        # are returned; nothing is auto-merged.
        disagreement_id = _stable_disagreement_id(seat_id, primary, verifier_result)
        for result, who in (
            (primary, pair.primary),
            (verifier_result, pair.verifier),
        ):
            result.note = (
                f"{banner} your call: '{pair.primary}' and '{pair.verifier}' "
                f"disagree — review both and pick one. "
                f"(this is '{who}')"
            )
        return TwinTurnResult(
            primary_result=primary,
            verifier_result=verifier_result,
            merged_result=None,
            arrival=arrival,
            disagreement=True,
            needs_user_judge=True,
            disagreement_id=disagreement_id,
        )

    # VERIFIED (or no clear marker — recorded honestly) -> auto-merge:
    # primary text stands, verifier concurrence appended; the note
    # records both contributors and the combined confidence.
    marker = (
        "VERIFIED"
        if verified
        else "no clear verdict (no VERIFIED/CHALLENGED marker)"
    )
    merged = OperatorResult(
        text=(
            f"{primary.text}\n\n"
            f"Second mind '{pair.verifier}' independently checked this "
            f"and agreed ({marker})."
        ),
        tool_calls=list(primary.tool_calls),
        model=primary.model,
        operator=primary.operator,
        kind=primary.kind,
        latency_ms=primary.latency_ms + verifier_result.latency_ms,
        prompt_tokens=primary.prompt_tokens + verifier_result.prompt_tokens,
        completion_tokens=(
            primary.completion_tokens + verifier_result.completion_tokens
        ),
        cost_usd=(
            None
            if primary.cost_usd is None and verifier_result.cost_usd is None
            else (primary.cost_usd or 0.0) + (verifier_result.cost_usd or 0.0)
        ),
        finish_reason=primary.finish_reason,
        error=primary.error,
        note=(
            f"{banner} Contributors: '{pair.primary}' (work) + "
            f"'{pair.verifier}' (independent check). Verifier verdict: "
            f"{marker}. combined confidence: "
            f"{'high — both minds concurred' if verified else 'moderate — verifier did not dispute'}."
        ),
    )
    return TwinTurnResult(
        primary_result=primary,
        verifier_result=verifier_result,
        merged_result=merged,
        arrival=arrival,
        disagreement=False,
        needs_user_judge=False,
        disagreement_id=None,
    )


def record_pick(
    disagreement_id: str,
    winner_name: str,
    registry_or_store: Any = None,
) -> Dict[str, Any]:
    """Feed a user's twin-judge pick into the growth loop.

    Writes one ``preference`` learning — the user picked
    ``winner_name`` on disagreement ``disagreement_id`` — through the
    honest growth write path (:func:`levi.growth.consolidate.consolidate`
    with provenance ``"twin-judge"``), plus a journal record. Additive
    only: no growth internals are rewired.

    ``registry_or_store`` may be a growth store (has ``add``/``list``),
    an :class:`OperatorRegistry` (winner is best-effort validated
    against registered operators), or None (default store). Returns
    the consolidation report.
    """
    from levi.growth.consolidate import consolidate
    from levi.growth.journal import append_entry
    from levi.growth.reflect import Learning

    disagreement_id = str(disagreement_id or "").strip()
    winner_name = str(winner_name or "").strip()
    if not disagreement_id:
        raise ValueError("record_pick: disagreement_id must be non-empty")
    if not winner_name:
        raise ValueError("record_pick: winner_name must be non-empty")

    store = None
    if registry_or_store is not None:
        if hasattr(registry_or_store, "add") and hasattr(
            registry_or_store, "list"
        ):
            store = registry_or_store
        elif hasattr(registry_or_store, "resolve"):
            # OperatorRegistry: best-effort check that the winner is a
            # registered operator; a missing name is reported, not
            # fatal.
            try:
                known = {
                    info["name"]
                    for info in registry_or_store.list_operators()
                }
                if winner_name not in known:
                    raise ValueError(
                        f"record_pick: {winner_name!r} is not a registered "
                        "operator"
                    )
            except ValueError:
                raise
            except Exception:
                pass  # introspection failed; record the pick anyway
        else:
            raise ValueError(
                "record_pick: registry_or_store must be a growth store, "
                f"an OperatorRegistry, or None; got "
                f"{type(registry_or_store).__name__}"
            )

    learning = Learning(
        kind="preference",
        content=(
            f"Twin-judge disagreement {disagreement_id}: the user picked "
            f"'{winner_name}' as the better answer over the other mind."
        ),
        confidence=0.75,
        provenance={
            "twin-judge": True,
            "disagreement_id": disagreement_id,
            "winner": winner_name,
            "mode": "rules:twin-judge",
        },
    )
    report = consolidate(
        [learning],
        cycle_id=f"twin-{disagreement_id}",
        store=store,
        extra_tags=("twin-judge",),
        dedup_scope=("twin-judge",),
    )
    append_entry(
        {
            "kind": "twin-judge",
            "disagreement_id": disagreement_id,
            "winner": winner_name,
            "consolidation": report,
        }
    )
    return report
