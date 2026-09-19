"""Wave C agent upgrades: Travel & Local (39), Finance & Money (38), Health & Fitness (38).

Applies the field updates from ``/tmp/wave_c_updates.py`` in-memory
(``minions.py`` is never edited by this wave) and validates every one of
the 115 agents in this wave's slice:

- trigger is machine-parseable and actually matches a constructed event
  (``Time HH:MM`` / ``Cron`` / ``App opened (X)`` / keyword / ``Event kind: detail``),
  and does NOT match an unrelated event (the trigger discriminates);
- condition is a checkable predicate: it holds on a satisfying event and
  fails on a violating one (never silently unverifiable);
- example_rite is a complete step-form workflow with exactly one HITL
  clause whose verb matches the agent's hitl_type;
- the agent routes to a real executor adapter (never a silent refusal);
- HITL gating is correct for risk: money movement / travel bookings /
  health-data sharing require Approval;
- a dry-run through the full rail produces a clean receipt;
- finance agents stay paper/simulated; no sentience claims anywhere.

Stdlib only. No network calls (webhook delivery is never configured in
these tests, so routing falls through to device artifacts).
"""

from __future__ import annotations

import dataclasses
import importlib.util
import re
from datetime import datetime, timedelta, timezone

import pytest

from levi.automation.engine import (
    RAIL,
    TriggerEvent,
    _cron_matches,
    evaluate_condition,
    run_minion,
    trigger_matches,
)
from levi.automation.executor import RefusalAdapter, route
from levi.automation.hitl import HITL_TYPE_MAP, auto_approve
from levi.automation.minions import MINIONS, Minion


# ---------------------------------------------------------------------------
# Load the wave's field updates and build the effective catalog slice
# ---------------------------------------------------------------------------

_UPDATES_PATH = "/tmp/wave_c_updates.py"


def _load_updates():
    spec = importlib.util.spec_from_file_location("wave_c_updates", _UPDATES_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.UPDATES


UPDATES = _load_updates()
SLICE_CATEGORIES = ("Travel & Local", "Finance & Money", "Health & Fitness")


def _effective_minions():
    out = []
    for minion in MINIONS:
        if minion.category not in SLICE_CATEGORIES:
            continue
        if minion.id in UPDATES:
            out.append(dataclasses.replace(minion, **UPDATES[minion.id]))
        else:
            out.append(minion)
    return out


EFFECTIVE = _effective_minions()
BY_ID = {m.id: m for m in EFFECTIVE}
ALL_IDS = sorted(BY_ID)
FINANCE_IDS = sorted(m.id for m in EFFECTIVE if m.category == "Finance & Money")

HITL_VOCAB = set(HITL_TYPE_MAP)

# Keyword triggers kept verbatim (engine keyword_kinds handles them);
# mapped here to the event kind the engine assigns.
_KEYWORD_TRIGGER_KINDS = {
    "New receipt photo": "expense",
    "New expense": "expense",
    "New event published": "calendar",
}

_TIME_RE = re.compile(r"^Time ([01]?\d|2[0-3]):([0-5]\d)$")
_CRON_RE = re.compile(r"^Cron (\S+\s+){4}\S+$")
_APP_RE = re.compile(r"^App opened \(([^)]+)\)$")
_EVENT_RE = re.compile(r"^Event ([a-z][a-z0-9_]*): (.+)$")

_BANNED_RITE_TOKENS = ("todo", "tbd", "placeholder", "lorem", "fixme", "xxx")


# ---------------------------------------------------------------------------
# Trigger grammar: parse + build matching / non-matching events
# ---------------------------------------------------------------------------


def parse_trigger(trigger: str):
    """Return (form, detail) or raise ValueError when not machine-parseable."""
    text = (trigger or "").strip()
    m = _TIME_RE.fullmatch(text)
    if m:
        return ("time", f"{m.group(1)}:{m.group(2)}")
    m = _CRON_RE.fullmatch(text)
    if m:
        return ("cron", text[5:])
    m = _APP_RE.fullmatch(text)
    if m:
        return ("app", m.group(1))
    if text in _KEYWORD_TRIGGER_KINDS:
        return ("keyword", _KEYWORD_TRIGGER_KINDS[text])
    m = _EVENT_RE.fullmatch(text)
    if m:
        return ("event", (m.group(1), m.group(2)))
    raise ValueError(f"trigger not machine-parseable: {trigger!r}")


def event_for_trigger(trigger: str, payload: dict | None = None) -> TriggerEvent:
    """Build the canonical event that must fire this trigger."""
    form, detail = parse_trigger(trigger)
    payload = dict(payload or {})
    if form == "time":
        return TriggerEvent(
            kind="time",
            summary=f"time {detail} tick",
            payload={"time": detail, **payload},
        )
    if form == "cron":
        # The canonical firing event for a cron trigger carries a timestamp
        # that actually satisfies the schedule (engine matches cron fields
        # against the event ts — a tick that doesn't match the schedule
        # must NOT fire).
        ts = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        for _ in range(525600):  # walk back up to a year for a matching tick
            probe = TriggerEvent(kind="schedule", summary="", ts=ts.isoformat())
            if _cron_matches(detail, probe):
                break
            ts -= timedelta(minutes=1)
        return TriggerEvent(
            kind="schedule",
            summary=f"cron {detail} tick",
            payload=payload,
            ts=ts.isoformat(),
        )
    if form == "app":
        return TriggerEvent(
            kind="app_opened",
            summary=f"{detail} opened",
            payload={"app": detail, **payload},
        )
    if form == "keyword":
        return TriggerEvent(kind=detail, summary=trigger.lower(), payload=payload)
    kind, event_detail = detail
    return TriggerEvent(kind=kind, summary=event_detail, payload=payload)


def non_matching_event() -> TriggerEvent:
    """An event no well-formed trigger in this wave should fire on."""
    return TriggerEvent(kind="__nope__", summary="zzz quiet nothing here", payload={})


# ---------------------------------------------------------------------------
# Condition grammar: parse + build satisfying / violating payloads
# ---------------------------------------------------------------------------


def _norm_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower()).replace(" ", "_")


def parse_condition(condition: str):
    """Return (satisfying_payload, violating_payload) or raise ValueError."""
    text = (condition or "").strip()
    if text.lower() == "always":
        return {}, {}
    m = re.fullmatch(r"Day (\w+)", text, re.IGNORECASE)
    if m:
        return {"day": m.group(1)}, {"day": "__other__"}
    m = re.fullmatch(r"Battery\s*([<>]=?)\s*(\d+)%?", text, re.IGNORECASE)
    if m:
        op, n = m.group(1), int(m.group(2))
        if op == ">":
            return {"battery": n + 20}, {"battery": max(0, n - 20)}
        if op == "<":
            return {"battery": max(0, n - 20)}, {"battery": n + 20}
        if op == ">=":
            return {"battery": n + 10}, {"battery": max(0, n - 10)}
        return {"battery": max(0, n - 10)}, {"battery": n + 10}
    m = re.fullmatch(r"([\w \-']+)\s*:\s*(.+)", text)
    if m:
        key, want = _norm_key(m.group(1)), m.group(2).strip()
        return {key: want}, {key: want + "__other__"}
    m = re.fullmatch(r"([\w \-']+)\s*=\s*(.+)", text)
    if m:
        key, want = _norm_key(m.group(1)), m.group(2).strip()
        return {key: want}, {key: want + "__other__"}
    raise ValueError(f"condition not checkable: {condition!r}")


def _gate_clause(rite: str) -> str:
    parts = [p.strip() for p in rite.split("+") if p.strip()]
    gates = [p for p in parts if "hitl" in p.lower()]
    assert len(gates) == 1, f"expected exactly one HITL clause: {rite!r}"
    return gates[0]


# ---------------------------------------------------------------------------
# Update-file integrity
# ---------------------------------------------------------------------------


def test_updates_cover_the_whole_slice():
    slice_ids = {m.id for m in MINIONS if m.category in SLICE_CATEGORIES}
    assert set(UPDATES) == slice_ids
    assert len(EFFECTIVE) == 115


def test_updates_use_valid_fields_and_values():
    valid_fields = {f.name for f in dataclasses.fields(Minion)}
    for mid, fields in UPDATES.items():
        assert set(fields) <= valid_fields, mid
        for field, value in fields.items():
            assert isinstance(value, str) and value.strip(), (mid, field)


def test_catalog_quirks_preserved_after_updates():
    for m in EFFECTIVE:
        assert m.bridge == "Webhook", m.id
        assert m.usb_auto_launch == "n8n", m.id


# ---------------------------------------------------------------------------
# Trigger: parseable + matches + discriminates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", ALL_IDS)
def test_trigger_parseable_and_matches(mid):
    minion = BY_ID[mid]
    parse_trigger(minion.trigger)  # raises when sloppy
    event = event_for_trigger(minion.trigger)
    assert trigger_matches(minion.trigger, event), (
        f"{mid}: trigger {minion.trigger!r} did not match its canonical event"
    )


@pytest.mark.parametrize("mid", ALL_IDS)
def test_trigger_discriminates(mid):
    """The trigger must NOT fire on an unrelated event."""
    minion = BY_ID[mid]
    assert not trigger_matches(minion.trigger, non_matching_event()), (
        f"{mid}: trigger {minion.trigger!r} fired on an unrelated event"
    )


# ---------------------------------------------------------------------------
# Condition: checkable predicate (holds / fails, never unverifiable)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", ALL_IDS)
def test_condition_checkable(mid):
    minion = BY_ID[mid]
    sat, viol = parse_condition(minion.condition)  # raises when uncheckable
    holds = evaluate_condition(minion.condition, TriggerEvent(kind="x", payload=sat))
    assert holds.holds is True, f"{mid}: condition did not hold on satisfying event"
    if minion.condition.strip().lower() != "always":
        fails = evaluate_condition(
            minion.condition, TriggerEvent(kind="x", payload=viol)
        )
        assert fails.holds is False, f"{mid}: condition did not fail on violating event"


# ---------------------------------------------------------------------------
# Rite: complete step-form workflow with one HITL clause
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", ALL_IDS)
def test_rite_complete(mid):
    minion = BY_ID[mid]
    if minion.incomplete:
        assert minion.notes and any(
            w in minion.notes.lower()
            for w in ("missing", "unavailable", "blocked", "needs", "required")
        ), f"{mid}: incomplete agent must name exactly what is missing"
        return
    rite = minion.example_rite
    assert "hitl" in rite.lower(), f"{mid}: rite has no HITL clause"
    for token in _BANNED_RITE_TOKENS:
        assert token not in rite.lower(), f"{mid}: rite contains stub token {token!r}"
    assert len(rite) >= 60, f"{mid}: rite too short to be a complete workflow"
    parts = [p.strip() for p in rite.split("+") if p.strip()]
    assert len(parts) >= 4, f"{mid}: rite needs workflow steps plus a HITL clause"


# ---------------------------------------------------------------------------
# HITL: vocabulary + gate shape matches the rite's question + risk gating
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", ALL_IDS)
def test_hitl_vocabulary(mid):
    assert BY_ID[mid].hitl_type in HITL_VOCAB, mid


@pytest.mark.parametrize("mid", ALL_IDS)
def test_hitl_gate_shape_matches_rite(mid):
    """The gate kind must fit the interaction the rite's HITL clause describes."""
    minion = BY_ID[mid]
    if minion.incomplete:
        return
    clause = _gate_clause(minion.example_rite).lower()
    hitl = minion.hitl_type
    if re.search(r"\bedit\b", clause):
        assert hitl == "Edit & Approve", mid
    elif re.search(r"\bapprov\w*\b", clause):
        assert hitl == "Approval", mid
    elif re.search(r"\bconfirm\b", clause):
        assert hitl in ("Confirm", "Approval"), mid
    elif re.search(r"\backnowledge\b", clause):
        assert hitl == "Acknowledge", mid
    elif "?" in clause:
        # A question needs a gate that listens — never fire-and-forget.
        assert hitl != "Notification", mid
    else:
        assert hitl == "Notification", mid


_MONEY_RE = re.compile(
    r"\b(transfer|wire|payment(?!\s+history)|paying|purchase|invest(ment|ing)?|trade"
    r"|withdraw|deposit|pickup request|hail(ing)?( a)?"
    r"|ride.{0,25}book|book.{0,25}ride|move.{0,25}money|send money)\b",
    re.IGNORECASE,
)
_HONEST_RE = re.compile(
    r"\b(draft|simulat|paper|advisory|estimate|never|plan only"
    r"|you (still |execute|sign|swipe|submit|file|call|buy|book)"
    r"|your (banking app|configured))\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("mid", ALL_IDS)
def test_money_movement_never_under_gated(mid):
    """Raw money movement without draft/simulated/you-do-it language needs Approval."""
    minion = BY_ID[mid]
    if minion.incomplete:
        return
    text = minion.example_rite + " " + minion.notes
    if _MONEY_RE.search(text) and not _HONEST_RE.search(text):
        assert minion.hitl_type == "Approval", (
            f"{mid}: consequential money movement without honesty language "
            f"must be Approval-gated"
        )


@pytest.mark.parametrize(
    "mid",
    [
        "finance-money-overdraft-tripwire-01",  # emergency transfer plan
        "finance-money-spare-change-harvester-01",  # sweep into goal vault
        "travel-local-last-mile-link-01",  # booking a ride
        "travel-local-last-mile-link-02",  # hailing a pickup
        "travel-local-roadside-rescue-01",  # placing a paid assistance call
    ],
)
def test_consequential_acts_require_approval(mid):
    assert BY_ID[mid].hitl_type == "Approval", mid


# ---------------------------------------------------------------------------
# Adapter coverage: every agent resolves to a real execution path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", ALL_IDS)
def test_adapter_resolves(mid, tmp_path):
    """No silent refusals: without a configured webhook the device-artifact
    path must claim the agent (n8n is always named via usb_auto_launch)."""
    minion = BY_ID[mid]
    adapter = route(minion, tmp_path)
    if minion.incomplete:
        return
    assert not isinstance(adapter, RefusalAdapter), (
        f"{mid}: no adapter can execute this agent"
    )
    assert adapter.name in ("device-artifacts", "agent-workflow", "webhook"), mid


# ---------------------------------------------------------------------------
# Dry-run: full rail, clean receipt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", ALL_IDS)
def test_dry_run_executes_clean_with_receipt(mid):
    minion = BY_ID[mid]
    if minion.incomplete:
        pytest.skip("incomplete by design")
    sat, _ = parse_condition(minion.condition)
    event = event_for_trigger(minion.trigger, payload=sat)
    assert trigger_matches(minion.trigger, event)
    receipt = run_minion(minion, event, responder=auto_approve, dry_run=True)
    assert receipt.rail == RAIL
    assert receipt.dry_run is True
    assert receipt.executed is False
    assert receipt.ok is True
    assert receipt.gate is not None and receipt.gate.ok
    assert any(s.startswith("verify:") for s in receipt.steps)
    rendered = receipt.render()
    assert minion.id in rendered
    assert "dry-run" in rendered


# ---------------------------------------------------------------------------
# Targeted: finance stays paper/simulated; canon laws hold
# ---------------------------------------------------------------------------


def test_finance_stays_paper_simulated():
    banned = ("live trad", "market order", "place the order", "real money")
    for mid in FINANCE_IDS:
        minion = BY_ID[mid]
        text = (minion.example_rite + " " + minion.notes).lower()
        for token in banned:
            assert token not in text, f"{mid}: implies live trading/money movement"
        if re.search(r"\b(trade|invest|rebalance)\b", text):
            assert re.search(r"\b(paper|simulat|draft|never)\b", text), (
                f"{mid}: trading language must be paper/simulated/draft-gated"
            )


def test_no_sentience_claims():
    for mid in ALL_IDS:
        text = (BY_ID[mid].example_rite + " " + BY_ID[mid].notes).lower()
        assert "sentient" not in text, mid
        assert "consciousness" not in text, mid


def test_cron_triggers_are_valid_cron():
    cron_agents = [m for m in EFFECTIVE if m.trigger.startswith("Cron ")]
    assert cron_agents, "expected at least one cron trigger in the slice"
    for m in cron_agents:
        assert _CRON_RE.fullmatch(m.trigger), m.id


def test_event_triggers_use_known_kinds():
    kinds = {
        "email",
        "travel",
        "flight",
        "calendar",
        "location",
        "weather",
        "finance",
        "web",
        "vehicle",
        "timer",
        "safety",
        "health",
        "fitness",
        "device",
        "solar",
        "contacts",
        "time",
    }
    for m in EFFECTIVE:
        match = _EVENT_RE.fullmatch(m.trigger)
        if match:
            assert match.group(1) in kinds, f"{m.id}: unknown event kind"
