"""Proof for the legion crew execution loop — behavioral verification of
the declared laws, not a formal proof.

Covers: the right member resolved per turn (role context in the system
prompt); unknown members fail loudly with the team's real roles (no
provider call, no guess); handoff rules carried into the prompt and left
intact on the team; all members resolving tools through the SAME pool
object Nanobit uses; no silent rerouting between members.
"""

import pytest

from levi.agent.providers import ChatProvider, ChatResponse
from levi.legion import crew_loop, team
from levi.legion.product import LegionError
from levi.legion.skill_pool.pool import get_pool
from levi.revival.omega import nanobit_loop as nl


class FakeProvider(ChatProvider):
    """Deterministic stand-in: answers plainly, records every call."""

    name = "fake"

    def __init__(self, final_text="done"):
        self.final_text = final_text
        self.calls = []

    def is_available(self) -> bool:
        return True

    def chat(self, messages, tools):
        self.calls.append((list(messages), list(tools)))
        return ChatResponse(text=self.final_text, model="fake", provider="fake")


@pytest.fixture()
def crew_team() -> team.Team:
    return team.assemble_team(
        team.BusinessProfile(
            business_type="restaurant",
            size="small",
            business_name="Test Diner",
        )
    )


def _system(provider: FakeProvider) -> str:
    return provider.calls[0][0][0].content


# -- the right member resolves per turn --------------------------------------


def test_crew_turn_resolves_right_member(crew_team: team.Team):
    provider = FakeProvider(final_text="table booked")
    transcript = crew_loop.run_crew_turn(
        crew_team, "booker", "book a table for two", provider=provider
    )
    assert transcript.task == "book a table for two"
    assert transcript.ok is True
    system = _system(provider)
    assert "booker" in system
    # the member's responsibility travels with the turn
    assert "takes and confirms appointments" in system
    # branded to the business, not a generic agent
    assert "Test Diner" in system


def test_each_member_gets_own_role_context(crew_team: team.Team):
    for role, needle in (
        ("cashier", "quotes prices"),
        ("marketer", "reviews"),
        ("receptionist", "takes messages"),
    ):
        provider = FakeProvider()
        crew_loop.run_crew_turn(crew_team, role, "hello", provider=provider)
        assert needle in _system(provider), role


# -- unknown members fail loudly ----------------------------------------------


def test_unknown_member_loud_error(crew_team: team.Team):
    provider = FakeProvider()
    with pytest.raises(LegionError) as exc:
        crew_loop.run_crew_turn(crew_team, "teleporter", "hello", provider=provider)
    message = str(exc.value)
    assert "teleporter" in message
    # names the team's REAL roles — never a guess, never a silent default
    for role in ("booker", "receptionist", "cashier", "marketer"):
        assert role in message
    # nothing ran
    assert provider.calls == []


def test_empty_task_rejected(crew_team: team.Team):
    with pytest.raises(ValueError):
        crew_loop.run_crew_turn(crew_team, "booker", "  ", provider=FakeProvider())


# -- handoff rules: in the prompt, intact on the team --------------------------


def test_handoff_rules_in_prompt_and_intact(crew_team: team.Team):
    before = [r.to_dict() for r in crew_team.handoff_rules]
    provider = FakeProvider()
    crew_loop.run_crew_turn(crew_team, "cashier", "what does it cost", provider=provider)
    system = _system(provider)
    # the member's handoff rules travel verbatim into the prompt
    assert "cannot complete a request" in system
    assert "hands to" in system
    # the owner catch-all is there too
    assert "owner" in system
    # the team object itself is untouched — the loop never reseats anyone
    assert [r.to_dict() for r in crew_team.handoff_rules] == before


def test_no_silent_reroute(crew_team: team.Team):
    # even when the "model" asks for a handoff, the loop returns THIS
    # member's transcript as-is — routing stays the router's job
    provider = FakeProvider(final_text="I need to hand this to the receptionist")
    transcript = crew_loop.run_crew_turn(
        crew_team, "booker", "a weird request", provider=provider
    )
    assert transcript.final == "I need to hand this to the receptionist"
    assert len(provider.calls) == 1  # no second turn for another member
    assert "booker" in _system(provider)


# -- one pool, every member -----------------------------------------------------


def test_all_members_resolve_through_same_pool(crew_team: team.Team):
    assert crew_loop.shared_pool() is get_pool()
    assert crew_loop.shared_pool() is nl.shared_pool()
    pool_ids = {s["id"] for s in get_pool().list_skills()}
    for member in crew_team.crew:
        provider = FakeProvider()
        crew_loop.run_crew_turn(crew_team, member.role, "hello", provider=provider)
        tool_names = [t["name"] for t in provider.calls[0][1]]
        assert tool_names, member.role  # every member gets real tool access
        for name in tool_names:
            assert name.startswith("skill_")
            assert name[len("skill_"):] in pool_ids, name


def test_registry_uses_shared_pool_object():
    skills = get_pool().find_skill("email")[:4]
    assert skills  # the pool really does match this query
    registry = crew_loop.registry_from_skills(skills)
    names = [t.name for t in registry.list()]
    assert names
    pool_ids = {s["id"] for s in get_pool().list_skills()}
    assert all(n[len("skill_"):] in pool_ids for n in names)


# -- honest limits in every turn -------------------------------------------------


def test_crew_honest_limits_in_prompt(crew_team: team.Team):
    provider = FakeProvider()
    crew_loop.run_crew_turn(crew_team, "cashier", "what does it cost", provider=provider)
    system = _system(provider)
    assert "never move money" in system
    assert "never claim to be another company's product" in system
    assert "never guess" in system
