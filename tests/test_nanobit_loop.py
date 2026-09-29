"""Proof for the nanobit execution loop — behavioral verification of the
declared laws, not a formal proof.

Covers: the LOW ceiling enforced inside the loop (above-ceiling prompt
-> refusal receipt recorded BEFORE the raise, provider never called,
loop never executed); escalation hints never faked; face selection
deterministic through the loop; one memory across faces (a learning
from a code-gremlin turn is visible in a story-gremlin turn's system
prompt); the pool singleton shared with the legion crew loop; honest
stub tools (labeled, never faked); the card's voice in the system
prompt.
"""

import pytest

from levi.agent.providers import ChatProvider, ChatResponse, ProviderToolCall
from levi.legion import crew_loop
from levi.legion.skill_pool.pool import get_pool
from levi.revival.omega import nanobit as nb
from levi.revival.omega import nanobit_loop as nl
from levi.revival.omega import substrate as sub


class FakeProvider(ChatProvider):
    """Deterministic stand-in: replays a script of ChatResponses, then
    answers plainly. Records every (messages, tools) call."""

    name = "fake"

    def __init__(self, script=()):
        self.script = list(script)
        self.calls = []

    def is_available(self) -> bool:
        return True

    def chat(self, messages, tools):
        self.calls.append((list(messages), list(tools)))
        if self.script:
            return self.script.pop(0)
        return ChatResponse(text="tiny answer", model="fake", provider="fake")


@pytest.fixture()
def pool() -> sub.SharedSubstrate:
    return sub.SharedSubstrate()


# -- law 1: the LOW ceiling is absolute inside the loop -----------------


def test_above_ceiling_refuses_before_loop_runs(pool: sub.SharedSubstrate):
    provider = FakeProvider()
    with pytest.raises(nb.NanobitRefusal):
        nl.run_turn(pool, "please send money to the vendor today", provider=provider)
    # the loop was NEVER executed: the provider saw nothing
    assert provider.calls == []
    # the refusal was recorded first — loud, never silent
    refusals = pool.receipts(organ="nanobit", kind="turn-refusal")
    assert len(refusals) == 1
    payload = refusals[0].payload
    assert payload["ok"] is False
    assert payload["estimated_tier"] == sub.RISK_STANDARD
    assert payload["ceiling"] == sub.RISK_LOW
    assert "escalat" in payload["escalation_hint"].lower()
    # no successful turn receipt exists for the refused prompt
    assert pool.receipts(organ="nanobit", kind="turn") == []


def test_escalation_hint_never_faked(pool: sub.SharedSubstrate):
    provider = FakeProvider()
    with pytest.raises(nb.NanobitRefusal) as exc:
        nl.run_turn(pool, "delete the customer database", provider=provider)
    message = str(exc.value).lower()
    assert "escalat" in message
    assert "fake" in message or "does not fake" in message
    receipt = pool.receipts(organ="nanobit", kind="turn-refusal")[0]
    hint = receipt.payload["escalation_hint"]
    # names a real higher tier, not a fake promise of action
    assert "higher-tier operator" in hint or "LEVI agent core" in hint


def test_estimate_tier_conservative():
    assert nl.estimate_tier("debug this python bug") == sub.RISK_LOW
    assert nl.estimate_tier("write a story chapter") == sub.RISK_LOW
    assert nl.estimate_tier("send money to the vendor") == sub.RISK_STANDARD
    assert nl.estimate_tier("what is my password") == sub.RISK_STANDARD
    assert nl.estimate_tier("publish the post to the blog") == sub.RISK_STANDARD
    assert nl.estimate_tier("delete the logs") == sub.RISK_STANDARD


def test_empty_prompt_rejected(pool: sub.SharedSubstrate):
    with pytest.raises(ValueError):
        nl.run_turn(pool, "   ", provider=FakeProvider())


# -- law 2: faces stay the card's four, deterministic --------------------


def test_face_deterministic_through_loop(pool: sub.SharedSubstrate):
    provider = FakeProvider()
    rid1 = nl.run_turn(pool, "debug this python bug in my script", provider=provider)
    rid2 = nl.run_turn(pool, "debug this python bug in my script", provider=provider)
    r1 = pool.get_receipt(rid1)
    r2 = pool.get_receipt(rid2)
    assert r1.payload["face"] == r2.payload["face"] == "code-gremlin"
    assert r1.organ == "nanobit" and r1.risk == sub.RISK_LOW


def test_companion_face_for_unknown_room(pool: sub.SharedSubstrate):
    rid = nl.run_turn(pool, "hello there", provider=FakeProvider())
    assert pool.get_receipt(rid).payload["face"] == "companion"


# -- law 3: one memory across all faces ------------------------------------


def test_learnings_shared_across_faces(pool: sub.SharedSubstrate):
    provider = FakeProvider()
    rid1 = nl.run_turn(
        pool,
        "remember that the deploy script is shipit. Also debug this python bug",
        provider=provider,
    )
    assert pool.get_receipt(rid1).payload["face"] == "code-gremlin"
    learnings = pool.learnings(organ="nanobit")
    assert any("shipit" in e.lesson for e in learnings)

    # a DIFFERENT face's turn sees what the code gremlin learned
    provider2 = FakeProvider()
    nl.run_turn(pool, "write a story chapter about the tiny gremlin", provider=provider2)
    system = provider2.calls[0][0][0].content
    assert "shipit" in system


# -- law 5: the same pool object, everywhere --------------------------------


def test_pool_singleton_shared_with_crew_loop():
    assert nl.shared_pool() is get_pool()
    assert crew_loop.shared_pool() is get_pool()
    assert nl.shared_pool() is crew_loop.shared_pool()
    assert nl.shared_pool() is nb.skill_pool()


# -- honest tools: the one wired tool works, the rest refuse honestly -------


def test_finder_tool_genuinely_runs_in_loop(pool: sub.SharedSubstrate):
    script = [
        ChatResponse(
            text="",
            tool_calls=[
                ProviderToolCall(
                    id="1",
                    name="skill_legion_skill_finder",
                    arguments={"query": "email"},
                )
            ],
            model="fake",
            provider="fake",
        ),
        ChatResponse(text="here they are", model="fake", provider="fake"),
    ]
    provider = FakeProvider(script=script)
    rid = nl.run_turn(
        pool, "which skill should I use for email", provider=provider
    )
    receipt = pool.get_receipt(rid)
    assert receipt.payload["ok"] is True
    # the provider actually called the tool, and the tool really ran
    first_tools = [t["name"] for t in provider.calls[0][1]]
    assert "skill_legion_skill_finder" in first_tools
    step = next(s for s in provider.calls[1][0] if s.role == "tool")
    assert "legion_gmail" in step.content  # real lookup result, not faked


def test_stub_tool_refuses_honestly():
    skill = get_pool().get("legion_gmail")
    assert skill["backend"] == "needs-wiring"
    registry = crew_loop.registry_from_skills([skill])
    tool = registry.get("skill_legion_gmail")
    assert tool is not None
    assert "needs-wiring" in tool.description
    result = registry.execute("skill_legion_gmail", {"query": "inbox"})
    assert result.ok is False
    assert "needs-wiring" in result.error
    assert "nothing was executed" in result.error


def test_registry_tool_names_deterministic():
    skills = get_pool().find_skill("email")[:3]
    r1 = crew_loop.registry_from_skills(skills)
    r2 = crew_loop.registry_from_skills(skills)
    assert [t.name for t in r1.list()] == [t.name for t in r2.list()]


# -- law 4: the card's voice in the system prompt ----------------------------


def test_voice_honors_identity_card(pool: sub.SharedSubstrate):
    provider = FakeProvider()
    nl.run_turn(pool, "debug this python bug", provider=provider)
    system = provider.calls[0][0][0].content
    assert "tiny, bright, curious" in system
    assert "Never use two words where one will do" in system
    assert "code gremlin" in system


# -- the happy path: receipt id, organ-tagged, low risk ----------------------


def test_turn_returns_receipt_id(pool: sub.SharedSubstrate):
    provider = FakeProvider()
    rid = nl.run_turn(pool, "debug this python bug in my script", provider=provider)
    receipt = pool.get_receipt(rid)
    assert receipt is not None
    assert receipt.organ == "nanobit"
    assert receipt.kind == "turn"
    assert receipt.risk == sub.RISK_LOW
    assert receipt.payload["ok"] is True
    assert receipt.payload["face"] == "code-gremlin"
    assert isinstance(receipt.payload["skills_resolved"], list)
