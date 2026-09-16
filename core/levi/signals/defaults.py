"""Default accountability instincts: the documented instinct specs from the
accountability, state & alignment, and energy/friction/sweeps modules,
registered on the :class:`InstinctRegistry`.

Each instinct's handler calls the owning module's ``check()``-equivalent
and translates its plain-string-grade dicts into real :class:`Signal`
objects (grade-capped at ``max_grade`` by the registry itself).

Evidence keys (evaluated by :func:`accountability_evidence`)::

    promises.overdue>=1        # any overdue promise  -> CARD (12h)
    promises.overdue_severe     # any ESCALATE-grade overdue -> ESCALATE (24h)
    decisions.revisit_due>=1    # decisions past revisit -> CARD (24h)
    interruptions.logged_7d     # anything logged in 7d -> NUDGE (7d)
    drift.card                  # weekly drift card fired -> CARD (7d)
    friction.captured>=3        # >=3 friction notes in 7d -> NUDGE (7d)
    teachback.due               # model untouched >=30d -> NUDGE (30d)
    energy.deep_shipped>=1      # internal peak recompute -> SILENT (7d)
    sweeps.have_specs>=1        # hygiene-sweep reminder -> NUDGE (7d)

Registered instincts::

    instinct.promise_overdue / instinct.promise_overdue_severe
    instinct.decision_revisit
    instinct.interruption_noise
    instinct.drift_card
    instinct.friction_review
    instinct.teachback_review
    instinct.energy_recompute
    instinct.sweep_cadence

Documented but NOT registered: ``instinct.premortem_before_lock`` would
fire on ``commitments.big_locked`` when a big commitment locks — but no
module emits that evidence (verified: neither the commitments nor the
premortem package has a "big lock" concept). Registering it would be a
dead spec, so it stays documented here until a real evidence source
exists.

Home resolution: the signal plane's ``home`` is the LEVI state home
(``<home>/signals/cooldowns.json``). The promises/decisions/interruptions
modules resolve storage under ``<user-base>/.levi/...`` (their own
convention), so they receive ``home.parent`` when the state home is
named ``.levi`` — the same translation ``wiring.commitments_missed``
already uses. Everything is read-only and best-effort: a missing or
unreadable store yields no evidence, never an exception.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.signals.grades import Signal, SignalGrade
from levi.signals.instincts import Instinct, InstinctRegistry

__all__ = [
    "accountability_evidence",
    "register_default_instincts",
    "EVIDENCE_KEYS",
]

EVIDENCE_KEYS = (
    "promises.overdue",
    "promises.overdue_severe",
    "decisions.revisit_due",
    "interruptions.logged_7d",
    "drift.card",
    "friction.captured",
    "teachback.due",
    "energy.deep_shipped",
    "sweeps.have_specs",
)

_GRADE_BY_NAME = {
    "SILENT": SignalGrade.SILENT,
    "NUDGE": SignalGrade.NUDGE,
    "CARD": SignalGrade.CARD,
    "ESCALATE": SignalGrade.ESCALATE,
}

_DAY = 24 * 3600


def _grade(name: Any) -> SignalGrade:
    return _GRADE_BY_NAME.get(str(name or "").upper(), SignalGrade.CARD)


def _user_base(home: Path) -> Path:
    """User-base home for modules that store under ``<base>/.levi/...``."""
    return home.parent if home.name == ".levi" else home


def _utc(now: Optional[datetime]) -> datetime:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _parse_iso(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# evidence gatherers (read-only, best-effort, never raise)
# ---------------------------------------------------------------------------


def _promises_evidence(base: Path) -> Dict[str, Any]:
    try:
        from levi.promises import check as promises_check
    except Exception:  # noqa: BLE001 - optional sibling, silence is honest
        return {}
    try:
        items = promises_check(home=_user_base(base)) or []
    except Exception:  # noqa: BLE001 - evidence gathering never raises
        return {}
    items = [i for i in items if isinstance(i, dict)]
    severe = [i for i in items if str(i.get("grade") or "").upper() == "ESCALATE"]
    return {
        "promises.overdue": len(items),
        "promises.overdue_severe": bool(severe),
        "_promises.items": items,
        "_promises.severe": severe,
    }


def _decisions_evidence(base: Path) -> Dict[str, Any]:
    try:
        from levi.decisions import check as decisions_check
    except Exception:  # noqa: BLE001
        return {}
    try:
        items = decisions_check(home=_user_base(base)) or []
    except Exception:  # noqa: BLE001
        return {}
    items = [i for i in items if isinstance(i, dict)]
    return {
        "decisions.revisit_due": len(items),
        "_decisions.items": items,
    }


def _interruptions_evidence(base: Path, now: datetime) -> Dict[str, Any]:
    try:
        from levi.interruptions.interruptions import InterruptionLedger
    except Exception:  # noqa: BLE001
        return {}
    try:
        report = InterruptionLedger(home=_user_base(base)).noise_roi(days=7, now=now)
    except Exception:  # noqa: BLE001
        return {}
    total = int(report.get("total") or 0) if isinstance(report, dict) else 0
    return {
        "interruptions.logged_7d": total > 0,
        "_interruptions.total": total,
    }


def _drift_evidence(base: Path, now: datetime) -> Dict[str, Any]:
    try:
        from levi.drift.tracker import DriftTracker
    except Exception:  # noqa: BLE001
        return {}
    try:
        card = DriftTracker(home=base).weekly_card(now=now)
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(card, dict):
        return {"drift.card": False}
    return {"drift.card": True, "_drift.card": card}


def _friction_evidence(base: Path) -> Dict[str, Any]:
    try:
        from levi.friction.log import FrictionLog
    except Exception:  # noqa: BLE001
        return {}
    try:
        count = len(FrictionLog(home=base).entries(since_days=7))
    except Exception:  # noqa: BLE001
        return {}
    return {"friction.captured": count}


def _teachback_evidence(base: Path, now: datetime) -> Dict[str, Any]:
    try:
        from levi.teachback.model import TeachbackModel
    except Exception:  # noqa: BLE001
        return {}
    try:
        statements = TeachbackModel(home=base).model() or []
    except Exception:  # noqa: BLE001
        return {}
    if not statements:
        return {"teachback.due": False}
    stale = 0
    for s in statements:
        ts = _parse_iso(s.get("updated_at")) if isinstance(s, dict) else None
        if ts is not None and (now - ts).total_seconds() >= 30 * _DAY:
            stale += 1
    return {
        "teachback.due": stale > 0,
        "_teachback.count": len(statements),
        "_teachback.stale": stale,
    }


def _energy_evidence(base: Path) -> Dict[str, Any]:
    try:
        from levi.energy.tracker import EnergyLog
    except Exception:  # noqa: BLE001
        return {}
    try:
        peaks = EnergyLog(home=base).peak_hours()
    except Exception:  # noqa: BLE001
        return {}
    n = int(peaks.get("n_deep_shipped") or 0) if isinstance(peaks, dict) else 0
    return {"energy.deep_shipped": n}


def _sweeps_evidence() -> Dict[str, Any]:
    try:
        from levi.sweeps.sweeps import builtin_specs
    except Exception:  # noqa: BLE001
        return {}
    try:
        count = len(builtin_specs() or [])
    except Exception:  # noqa: BLE001
        return {}
    return {"sweeps.have_specs": count}


def accountability_evidence(
    home: "str | Path | None" = None, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """Evidence for the default accountability instincts.

    ``home`` is the LEVI state home. Missing stores yield no evidence —
    the instincts stay silent, honestly.
    """
    from levi.signals.instincts import levi_home

    base = Path(home).expanduser() if home is not None else levi_home()
    moment = _utc(now)
    evidence: Dict[str, Any] = {
        "_now_iso": moment.isoformat(),
        "_state_home": str(base),
    }
    for gather in (
        lambda: _promises_evidence(base),
        lambda: _decisions_evidence(base),
        lambda: _interruptions_evidence(base, moment),
        lambda: _drift_evidence(base, moment),
        lambda: _friction_evidence(base),
        lambda: _teachback_evidence(base, moment),
        lambda: _energy_evidence(base),
        _sweeps_evidence,
    ):
        try:
            evidence.update(gather())
        except Exception:  # noqa: BLE001 - one bad gatherer never kills the plane
            continue
    return evidence


# ---------------------------------------------------------------------------
# handlers: module dicts -> Signal objects
# ---------------------------------------------------------------------------


def _dict_signal(
    item: Dict[str, Any],
    *,
    tag: str,
    source: str,
    actions: tuple = (),
    requires_ack: bool = False,
    due_now: bool = False,
) -> Signal:
    provenance = str(item.get("tag") or "").strip()
    body = str(item.get("body") or "")
    if provenance:
        body = "(from %s)\n%s" % (provenance, body)
    return Signal(
        grade=_grade(item.get("grade")),
        tag=tag,
        title=str(item.get("title") or "signal"),
        body=body,
        actions=tuple(actions),
        requires_ack=requires_ack,
        due_now=due_now,
        source=source,
    )


def _promise_signal(
    items: List[Dict[str, Any]], *, severe: bool, source: str
) -> Signal:
    shown = items[:3]
    titles = "; ".join(
        '"%s"' % str(i.get("title") or "").replace("Overdue promise — ", "")[:60]
        for i in shown
    )
    more = "" if len(items) <= 3 else " (+%d more)" % (len(items) - 3)
    grade = SignalGrade.ESCALATE if severe else SignalGrade.CARD
    return Signal(
        grade=grade,
        tag="[warden]",
        title="%d overdue promise%s" % (len(items), "" if len(items) == 1 else "s"),
        body=(
            "%s%s Fulfill each one or record it broken with a reason; "
            "broken promises stay on the ledger." % (titles, more)
        ),
        actions=("fulfill", "record broken"),
        requires_ack=severe,
        source=source,
    )


def _promise_overdue_handler(evidence: Dict[str, Any]) -> Optional[Signal]:
    items = [
        i
        for i in evidence.get("_promises.items", [])
        if str(i.get("grade") or "").upper() != "ESCALATE"
    ]
    if not items:
        return None
    return _promise_signal(items, severe=False, source="instinct.promise_overdue")


def _promise_severe_handler(evidence: Dict[str, Any]) -> Optional[Signal]:
    items = evidence.get("_promises.severe") or []
    if not items:
        return None
    return _promise_signal(items, severe=True, source="instinct.promise_overdue_severe")


def _decision_revisit_handler(evidence: Dict[str, Any]) -> Optional[Signal]:
    items = evidence.get("_decisions.items") or []
    if not items:
        return None
    first = items[0]
    titles = "; ".join('"%s"' % str(i.get("title") or "")[:60] for i in items[:3])
    more = "" if len(items) <= 3 else " (+%d more)" % (len(items) - 3)
    signal = _dict_signal(
        first,
        tag="[warden]",
        source="instinct.decision_revisit",
        actions=("reaffirm", "retire"),
    )
    signal.title = "%d decision%s due for revisit" % (
        len(items),
        "" if len(items) == 1 else "s",
    )
    signal.body = "%s%s\n\n%s" % (titles, more, signal.body)
    return signal


def _interruption_noise_handler(evidence: Dict[str, Any]) -> Optional[Signal]:
    state_home = evidence.get("_state_home")
    if not state_home:
        return None
    try:
        from levi.interruptions import check as interruptions_check
    except Exception:  # noqa: BLE001
        return None
    try:
        cards = interruptions_check(home=_user_base(Path(state_home))) or []
    except Exception:  # noqa: BLE001
        return None
    if not cards or not isinstance(cards[0], dict):
        return None
    return _dict_signal(
        cards[0],
        tag="[sentinel]",
        source="instinct.interruption_noise",
        actions=("mute a source", "dismiss"),
    )


def _drift_card_handler(evidence: Dict[str, Any]) -> Optional[Signal]:
    card = evidence.get("_drift.card")
    if not isinstance(card, dict):
        return None
    return _dict_signal(
        card,
        tag="[sentinel]",
        source="instinct.drift_card",
        actions=("adjust the goal", "adjust the week"),
    )


def _friction_review_handler(evidence: Dict[str, Any]) -> Optional[Signal]:
    count = int(evidence.get("friction.captured") or 0)
    state_home = evidence.get("_state_home")
    if not state_home:
        return None
    try:
        from levi.friction.log import FrictionLog

        review = FrictionLog(home=Path(state_home)).weekly_review()
    except Exception:  # noqa: BLE001
        review = {}
    candidates = review.get("candidates") or [] if isinstance(review, dict) else []
    themes = ", ".join(
        "%s (%dx)" % (c.get("theme"), c.get("count"))
        for c in candidates[:5]
        if isinstance(c, dict)
    )
    return Signal(
        grade=SignalGrade.NUDGE,
        tag="[sentinel]",
        title="friction review: %d notes this week" % count,
        body=(
            "Candidate fixes by theme: %s. "
            "One tap per theme: promote to a real fix or drop it."
            % (themes or "none yet")
        ),
        actions=("promote", "drop"),
        source="instinct.friction_review",
    )


def _teachback_review_handler(evidence: Dict[str, Any]) -> Optional[Signal]:
    count = int(evidence.get("_teachback.count") or 0)
    stale = int(evidence.get("_teachback.stale") or 0)
    return Signal(
        grade=SignalGrade.NUDGE,
        tag="[sentinel]",
        title="goal model review: %d of %d statements stale" % (stale, count),
        body=(
            "%d statement(s) in your goal model have not been touched in "
            "30+ days. Render the brief and correct, affirm, or drop what "
            "no longer holds — never present a guess as fact." % stale
        ),
        actions=("render brief", "dismiss"),
        source="instinct.teachback_review",
    )


def _energy_recompute_handler(evidence: Dict[str, Any]) -> Optional[Signal]:
    n = int(evidence.get("energy.deep_shipped") or 0)
    return Signal(
        grade=SignalGrade.SILENT,
        tag="[sentinel]",
        title="energy peaks recomputed",
        body="internal: %d shipped deep session(s) on record; peak windows refreshed."
        % n,
        source="instinct.energy_recompute",
    )


def _sweep_cadence_handler(evidence: Dict[str, Any]) -> Optional[Signal]:
    count = int(evidence.get("sweeps.have_specs") or 0)
    return Signal(
        grade=SignalGrade.NUDGE,
        tag="[sentinel]",
        title="hygiene sweep window is open",
        body=(
            "%d registered sweep spec(s). Run `python -m levi.sweeps run "
            "<data-root>` — safe specs auto-fix, unsafe ones only report. "
            "Broken windows compound; this is the cheap hour to fix them." % count
        ),
        actions=("run sweep", "dismiss"),
        source="instinct.sweep_cadence",
    )


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------


def register_default_instincts(
    registry: InstinctRegistry,
) -> InstinctRegistry:
    """Register the documented default instincts on ``registry``."""
    specs = [
        Instinct(
            id="instinct.promise_overdue",
            fires_on="promises.overdue>=1",
            cooldown=12 * 3600,
            max_grade=SignalGrade.CARD,
            does="surface overdue promises with fulfill / record-broken options",
            handler=_promise_overdue_handler,
            tag="[warden]",
        ),
        Instinct(
            id="instinct.promise_overdue_severe",
            fires_on="promises.overdue_severe",
            cooldown=_DAY,
            max_grade=SignalGrade.ESCALATE,
            does="escalate promises overdue past the escalation threshold",
            handler=_promise_severe_handler,
            tag="[warden]",
        ),
        Instinct(
            id="instinct.decision_revisit",
            fires_on="decisions.revisit_due>=1",
            cooldown=_DAY,
            max_grade=SignalGrade.CARD,
            does="show the decision + reasoning; offer reaffirm / retire",
            handler=_decision_revisit_handler,
            tag="[warden]",
        ),
        Instinct(
            id="instinct.interruption_noise",
            fires_on="interruptions.logged_7d",
            cooldown=7 * _DAY,
            max_grade=SignalGrade.NUDGE,
            does="present the weekly noise ROI card; propose muting top sources",
            handler=_interruption_noise_handler,
            tag="[sentinel]",
        ),
        Instinct(
            id="instinct.drift_card",
            fires_on="drift.card",
            cooldown=7 * _DAY,
            max_grade=SignalGrade.CARD,
            does="surface the weekly drift card once; never nag",
            handler=_drift_card_handler,
            tag="[sentinel]",
        ),
        Instinct(
            id="instinct.friction_review",
            fires_on="friction.captured>=3",
            cooldown=7 * _DAY,
            max_grade=SignalGrade.NUDGE,
            does="run the weekly friction review; ask which themes to promote",
            handler=_friction_review_handler,
            tag="[sentinel]",
        ),
        Instinct(
            id="instinct.teachback_review",
            fires_on="teachback.due",
            cooldown=30 * _DAY,
            max_grade=SignalGrade.NUDGE,
            does="invite a goal-model review: correct, affirm, or drop",
            handler=_teachback_review_handler,
            tag="[sentinel]",
        ),
        Instinct(
            id="instinct.energy_recompute",
            fires_on="energy.deep_shipped>=1",
            cooldown=7 * _DAY,
            max_grade=SignalGrade.SILENT,
            does="recompute peak windows internally; never surfaces",
            handler=_energy_recompute_handler,
            tag="[sentinel]",
        ),
        Instinct(
            id="instinct.sweep_cadence",
            fires_on="sweeps.have_specs>=1",
            cooldown=7 * _DAY,
            max_grade=SignalGrade.NUDGE,
            does="remind about the hygiene sweep; safe auto-fix, unsafe report-only",
            handler=_sweep_cadence_handler,
            tag="[sentinel]",
        ),
    ]
    for spec in specs:
        registry.register(spec)
    return registry
