"""The entrance: Omega as the mega platform, and Alpha as the builder.

Canon (docs/LEXICON.md): "Omega is the entrance and platform; Alpha
built it and keeps it running." So the entrance is a platform call path,
not a module in its own right — it routes through the real Omega organs
in ``levi.revival.omega``:

- understanding is built by Alpha's deliberation (``reasoning`` ->
  ``levi.alpha.reason``: propose -> critique -> verdict);
- the platform is Omega's routing/policy layer (``nexus.route``);
- blueprints are drawn by the Echo organ (``blueprint``) and compiled by
  the Alpha organ (``generators``) — the build crew.

``enter()`` is the single door: one task in, an ``EntrySession`` out,
carrying the deliberation, the routing, and the honest limits of both.
Alpha is imported lazily (through ``reasoning``) so the entrance stays
import-light; if the organs are unavailable the entrance says so loudly
instead of pretending.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


class EntranceError(RuntimeError):
    """The entrance could not admit the task — organs missing or input invalid."""


@dataclass
class EntrySession:
    """One admission through the entrance.

    entrance: always "omega" — Omega is the entrance and platform.
    built_by: always "alpha" — Alpha built it and keeps it running.
    verdict/answer/substrate/limits: Alpha's deliberation, verbatim.
    routes/top_provider/mode: Omega's platform routing, verbatim.
    caveats: everything the caller should not misunderstand.
    brain_voice: the labeled evidence trail — Alpha's brain-voice
        continuation verbatim when the brain ran (heard, never obeyed),
        None when it did not (absent, never invented).
    """

    task_text: str
    entrance: str = "omega"
    built_by: str = "alpha"
    verdict: Dict[str, Any] = field(default_factory=dict)
    answer: str = ""
    task_type: str = ""
    substrate: str = ""
    limits: str = ""
    routes: List[Any] = field(default_factory=list)
    top_provider: Optional[str] = None
    mode: str = "balanced"
    caveats: List[str] = field(default_factory=list)
    # The evidence trail: verbatim brain-voice continuation threaded from
    # the deliberation via ReasonedPlan.brain_voice (the same trail the
    # omega reasoning layer carries) — labeled at display time as heard,
    # never obeyed; None means the brain did not run, never invented.
    brain_voice: Optional[str] = None

    def summary(self) -> Dict[str, Any]:
        return {
            "task": self.task_text,
            "entrance": self.entrance,
            "built_by": self.built_by,
            "task_type": self.task_type,
            "answer": self.answer,
            "verdict_choice": self.verdict.get("choice"),
            "verdict_confidence": self.verdict.get("confidence"),
            "substrate": self.substrate,
            "limits": self.limits,
            "mode": self.mode,
            "top_provider": self.top_provider,
            "brain_voice": self.brain_voice,
            "routes": [
                {
                    "provider": r.provider,
                    "eligible": r.eligible,
                    "confidence": round(r.confidence, 3),
                    "reasons": list(r.reasons),
                }
                for r in self.routes
            ],
            "caveats": list(self.caveats),
        }


def _reasoning():
    try:
        from levi.revival.omega import reasoning

        return reasoning
    except Exception as exc:  # pragma: no cover - organs always present in-tree
        raise EntranceError(
            "the entrance is down: the Omega organs (levi.revival.omega.reasoning) "
            f"could not be reached: {exc}"
        ) from exc


def _fallback_fleet(reasoning):
    """The entrance's own fallback fleet: one lawful local provider.

    Used only when the caller passes no providers — reported in
    ``caveats`` as a fallback, never presented as the caller's fleet.
    """
    nexus = reasoning.nexus
    return [
        nexus.Provider(
            name="levi-local",
            source=nexus.SOURCE_LOCAL,
            kinds=frozenset({"chat"}),
            cost=1,
            quality=0.6,
        )
    ]


def enter(
    task_text: str,
    providers: Optional[Sequence[Any]] = None,
    mode: str = "balanced",
    kinds: Optional[frozenset] = None,
    needs_local: bool = False,
) -> EntrySession:
    """Admit one task through the entrance.

    Runs Alpha's propose -> critique -> verdict deliberation over the
    task text, then routes under Omega's unchanged Nexus policy — the
    same ``reason_route`` call path as ``levi omega route``. One call
    path, one session: "everything in one."
    """
    if not isinstance(task_text, str) or not task_text.strip():
        raise EntranceError(
            "empty task: nothing to enter with — give the entrance a task to admit"
        )
    reasoning = _reasoning()
    fleet: Sequence[Any]
    fleet_caveat: Optional[str] = None
    if providers is None:
        fleet = _fallback_fleet(reasoning)
        fleet_caveat = (
            "no provider fleet supplied: the entrance admitted on its own "
            "fallback fleet (levi-local, chat only) — pass providers to "
            "route on a real fleet"
        )
    else:
        fleet = providers
    plan = reasoning.reason_route(
        task_text, fleet, mode=mode, kinds=kinds, needs_local=needs_local
    )
    caveats = list(plan.caveats)
    if fleet_caveat:
        caveats.append(fleet_caveat)
    session = EntrySession(
        task_text=task_text,
        verdict=dict(plan.verdict),
        answer=str(plan.verdict.get("answer", "")),
        task_type=plan.task_type,
        substrate=plan.substrate,
        limits=plan.limits,
        routes=list(plan.routes),
        top_provider=plan.top_provider,
        mode=mode,
        caveats=caveats,
        brain_voice=plan.brain_voice,
    )
    return session


def build_crew() -> Dict[str, str]:
    """The builder's crew: who built the park and who keeps it running.

    Canon: "Alpha is the engine — the builder of the park. ... Alpha
    built it and keeps it running." A static wiring map (no imports —
    the entrance already proves the call path works via ``enter()``).
    """
    return {
        "designed_by": "levi.revival.omega.blueprint (Echo organ: prompt -> blueprint)",
        "built_by": "levi.revival.omega.generators (Alpha organ: blueprint -> scaffold)",
        "understood_by": "levi.alpha.reason (propose -> critique -> verdict)",
        "routed_by": "levi.revival.omega.nexus (provider routing, sourcing law)",
        "admitted_by": "levi.universe.entrance.enter (the single door)",
    }
