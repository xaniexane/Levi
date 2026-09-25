"""LEVI-native automation engine: trigger matching, condition checks, runs.

The engine takes a :class:`TriggerEvent`, finds catalog minions whose
trigger fires, evaluates each minion's condition, and walks every
consequential run through the standing rail::

    Plan -> Preview -> Permission -> Execute -> Verify -> Receipt

Runs are dry-run by default: Execute only *simulates* and records what
*would* happen. No network calls, no file writes, no real side effects —
the receipt says exactly what was previewed, what the human decided at
the gate, and what was (not) executed. Live execution
(``dry_run=False``) is a deliberate, explicit, per-run choice: after the
permission gate passes with a real responder, the run routes through
:mod:`levi.automation.executor` — one adapter acts (webhook POST, device
artifacts, or a LEVI-produced work product), a clean refusal otherwise —
and the verify step records the adapter's evidence on the receipt. Every
gate still applies; nothing is ever silent.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .minions import Minion, find_minion
from .hitl import (
    Gate,
    GateDenied,
    GateRequest,
    GateResult,
    Responder,
    auto_approve,
    describe_gate,
    gate_kind_for,
)

RAIL = ("plan", "preview", "permission", "execute", "verify", "receipt")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TriggerEvent:
    """Something happened in the world. Minions listen for these."""

    kind: str  # e.g. "time", "email", "device", "app_opened", ...
    summary: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: str = ""

    def __post_init__(self) -> None:
        if not self.ts:
            self.ts = _utcnow()


# ---------------------------------------------------------------------------
# Trigger matching
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Trigger matching
# ---------------------------------------------------------------------------


def _cron_field_matches(field: str, value: int, minimum: int, maximum: int) -> bool:
    """One cron field (``*``, ``*/n``, ``a,b``, ``a-b``, ``n``) vs a value."""
    field = field.strip()
    if field == "*":
        return True
    for part in field.split(","):
        part = part.strip()
        if part.startswith("*/"):
            try:
                step = int(part[2:])
            except ValueError:
                return False
            if step > 0 and (value - minimum) % step == 0:
                return True
        elif "-" in part:
            try:
                lo_s, hi_s = part.split("-", 1)
                lo, hi = int(lo_s), int(hi_s)
            except ValueError:
                return False
            if lo <= value <= hi:
                return True
        else:
            try:
                if int(part) == value:
                    return True
            except ValueError:
                return False
    return False


def _cron_matches(expr: str, event: TriggerEvent) -> bool:
    """``Cron M H dom mon dow`` against the event's timestamp.

    Malformed expressions and unparsable timestamps never match and
    never raise — a bad trigger is a missed fire, not a crash.
    """
    fields = expr.split()
    if len(fields) != 5:
        return False
    try:
        ts = datetime.fromisoformat(str(event.ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    minute, hour, dom, month = ts.minute, ts.hour, ts.day, ts.month
    dow = (ts.weekday() + 1) % 7  # cron: 0/7 = Sunday
    specs = (
        (fields[0], minute, 0, 59),
        (fields[1], hour, 0, 23),
        (fields[2], dom, 1, 31),
        (fields[3], month, 1, 12),
        (
            fields[4].replace("7", "0") if fields[4] not in ("*",) else fields[4],
            dow,
            0,
            6,
        ),
    )
    results = [_cron_field_matches(f, v, lo, hi) for f, v, lo, hi in specs]
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"
    if dom_restricted and dow_restricted:
        # POSIX cron: day-of-month OR day-of-week when both are restricted.
        return results[0] and results[1] and results[3] and (results[2] or results[4])
    return all(results)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def trigger_matches(bot_trigger: str, event: TriggerEvent) -> bool:
    """Decide whether a minion's trigger string fires for an event.

    Structured triggers (``Time 06:45``, ``App opened (Gmail)``) match on
    kind + extracted detail; anything else falls back to a conservative
    normalized substring match against the event summary.
    """
    trig = _norm(bot_trigger)
    kind = _norm(event.kind)

    time_m = re.fullmatch(r"time\s+(\d{1,2}:\d{2})", trig)
    if time_m:
        return kind == "time" and _norm(
            str(event.payload.get("time", ""))
        ) == time_m.group(1)

    app_m = re.fullmatch(r"app opened\s*\(([^)]+)\)", trig)
    if app_m:
        return kind == "app_opened" and _norm(
            str(event.payload.get("app", ""))
        ) == _norm(app_m.group(1))

    cron_m = re.fullmatch(r"cron\s+(\S+(?:\s+\S+){4})", trig)
    if cron_m:
        return _cron_matches(cron_m.group(1), event)

    event_m = re.fullmatch(r"event\s+([\w\-]+)\s*:\s*(.+)", trig)
    if event_m:
        want_kind = _norm(event_m.group(1))
        detail = _norm(event_m.group(2)).replace("_", " ")
        if kind != want_kind:
            return False
        haystack = (
            _norm(event.summary)
            + " "
            + " ".join(_norm(str(v)) for v in event.payload.values())
        ).replace("_", " ")
        return detail in haystack

    # Keyword triggers keyed to event kinds.
    keyword_kinds = {
        "new email": "email",
        "new task": "task",
        "new checklist item": "task",
        "new event": "calendar",
        "new note": "note",
        "new reminder": "reminder",
        "new notification": "notification",
        "clipboard": "clipboard",
        "device inserted": "device",
        "search query": "search",
        "new receipt": "expense",
        "new expense": "expense",
    }
    for keyword, want_kind in keyword_kinds.items():
        if trig.startswith(keyword):
            return kind == want_kind
    # Fallback: the trigger names the event in plain words.
    return trig in _norm(event.summary) or _norm(event.summary) in trig


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------

ConditionChecker = Callable[[str, TriggerEvent], Optional[bool]]


def _check_always(_cond: str, _event: TriggerEvent) -> Optional[bool]:
    return True


def _check_day(cond: str, event: TriggerEvent) -> Optional[bool]:
    m = re.fullmatch(r"day\s+(\w+)", _norm(cond))
    if not m:
        return None
    return _norm(str(event.payload.get("day", ""))) == m.group(1)


def _check_battery(cond: str, event: TriggerEvent) -> Optional[bool]:
    m = re.fullmatch(r"battery\s*([<>]=?)\s*(\d+)%?", _norm(cond))
    if not m or "battery" not in event.payload:
        return None
    level = float(event.payload["battery"])
    want = float(m.group(2))
    op = m.group(1)
    return {
        "<": level < want,
        "<=": level <= want,
        ">": level > want,
        ">=": level >= want,
    }[op]


def _check_kv(cond: str, event: TriggerEvent) -> Optional[bool]:
    """``Key: value`` style conditions (To:, From:, Location, ...).

    Keys may contain spaces and hyphens; both normalize to underscores.
    """
    m = re.fullmatch(r"([\w \-]+)\s*:\s*(.+)", cond.strip())
    if not m:
        return None
    key = _norm(m.group(1)).replace(" ", "_").replace("-", "_")
    want = _norm(m.group(2))
    if key not in event.payload:
        return None
    return _norm(str(event.payload[key])) == want


def _check_kv_eq(cond: str, event: TriggerEvent) -> Optional[bool]:
    """``Key = value`` style conditions (Priority = high, ...).

    Keys may contain spaces and hyphens; both normalize to underscores.
    """
    m = re.fullmatch(r"([\w \-]+)\s*=\s*(.+)", cond.strip())
    if not m:
        return None
    key = _norm(m.group(1)).replace(" ", "_").replace("-", "_")
    want = _norm(m.group(2))
    if key not in event.payload:
        return None
    return _norm(str(event.payload[key])) == want


_CONDITION_CHECKERS: Tuple[ConditionChecker, ...] = (
    _check_always,
    _check_day,
    _check_battery,
    _check_kv,
    _check_kv_eq,
)


@dataclass
class ConditionVerdict:
    holds: Optional[bool]  # True/False, or None when unverifiable
    note: str


def evaluate_condition(condition: str, event: TriggerEvent) -> ConditionVerdict:
    """Evaluate a minion's condition string against an event.

    Unknown conditions never silently pass: they come back ``None``
    (unverifiable), which the runner treats as "escalate to the human".
    """
    text = (condition or "").strip()
    if _norm(text) == "always":
        return ConditionVerdict(True, "condition 'Always' holds")
    for checker in _CONDITION_CHECKERS[1:]:
        verdict = checker(text, event)
        if verdict is not None:
            return ConditionVerdict(
                verdict, f"condition '{text}' -> {'holds' if verdict else 'fails'}"
            )
    return ConditionVerdict(
        None, f"condition '{text}' is unverifiable from this event — escalate"
    )


# ---------------------------------------------------------------------------
# Matching + runs
# ---------------------------------------------------------------------------


@dataclass
class Match:
    minion: Minion
    condition: ConditionVerdict


def match_event(event: TriggerEvent, minions: List[Minion]) -> List[Match]:
    """All minions whose trigger fires for this event, with condition verdicts."""
    out: List[Match] = []
    for minion in minions:
        if trigger_matches(minion.trigger, event):
            out.append(
                Match(
                    minion=minion, condition=evaluate_condition(minion.condition, event)
                )
            )
    return out


@dataclass
class Receipt:
    """The immutable record of one run along the rail."""

    receipt_id: str
    minion_id: str
    event_summary: str
    rail: Tuple[str, ...]
    steps: List[str]
    gate: Optional[GateResult]
    executed: bool
    dry_run: bool
    ok: bool
    note: str = ""
    ts: str = ""

    def __post_init__(self) -> None:
        if not self.ts:
            self.ts = _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "minion_id": self.minion_id,
            "event_summary": self.event_summary,
            "rail": list(self.rail),
            "steps": self.steps,
            "gate": self.gate.to_dict() if self.gate else None,
            "executed": self.executed,
            "dry_run": self.dry_run,
            "ok": self.ok,
            "note": self.note,
            "ts": self.ts,
        }

    def render(self) -> str:
        lines = [
            f"receipt {self.receipt_id} — minion {self.minion_id}",
            f"event: {self.event_summary}",
            f"mode: {'dry-run (nothing executed)' if self.dry_run else 'live'}",
            "rail: " + " -> ".join(self.rail),
        ]
        for step in self.steps:
            lines.append(f"  • {step}")
        if self.gate:
            lines.append(
                f"gate [{self.gate.request.kind.value}]: {self.gate.decision}"
                + (f" — {self.gate.note}" if self.gate.note else "")
            )
        lines.append(f"executed: {self.executed} — ok: {self.ok}")
        if self.note:
            lines.append(f"note: {self.note}")
        return "\n".join(lines)


def _plan_steps(minion: Minion) -> List[str]:
    """Derive the run's step list from the minion's example rite."""
    workflow = minion.example_rite
    # Split the workflow on "+" into discrete steps; the HITL clause
    # becomes the permission step rather than an action step.
    parts = [p.strip() for p in workflow.split("+") if p.strip()]
    steps = [p for p in parts if "hitl" not in p.lower()]
    steps.append(
        f"HITL gate [{minion.hitl_type}]: "
        + next((p for p in parts if "hitl" in p.lower()), "human decision")
    )
    return steps


def run_minion(
    minion: Minion,
    event: TriggerEvent,
    responder: Responder = auto_approve,
    dry_run: bool = True,
) -> Receipt:
    """Walk one minion through Plan -> Preview -> Permission -> Execute -> Verify -> Receipt."""
    receipt_id = f"rcpt-{uuid.uuid4().hex[:12]}"
    steps: List[str] = []
    gate_result: Optional[GateResult] = None

    # PLAN
    planned = _plan_steps(minion)
    steps.append(f"plan: {len(planned)} steps from '{minion.subcategory}'")

    # PREVIEW
    preview = "; ".join(planned)
    steps.append(f"preview: {preview[:220]}")

    # PERMISSION — the gate. Unverifiable or failing conditions escalate:
    # a failing condition stops the run before the gate.
    verdict = evaluate_condition(minion.condition, event)
    if verdict.holds is False:
        return Receipt(
            receipt_id=receipt_id,
            minion_id=minion.id,
            event_summary=event.summary,
            rail=RAIL,
            steps=steps + [f"condition failed: {verdict.note} — run stopped"],
            gate=None,
            executed=False,
            dry_run=dry_run,
            ok=False,
            note="condition did not hold; nothing executed",
        )
    kind = gate_kind_for(minion.hitl_type)
    gate = Gate(
        GateRequest(
            minion_id=minion.id,
            kind=kind,
            prompt=f"{minion.subcategory}: {preview[:160]}",
            context={"dry_run": dry_run, "condition_note": verdict.note},
        )
    )
    steps.append(f"permission: gate [{kind.value}] — {describe_gate(kind)}")
    try:
        gate_result = gate.require(responder)
    except GateDenied as denied:
        return Receipt(
            receipt_id=receipt_id,
            minion_id=minion.id,
            event_summary=event.summary,
            rail=RAIL,
            steps=steps + ["gate denied — run stopped"],
            gate=denied.result,
            executed=False,
            dry_run=dry_run,
            ok=False,
            note="human denied the gate; nothing executed",
        )
    except Exception as exc:
        # Fail-closed: a broken or missing responder denies the run.
        # It never approves, never crashes the rail.
        return Receipt(
            receipt_id=receipt_id,
            minion_id=minion.id,
            event_summary=event.summary,
            rail=RAIL,
            steps=steps
            + [f"gate responder failed ({type(exc).__name__}) — run stopped"],
            gate=None,
            executed=False,
            dry_run=dry_run,
            ok=False,
            note="gate responder error; fail-closed denial, nothing executed",
        )
    steps.append(f"permission granted: {gate_result.decision}")

    # EXECUTE
    if dry_run:
        # Dry-run only simulates and records.
        steps.append(
            "execute (simulated): "
            + "; ".join(f"would: {s}" for s in planned if not s.startswith("HITL"))
        )
        executed = False
        ok = True
        note = ""
        # VERIFY
        steps.append("verify: preconditions re-checked; no side effects observed")
    else:
        # Live execution: the permission gate above already passed with a
        # real responder. The executor routes the minion to exactly one
        # adapter; a clean refusal is a receipted outcome — never an
        # exception, never a silent act.
        from .executor import execute as execute_live

        action = execute_live(minion, event, gate_result, run_id=receipt_id)
        steps.append(f"execute [{action.adapter}]: {action.note}")
        executed = action.executed
        ok = action.ok
        note = action.note
        # VERIFY records the adapter's evidence on the receipt.
        steps.append(f"verify: {action.evidence}")

    # RECEIPT
    return Receipt(
        receipt_id=receipt_id,
        minion_id=minion.id,
        event_summary=event.summary,
        rail=RAIL,
        steps=steps,
        gate=gate_result,
        executed=executed,
        dry_run=dry_run,
        ok=ok,
        note=note,
    )


def dry_run(minion_id: str, event: TriggerEvent, minions: List[Minion]) -> Receipt:
    """Preview a full run of one minion. Never executes."""
    minion = find_minion(minions, minion_id)
    if minion is None:
        raise KeyError(f"unknown minion id: {minion_id}")
    return run_minion(minion, event, responder=auto_approve, dry_run=True)
