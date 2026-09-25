"""Hermetic tests for the Legion service-operator personas (Wren, Sidewinder).

Law -> guard -> prove: each persona must satisfy the operator
contract (no-mask law enforced at registration), carry its spec
content verbatim (signature line, shared soul, corroboration rule),
resolve through seats and twin-pair verification, and delegate
turns to its backing brain with the persona prompt prepended — or
degrade honestly when it cannot.
"""

import sys
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core"))

from levi.legion.operators import (  # noqa: E402
    CORROBORATION_RULE,
    SHARED_SOUL,
    SERVICE_CARDS,
    SERVICE_SEATS,
    SERVICE_TWINS_CONFIG,
    ServicePersona,
    build_system_prompt,
    make_persona,
    register_service_personas,
    service_persona_names,
)
from levi.operator.contract import (  # noqa: E402
    NATIVE,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    claims_native_identity,
    validate_operator,
)
from levi.operator.registry import (  # noqa: E402
    OperatorRegistry,
    resolve_for_seat,
    resolve_twin,
)

EXPECTED_SIGNATURES = {
    "wren": "Your site's tired. Give me a week.",
    "sidewinder": "Give me the goal. I'll bring back the proof.",
}

EXPECTED_SERVICES = {
    "wren": "dev-lift",
    "sidewinder": "goal-line",
}


class FakeBrain(Operator):
    """Minimal backing brain for delegation tests."""

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


@pytest.fixture()
def registry():
    reg = OperatorRegistry()
    reg.register("test-brain", FakeBrain(), replace=True)
    return register_service_personas(reg, base_name="test-brain")


# -- the two exist, in spec order --------------------------------------------

def test_two_personas_in_spec_order():
    assert service_persona_names() == ["wren", "sidewinder"]


def test_only_two_personas_built():
    assert set(SERVICE_CARDS) == {"wren", "sidewinder"}


def test_signature_lines_verbatim():
    for name, card in SERVICE_CARDS.items():
        assert card.signature_line == EXPECTED_SIGNATURES[name], name


def test_services_match_spec():
    for name, card in SERVICE_CARDS.items():
        assert card.service == EXPECTED_SERVICES[name], name


# -- contract: each persona validates, no masks --------------------------------

@pytest.mark.parametrize("name", list(EXPECTED_SIGNATURES))
def test_persona_passes_operator_contract(name):
    persona = make_persona(name)
    validate_operator(persona)  # raises on no-mask / malformed
    assert persona.kind == "si"
    assert persona.identity_label == f"si:{name}"
    assert not claims_native_identity(persona)


@pytest.mark.parametrize("name", list(EXPECTED_SIGNATURES))
def test_system_prompt_carries_spec(name):
    card = SERVICE_CARDS[name]
    prompt = build_system_prompt(card)
    assert card.signature_line in prompt
    assert card.voice in prompt
    assert card.soul in prompt
    assert card.eerily_human in prompt
    assert CORROBORATION_RULE in prompt
    for bullet in SHARED_SOUL:
        assert bullet in prompt
    # public identities only: no dynasty language
    lowered = prompt.lower()
    for banned in ("dynasty", "bloodline"):
        assert banned not in lowered
    # no-mask stated
    assert "not LEVI itself" in prompt


# -- registry: registration, seats, twins --------------------------------------

def test_both_registered(registry):
    listed = {d["name"] for d in registry.list_operators()}
    for name in EXPECTED_SIGNATURES:
        assert name in listed
    kinds = {d["name"]: d["kind"] for d in registry.list_operators()}
    assert all(kinds[n] == "si" for n in EXPECTED_SIGNATURES)


def test_seats_cover_both():
    assert set(SERVICE_SEATS.values()) == set(EXPECTED_SIGNATURES)
    for seat, name in SERVICE_SEATS.items():
        assert resolve_for_seat(seat, {"seats": SERVICE_SEATS}) == name


def test_twin_verifier_per_seat():
    for seat, name in SERVICE_SEATS.items():
        twin = resolve_twin(seat, SERVICE_TWINS_CONFIG)
        assert twin is not None, seat
        assert twin.primary == name
        assert twin.verifier == SERVICE_CARDS[name].verifier
        assert twin.verifier in SERVICE_CARDS  # verifier is a real persona
        assert twin.mode == "on_demand"


def test_cross_verification():
    # the two verify each other — no agent ships alone
    assert SERVICE_CARDS["wren"].verifier == "sidewinder"
    assert SERVICE_CARDS["sidewinder"].verifier == "wren"


# -- behavior: delegation and honest degradation --------------------------------

def test_step_prepends_persona_prompt_and_delegates(registry):
    persona = registry.resolve("wren")
    assert isinstance(persona, ServicePersona)
    result = persona.step(
        [OperatorMessage(role="user", content="lift my site")],
        [],
        {},
    )
    assert result.ok
    brain = registry.resolve("test-brain")
    assert brain.seen[0].role == "system"
    assert "Wren" in brain.seen[0].content
    assert EXPECTED_SIGNATURES["wren"] in brain.seen[0].content
    assert brain.seen[1].content == "lift my site"
    assert result.note.startswith("[wren]")


def test_unbound_persona_degrades_honestly():
    persona = make_persona("sidewinder")  # no bind(registry)
    result = persona.step([OperatorMessage(role="user", content="hi")], [], {})
    assert result.finish_reason == "degraded"
    assert not result.ok


def test_unknown_persona_name_rejected():
    with pytest.raises(ValueError):
        make_persona("marlow")  # reverted, not built


# -- Sidewinder refinements (Chauncey, 2026-09-22) -------------------------------

def test_sidewinder_unique_angle_trait():
    card = SERVICE_CARDS["sidewinder"]
    assert card.unique_angle, "unique-angle trait must be set"
    assert "Never the generic answer" in card.unique_angle
    assert "original or less-common" in card.unique_angle
    prompt = build_system_prompt(card)
    assert "UNIQUE ANGLE" in prompt
    assert card.unique_angle in prompt


def test_sidewinder_guided_tutorial_trait():
    card = SERVICE_CARDS["sidewinder"]
    assert card.guided_tutorial, "guided-tutorial trait must be set"
    assert "step-by-step" in card.guided_tutorial
    assert "detailed guided steps" in card.guided_tutorial
    prompt = build_system_prompt(card)
    assert "GUIDED STEPS" in prompt
    assert card.guided_tutorial in prompt


def test_sidewinder_signature_and_soul_unchanged():
    card = SERVICE_CARDS["sidewinder"]
    assert card.signature_line == EXPECTED_SIGNATURES["sidewinder"]
    prompt = build_system_prompt(card)
    for bullet in SHARED_SOUL:
        assert bullet in prompt, "shared-soul bullet missing"
    assert CORROBORATION_RULE in prompt


def test_wren_prompt_untouched_by_traits():
    card = SERVICE_CARDS["wren"]
    assert card.unique_angle == ""
    assert card.guided_tutorial == ""
    prompt = build_system_prompt(card)
    assert "UNIQUE ANGLE" not in prompt
    assert "GUIDED STEPS" not in prompt
