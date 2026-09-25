"""Tests for the synthesis front door: mind, config, status, CLI wiring.

Hermetic: no network, no daemons, no user-HOME writes (LEVI_SYNTHESIS_DIR is
redirected to tmp_path wherever the config touches disk).
"""

import argparse
import json

import pytest

from levi.synthesis import mind
from levi.synthesis import status as status_mod
from levi.synthesis.cli import add_synthesis_arguments, cmd_synthesis
from levi.synthesis.config import SynthesisConfig


# -- mind -----------------------------------------------------------------


def test_ask_rules_only_reports_substrate():
    out = mind.ask("Should the press publish at dawn?", brain_policy="rules-only")
    assert out["substrate"] == "rules-engine"
    assert "native-brain" not in out["substrate"]
    assert out["answer"]
    assert out["limits"]
    assert "proposals" in out and "verdict" in out


def test_ask_brain_policy_is_positional_by_contract():
    # Middle-team contract B1: the flagship calls ask(task, policy) as the
    # deliberative partner — brain_policy must be positional-or-keyword.
    out = mind.ask("Should the press publish at dawn?", "rules-only")
    assert out["substrate"] == "rules-engine"
    assert out["answer"]


def test_ask_empty_task_refused():
    with pytest.raises(ValueError):
        mind.ask("   ", brain_policy="rules-only")


def test_ask_bad_policy_refused():
    with pytest.raises(ValueError):
        mind.ask("hello", brain_policy="bogus")


def test_ask_auto_reports_honestly():
    out = mind.ask("Should the press publish at dawn?", brain_policy="auto")
    assert out["substrate"] in ("rules-engine", "rules-engine + native-brain")
    assert out["limits"]
    if out["substrate"] == "rules-engine + native-brain":
        # The brain's contribution is labeled verbatim, never as reasoning.
        voices = [p for p in out["proposals"] if p.get("stance") == "brain-voice"]
        assert voices
        assert voices[0]["label"] == "raw brain continuation — not reasoning"


def test_substrate_report_shape():
    rep = mind.substrate(brain_policy="rules-only")
    assert rep["substrate"] == "rules-engine"
    assert rep["limits"]
    assert "brain" in rep


# -- config ---------------------------------------------------------------


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SYNTHESIS_DIR", str(tmp_path / "syn"))
    cfg = SynthesisConfig.load()
    assert cfg.brain_policy == "auto"
    assert cfg.offline_enforced is True
    cfg.brain_policy = "rules-only"
    saved = cfg.save()
    assert saved.is_file()
    assert json.loads(saved.read_text(encoding="utf-8"))["brain_policy"] == "rules-only"
    assert SynthesisConfig.load().brain_policy == "rules-only"


def test_config_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SYNTHESIS_DIR", str(tmp_path / "syn"))
    monkeypatch.setenv("LEVI_SYNTHESIS_BRAIN_POLICY", "rules-only")
    assert SynthesisConfig.load().brain_policy == "rules-only"


def test_config_rejects_bad_policy():
    with pytest.raises(ValueError):
        SynthesisConfig(brain_policy="bogus")


def test_config_weights_default_points_at_shipped_weights():
    cfg = SynthesisConfig()
    assert cfg.weights_path().name == "tiny-gpt.pt"
    assert cfg.weights_path().parent.name == "weights"


def test_config_scan_budget_ms_default_and_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SYNTHESIS_DIR", str(tmp_path / "syn"))
    cfg = SynthesisConfig.load()
    assert cfg.scan_budget_ms == 100
    cfg2 = SynthesisConfig(scan_budget_ms=500)
    cfg2.save()
    assert SynthesisConfig.load().scan_budget_ms == 500


def test_config_scan_budget_ms_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SYNTHESIS_DIR", str(tmp_path / "syn"))
    monkeypatch.setenv("LEVI_SYNTHESIS_SCAN_BUDGET_MS", "250")
    assert SynthesisConfig.load().scan_budget_ms == 250
    monkeypatch.setenv("LEVI_SYNTHESIS_SCAN_BUDGET_MS", "nope")
    with pytest.raises(ValueError):
        SynthesisConfig.load()


def test_config_rejects_bad_scan_budget_ms():
    with pytest.raises(ValueError):
        SynthesisConfig(scan_budget_ms=0)
    with pytest.raises(ValueError):
        SynthesisConfig(scan_budget_ms="soon")


# -- status ---------------------------------------------------------------


def test_status_shape():
    st = status_mod.collect_status()
    for key in ("brain", "skills", "growth", "lwp", "finance", "daemon"):
        assert key in st, f"missing status section: {key}"
    assert isinstance(st["brain"]["weights_present"], bool)
    assert st["finance"]["mode"] in ("paper-only", "live", "unknown")
    rendered = status_mod.render_status(st)
    assert "vital signs" in rendered
    assert "finance" in rendered


def test_status_never_raises():
    # Every organ check degrades to "unverifiable", never an exception.
    st = status_mod.collect_status()
    assert st["skills"]["registered"] is None or isinstance(
        st["skills"]["registered"], int
    )


# -- CLI wiring -----------------------------------------------------------


def _parse(argv):
    parser = argparse.ArgumentParser(prog="levi synthesis")
    add_synthesis_arguments(parser)
    return parser.parse_args(argv)


def test_cli_parses_ask():
    ns = _parse(["ask", "hello there"])
    assert ns.synthesis_cmd == "ask"
    assert ns.task == "hello there"


def test_cli_parses_prove_offline_defaults():
    ns = _parse(["prove-offline"])
    assert ns.synthesis_cmd == "prove-offline"
    assert ns.brain_policy == "rules-only"


def test_cli_parses_config():
    ns = _parse(["config", "--brain-policy", "auto"])
    assert ns.synthesis_cmd == "config"
    assert ns.brain_policy == "auto"


def test_cmd_synthesis_ask_rules_only(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SYNTHESIS_DIR", str(tmp_path / "syn"))
    ns = _parse(
        ["ask", "Should the press publish at dawn?", "--brain-policy", "rules-only"]
    )
    assert cmd_synthesis(ns) == 0
    out = capsys.readouterr().out
    assert "substrate: rules-engine" in out


def test_cmd_synthesis_ask_needs_task(capsys):
    ns = _parse(["ask"])
    assert cmd_synthesis(ns) == 2


def test_cmd_synthesis_status(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_SYNTHESIS_DIR", str(tmp_path / "syn"))
    ns = _parse(["status"])
    assert cmd_synthesis(ns) == 0
    assert "vital signs" in capsys.readouterr().out


def test_cmd_synthesis_unknown_command(capsys):
    ns = argparse.Namespace(synthesis_cmd=None)
    assert cmd_synthesis(ns) == 2
