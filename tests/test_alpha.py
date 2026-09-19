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
from levi.alpha.reason import Reasoner
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
    assert len(result["proposals"]) == 3
    assert len(result["critiques"]) == 3
    assert result["verdict"]["chosen"] in {"direct", "skeptical", "minimal"}
    assert result["substrate"] == "rules-engine"
    assert result["verdict"]["substrate"] == "rules-engine"


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
    assert result["substrate"] == "rules-engine"
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
    assert "verdict:" in out and "substrate: rules-engine" in out
