"""Hermetic tests for Legion service operations over Cybrus.

Law -> guard -> prove for the O-laws in
``core/levi/legion/operators/cybrus_ops.py``: every operation crosses
the choke point authenticated (O1); inputs/results travel sealed over
Veil with metadata-only audit (O2); twin verification runs over the
wire and only VERIFIED ships (O3); money-intent jobs fail closed (O4);
no Veil degrades honestly, a locked Veil refuses (O5); nothing is
invented (O6); the personas' public surface is untouched (O7).

Hermetic: LEVI_HOME is monkeypatched to a tmp dir — no real HOME
writes, no network. Veil gets a test passphrase.
"""

import base64
import json
import sys
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from levi.cybrus.enforce import CallDenied, NotAuthenticated  # noqa: E402
from levi.cybrus.money import MoneyRefused  # noqa: E402
from levi.cybrus.policy import PolicyEngine  # noqa: E402
from levi.cybrus.router import RouteRegistry  # noqa: E402
from levi.cybrus.veil import Veil, VeilError  # noqa: E402
from levi.legion.operators import build_system_prompt  # noqa: E402
from levi.legion.operators import SERVICE_CARDS  # noqa: E402
from levi.legion.operators import register_service_personas  # noqa: E402
from levi.legion.operators.cybrus_ops import (  # noqa: E402
    TRANSPORT_LOCAL,
    TRANSPORT_SEALED,
    CybrusServiceBus,
    JobNotShipped,
    ServiceBusError,
    new_job,
)
from levi.operator.contract import (  # noqa: E402
    NATIVE,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
)
from levi.operator.registry import OperatorRegistry  # noqa: E402


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def veil(home, tmp_path):
    return Veil(passphrase="test-passphrase", home=tmp_path / "veil")


@pytest.fixture()
def bus(veil):
    return CybrusServiceBus(veil=veil)


@pytest.fixture()
def registry():
    reg = OperatorRegistry()
    reg.register("test-brain", FakeBrain(), replace=True)
    return register_service_personas(reg, base_name="test-brain")


class FakeBrain(Operator):
    """Minimal backing brain for persona-through-bus tests."""

    name = "test-brain"
    kind = NATIVE

    def __init__(self) -> None:
        self.seen: List[OperatorMessage] = []

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(tools=(), context_window=1024)

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="test brain")

    def step(self, messages, tools, context):
        self.seen = list(messages)
        return OperatorResult(
            text="fake brain reply",
            operator=self.name,
            kind=self.kind,
            note="from the fake brain",
        )


def _job(seat="service.dev-lift", **kw):
    kw.setdefault("action", "lift")
    kw.setdefault("input", {"url": "https://example.com"})
    return new_job(seat, **kw)


# -- provisioning: registered originals, idempotent ---------------------------

def test_provision_registers_routes_and_rules_idempotent(bus):
    first = bus.provisioned
    assert set(first["routes"]) == {"levi.service.dev-lift", "levi.service.goal-line"}
    # 2 own-seat rules + 2 twin-verifier rules (job.verify on the twin's seat)
    assert len(first["rules"]) == 4
    again = bus.provision()
    assert again["rules"] == []  # nothing added twice
    assert again["devices"] == []
    assert RouteRegistry().resolve("levi.service.dev-lift")["kind"] == "internal"


def test_unknown_seat_refused_at_construction():
    with pytest.raises(ServiceBusError):
        new_job("service.nope", "x", {})


def test_locked_veil_refuses_bus_construction(veil):
    veil.lock()
    with pytest.raises(ServiceBusError):
        CybrusServiceBus(veil=veil)


# -- O1: the choke point guards every operation -------------------------------

def test_unauthenticated_submit_refused(bus, veil):
    job = _job()
    with pytest.raises(NotAuthenticated):
        bus.submit(job, credential="bogus-token")
    assert job.job_id not in bus._jobs  # refused work never records
    assert veil.fetch_envelopes(f"svc-{job.job_id}") == []  # nothing sealed


def test_policy_deny_wins(bus):
    PolicyEngine().add_rule(
        "sidewinder", "service.levi.service.goal-line", "*", "deny", "high"
    )
    job = _job(seat="service.goal-line", action="obtain")
    with pytest.raises(CallDenied):
        bus.submit(job)


# -- O2: sealed transport, metadata-only audit --------------------------------

def test_submit_seals_input_round_trip(bus, veil):
    job = _job()
    out = bus.submit(job)
    assert out["transport"] == TRANSPORT_SEALED
    envelopes = veil.fetch_envelopes(f"svc-{job.job_id}")
    assert len(envelopes) == 1
    opened = veil.open_message(envelopes[0])
    body = json.loads(opened["plaintext"].decode())
    assert body["kind"] == "job.input"
    assert body["input"] == {"url": "https://example.com"}
    # attested sender is the primary's service device, recipient the verifier's
    assert opened["sender"] == bus._device_id("wren")
    assert opened["recipient"] == bus._device_id("sidewinder")


def test_tampered_envelope_fails_closed(bus, veil):
    job = _job()
    bus.submit(job)
    envelope = veil.fetch_envelopes(f"svc-{job.job_id}")[0]
    raw = bytearray(base64.b64decode(envelope["blob"]))
    raw[20] ^= 0xFF
    envelope["blob"] = base64.b64encode(bytes(raw)).decode()
    with pytest.raises(VeilError):
        veil.open_message(envelope)


def test_replayed_envelope_rejected(bus, veil):
    job = _job()
    bus.submit(job)
    envelope = veil.fetch_envelopes(f"svc-{job.job_id}")[0]
    veil.open_message(envelope)  # first open ok
    with pytest.raises(VeilError):
        veil.open_message(envelope)  # replay refused


# -- O3: twin verification over the wire --------------------------------------

def _full_run(bus, job, verdict="VERIFIED"):
    bus.submit(job)
    bus.run_primary(job.job_id, lambda inp: {"done": True, "echo": inp})
    return bus.verify(
        job.job_id, lambda out: {"verdict": verdict, "reason": "looks right"}
    )


def test_full_run_verify_ship(bus, veil):
    job = _job()
    bus.submit(job)
    # input envelope opens exactly once: primary -> verifier, attested
    input_env = veil.fetch_envelopes(f"svc-{job.job_id}")[0]
    opened = veil.open_message(input_env)
    body = json.loads(opened["plaintext"].decode())
    assert body["kind"] == "job.input"
    assert body["input"] == {"url": "https://example.com"}
    assert opened["sender"] == bus._device_id("wren")
    assert opened["recipient"] == bus._device_id("sidewinder")

    run = bus.run_primary(job.job_id, lambda inp: {"done": True, "echo": inp})
    assert run["transport"] == TRANSPORT_SEALED
    # verify() authenticates as the verifier, opens the primary's sealed
    # output envelope over the wire (attestation + replay checked inside)
    result = bus.verify(
        job.job_id, lambda out: {"verdict": "VERIFIED", "reason": "looks right"}
    )
    assert result["verdict"] == "VERIFIED"
    assert result["transport"] == TRANSPORT_SEALED

    # verdict envelope: the one envelope not yet consumed, sealed back
    # to the primary, opens exactly once
    rec = bus._require_job(job.job_id)
    remaining = [
        e
        for e in veil.fetch_envelopes(f"svc-{job.job_id}")
        if e["message_id"]
        not in (rec["input_envelope_id"], rec["output_envelope_id"])
    ]
    assert len(remaining) == 1
    verdict_opened = veil.open_message(remaining[0])
    verdict_body = json.loads(verdict_opened["plaintext"].decode())
    assert verdict_body["kind"] == "job.verdict"
    assert verdict_body["verdict"]["verdict"] == "VERIFIED"
    assert verdict_opened["sender"] == bus._device_id("sidewinder")
    assert verdict_opened["recipient"] == bus._device_id("wren")

    receipt = bus.receipt(job.job_id)
    assert receipt["shipped"] is True
    assert [p["phase"] for p in receipt["phases"]] == [
        "submitted",
        "output_sealed",
        "verified",
    ]


def test_challenged_verdict_never_ships(bus):
    job = _job()
    bus.submit(job)
    bus.run_primary(job.job_id, lambda inp: {"done": True})
    with pytest.raises(JobNotShipped):
        bus.verify(job.job_id, lambda out: {"verdict": "CHALLENGED", "reason": "no"})
    assert bus.receipt(job.job_id)["shipped"] is False


def test_verifier_must_return_a_real_verdict(bus):
    job = _job()
    bus.submit(job)
    bus.run_primary(job.job_id, lambda inp: {"done": True})
    with pytest.raises(ServiceBusError):
        bus.verify(job.job_id, lambda out: {"verdict": "MAYBE"})


# -- O4: money stays fail-closed ------------------------------------------------

def test_money_intent_job_refused_with_remedy(bus, veil):
    job = _job(money_intent=True)
    with pytest.raises(MoneyRefused) as exc:
        bus.submit(job)
    assert "register_rail" in str(exc.value)  # remedy named
    assert "MoneyAuthorization" in str(exc.value)
    assert veil.fetch_envelopes(f"svc-{job.job_id}") == []  # never sealed
    assert job.job_id not in bus._jobs


# -- O5: honest degradation ------------------------------------------------------

def test_no_veil_runs_labeled_local_unsealed(home):
    bus = CybrusServiceBus(veil=None)
    job = _job()
    out = bus.submit(job)
    assert out["transport"] == TRANSPORT_LOCAL
    run = bus.run_primary(job.job_id, lambda inp: {"done": True})
    assert run["transport"] == TRANSPORT_LOCAL
    assert run["envelope_id"] is None
    verdict = bus.verify(job.job_id, lambda o: {"verdict": "VERIFIED"})
    assert verdict["transport"] == TRANSPORT_LOCAL
    receipt = bus.receipt(job.job_id)
    assert receipt["shipped"] is True
    assert "local-unsealed" in receipt["note"]
    assert "no sealed-transport claim" in receipt["note"]


# -- personas ride the bus, surface unchanged (O7) --------------------------------

def test_run_persona_through_bus(bus, registry):
    job = _job()
    bus.submit(job)
    out = bus.run_persona(job.job_id, "wren", registry, "lift my site")
    assert out["transport"] == TRANSPORT_SEALED
    assert out["output_ref"]
    brain = registry.resolve("test-brain")
    assert brain.seen[0].role == "system"
    assert "Wren" in brain.seen[0].content
    assert brain.seen[1].content == "lift my site"


def test_sidewinder_traits_ride_the_bus(bus, registry):
    job = _job(seat="service.goal-line", action="obtain")
    bus.submit(job)
    bus.run_persona(job.job_id, "sidewinder", registry, "get me there")
    brain = registry.resolve("test-brain")
    prompt = brain.seen[0].content
    assert "UNIQUE ANGLE" in prompt
    assert "GUIDED STEPS" in prompt
    assert "Give me the goal. I'll bring back the proof." in prompt


def test_public_surface_has_no_mechanics_leak():
    for name, card in SERVICE_CARDS.items():
        prompt = build_system_prompt(card).lower()
        for word in ("veil", "cybrus", "envelope", "choke point", "seal"):
            assert word not in prompt, f"{name}: {word!r} leaked into public text"


def test_posture_is_honest(bus):
    posture = bus.describe_posture()
    assert posture["transport"] == TRANSPORT_SEALED
    assert posture["laws"] == ["O1", "O2", "O3", "O4", "O5", "O6", "O7"]
    assert "never calls MoneyGateway.execute" in posture["money"]
    assert posture["deletes_data"] is False
    local = CybrusServiceBus(veil=None)
    assert local.describe_posture()["transport"] == TRANSPORT_LOCAL
