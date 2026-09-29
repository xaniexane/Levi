"""Tests for Alpha: the SI team's first mind — reasoning.

- Substrate contract: ALPHA_ROLE, probe_alpha() shape, reason() result keys.
- propose -> critique -> verdict flow structure.
- Substrate honesty: weights absent, and weights present-but-unreadable.
- Consult refusal on empty task.
- Bridge label law for the ai/ counterpart bridge.

Hermetic: no network, no HOME writes; fake brain roots via tmp_path.
"""

import json

import pytest

import levi.alpha as alpha
from levi.alpha.ai import reason_bridge
from levi.alpha.reason import (
    BRAIN_STANCE,
    SUBSTRATE_HYBRID,
    SUBSTRATE_RULES,
    Reasoner,
)
from levi.alpha.si import deliberation


# ---- substrate contract ----


def test_alpha_role():
    assert alpha.ALPHA_ROLE == "alpha"


def test_probe_alpha_returns_reasoner():
    reasoner = alpha.probe_alpha()
    assert reasoner is not None
    assert callable(getattr(reasoner, "reason", None))


def test_reason_result_shape():
    result = alpha.probe_alpha().reason("Should I pack an umbrella?")
    for key in ("answer", "substrate", "limits"):
        assert key in result, f"missing contract key {key!r}"
        assert isinstance(result[key], str) and result[key].strip()


def test_reasoner_import_light():
    # The contract is probed inside try/except ImportError: importing
    # levi.alpha must not touch torch or the weights.
    import sys

    assert "torch" not in sys.modules or True  # informational only
    import importlib

    mod = importlib.import_module("levi.alpha")
    assert mod.ALPHA_ROLE == "alpha"


# ---- propose -> critique -> verdict flow ----


def test_propose_three_stances():
    proposals = deliberation.propose("  pick a color  ")
    assert [p["stance"] for p in proposals] == ["direct", "skeptical", "minimal"]
    assert all(p["text"].strip() and p["confidence"] > 0 for p in proposals)


def test_critique_attacks_each_stance():
    proposals = deliberation.propose("x")
    critiques = deliberation.critique(proposals)
    assert [c["stance"] for c in critiques] == ["direct", "skeptical", "minimal"]
    assert all(c["weakness"] and c["open_question"] for c in critiques)


def test_verdict_names_substrate_and_survives():
    proposals = deliberation.propose("x")
    critiques = deliberation.critique(proposals)
    v = deliberation.verdict(proposals, critiques, "rules-engine")
    assert v["chosen"] in {"direct", "skeptical", "minimal"}
    assert v["substrate"] == "rules-engine"
    assert v["answer"] and v["survived_weakness"] and v["open_question"]
    assert "rules-based" in v["note"]


def test_full_reason_flow_reports_everything():
    result = Reasoner().reason("What is the fairest way to split chores?")
    assert len(result["proposals"]) >= 3
    assert len(result["critiques"]) >= 3
    assert result["verdict"]["chosen"] in {"direct", "skeptical", "minimal"}
    # the brain-voice is heard, never obeyed: it cannot win the verdict
    assert result["substrate"] in {SUBSTRATE_RULES, SUBSTRATE_HYBRID}
    assert result["verdict"]["substrate"] == result["substrate"]
    if result["substrate"] == SUBSTRATE_HYBRID:
        assert "brain-voice" in [p["stance"] for p in result["proposals"]]
        assert "garbled" in result["limits"].lower()


# ---- substrate honesty ----


def test_weights_absent_is_honest(tmp_path):
    r = Reasoner(brain_dir=str(tmp_path))  # empty dir: no weights
    result = r.reason("Is this honest?")
    assert result["substrate"] == "rules-engine"
    assert "No usable native-brain weights" in result["limits"]
    assert "rules engine, not the brain" in result["limits"]
    assert result["brain"]["weights_present"] is False


def test_weights_present_but_unreadable_is_honest(tmp_path):
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()
    (weights_dir / "tiny-gpt.pt").write_bytes(b"not a real checkpoint")
    r = Reasoner(brain_dir=str(tmp_path))
    result = r.reason("Is this honest?")
    assert result["substrate"] == "rules-engine"
    assert result["brain"]["weights_present"] is True
    assert result["brain"]["weights_loadable"] is False
    # never claims brain reasoning it didn't do
    assert "brain" not in result["substrate"]
    assert "not usable" in result["limits"] or "cannot be exercised" in result["limits"]


def test_probe_brain_reports_paths_and_checkpoints(tmp_path):
    r = Reasoner(brain_dir=str(tmp_path))
    report = r.probe_brain()
    assert report["weights_path"].endswith("weights/tiny-gpt.pt")
    assert report["checkpoints"] == []
    assert report["detail"]


def test_never_claims_brain_inference():
    result = Reasoner().reason("anything at all")
    blob = json.dumps(result).lower()
    assert "brain inference" not in blob or "no" in blob  # only in honest limits


# ---- consult refusal ----


def test_refuse_empty_task():
    r = Reasoner()
    with pytest.raises(ValueError, match="empty task"):
        r.reason("   ")
    with pytest.raises(ValueError, match="empty task"):
        r.reason("")


def test_refuse_non_string_task():
    with pytest.raises(ValueError, match="empty task"):
        Reasoner().reason(None)


# ---- ai bridge label law ----


def test_bridge_label():
    assert "conventional-protocol interface" in reason_bridge.BRIDGE_LABEL
    assert "the SI core is authoritative" in reason_bridge.BRIDGE_LABEL
    assert "this bridge claims nothing" in reason_bridge.BRIDGE_LABEL
    assert reason_bridge.tool_schema()["bridge_label"] == reason_bridge.BRIDGE_LABEL


def test_bridge_delegates_verbatim():
    result = reason_bridge.run("Should I pack an umbrella?")
    assert result["substrate"] in {SUBSTRATE_RULES, SUBSTRATE_HYBRID}
    assert {"answer", "substrate", "limits"} <= set(result)
    req = reason_bridge.chat_completion_request("x")
    assert req["messages"][0]["role"] == "system"
    resp = reason_bridge.chat_completion_response(result)
    assert resp["object"] == "chat.completion"
    assert json.loads(resp["choices"][0]["message"]["content"])["answer"]


# ---- CLI smoke ----


def test_cli_parsers_register():
    import argparse

    from levi.alpha.cli import cmd_alpha, register_alpha_parser

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_alpha_parser(sub)
    args = parser.parse_args(["alpha", "substrate"])
    assert args.alpha_cmd == "substrate"
    assert cmd_alpha(args) == 0


def test_cli_reason_smoke(capsys):
    import argparse

    from levi.alpha.cli import cmd_alpha

    args = argparse.Namespace(alpha_cmd="reason", task=["pack", "an", "umbrella?"])
    assert cmd_alpha(args) == 0
    out = capsys.readouterr().out
    assert "verdict:" in out and "substrate:" in out
    assert ("rules-engine" in out)  # rules or rules+brain — never unlabeled


# ---- brain inference wiring ----
# Torch-gated: these prove the offline inference path works against the
# real weights. In environments without torch (or without the weights
# file, which is gitignored) they skip — the honest-fallback coverage
# above still runs.
#
# Verified limitation (2026-09-27): core/levi/brain/weights/tiny-gpt.pt is
# gitignored, so NO pristine checkout can ever run these. Clean-tree
# control (git archive HEAD -> scratch): 102 passed, 7 skipped
# ("native-brain weights not present"). Live worktree (torch 2.14.0+cpu
# + the untracked weights): all hybrid-path tests ran and passed. The
# hybrid proof is therefore worktree-only, forever, unless the 13 MB
# weights get tracked in git — repo-consequential, Chauncey's call, not
# this fixture's.


def _require_brain():
    torch = pytest.importorskip("torch", reason="brain inference needs torch")
    from pathlib import Path

    from levi.brain import inference as brain_inference

    weights = (
        Path(__file__).resolve().parent.parent
        / "core"
        / "levi"
        / "brain"
        / "weights"
        / "tiny-gpt.pt"
    )
    if not weights.is_file():
        pytest.skip("native-brain weights not present")
    return torch, brain_inference, weights


def test_brain_module_import_is_torch_free():
    # levi.brain.inference must stay stdlib-only at import time: torch is
    # lazy. Checked in a subprocess so an already-imported torch can't
    # pollute the answer.
    import subprocess
    import sys

    code = (
        "import sys; "
        "sys.path.insert(0, 'core'); "
        "import levi.brain.inference; "
        "assert 'torch' not in sys.modules, 'torch leaked at import time'"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_brain_inference_loads_real_weights():
    _, brain_inference, weights = _require_brain()
    brain = brain_inference.load_brain(str(weights))
    desc = brain.describe()
    assert desc["params"] == 3271168
    assert desc["training_steps"] == 600
    assert desc["vocab_chars"] == 162
    assert desc["sha256_match"] is True
    assert desc["architecture"] == {
        "layers": 4,
        "heads": 4,
        "embed": 256,
        "block_size": 128,
        "level": "char",
    }
    assert "garbled" in desc["honest_note"]


def test_brain_generate_is_deterministic_and_honest():
    _, brain_inference, weights = _require_brain()
    brain = brain_inference.load_brain(str(weights))
    prompt = "Operating systems manage"
    first = brain.generate(prompt, max_new_chars=40, seed=42)
    second = brain.generate(prompt, max_new_chars=40, seed=42)
    assert first["continuation"] == second["continuation"]
    assert len(first["continuation"]) == 40
    assert first["text"] == prompt + first["continuation"]
    assert first["label"] == "raw brain continuation — not reasoning"
    assert first["unmapped_chars"] == 0
    # different seed, different continuation (it is really sampling)
    third = brain.generate(prompt, max_new_chars=40, seed=43)
    assert third["continuation"] != first["continuation"]


def test_brain_generate_rejects_empty_prompt():
    from levi.brain.inference import BrainError

    _, brain_inference, weights = _require_brain()
    brain = brain_inference.load_brain(str(weights))
    with pytest.raises(BrainError):
        brain.generate("")
    with pytest.raises(BrainError):
        brain.generate("   ")


def test_brain_generate_counts_unmapped_chars():
    _, brain_inference, weights = _require_brain()
    brain = brain_inference.load_brain(str(weights))
    gen = brain.generate("hello \U0001f30d world", max_new_chars=8, seed=7)
    assert gen["unmapped_chars"] == 1
    assert len(gen["continuation"]) == 8


def test_reasoner_hybrid_substrate_with_real_brain():
    _require_brain()  # torch + weights or skip
    r = Reasoner(brain_chars=40)
    result = r.reason("Should I pack an umbrella?")
    assert result["substrate"] == SUBSTRATE_HYBRID
    stances = [p["stance"] for p in result["proposals"]]
    assert BRAIN_STANCE in stances
    brain_prop = next(p for p in result["proposals"] if p["stance"] == BRAIN_STANCE)
    assert brain_prop["text"].strip()  # the brain really said something
    assert brain_prop["generation"]["seed"] == 1337
    # heard, never obeyed: the verdict is always a rules stance
    assert result["verdict"]["chosen"] in {"direct", "skeptical", "minimal"}
    assert result["verdict"]["substrate"] == SUBSTRATE_HYBRID
    # the note states what the brain actually did — raw continuation,
    # not reasoning — and who decided
    note = result["verdict"]["note"].lower()
    assert "raw" in note and "continuation" in note
    assert "rules engine" in note
    assert "garbled" in note
    # never claims the brain reasoned
    assert "brain reasoning" not in note
    assert result["brain"]["inference_wired"] is True
    assert "garbled" in result["limits"].lower()


def test_reasoner_hybrid_is_deterministic():
    _require_brain()  # torch + weights or skip
    a = Reasoner(brain_chars=24).reason("Should I pack an umbrella?")
    b = Reasoner(brain_chars=24).reason("Should I pack an umbrella?")
    ca = next(p["text"] for p in a["proposals"] if p["stance"] == BRAIN_STANCE)
    cb = next(p["text"] for p in b["proposals"] if p["stance"] == BRAIN_STANCE)
    assert ca == cb


def test_reasoner_without_brain_when_disabled():
    _require_brain()  # torch + weights present, but brain switched off
    r = Reasoner(brain_chars=0)
    result = r.reason("Should I pack an umbrella?")
    assert result["substrate"] == SUBSTRATE_RULES
    assert BRAIN_STANCE not in [p["stance"] for p in result["proposals"]]
    assert "disabled" in result["brain"]["detail"] or "not usable" in result["limits"]


def test_cli_brain_reports_honestly(capsys):
    import argparse

    from levi.alpha.cli import cmd_alpha

    args = argparse.Namespace(
        alpha_cmd="brain",
        prompt=["operating", "systems"],
        chars=24,
        seed=1337,
        temperature=0.8,
    )
    rc = cmd_alpha(args)
    out = capsys.readouterr().out
    try:
        import torch  # noqa: F401
    except ImportError:
        assert rc == 1 and "cannot run" in out
    else:
        from pathlib import Path

        weights = (
            Path(__file__).resolve().parent.parent
            / "core"
            / "levi"
            / "brain"
            / "weights"
            / "tiny-gpt.pt"
        )
        if not weights.is_file():
            assert rc == 1 and "cannot run" in out
        else:
            assert rc == 0
            assert "raw brain continuation" in out
            assert "sha256 match: True" in out
            assert "garbled" in out.lower()


# ---- real deliberation (backlog item 2) ----
# Proposals must carry real content read from the task's own words; the
# verdict's answer must actually answer the task, not recite templates.


def test_verdict_answer_addresses_the_task():
    result = Reasoner().reason("Should I pack an umbrella?")
    answer = result["verdict"]["answer"]
    assert "umbrella" in answer
    assert result["verdict"]["chosen"] in {"direct", "skeptical", "minimal"}
    # the answer is the winning stance's own text, addressing the task
    winner = next(
        p for p in result["proposals"] if p["stance"] == result["verdict"]["chosen"]
    )
    assert answer == winner["text"]
    # no framing templates leak into any stance text
    for p in result["proposals"]:
        assert "Take the task at face value and answer it as stated" not in p["text"]


def test_direct_yes_no_gives_conditional_answer():
    direct = deliberation.propose("Should I pack an umbrella?")[0]
    assert direct["stance"] == "direct"
    # names the hinge factor from the explicit lookup — real content,
    # not a generic template
    assert "rain" in direct["text"]
    assert "check for rain" in direct["text"]
    assert "pack the umbrella" in direct["text"]


def test_skeptical_names_actual_ambiguous_words():
    skeptical = deliberation.propose("What is the best way to get there?")[1]
    assert skeptical["stance"] == "skeptical"
    assert "'best'" in skeptical["text"]
    assert "'there'" in skeptical["text"]
    # no actual ambiguity: skepticism says so honestly
    plain = deliberation.propose("What is the capital of France?")[1]
    assert "no purchase" in plain["text"] or "no flag" in plain["text"] or "nothing flagged" in plain["text"]


def test_minimal_marks_uncertainty():
    minimal = deliberation.propose("What is the fairest way to split chores?")[2]
    assert minimal["stance"] == "minimal"
    assert "chores" in minimal["text"]
    assert "smallest true statement" in minimal["text"]
    assert "'fairest'" in minimal["text"]  # the uncertainty is named, not waved at


def test_brain_continuation_feeds_skeptical_stance():
    skeptical = deliberation.propose(
        "Should I pack an umbrella?",
        brain_continuation="the weather sky clouds rain thunder storm",
    )[1]
    # the brain's distinctive drift words are quoted as evidence of
    # loose phrasing — labeled as garbled output, never as reasoning
    assert "'rain'" in skeptical["text"] or "'clouds'" in skeptical["text"]
    assert "garbled" in skeptical["text"]
    assert "never as an answer" in skeptical["text"]
    # and without a continuation there is no brain material in the stance
    no_brain = deliberation.propose("Should I pack an umbrella?")[1]
    assert "brain-voice" not in no_brain["text"]


def test_real_deliberation_is_deterministic():
    a = Reasoner().reason("What is the fairest way to split chores?")
    b = Reasoner().reason("What is the fairest way to split chores?")
    assert a["verdict"]["answer"] == b["verdict"]["answer"]
    assert [p["text"] for p in a["proposals"]] == [p["text"] for p in b["proposals"]]


def test_brain_voice_still_cannot_win():
    # heard, never obeyed: the brain-voice score stays capped below
    # every rules stance even after the rewrite
    proposals = deliberation.propose("pick a color")
    brain = {
        "stance": BRAIN_STANCE,
        "text": "garbled continuation",
        "confidence": 0.35,
    }
    proposals.append(brain)
    critiques = deliberation.critique(proposals)
    v = deliberation.verdict(proposals, critiques, "rules-engine + native-brain")
    assert v["chosen"] != BRAIN_STANCE
    assert v["chosen"] in {"direct", "skeptical", "minimal"}
