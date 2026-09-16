"""Hermetic tests for levi.agent.brain_checkpoints.

Manifest discovery, eval parsing, and the honest capability gates.
All fixtures are synthetic tmp dirs — never the real weights dir.
"""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import pytest

from levi.agent import brain_checkpoints as ck


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _pt(directory: Path, stem: str = "tiny-gpt") -> Path:
    p = directory / (stem + ".pt")
    p.write_bytes(b"fake-ckpt")
    return p


def _manifest(directory: Path, stem: str = "tiny-gpt", **fields) -> Path:
    base = {
        "checkpoint": stem + ".pt",
        "held_out_loss": 1.857,
        "eval_date": "2026-09-15",
        "corpus_version": "test-corpus v1",
        "params": 100,
        "steps": 10,
    }
    base.update(fields)
    return _write(directory / (stem + ".eval.json"), base)


def _passing_manifest(directory: Path, stem: str = "tiny-gpt", **fields):
    today = dt.date.today().isoformat()
    return _manifest(
        directory,
        stem,
        held_out_loss=0.9,
        eval_date=today,
        tool_use={"pass_rate": 0.95, "n": 100},
        **fields,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_discover_empty_dir(tmp_path):
    assert ck.discover(tmp_path) == []


def test_discover_missing_dir(tmp_path):
    assert ck.discover(tmp_path / "nope") == []


def test_discover_finds_pt_with_manifest(tmp_path):
    _pt(tmp_path)
    _manifest(tmp_path)
    found = ck.discover(tmp_path)
    assert [c.name for c in found] == ["tiny-gpt"]
    assert found[0].held_out_loss == pytest.approx(1.857)
    assert found[0].perplexity == pytest.approx(math.exp(1.857))
    assert found[0].manifest_path is not None


def test_discover_derives_perplexity_from_loss(tmp_path):
    _pt(tmp_path)
    _manifest(tmp_path, perplexity=None)
    c = ck.discover(tmp_path)[0]
    assert c.perplexity == pytest.approx(math.exp(1.857))


def test_discover_malformed_manifest_is_no_eval_not_crash(tmp_path):
    _pt(tmp_path)
    (tmp_path / "tiny-gpt.eval.json").write_text("{not json", encoding="utf-8")
    found = ck.discover(tmp_path)
    assert len(found) == 1
    assert found[0].eval == {}
    assert found[0].held_out_loss is None


def test_v2_eval_report_shape_is_understood(tmp_path):
    # The SCAFFOLD worker's EvalReport JSON, dropped as a manifest,
    # is normalized to the gate's manifest shape.
    _pt(tmp_path, "model_v2")
    _write(
        tmp_path / "model_v2.eval.json",
        {
            "model_name": "model_v2",
            "step": 5000,
            "created_at": "2026-09-20T04:00:00+00:00",
            "perplexity": {"perplexity": 2.46, "n_tokens": 1000},
            "next_token": {"accuracy": 0.31, "n": 200},
            "topic": {"accuracy": 0.55, "n": 100},
            "notes": [
                "topic probes: accuracy 0.55 — modest signal, verify before use."
            ],
        },
    )
    found = ck.discover(tmp_path)
    assert len(found) == 1
    c = found[0]
    assert c.perplexity == pytest.approx(2.46)
    assert c.held_out_loss == pytest.approx(math.log(2.46))
    assert c.eval["eval_date"] == "2026-09-20"
    assert c.eval["steps"] == 5000
    assert c.eval["probes"]["topic_accuracy"] == pytest.approx(0.55)
    # probe accuracies are display-only: no tool_use section, so the
    # gate still demands real tool-use evidence for heavier duties.
    gate = ck.gate_for(c)
    assert gate.tier == "prose-only"


def test_v2_eval_report_bad_perplexity_is_no_eval_not_crash(tmp_path):
    _pt(tmp_path, "model_v2")
    _write(
        tmp_path / "model_v2.eval.json",
        {"model_name": "model_v2", "perplexity": {"perplexity": "n/a"}},
    )
    found = ck.discover(tmp_path)
    assert found[0].held_out_loss is None
    assert ck.gate_for(found[0]).tier == "prose-only"


def _stellar_manifest(arch: str | None) -> dict:
    import datetime as _dt

    m = {
        "held_out_loss": 0.9,
        "eval_date": _dt.date.today().isoformat(),
        "tool_use": {"pass_rate": 0.95, "n": 100},
    }
    if arch is not None:
        m["architecture"] = arch
    return m


def test_architecture_defaults_to_unknown_for_per_stem_manifests(tmp_path):
    _pt(tmp_path, "model_v2")
    _write(tmp_path / "model_v2.eval.json", _stellar_manifest(None))
    (found,) = ck.discover(tmp_path)
    assert found.architecture == "unknown"
    # Measured as default-candidate, but the architecture is unknown:
    # the gate measures, the provider decides loadability.
    assert ck.gate_for(found).default_eligible is True


def test_architecture_declared_in_manifest(tmp_path):
    _pt(tmp_path, "model_v2")
    _write(tmp_path / "model_v2.eval.json", _stellar_manifest("tiny-gpt"))
    (found,) = ck.discover(tmp_path)
    assert found.architecture == "tiny-gpt"


def test_legacy_fallback_reports_tiny_gpt_architecture(tmp_path):
    _pt(tmp_path)  # tiny-gpt.pt
    _write(tmp_path / "eval.json", {"held_out_loss": 1.857, "params": 50})
    _write(tmp_path / "train_log.json", {"params": 60, "steps": 600})
    (found,) = ck.discover(tmp_path)
    assert found.legacy_fallback is True
    assert found.architecture == "tiny-gpt"


def test_status_report_includes_architecture(tmp_path):
    _pt(tmp_path, "model_v2")
    _write(tmp_path / "model_v2.eval.json", _stellar_manifest(None))
    rep = ck.status_report(tmp_path)
    assert rep["checkpoints"][0]["architecture"] == "unknown"


def test_discover_legacy_eval_json_fallback(tmp_path):
    # Pre-manifest layout: bare eval.json + train_log.json in the dir root.
    _pt(tmp_path)
    _write(tmp_path / "eval.json", {"held_out_loss": 1.857, "params": 50})
    _write(tmp_path / "train_log.json", {"params": 60, "steps": 600})
    found = ck.discover(tmp_path)
    assert len(found) == 1
    assert found[0].held_out_loss == pytest.approx(1.857)
    assert found[0].eval["params"] == 50  # eval.json wins over train_log
    assert found[0].eval["steps"] == 600  # backfilled from train_log


def test_discover_legacy_fallback_only_for_tiny_gpt(tmp_path):
    _pt(tmp_path, "model_v2")
    _write(tmp_path / "eval.json", {"held_out_loss": 0.5})
    found = ck.discover(tmp_path)
    assert found[0].held_out_loss is None  # no cross-contamination


def test_discover_sorts_best_loss_first(tmp_path):
    _pt(tmp_path, "b-worse")
    _pt(tmp_path, "a-best")
    _manifest(tmp_path, "b-worse", held_out_loss=2.0)
    _manifest(tmp_path, "a-best", held_out_loss=0.7)
    names = [c.name for c in ck.discover(tmp_path)]
    assert names == ["a-best", "b-worse"]


def test_discover_unevaluated_sinks_to_bottom(tmp_path):
    _pt(tmp_path, "zzz-noeval")
    _pt(tmp_path, "aaa-evaled")
    _manifest(tmp_path, "aaa-evaled", held_out_loss=1.5)
    names = [c.name for c in ck.discover(tmp_path)]
    assert names == ["aaa-evaled", "zzz-noeval"]


def test_get_by_name(tmp_path):
    _pt(tmp_path)
    _manifest(tmp_path)
    assert ck.get("tiny-gpt", tmp_path) is not None
    assert ck.get("missing", tmp_path) is None


def test_weights_dir_respects_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_BRAIN_WEIGHTS", str(tmp_path / "custom.pt"))
    assert ck.weights_dir() == tmp_path


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


def _ckpt(tmp_path, stem="tiny-gpt", **manifest_fields):
    _pt(tmp_path, stem)
    if manifest_fields is not None:
        _manifest(tmp_path, stem, **manifest_fields)
    return ck.get(stem, tmp_path)


def test_no_eval_is_prose_only(tmp_path):
    _pt(tmp_path)
    c = ck.get("tiny-gpt", tmp_path)
    gate = ck.gate_for(c)
    assert gate.tier == "prose-only"
    assert not gate.tool_loop_eligible
    assert not gate.default_eligible
    assert any("no eval report" in r for r in gate.reasons)


def test_current_reality_stays_prose_only(tmp_path):
    # held_out_loss 1.857, no tool-use eval -> prose-only, says why.
    c = _ckpt(tmp_path, held_out_loss=1.857)
    gate = ck.gate_for(c)
    assert gate.tier == "prose-only"
    assert any("1.857" in r and "1.20" in r for r in gate.reasons)
    assert any("no tool-use eval" in r for r in gate.reasons)


def test_tool_loop_candidate(tmp_path):
    today = dt.date.today().isoformat()
    c = _ckpt(
        tmp_path,
        held_out_loss=1.10,
        eval_date=today,
        tool_use={"pass_rate": 0.85, "n": 60},
    )
    gate = ck.gate_for(c)
    assert gate.tier == "tool-loop-candidate"
    assert gate.tool_loop_eligible
    assert not gate.default_eligible  # loss above the 1.00 default ceiling


def test_tool_use_too_weak_stays_prose_only(tmp_path):
    today = dt.date.today().isoformat()
    c = _ckpt(
        tmp_path,
        held_out_loss=0.9,
        eval_date=today,
        tool_use={"pass_rate": 0.5, "n": 60},
    )
    gate = ck.gate_for(c)
    assert gate.tier == "prose-only"
    assert any("pass_rate" in r for r in gate.reasons)


def test_default_candidate_when_all_thresholds_met(tmp_path):
    c = _ckpt(
        tmp_path,
        held_out_loss=0.9,
        eval_date=dt.date.today().isoformat(),
        tool_use={"pass_rate": 0.95, "n": 100},
    )
    gate = ck.gate_for(c)
    assert gate.tier == "default-candidate"
    assert gate.tool_loop_eligible
    assert gate.default_eligible


def test_stale_eval_blocks_default(tmp_path):
    old = (dt.date.today() - dt.timedelta(days=200)).isoformat()
    c = _ckpt(
        tmp_path,
        held_out_loss=0.9,
        eval_date=old,
        tool_use={"pass_rate": 0.95, "n": 100},
    )
    gate = ck.gate_for(c)
    assert gate.tier == "tool-loop-candidate"
    assert not gate.default_eligible
    assert any("200 days old" in r or "days old" in r for r in gate.reasons)


def test_bad_eval_date_blocks_default_not_tool_loop(tmp_path):
    c = _ckpt(
        tmp_path,
        held_out_loss=1.10,
        eval_date="not-a-date",
        tool_use={"pass_rate": 0.85, "n": 60},
    )
    gate = ck.gate_for(c)
    assert gate.tier == "tool-loop-candidate"


def test_thresholds_are_documented_constants():
    assert ck.TOOL_LOOP_MAX_LOSS == 1.20
    assert ck.DEFAULT_MAX_LOSS == 1.00
    assert ck.DEFAULT_MAX_EVAL_AGE_DAYS == 180
    assert set(ck.TIERS) == {"prose-only", "tool-loop-candidate", "default-candidate"}


# ---------------------------------------------------------------------------
# best_default_candidate — the earning mechanism
# ---------------------------------------------------------------------------


def test_nothing_earned_without_eval(tmp_path):
    _pt(tmp_path)
    assert ck.best_default_candidate(tmp_path) is None


def test_earned_checkpoint_returned(tmp_path):
    _pt(tmp_path, "tiny-gpt")
    _pt(tmp_path, "model_v2")
    _manifest(tmp_path, "tiny-gpt", held_out_loss=1.857)  # prose-only
    _passing_manifest(tmp_path, "model_v2")  # earns it
    best = ck.best_default_candidate(tmp_path)
    assert best is not None
    assert best.name == "model_v2"


def test_status_report_shape(tmp_path):
    _pt(tmp_path)
    _manifest(tmp_path)
    rep = ck.status_report(tmp_path)
    assert rep["weights_dir"] == str(tmp_path)
    (entry,) = rep["checkpoints"]
    assert entry["name"] == "tiny-gpt"
    assert entry["tier"] == "prose-only"
    assert entry["held_out_loss"] == pytest.approx(1.857)
    assert entry["perplexity"] == pytest.approx(math.exp(1.857))
    assert entry["eval_date"] == "2026-09-15"
    assert entry["corpus_version"] == "test-corpus v1"
    assert isinstance(entry["why"], list) and entry["why"]
