"""Tests for the LEVI-native automation minions upgrade.

Covers the 471-minion catalog integrity, trigger/condition matching, the
HITL gate framework, dry-run receipts (no side effects), and the
additive minion chat wiring.
"""

import pytest

from levi.automation import minions as catalog
from levi.automation.minions import (
    MINIONS,
    Minion,
    by_category,
    by_hitl,
    find_minion,
    search,
)
from levi.automation.engine import (
    RAIL,
    TriggerEvent,
    dry_run,
    evaluate_condition,
    match_event,
    run_minion,
    trigger_matches,
)
from levi.automation.hitl import (
    Gate,
    GateDenied,
    GateKind,
    GateRequest,
    auto_approve,
    auto_deny,
    describe_gate,
    gate_kind_for,
)
from levi.bot import hitl as bot_hitl

HITL_VOCAB = {
    "Notification",
    "Notification & Dialog",
    "Approval",
    "Edit & Approve",
    "Acknowledge",
    "Confirm",
}

EXPECTED_CATEGORY_COUNTS = {
    "Productivity": 83,  # 51 complete + 1 incomplete intake + 28 triple + 3 replacements
    "Communication": 39,  # 11 double + 28 triple
    "Finance & Money": 38,  # 10 double + 28 triple
    "Health & Fitness": 38,  # 10 double + 28 triple
    "Smart Home & IoT": 39,  # 11 double + 28 triple
    "Security & Privacy": 39,  # 11 double + 28 triple
    "Social & Content": 38,  # 10 double + 28 triple
    "Shopping & Deals": 38,  # 10 double + 28 triple
    "Travel & Local": 39,  # 11 double + 28 triple
    "Learning & Notes": 38,  # 10 double + 28 triple
    "System & Device Care": 42,  # 10 double + 32 triple
}


# ---------------------------------------------------------------------------
# Catalog integrity
# ---------------------------------------------------------------------------


def test_catalog_total_is_471():
    assert len(MINIONS) == 471


def test_catalog_bloodlines():
    origins = [b.origin for b in MINIONS]
    assert origins.count("chauncey-intake") == 52
    assert origins.count("levi-original") == 419


def test_incomplete_intake_row_flagged():
    incomplete = [b for b in MINIONS if b.incomplete]
    assert len(incomplete) == 1
    row = incomplete[0]
    assert row.origin == "chauncey-intake"
    assert row.category == "Productivity"
    assert row.subcategory == "Calendar Conflict"


def test_category_counts():
    for category, expected in EXPECTED_CATEGORY_COUNTS.items():
        assert len(by_category(category)) == expected, category
    assert sum(EXPECTED_CATEGORY_COUNTS.values()) == 471


def test_bot_ids_unique():
    ids = [b.id for b in MINIONS]
    assert len(ids) == len(set(ids))


def test_schema_fields_present():
    fields = (
        "category",
        "subcategory",
        "trigger",
        "condition",
        "android_tool",
        "windows_tool",
        "mac_tool",
        "chrome_extension",
        "bridge",
        "usb_auto_launch",
        "hitl_type",
        "example_rite",
        "notes",
    )
    for b in MINIONS:
        if b.incomplete:
            continue
        for f in fields:
            assert getattr(b, f), f"{b.id} missing {f}"


def test_schema_quirk_preserved():
    # His authored quirk: bridge is always "Webhook", usb_auto_launch "n8n".
    for b in MINIONS:
        if b.incomplete:
            continue
        assert b.bridge == "Webhook", b.id
        assert b.usb_auto_launch == "n8n", b.id


def test_hitl_vocabulary():
    for b in MINIONS:
        if b.incomplete:
            continue
        assert b.hitl_type in HITL_VOCAB, f"{b.id}: {b.hitl_type}"


def test_every_workflow_has_hitl_gate():
    for b in MINIONS:
        if b.incomplete:
            continue
        assert "hitl" in b.example_rite.lower(), b.id


def test_new_bots_are_original_categories():
    new_cats = {b.category for b in MINIONS if b.origin == "levi-original"}
    # The double opened 10 new categories; the triple extended into
    # Productivity as well — LEVI-originals now span all 11.
    assert len(new_cats) == 11
    assert set(EXPECTED_CATEGORY_COUNTS) == new_cats


def test_his_rows_verbatim_duplicates_preserved():
    # His intake repeats some rows verbatim; nothing is deleted.
    note_search = [
        b
        for b in MINIONS
        if b.origin == "chauncey-intake"
        and b.subcategory == "Note Search"
        and b.trigger == "Search query"
    ]
    assert len(note_search) == 3


def test_query_helpers():
    assert find_minion(MINIONS, MINIONS[0].id) is MINIONS[0]
    assert find_minion(MINIONS, "no-such-minion") is None
    assert by_hitl("Approval")
    assert search("clipboard")
    assert catalog.categories()[0] == "Productivity"


# ---------------------------------------------------------------------------
# Trigger matching
# ---------------------------------------------------------------------------


def _bot_with(trigger: str, condition: str = "Always") -> Minion:
    return Minion(
        id="test-minion-01",
        category="Test",
        subcategory="Trigger Lab",
        trigger=trigger,
        condition=condition,
        android_tool="MacroDroid",
        windows_tool="AutoHotkey",
        mac_tool="AppleScript",
        chrome_extension="Bardeen",
        bridge="Webhook",
        usb_auto_launch="n8n",
        hitl_type="Notification",
        example_rite="Do the thing + HITL: Approve?",
        notes="test",
        origin="levi-original",
    )


def test_time_trigger_matches():
    minion = _bot_with("Time 06:45")
    event = TriggerEvent(kind="time", summary="morning", payload={"time": "06:45"})
    assert trigger_matches(minion.trigger, event)
    off = TriggerEvent(kind="time", summary="morning", payload={"time": "07:00"})
    assert not trigger_matches(minion.trigger, off)


def test_app_opened_trigger_matches():
    minion = _bot_with("App opened (Gmail)")
    event = TriggerEvent(
        kind="app_opened", summary="gmail opened", payload={"app": "Gmail"}
    )
    assert trigger_matches(minion.trigger, event)
    other = TriggerEvent(
        kind="app_opened", summary="maps opened", payload={"app": "Maps"}
    )
    assert not trigger_matches(minion.trigger, other)


def test_keyword_trigger_matches_kind():
    minion = _bot_with("New Email")
    assert trigger_matches(
        minion.trigger, TriggerEvent(kind="email", summary="mail arrived")
    )
    assert not trigger_matches(
        minion.trigger, TriggerEvent(kind="calendar", summary="mail arrived")
    )


def test_match_event_returns_condition_verdicts():
    minions = [_bot_with("Time 18:00", "Day Monday")]
    monday = TriggerEvent(
        kind="time", summary="evening", payload={"time": "18:00", "day": "Monday"}
    )
    matches = match_event(monday, minions)
    assert len(matches) == 1
    assert matches[0].condition.holds is True


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------


def test_condition_always():
    v = evaluate_condition("Always", TriggerEvent(kind="x"))
    assert v.holds is True


def test_condition_day():
    event = TriggerEvent(kind="time", payload={"day": "Monday"})
    assert evaluate_condition("Day Monday", event).holds is True
    assert evaluate_condition("Day Tuesday", event).holds is False


def test_condition_battery():
    event = TriggerEvent(kind="device", payload={"battery": 25})
    assert evaluate_condition("Battery >30%", event).holds is False
    assert evaluate_condition("Battery <30%", event).holds is True


def test_condition_kv_colon():
    event = TriggerEvent(kind="email", payload={"to": "me@work.com"})
    assert evaluate_condition("To: me@work.com", event).holds is True
    assert evaluate_condition("To: other@work.com", event).holds is False


def test_condition_unknown_escalates():
    v = evaluate_condition("Moon phase: waxing", TriggerEvent(kind="x"))
    assert v.holds is None
    assert "escalate" in v.note


# ---------------------------------------------------------------------------
# HITL gates
# ---------------------------------------------------------------------------


def _request(kind: GateKind) -> GateRequest:
    return GateRequest(minion_id="test-minion-01", kind=kind, prompt="do the thing?")


def test_gate_kind_mapping_fail_closed():
    assert gate_kind_for("Notification") is GateKind.NOTIFICATION
    assert gate_kind_for("Notification & Dialog") is GateKind.DIALOG
    assert gate_kind_for("Approval") is GateKind.APPROVAL
    assert gate_kind_for("Edit & Approve") is GateKind.EDIT_APPROVE
    assert gate_kind_for("Acknowledge") is GateKind.ACKNOWLEDGE
    assert gate_kind_for("Confirm") is GateKind.CONFIRM
    assert gate_kind_for("Something Weird") is GateKind.APPROVAL


def test_notification_gate_never_blocks():
    result = Gate(_request(GateKind.NOTIFICATION)).resolve(auto_deny)
    assert result.decision == "noted"
    assert result.ok


@pytest.mark.parametrize(
    "kind", [GateKind.DIALOG, GateKind.APPROVAL, GateKind.CONFIRM, GateKind.ACKNOWLEDGE]
)
def test_gates_resolve_via_responder(kind):
    result = Gate(_request(kind)).resolve(auto_approve)
    assert result.ok
    assert result.decision == "approved"


def test_denied_gate_raises_on_require():
    with pytest.raises(GateDenied):
        Gate(_request(GateKind.APPROVAL)).require(auto_deny)


def test_describe_gate_covers_all_kinds():
    for kind in GateKind:
        assert describe_gate(kind)


# ---------------------------------------------------------------------------
# Dry-run receipts: full rail, no side effects
# ---------------------------------------------------------------------------


def test_dry_run_receipt_full_rail():
    minion = _bot_with("Time 06:45", "Always")
    event = TriggerEvent(kind="time", summary="morning", payload={"time": "06:45"})
    receipt = dry_run(minion.id, event, [minion])
    assert receipt.rail == RAIL
    assert list(RAIL) == [
        "plan",
        "preview",
        "permission",
        "execute",
        "verify",
        "receipt",
    ]
    assert receipt.dry_run is True
    assert receipt.executed is False
    assert receipt.ok is True
    assert receipt.gate is not None and receipt.gate.ok
    rendered = receipt.render()
    assert minion.id in rendered
    assert "dry-run" in rendered


def test_dry_run_failing_condition_stops_before_gate():
    minion = _bot_with("Time 06:45", "Day Monday")
    event = TriggerEvent(
        kind="time", summary="morning", payload={"time": "06:45", "day": "Tuesday"}
    )
    receipt = run_minion(minion, event, responder=auto_approve, dry_run=True)
    assert receipt.ok is False
    assert receipt.gate is None
    assert receipt.executed is False


def test_dry_run_denied_gate_stops():
    minion = _bot_with("Time 06:45", "Always")
    object.__setattr__(minion, "hitl_type", "Approval")  # frozen dataclass
    event = TriggerEvent(kind="time", summary="morning", payload={"time": "06:45"})
    receipt = run_minion(minion, event, responder=auto_deny, dry_run=True)
    assert receipt.ok is False
    assert receipt.executed is False
    assert receipt.gate.decision == "denied"


def test_dry_run_unknown_bot():
    with pytest.raises(KeyError):
        dry_run("no-such-minion", TriggerEvent(kind="x"), [])


# ---------------------------------------------------------------------------
# Additive minion chat wiring
# ---------------------------------------------------------------------------


def test_present_gate_mentions_bot_and_gate():
    text = bot_hitl.present_gate(_request(GateKind.APPROVAL))
    assert "test-minion-01" in text
    assert "yes" in text.lower()


def test_parse_reply_yes_no():
    req = _request(GateKind.APPROVAL)
    assert bot_hitl.parse_reply("yes, do it", req)["decision"] == "approved"
    assert bot_hitl.parse_reply("no way", req)["decision"] == "denied"
    assert bot_hitl.parse_reply("hmm maybe later?", req) is None


def test_chat_responder_fail_closed():
    req = _request(GateKind.CONFIRM)
    assert bot_hitl.chat_responder(req, "yes")["decision"] == "approved"
    denied = bot_hitl.chat_responder(req, "tell me more first")
    assert denied["decision"] == "denied"
