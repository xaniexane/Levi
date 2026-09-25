"""Alpha twin-behavior guard: the si_team worker and ai/ bridge contracts
under load, cache reuse, cross-call isolation, and honest degradation.

The everything standard on the new alpha/brain wiring (backlog item 9).
This file never changes twin behavior — it locks the contracts in:

- Repeated ``Reasoner.reason()`` calls: deterministic, proposal count
  stable (no accumulation), results are independent objects.
- Brain load caching: the weights load exactly once per Reasoner;
  a mid-session corruption can't poison an in-flight session.
- No cross-call leakage: brain-voice drift words from one call never
  appear in another call's deliberation.
- Corrupted checkpoint: ``reason()`` never raises — the substrate stays
  rules-engine and ``limits`` reports the honest reason.
- si_team worker (AlphaCore) + ai/ bridge contracts: stateless, shape-stable.

Hermetic: no network, no HOME writes, torch-free — the brain path is
exercised through a fake ``load_brain`` monkeypatch.
"""

import pytest

from levi.alpha.ai import reason_bridge
from levi.alpha.reason import BRAIN_STANCE, SUBSTRATE_RULES, Reasoner
from levi.alpha.si import deliberation
from levi.brain import inference as brain_inference
from levi.si_team.si.alpha import AlphaCore

_TASKS = [
    "Should I pack an umbrella?",
    "What is the fairest way to split chores?",
    "Explain why the sky is blue?",
]


# ---- fake brain -------------------------------------------------------------


class _FakeBrain:
    """A brain whose continuation names task-specific distinctive words."""

    def __init__(self, marker_words):
        self.marker_words = marker_words
        self.generate_calls = 0

    def describe(self):
        return {
            "params": 1,
            "training_steps": 600,
            "vocab_chars": 162,
            "sha256_match": True,
        }

    def generate(self, prompt, max_new_chars=160, temperature=0.8, seed=1337):
        self.generate_calls += 1
        words = self.marker_words.get(prompt.strip(), "static driftword")
        return {
            "continuation": f" {words}",
            "unmapped_chars": 0,
            "max_new_chars": max_new_chars,
            "temperature": temperature,
            "seed": seed,
            "params": 1,
        }


@pytest.fixture(autouse=True)
def _reset_bridge_singleton():
    """The ai bridge keeps a module-level Reasoner singleton: reset it
    after every test so a latched fake brain can never leak into another
    test file sharing the pytest process."""
    yield
    reason_bridge._reasoner = None


@pytest.fixture()
def fake_brain(monkeypatch):
    """Install a fake load_brain; return (brain_instance, call_counter)."""
    brain = _FakeBrain(
        {
            "Should I pack an umbrella?": "xylophone",
            "What is the fairest way to split chores?": "quasar",
            "Explain why the sky is blue?": "zebrafinch",
        }
    )
    calls = {"n": 0}

    def _load(path):
        calls["n"] += 1
        return brain

    monkeypatch.setattr(brain_inference, "load_brain", _load)
    return brain, calls


# ---- repeated reason() calls ------------------------------------------------


def test_repeated_reason_calls_are_deterministic(fake_brain):
    r = Reasoner()
    first = [r.reason(t)["verdict"]["answer"] for t in _TASKS]
    second = [r.reason(t)["verdict"]["answer"] for t in _TASKS]
    assert first == second


def test_repeated_calls_do_not_accumulate_proposals(fake_brain):
    r = Reasoner()
    for t in _TASKS:
        result = r.reason(t)
        # 3 rules stances + 1 brain-voice, every call, never growing
        stances = [p["stance"] for p in result["proposals"]]
        assert stances == ["direct", "skeptical", "minimal", BRAIN_STANCE]
        assert len(result["critiques"]) == 4
    r2 = Reasoner()
    for t in _TASKS:  # a fresh Reasoner agrees — no session state leaked
        assert [p["stance"] for p in r2.reason(t)["proposals"]] == stances


def test_results_are_independent_objects(fake_brain):
    r = Reasoner()
    a = r.reason("Should I pack an umbrella?")
    a["verdict"]["answer"] = "MUTATED"
    a["proposals"].clear()
    b = r.reason("Should I pack an umbrella?")
    assert b["verdict"]["answer"] != "MUTATED"
    assert len(b["proposals"]) == 4  # the mutation of a's list died with a


# ---- cache reuse ------------------------------------------------------------


def test_brain_loads_exactly_once_across_repeated_calls(fake_brain):
    brain, calls = fake_brain
    r = Reasoner()
    for t in _TASKS:
        r.reason(t)
    assert calls["n"] == 1  # cached — not re-read per call
    assert brain.generate_calls == 3  # one fresh continuation per task


def test_mid_session_corruption_cannot_poison_a_session(fake_brain):
    brain, calls = fake_brain
    r = Reasoner()
    first = r.reason("Should I pack an umbrella?")
    assert "'xylophone'" in first["proposals"][1]["text"]

    # the weights file is now garbage: the loader would raise — but the
    # latch means it is never called again for this Reasoner.
    def _corrupt(path):
        raise brain_inference.BrainError(
            "weights file present but unreadable (UnpicklingError: corrupted)"
        )

    # bypass the fixture monkeypatch by patching the module attribute again
    brain_inference.load_brain = _corrupt
    second = r.reason("Should I pack an umbrella?")
    assert calls["n"] == 1  # the corrupt loader never ran
    assert "'xylophone'" in second["proposals"][1]["text"]  # cached brain speaks
    assert first["verdict"]["answer"] == second["verdict"]["answer"]


# ---- no cross-call leakage --------------------------------------------------


def test_no_cross_call_leakage_between_tasks(fake_brain):
    r = Reasoner()
    umbrella = r.reason("Should I pack an umbrella?")
    chores = r.reason("What is the fairest way to split chores?")
    # each call's skeptical stance quotes only its own brain-voice drift
    skeptical_umbrella = umbrella["proposals"][1]["text"]
    skeptical_chores = chores["proposals"][1]["text"]
    assert "'xylophone'" in skeptical_umbrella
    assert "'quasar'" not in skeptical_umbrella
    assert "'quasar'" in skeptical_chores
    assert "'xylophone'" not in skeptical_chores
    # brain-voice proposals are per-call continuations, not shared objects
    voice_umbrella = next(
        p for p in umbrella["proposals"] if p["stance"] == BRAIN_STANCE
    )
    voice_chores = next(p for p in chores["proposals"] if p["stance"] == BRAIN_STANCE)
    assert voice_umbrella is not voice_chores
    assert "xylophone" in voice_umbrella["text"]
    assert "quasar" in voice_chores["text"]


def test_deliberation_lexicons_are_immutable():
    hinges = dict(deliberation._HINGE)
    ambig_len = len(deliberation._AMBIGUITY)
    r = Reasoner()
    for t in _TASKS:
        r.reason(t)
    assert deliberation._HINGE == hinges
    assert len(deliberation._AMBIGUITY) == ambig_len


# ---- corrupted checkpoint degrades honestly ---------------------------------


def test_corrupted_checkpoint_never_raises(tmp_path, monkeypatch):
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()
    (weights_dir / "tiny-gpt.pt").write_bytes(b"corrupted checkpoint bytes")

    def _boom(path):
        raise brain_inference.BrainError(
            "weights file present but unreadable (UnpicklingError: corrupted)"
        )

    monkeypatch.setattr(brain_inference, "load_brain", _boom)
    r = Reasoner(brain_dir=str(tmp_path))
    result = r.reason("Is this honest?")
    assert result["substrate"] == SUBSTRATE_RULES  # never the hybrid claim
    assert "brain" not in result["substrate"]
    assert result["brain"]["inference_wired"] is False
    assert "corrupted" in result["limits"] or "not usable" in result["limits"]
    # and the honest verdict still answers the task
    assert result["verdict"]["chosen"] in {"direct", "skeptical", "minimal"}
    # the loader is latched: no retry spam, no exception accumulation
    second = r.reason("Is this honest?")
    assert second["substrate"] == SUBSTRATE_RULES
    assert second["verdict"]["answer"] == result["verdict"]["answer"]


def test_torch_missing_degrades_honestly_without_brain(monkeypatch):
    def _boom(path):
        raise brain_inference.BrainError(
            "torch is not installed in this environment — "
            "the native-brain weights cannot be exercised"
        )

    monkeypatch.setattr(brain_inference, "load_brain", _boom)
    r = Reasoner()
    result = r.reason("What should I do today?")
    assert result["substrate"] == SUBSTRATE_RULES
    # Honest-unusable wording has two committed forms: "are not usable"
    # when a weights file exists but cannot load, and "No usable
    # native-brain weights were found" when no weights file exists at all.
    # Accept both — the guard must not depend on whether a weights file
    # happens to sit in the environment.
    limits = result["limits"]
    assert (
        "not usable" in limits
        or "cannot be exercised" in limits
        or "No usable native-brain weights were found" in limits
    )
    assert BRAIN_STANCE not in [p["stance"] for p in result["proposals"]]


# ---- si_team worker contract under load -------------------------------------


def test_si_worker_alpha_is_stateless_under_load():
    core = AlphaCore()
    rules_before = [r for r in core.rules]
    out1 = core.reason("should I compare apples versus oranges?")
    out2 = core.reason("should I compare apples versus oranges?")
    out3 = core.reason("should I explain trade offs of moving?")
    assert out1["answer"] == out2["answer"]  # deterministic
    assert out1["answer"] != out3["answer"]  # task-dependent
    assert {"answer", "substrate_used", "rule_tag", "limits"} <= set(out1)
    assert out1["substrate_used"] == "rules-engine"
    assert any("no persistent memory of past consults" in lim for lim in out1["limits"])
    # the class-level rules were not mutated by any call
    assert core.rules == rules_before


def test_si_worker_result_dicts_are_fresh_per_call():
    core = AlphaCore()
    a = core.reason("why is the sky blue?")
    a["answer"] = "MUTATED"
    a["limits"].append("injected")
    b = core.reason("why is the sky blue?")
    assert b["answer"] != "MUTATED"
    assert "injected" not in b["limits"]


# ---- ai bridge contract under load ------------------------------------------


def test_bridge_is_stateless_under_load(fake_brain):
    tasks = _TASKS + ["Should I pack an umbrella?"]
    results = [reason_bridge.run(t) for t in tasks]
    # same task, same answer — the bridge's shared singleton keeps no
    # per-call memory; different tasks get different deliberations
    assert results[0]["verdict"]["answer"] == results[3]["verdict"]["answer"]
    assert results[0]["verdict"]["answer"] != results[1]["verdict"]["answer"]
    assert all(len(res["proposals"]) == 4 for res in results)
    assert all(res["substrate"] == "rules-engine + native-brain" for res in results)


def test_bridge_chat_envelopes_round_trip_verbatim(fake_brain):
    result = reason_bridge.run("Should I pack an umbrella?")
    req = reason_bridge.chat_completion_request("Should I pack an umbrella?")
    assert req["messages"][-1]["content"] == "Should I pack an umbrella?"
    assert req["tool_choice"]["function"]["name"] == reason_bridge.TOOL_NAME
    resp = reason_bridge.chat_completion_response(result)
    assert resp["bridge_label"] == reason_bridge.BRIDGE_LABEL
    import json as _json

    payload = _json.loads(resp["choices"][0]["message"]["content"])
    assert payload["answer"] == result["answer"]
    assert payload["verdict"]["score"] == result["verdict"]["score"]


def test_si_ai_bridge_contract_shape():
    from levi.si_team.ai import alpha as si_ai_alpha

    tools = si_ai_alpha.to_mcp_tools()
    assert tools and tools[0]["name"] == "alpha_reason"
    assert (
        "the SI core" in tools[0]["description"]
        or "first mind" in tools[0]["description"]
    )
    adapter = si_ai_alpha.chat_adapter()
    built = adapter["build_request"](
        [{"role": "user", "content": "compare apples versus oranges"}]
    )
    assert built["messages"][0]["role"] == "system"
    assert (
        "bridge" in built["messages"][0]["content"].lower()
        or "counterpart" in built["messages"][0]["content"].lower()
    )
    parsed = adapter["parse_response"](
        {"choices": [{"message": {"role": "assistant", "content": "answer text"}}]}
    )
    assert parsed == {"role": "assistant", "content": "answer text"}


def test_bridge_refuses_empty_task_like_the_core():
    with pytest.raises(ValueError, match="empty task"):
        reason_bridge.run("  ")
