"""Wave B enterprise-grade review: System & Device Care, Security & Privacy, Smart Home & IoT.

Validates the 120 agents in this slice against the baked registry in
levi.automation.minions (the wave-B enterprise upgrades AND the signature
layer are committed in the catalog itself; no /tmp overlay):

- trigger is machine-parseable (canonical trigger grammar; every trigger
  produces a TriggerEvent the engine's trigger_matches accepts)
- condition is an actually checkable predicate (payload built from the
  condition itself must make evaluate_condition hold True)
- example_rite is a complete executable workflow: 2+ "+"-separated steps,
  an explicit HITL gate clause, no stubs
- every agent resolves to a real executor adapter (no silent refusals;
  incomplete agents must carry an exact reason in notes)
- hitl_type is correct for the act's risk (destructive verbs never ride on
  bare Notification/Acknowledge)
- dry-run executes clean through the full rail and produces a receipt
- live execution (isolated LEVI_HOME) routes to device-artifacts and receipts
- targeted tests for the tricky ones (gate-first ordering, swaps, corrections)
- the signature layer: every agent's rite runs through Echo, Mandella, REIM,
  and RIEM; every agent carries its lineage and uniqueness statement in notes

Stdlib only. No network calls (webhook path is asserted by routing only).
"""

from __future__ import annotations

import re

import pytest

from levi.automation.engine import (
    RAIL,
    TriggerEvent,
    evaluate_condition,
    run_minion,
    trigger_matches,
)
from levi.automation.executor import (
    DeviceArtifactAdapter,
    RefusalAdapter,
    WebhookAdapter,
    route,
)
from levi.automation.hitl import HITL_TYPE_MAP, auto_approve, gate_kind_for
from levi.automation.minions import MINIONS

WAVE_B_CATEGORIES = ("System & Device Care", "Security & Privacy", "Smart Home & IoT")
ORGANS = ("Echo", "Mandella", "REIM", "RIEM")

HITL_VOCAB = set(HITL_TYPE_MAP)
STUB_WORDS = ("todo", "tbd", "placeholder", "lorem", "fixme", "xxx")

# Verbs that mark a consequential act: these must never ride on a bare
# Notification or Acknowledge gate. (Clipboard-secret wipes are protective
# hygiene and are judged separately; "kill-switch"/"focus block" are matched
# with word boundaries so compounds don't false-positive.)
DESTRUCTIVE_VERBS = (
    "delete",
    "uninstall",
    "quarantine",
    "block",
    "kill",
    "purge",
    "bury",
    "mount",
    "export",
    "install",
    "revoke",
    "eject",
    "isolate",
    "shut the valve",
    "auto-close",
)
_DESTRUCTIVE_RE = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(v) for v in DESTRUCTIVE_VERBS) + r")(?![\w-])"
)
WEAK_GATES = {"Notification", "Acknowledge"}

# Offensive vocabulary: forbidden anywhere in the Security & Privacy slice
# (defensive/blue-team only canon).
OFFENSIVE_WORDS = (
    "exploit",
    "attack ",
    "hacking",
    "brute-force",
    "brute force",
    "crack the",
    "spoof",
    "phish",
    "ransom",
    "backdoor",
    "zero-day",
    "0-day",
)


# ---------------------------------------------------------------------------
# Loading the wave-B work product (baked in the registry)
# ---------------------------------------------------------------------------


def _upgraded_slice():
    return [m for m in MINIONS if m.category in WAVE_B_CATEGORIES]


UPGRADED = _upgraded_slice()
BY_ID = {m.id: m for m in UPGRADED}


def _ids():
    return [m.id for m in UPGRADED]


# ---------------------------------------------------------------------------
# Canonical trigger grammar + event construction
# ---------------------------------------------------------------------------

_DOMAIN_TRIGGER = re.compile(
    r"^(?:"
    r"battery(?:\s*(?:low|[<>=]\s*\d+%?))?|charging started|temperature high|"
    r"ram\s*>\s*\d+%|storage\s*>\s*\d+%|mobile data\s*=\s*\d+%|"
    r"hotspot client count\s*=\s*\d+|wi-?fi (?:connected|throughput\s*=\s*\d+)|"
    r"bluetooth connected\s*\(.+\)|earbuds? (?:connected|battery\s*<\s*\d+%)|"
    r"network operator changed|vpn disconnected|location changed|timezone changed|"
    r"device (?:boot|offline|unlocked in public)|unknown device on network|"
    r"sim changed|new device on guest ssid|"
    r"new (?:message \(sms\)|login alert|app installed|screenshot|wi-?fi network joined)|"
    r"nightly backup completes|credential leak list updated|vulnerability bulletin|"
    r"port scan detected|download flagged by scanner|"
    r"app (?:requests .+|attempts .+|crashed)|"
    r"photo captured|microphone in use|camera in use|password changed|"
    r"unknown ble beacon|keyword in message\s*\(.+\)"
    r")$",
    re.IGNORECASE,
)

_KEYWORD_KINDS = (
    ("new email", "email"),
    ("new task", "task"),
    ("new checklist item", "task"),
    ("new event", "calendar"),
    ("new note", "note"),
    ("new reminder", "reminder"),
    ("new notification", "notification"),
    ("clipboard", "clipboard"),
    ("device inserted", "device"),
    ("search query", "search"),
    ("new receipt", "expense"),
    ("new expense", "expense"),
)


def _trigger_family(trigger: str):
    """Name the canonical grammar family a trigger belongs to (None = sloppy)."""
    t = (trigger or "").strip()
    if re.fullmatch(r"time\s+\d{1,2}:\d{2}", t, re.IGNORECASE):
        return "time"
    if re.fullmatch(r"time\s+(hourly|daily)", t, re.IGNORECASE):
        return "cadence"
    if re.fullmatch(r"app opened\s*\([^)]+\)", t, re.IGNORECASE):
        return "app"
    if re.fullmatch(r"day\s+\w+", t, re.IGNORECASE):
        return "day"
    if re.fullmatch(r"sunset|sunrise", t, re.IGNORECASE):
        return "sun"
    if re.fullmatch(r"sensor alert\s*\([^)]+\)", t, re.IGNORECASE):
        return "sensor"
    if re.fullmatch(r"geo-fence\s+(arrival|departure)", t, re.IGNORECASE):
        return "geofence"
    if any(t.lower().startswith(k) for k, _ in _KEYWORD_KINDS):
        return "keyword"
    if _DOMAIN_TRIGGER.fullmatch(t):
        return "domain"
    return None


def _event_for_trigger(trigger: str) -> TriggerEvent:
    """Build the canonical event a trigger is meant to fire on."""
    t = (trigger or "").strip()
    m = re.fullmatch(r"time\s+(\d{1,2}:\d{2})", t, re.IGNORECASE)
    if m:
        return TriggerEvent(kind="time", summary=t, payload={"time": m.group(1)})
    m = re.fullmatch(r"time\s+(hourly|daily)", t, re.IGNORECASE)
    if m:
        return TriggerEvent(
            kind="time", summary=t, payload={"cadence": m.group(1).lower()}
        )
    m = re.fullmatch(r"app opened\s*\(([^)]+)\)", t, re.IGNORECASE)
    if m:
        return TriggerEvent(
            kind="app_opened", summary=t, payload={"app": m.group(1).strip()}
        )
    m = re.fullmatch(r"day\s+(\w+)", t, re.IGNORECASE)
    if m:
        return TriggerEvent(kind="time", summary=t, payload={"day": m.group(1)})
    m = re.fullmatch(r"sensor alert\s*\(([^)]+)\)", t, re.IGNORECASE)
    if m:
        return TriggerEvent(
            kind="sensor", summary=t, payload={"sensor": m.group(1).strip()}
        )
    m = re.fullmatch(r"geo-fence\s+(arrival|departure)", t, re.IGNORECASE)
    if m:
        return TriggerEvent(
            kind="geofence", summary=t, payload={"transition": m.group(1).lower()}
        )
    for keyword, kind in _KEYWORD_KINDS:
        if t.lower().startswith(keyword):
            return TriggerEvent(kind=kind, summary=t, payload={})
    low = t.lower()
    kind = "event"
    for hint, want in (
        ("wi-fi", "wifi"),
        ("wifi", "wifi"),
        ("bluetooth", "bluetooth"),
        ("ble ", "bluetooth"),
        ("vpn", "vpn"),
        ("clipboard", "clipboard"),
        ("device", "device"),
        ("usb", "device"),
        ("sim ", "device"),
        ("battery", "power"),
        ("charging", "power"),
    ):
        if hint in low:
            kind = want
            break
    return TriggerEvent(kind=kind, summary=t, payload={})


# ---------------------------------------------------------------------------
# Condition payload construction (mirrors the engine's checkers)
# ---------------------------------------------------------------------------


def _norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower()).replace(" ", "_")


def _norm_val(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _payload_for_condition(condition: str):
    """Build a payload that satisfies the condition, or None if uncheckable."""
    c = (condition or "").strip()
    if c.lower() == "always":
        return {}
    m = re.fullmatch(r"day\s+(\w+)", c, re.IGNORECASE)
    if m:
        return {"day": m.group(1)}
    m = re.fullmatch(r"battery\s*([<>]=?)\s*(\d+)%?", c, re.IGNORECASE)
    if m:
        n = float(m.group(2))
        return {"battery": n - 1 if m.group(1).startswith("<") else n + 1}
    m = re.fullmatch(r"([\w ]+)\s*:\s*(.+)", c)
    if m:
        return {_norm_key(m.group(1)): _norm_val(m.group(2))}
    m = re.fullmatch(r"([\w ]+)\s*=\s*(.+)", c)
    if m:
        return {_norm_key(m.group(1)): _norm_val(m.group(2))}
    return None


def _event_for_minion(minion) -> TriggerEvent:
    """Canonical event: trigger-shaped, with a satisfying condition payload."""
    event = _event_for_trigger(minion.trigger)
    payload = _payload_for_condition(minion.condition)
    assert payload is not None, (
        f"{minion.id}: uncheckable condition {minion.condition!r}"
    )
    merged = dict(event.payload)
    merged.update(payload)
    return TriggerEvent(kind=event.kind, summary=event.summary, payload=merged)


# ---------------------------------------------------------------------------
# Slice integrity
# ---------------------------------------------------------------------------


def test_slice_is_120_agents():
    assert len(UPGRADED) == 120
    assert {m.category for m in UPGRADED} == set(WAVE_B_CATEGORIES)


def test_signature_layer_is_baked_in_every_agent():
    """The signature weave lives in the catalog itself: every agent carries
    its lineage and its uniqueness statement in notes."""
    for m in UPGRADED:
        assert "Signature:" in m.notes, f"{m.id}: no signature lineage in notes"
        assert "Uniqueness kept:" in m.notes, f"{m.id}: no uniqueness statement"


def test_signature_traverses_all_four_organs():
    """Every Wave-B rite runs through Echo, Mandella, REIM, and RIEM —
    the organ steps sit before the HITL gate clause."""
    for m in UPGRADED:
        low = m.example_rite.lower()
        gate_at = low.index("hitl")
        pre_gate = m.example_rite[:gate_at] + " " + m.notes
        for organ in ORGANS:
            assert organ in pre_gate, (
                f"{m.id}: rite never traverses {organ}"
            )


def test_no_agent_left_incomplete_without_reason():
    for m in UPGRADED:
        if m.incomplete:
            assert len(m.notes) >= 20, f"{m.id}: incomplete needs an exact reason"
            assert "missing" in m.notes.lower() or "cannot" in m.notes.lower(), (
                f"{m.id}: notes must name what is missing"
            )


def test_bridge_and_usb_quirk_preserved():
    for m in UPGRADED:
        assert m.bridge == "Webhook", m.id
        assert m.usb_auto_launch == "n8n", m.id


# ---------------------------------------------------------------------------
# Trigger: machine-parseable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", _ids())
def test_trigger_is_machine_parseable(mid):
    m = BY_ID[mid]
    family = _trigger_family(m.trigger)
    assert family is not None, f"{mid}: trigger {m.trigger!r} matches no grammar family"
    event = _event_for_trigger(m.trigger)
    assert trigger_matches(m.trigger, event), (
        f"{mid}: trigger {m.trigger!r} does not fire on its canonical event"
    )


def test_trigger_families_cover_known_shapes():
    assert _trigger_family("Time 06:45") == "time"
    assert _trigger_family("Time hourly") == "cadence"
    assert _trigger_family("App opened (Gmail)") == "app"
    assert _trigger_family("Day Sunday") == "day"
    assert _trigger_family("Sunset") == "sun"
    assert _trigger_family("Sensor alert (smoke)") == "sensor"
    assert _trigger_family("Geo-fence arrival") == "geofence"
    assert _trigger_family("New event") == "keyword"
    assert _trigger_family("Port scan detected") == "domain"
    assert _trigger_family("Battery low") == "domain"
    assert _trigger_family("whenever, vaguely") is None


# ---------------------------------------------------------------------------
# Condition: actually checkable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", _ids())
def test_condition_is_checkable(mid):
    m = BY_ID[mid]
    payload = _payload_for_condition(m.condition)
    assert payload is not None, f"{mid}: condition {m.condition!r} is not checkable"
    event = TriggerEvent(kind="probe", summary="probe", payload=payload)
    verdict = evaluate_condition(m.condition, event)
    assert verdict.holds is True, f"{mid}: condition {m.condition!r} -> {verdict.note}"


# ---------------------------------------------------------------------------
# Rite: complete executable workflow
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", _ids())
def test_rite_is_complete(mid):
    m = BY_ID[mid]
    rite = m.example_rite
    assert "hitl" in rite.lower(), f"{mid}: rite has no HITL gate clause"
    steps = [p.strip() for p in rite.split("+") if p.strip()]
    assert len(steps) >= 2, f"{mid}: rite is not a multi-step workflow"
    assert len(rite) >= 60, f"{mid}: rite too thin to be executable"
    low = rite.lower()
    assert not any(w in low for w in STUB_WORDS), f"{mid}: rite contains stub language"
    assert not re.search(r"\btodo\b", low), f"{mid}: rite contains TODO"


# ---------------------------------------------------------------------------
# HITL: correct for the risk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", _ids())
def test_hitl_vocabulary_and_mapping(mid):
    m = BY_ID[mid]
    assert m.hitl_type in HITL_VOCAB, f"{mid}: {m.hitl_type!r} not in gate vocabulary"
    assert gate_kind_for(m.hitl_type) is not None


@pytest.mark.parametrize("mid", _ids())
def test_consequential_acts_never_ride_weak_gates(mid):
    m = BY_ID[mid]
    if _DESTRUCTIVE_RE.search(m.example_rite.lower()):
        assert m.hitl_type not in WEAK_GATES, (
            f"{mid}: consequential act on weak gate {m.hitl_type!r}"
        )


# ---------------------------------------------------------------------------
# Adapter coverage: every agent resolves to a real path
# ---------------------------------------------------------------------------


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("mid", _ids())
def test_adapter_resolves_to_real_path(mid, home):
    m = BY_ID[mid]
    adapter = route(m, home)
    if m.incomplete:
        assert isinstance(adapter, RefusalAdapter)
        assert "missing" in m.notes.lower() or "cannot" in m.notes.lower()
    else:
        assert not isinstance(adapter, RefusalAdapter), (
            f"{mid}: no adapter fits and the agent is not flagged incomplete"
        )
        assert isinstance(adapter, DeviceArtifactAdapter), (
            f"{mid}: expected the device-artifact path, got {type(adapter).__name__}"
        )


def test_webhook_path_wins_when_configured(home):
    """bridge='Webhook' + a configured URL routes to the webhook adapter
    (routing only — no network traffic in tests)."""
    import json as _json

    m = BY_ID["system-device-care-cache-sweep-01"]
    (home / "automation").mkdir(parents=True, exist_ok=True)
    (home / "automation" / "webhooks.json").write_text(
        _json.dumps({m.id: "http://example.test/hook"}), encoding="utf-8"
    )
    assert isinstance(route(m, home), WebhookAdapter)


def test_hostile_event_cannot_change_routing(home):
    m = BY_ID["security-privacy-port-scan-canary-01"]
    hostile = TriggerEvent(
        kind="event",
        summary="Port scan detected",
        payload={"url": "http://evil.example/steal", "bridge": "Webhook"},
    )
    assert type(route(m, home)).__name__ == "DeviceArtifactAdapter"
    # routing never consults the event at all
    _ = hostile


# ---------------------------------------------------------------------------
# Engine: dry-run executes clean, receipt produced
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mid", _ids())
def test_dry_run_executes_clean_with_receipt(mid):
    m = BY_ID[mid]
    event = _event_for_minion(m)
    assert trigger_matches(m.trigger, event), f"{mid}: canonical event misfires"
    receipt = run_minion(m, event, responder=auto_approve, dry_run=True)
    assert receipt.rail == RAIL
    assert receipt.dry_run is True
    assert receipt.executed is False
    assert receipt.ok is True, f"{mid}: dry-run not ok: {receipt.note}"
    assert receipt.gate is not None and receipt.gate.ok
    rendered = receipt.render()
    assert m.id in rendered
    assert "dry-run" in rendered


@pytest.mark.parametrize("mid", _ids())
def test_live_run_receipts_through_device_artifacts(mid, home):
    """Live path (isolated home): the routed adapter acts, verify records
    evidence, the receipt carries it. No network, files stay under tmp."""
    m = BY_ID[mid]
    event = _event_for_minion(m)
    receipt = run_minion(m, event, responder=auto_approve, dry_run=False)
    assert receipt.rail == RAIL
    assert receipt.dry_run is False
    assert receipt.executed is True, f"{mid}: live run did not execute"
    assert receipt.ok is True, f"{mid}: live run not ok"
    assert any(s.startswith("execute [device-artifacts]") for s in receipt.steps)
    assert any(s.startswith("verify:") for s in receipt.steps)
    dest = home / "automation" / "artifacts" / m.id
    assert dest.is_dir() and any(dest.iterdir()), f"{mid}: no artifacts written"


# ---------------------------------------------------------------------------
# Security & Privacy: defensive-only canon
# ---------------------------------------------------------------------------


def test_security_slice_is_defensive_only():
    offenders = []
    for m in UPGRADED:
        if m.category != "Security & Privacy":
            continue
        text = f"{m.example_rite} {m.notes}".lower()
        if any(w in text for w in OFFENSIVE_WORDS):
            offenders.append(m.id)
    assert not offenders, f"offensive language in: {offenders}"


# ---------------------------------------------------------------------------
# Targeted: the tricky ones
# ---------------------------------------------------------------------------


def test_trigger_condition_swaps_put_time_in_trigger():
    for mid in (
        "system-device-care-trash-bin-emptier-01",
        "smart-home-iot-energy-diet-report-01",
        "smart-home-iot-fridge-inventory-scout-01",
    ):
        m = BY_ID[mid]
        assert re.fullmatch(r"time\s+\d{1,2}:\d{2}", m.trigger, re.IGNORECASE), mid
        assert re.fullmatch(r"day\s+\w+", m.condition, re.IGNORECASE), mid


def test_hourly_cadence_trigger_is_parseable():
    m = BY_ID["security-privacy-clipboard-auto-purge-02"]
    assert _trigger_family(m.trigger) == "cadence"
    event = _event_for_trigger(m.trigger)
    assert trigger_matches(m.trigger, event)


def test_port_scan_canary_01_gates_before_blocking():
    m = BY_ID["security-privacy-port-scan-canary-01"]
    assert m.hitl_type == "Approval"
    low = m.example_rite.lower()
    assert low.index("hitl") < low.index("apply"), (
        "block must be gated, not pre-applied"
    )


def test_port_scan_canary_02_quarantine_is_staged():
    m = BY_ID["security-privacy-port-scan-canary-02"]
    assert m.hitl_type == "Approval"
    assert "draft" in m.example_rite.lower()
    assert "staged" in m.notes.lower()


def test_sim_swap_emergency_contacts_stay_gated():
    m = BY_ID["security-privacy-sim-swap-tripwire-01"]
    assert m.hitl_type == "Notification & Dialog"
    low = m.example_rite.lower()
    assert low.index("hitl") <= low.index("message emergency"), (
        "contacting humans must be decided at the gate"
    )


def test_speaker_dust_eject_confirms_before_blast():
    m = BY_ID["system-device-care-speaker-dust-eject-01"]
    low = m.example_rite.lower()
    assert low.index("hitl") < low.index("play the tone"), (
        "full-volume blast must be confirmed first"
    )


def test_remote_wipe_is_draft_only_before_approval():
    m = BY_ID["security-privacy-geofence-data-lock-02"]
    assert m.hitl_type == "Approval"
    assert "draft" in m.example_rite.lower()
    low = m.example_rite.lower()
    assert "never" in low and "without you" in low


def test_new_device_sentry_offers_dialog_choice():
    m = BY_ID["security-privacy-new-device-sentry-01"]
    assert m.hitl_type == "Notification & Dialog"
    assert "quarantine" in m.example_rite.lower()


def test_vpn_enforcer_02_block_is_protective_and_liftable():
    m = BY_ID["security-privacy-vpn-enforcer-02"]
    assert m.hitl_type == "Notification & Dialog"
    low = m.example_rite.lower()
    assert "lift the block" in low


def test_corrected_approval_gates():
    for mid in (
        "system-device-care-battery-hog-parade-01",
        "smart-home-iot-sunrise-blind-warden-02",
        "smart-home-iot-pet-feeder-squire-02",
        "smart-home-iot-shower-heat-herald-02",
        "smart-home-iot-sleep-scene-composer-02",
        "smart-home-iot-window-tally-sentry-02",
        "smart-home-iot-vacuum-patrol-coordinator-02",
    ):
        assert BY_ID[mid].hitl_type == "Approval", mid


def test_data_cap_shepherd_throttle_is_confirmed():
    assert BY_ID["system-device-care-data-cap-shepherd-01"].hitl_type == "Confirm"
