"""Tests for the learning loop (levi.brain.learn_*): observe -> corpus ->
retrain -> eval-gate -> promote/rollback.

Hermetic: no network, no daemons, no user HOME writes, no torch. Every
path that would need torch (training, candidate export, real forward
passes) is injected with fakes; the gate DECISION logic — the part that
guards the live weights — is tested directly against synthetic scores.
"""

import hashlib
import json
from pathlib import Path

import pytest

from levi.brain.learn_corpus import (
    BrainLoopError,
    build_corpus,
    difficulty_score,
    score_observation,
)
from levi.brain.learn_eval import (
    GateScores,
    ScoredModel,
    append_lineage,
    capture_anchors,
    gate_decision,
    heldout_nats,
    list_rollbacks,
    load_anchors,
    promote,
    read_lineage,
    rollback,
    run_behavioral_checks,
)
from levi.brain.learn_loop import (
    LoopConfig,
    load_schedule,
    main_cli,
    read_receipts,
    run_cycle,
    schedule_loop,
    status,
    tick,
    unschedule_loop,
    write_receipt,
)
from levi.brain.learn_obs import extract_text, read_observations
from levi.brain.learn_train import estimate_cost, run_retrain


# ---------------------------------------------------------------- fixtures


def make_obs(
    model_id="teacher-a",
    prompt="the quick brown fox",
    output="jumps over the lazy dog and keeps going for a while",
    ok=True,
    ts="2026-09-21T00:00:00+00:00",
    sha=None,
):
    return {
        "schema": "levi-observation/1",
        "ts": ts,
        "model_id": model_id,
        "arch": "qwen-class",
        "origin": "reference",
        "prompt": prompt,
        "prompt_truncated": False,
        "prompt_sha256": sha or hashlib.sha256(prompt.encode()).hexdigest(),
        "output": output,
        "output_chars": len(output),
        "sampling": {"temperature": 0.7, "seed": 1},
        "timing": {"seconds": 0.5},
        "receipt": {"ok": ok} if ok else {"ok": False, "error": "boom"},
    }


def write_obs(path: Path, records, corrupt=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
        for c in corrupt:
            fh.write(c + "\n")


def big_records(n=40, model_id="teacher-a"):
    recs = []
    for i in range(n):
        prompt = f"prompt number {i} " + "word " * 20
        output = f"model output number {i} " + "token " * 40
        recs.append(
            make_obs(
                model_id=model_id,
                prompt=prompt,
                output=output,
                ts=f"2026-09-21T00:{i // 60:02d}:{i % 60:02d}+00:00",
                sha=f"sha-{model_id}-{i}",
            )
        )
    return recs


class FakeModel(ScoredModel):
    """Deterministic fake behind the ScoredModel protocol."""

    def __init__(
        self,
        vocab_chars=None,
        loss_per_char=1.0,
        continuation="abc abc abc",
        unmapped=1,
    ):
        self.vocab_chars = list(vocab_chars or ["a", "b", "c", " "])
        self.loss_per_char = loss_per_char
        self.continuation = continuation
        self.unmapped = unmapped
        self.label = "fake"

    def ce_loss(self, text):
        n = len(text)
        return (self.loss_per_char * n, n, 0)

    def generate(self, prompt, max_new_chars, temperature, seed):
        return {
            "continuation": self.continuation[:max_new_chars],
            "unmapped_chars": self.unmapped,
        }


def passing_scores(**kw):
    base = dict(
        heldout_candidate=1.5,
        heldout_incumbent=2.0,
        positions_scored=100,
        behavioral=[
            {"name": "deterministic_argmax", "passed": True, "detail": ""},
            {"name": "charset_adherence", "passed": True, "detail": ""},
            {"name": "no_collapse", "passed": True, "detail": ""},
            {"name": "unmapped_honest", "passed": True, "detail": ""},
        ],
        regret_skipped="no anchors yet",
    )
    base.update(kw)
    return GateScores(**base)


def make_cfg(tmp_path, **kw):
    loop_dir = tmp_path / "loop"
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    obs = tmp_path / "obs.jsonl"
    base = dict(loop_dir=loop_dir, weights_dir=weights_dir, observations_path=obs)
    base.update(kw)
    return LoopConfig(**base), obs


# ---------------------------------------------------------------- learn_obs


def test_read_missing_store_returns_empty(tmp_path):
    res = read_observations(tmp_path / "nope.jsonl")
    assert res["records"] == [] and res["skipped"] == 0


def test_read_skips_corrupt_lines_with_count(tmp_path):
    p = tmp_path / "obs.jsonl"
    good = [make_obs(), make_obs(prompt="another prompt here")]
    write_obs(
        p,
        good,
        corrupt=(
            "not json at all",
            json.dumps({"schema": "levi-observation/9", "ts": "x"}),
            json.dumps({"schema": "levi-observation/1", "ts": "x"}),  # missing fields
            "[1,2,3]",
        ),
    )
    res = read_observations(p)
    assert len(res["records"]) == 2
    assert res["skipped"] == 4


def test_read_model_id_filter(tmp_path):
    p = tmp_path / "obs.jsonl"
    write_obs(p, [make_obs(model_id="a"), make_obs(model_id="b")])
    res = read_observations(p, model_id="b")
    assert [r["model_id"] for r in res["records"]] == ["b"]


def test_extract_text_joins_prompt_and_output():
    rec = make_obs(prompt="hello there", output="general kenobi indeed")
    text = extract_text(rec)
    assert "hello there" in text and "general kenobi indeed" in text


def test_extract_text_empty_record_scores_zero():
    assert extract_text({}) == ""
    assert score_observation({}) == 0.0


def test_observations_env_override(tmp_path, monkeypatch):
    p = tmp_path / "custom.jsonl"
    write_obs(p, [make_obs()])
    monkeypatch.setenv("LEVI_OBSERVATIONS_FILE", str(p))
    from levi.brain.learn_obs import observations_file

    assert observations_file() == p
    assert len(read_observations()["records"]) == 1


# ---------------------------------------------------------------- learn_corpus


def test_corpus_determinism(tmp_path):
    recs = big_records(30)
    a = build_corpus(recs, tmp_path / "a", seed=1337)
    b = build_corpus(recs, tmp_path / "b", seed=1337)
    for key in ("train.jsonl", "val.jsonl"):
        ha = hashlib.sha256((tmp_path / "a" / key).read_bytes()).hexdigest()
        hb = hashlib.sha256((tmp_path / "b" / key).read_bytes()).hexdigest()
        assert ha == hb
    assert a["manifest"]["files"] == b["manifest"]["files"]
    assert a["corpus_id"] == b["corpus_id"]


def test_corpus_dedupe(tmp_path):
    recs = [make_obs(prompt="same prompt here", output="same output here ok")]
    recs.append(make_obs(prompt="same prompt here", output="same output here ok"))
    recs.append(make_obs(prompt="different prompt!", output="different output!!"))
    built = build_corpus(recs, tmp_path / "c")
    total = (
        built["manifest"]["counts"]["train_lines"]
        + built["manifest"]["counts"]["val_lines"]
    )
    assert total == 2
    assert built["manifest"]["counts"]["deduped"] == 1


def test_corpus_quality_filter(tmp_path):
    good = make_obs(prompt="a fine prompt here", output="a fine output indeed ok")
    empty = make_obs(prompt="p", output="")
    failed = make_obs(prompt="ok prompt here", output="ok output here", ok=False)
    built = build_corpus([good, empty, failed], tmp_path / "c", min_quality=0.3)
    total = (
        built["manifest"]["counts"]["train_lines"]
        + built["manifest"]["counts"]["val_lines"]
    )
    # empty output scores 0; failed receipt scores 0.5 (no ok bonus, has output)
    assert built["manifest"]["counts"]["filtered_quality"] == 1
    assert total == 2


def test_corpus_teacher_weighting(tmp_path):
    recs = []
    for i in range(2):
        recs.append(
            make_obs(
                model_id="A",
                prompt=f"A prompt {i} here",
                output=f"A output {i} here ok",
                sha=f"a-{i}",
            )
        )
    for i in range(2):
        recs.append(
            make_obs(
                model_id="B",
                prompt=f"B prompt {i} here",
                output=f"B output {i} here ok",
                sha=f"b-{i}",
            )
        )
    built = build_corpus(recs, tmp_path / "c", teacher_weights={"A": 2.0, "B": 1.0})
    per = built["manifest"]["per_model_lines"]
    assert per == {"A": 4, "B": 2}


def test_corpus_vocab_filter(tmp_path):
    recs = [make_obs(prompt="abc def", output="abc XYZ abc def ghi")]
    built = build_corpus(
        recs, tmp_path / "c", vocab_chars=["a", "b", "c", "d", "e", "f", " ", "\n"]
    )
    assert built["manifest"]["counts"]["dropped_chars"] > 0
    text = (tmp_path / "c" / "train.jsonl").read_text()
    assert "X" not in text and "Y" not in text and "Z" not in text
    assert "abc" in text


def test_corpus_empty_raises_honest(tmp_path):
    with pytest.raises(BrainLoopError, match="no usable records"):
        build_corpus([], tmp_path / "c")
    with pytest.raises(BrainLoopError, match="no usable records"):
        build_corpus([make_obs(prompt="x", output="")], tmp_path / "c")


def test_corpus_curriculum_order(tmp_path):
    recs = big_records(25)
    build_corpus(recs, tmp_path / "c", val_ratio=0.2)
    diffs = []
    with open(tmp_path / "c" / "train.jsonl", encoding="utf-8") as fh:
        for line in fh:
            diffs.append(json.loads(line)["source"]["difficulty"])
    assert diffs == sorted(diffs)


def test_score_observation_prefers_clean_runs():
    clean = make_obs()
    failed = make_obs(ok=False)
    assert score_observation(clean) > score_observation(failed)
    assert 0.0 <= score_observation(clean) <= 1.0


def test_difficulty_score_bounds():
    assert difficulty_score("") == 0.0
    d = difficulty_score("a" * 5000 + "b" * 5000)
    assert 0.0 <= d <= 1.0


# ---------------------------------------------------------------- learn_train


def test_estimate_cost_uncalibrated():
    est = estimate_cost(corpus_chars=50_000, steps=600, max_seconds=3600)
    assert est["calibrated"] is False
    assert est["est_seconds"] is None
    assert "uncalibrated" in est["note"]


def test_estimate_cost_calibrated():
    est = estimate_cost(
        corpus_chars=60_000, steps=600, calibration={"chars_per_sec": 10.0}
    )
    assert est["calibrated"] is True
    assert est["est_seconds"] == pytest.approx(600 * 60.0 / 10.0)


def test_run_retrain_idempotent(tmp_path):
    calls = []

    def fake_train(**kw):
        calls.append(kw)
        out = Path(kw["out_dir"])
        (out / "tiny-gpt.pt").write_bytes(b"FAKE")
        return {"weights_pt": str(out / "tiny-gpt.pt"), "train_log": {"loss_last": 1.0}}

    data = tmp_path / "train.jsonl"
    data.write_text('{"text": "hello"}\n')
    kw = dict(
        train_jsonl=data,
        corpus_id="abc123",
        corpus_chars=12_000,
        staging_root=tmp_path / "staging",
        loop_dir=tmp_path / "loop",
        steps=10,
        seed=1,
        train_fn=fake_train,
    )
    r1 = run_retrain(**kw)
    r2 = run_retrain(**kw)
    assert r1["reused"] is False
    assert r2["reused"] is True
    assert len(calls) == 1


def test_run_retrain_refuses_live_weights_dir(tmp_path):
    def fake_train(**kw):
        raise AssertionError("must not train")

    data = tmp_path / "train.jsonl"
    data.write_text('{"text": "hello"}\n')
    staging_root = tmp_path / "staging"
    with pytest.raises(BrainLoopError, match="must not be the live weights dir"):
        run_retrain(
            train_jsonl=data,
            corpus_id="abc123",
            corpus_chars=12_000,
            staging_root=staging_root,
            loop_dir=tmp_path / "loop",
            steps=10,
            seed=1,
            weights_dir=staging_root / "candidate-abc123",
            train_fn=fake_train,
        )


def test_run_retrain_force_retrains(tmp_path):
    calls = []

    def fake_train(**kw):
        calls.append(1)
        out = Path(kw["out_dir"])
        (out / "tiny-gpt.pt").write_bytes(b"FAKE")
        return {"weights_pt": str(out / "tiny-gpt.pt"), "train_log": {}}

    data = tmp_path / "train.jsonl"
    data.write_text('{"text": "hello"}\n')
    kw = dict(
        train_jsonl=data,
        corpus_id="abc123",
        corpus_chars=12_000,
        staging_root=tmp_path / "staging",
        loop_dir=tmp_path / "loop",
        steps=10,
        seed=1,
        train_fn=fake_train,
    )
    run_retrain(**kw)
    run_retrain(force=True, **kw)
    assert len(calls) == 2


# ---------------------------------------------------------------- learn_eval: gate logic


def test_gate_promotes_better_candidate():
    decision, reasons = gate_decision(
        passing_scores(), promote_margin=0.02, regret_margin=0.05
    )
    assert decision == "promote"
    assert reasons


def test_gate_rejects_worse_candidate():
    decision, reasons = gate_decision(
        passing_scores(heldout_candidate=2.5, heldout_incumbent=2.0),
        promote_margin=0.02,
        regret_margin=0.05,
    )
    assert decision == "reject"
    assert any("margin" in r for r in reasons)


def test_gate_rejects_failed_behavioral():
    bad = passing_scores()
    bad.behavioral = [{"name": "no_collapse", "passed": False, "detail": "degenerate"}]
    decision, reasons = gate_decision(bad, promote_margin=0.02, regret_margin=0.05)
    assert decision == "reject"
    assert any("no_collapse" in r for r in reasons)


def test_gate_regret_rejects_forgetting():
    s = passing_scores(regret_candidate=3.0, regret_incumbent=2.0, regret_skipped="")
    decision, reasons = gate_decision(s, promote_margin=0.02, regret_margin=0.05)
    assert decision == "reject"
    assert any("regret" in r for r in reasons)


def test_gate_regret_skipped_first_cycle():
    s = passing_scores(regret_skipped="no anchors yet")
    decision, _ = gate_decision(s, promote_margin=0.02, regret_margin=0.05)
    assert decision == "promote"


def test_behavioral_checks_good_fake():
    checks = run_behavioral_checks(FakeModel())
    assert all(c["passed"] for c in checks)
    assert {c["name"] for c in checks} == {
        "deterministic_argmax",
        "charset_adherence",
        "no_collapse",
        "unmapped_honest",
    }


def test_behavioral_checks_catch_collapse():
    bad = FakeModel(continuation="a" * 64)
    checks = {c["name"]: c for c in run_behavioral_checks(bad)}
    assert checks["no_collapse"]["passed"] is False


def test_heldout_nats_fake():
    m = FakeModel(loss_per_char=1.25)
    res = heldout_nats(m, "abc abc abc", windows=2, window_chars=4, seed=1)
    assert res["mean_nats"] == pytest.approx(1.25)
    assert res["positions_scored"] > 0


def test_capture_anchors_deterministic():
    a1 = capture_anchors(FakeModel(), k=4)
    a2 = capture_anchors(FakeModel(), k=4)
    assert a1 == a2
    assert len(a1) == 4


# ---------------------------------------------------------------- learn_eval: promote/rollback


def _weights_tree(tmp_path):
    wd = tmp_path / "weights"
    wd.mkdir()
    (wd / "tiny-gpt.pt").write_bytes(b"LIVE-WEIGHTS")
    port = wd / "tiny-gpt-portable"
    port.mkdir()
    (port / "manifest.json").write_text("{}")
    cand_pt = tmp_path / "cand.pt"
    cand_pt.write_bytes(b"CANDIDATE-WEIGHTS")
    cand_port = tmp_path / "cand-portable"
    cand_port.mkdir()
    (cand_port / "manifest.json").write_text("{}")
    return wd, cand_pt, cand_port


def test_promote_and_rollback(tmp_path):
    wd, cand_pt, cand_port = _weights_tree(tmp_path)
    res = promote(
        candidate_pt=cand_pt,
        candidate_portable_dir=cand_port,
        weights_dir=wd,
        lineage_entry={"corpus_id": "x"},
        incumbent=None,
        validate_fn=lambda d: None,
    )
    assert (wd / "tiny-gpt.pt").read_bytes() == b"CANDIDATE-WEIGHTS"
    backups = list_rollbacks(wd)
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"LIVE-WEIGHTS"
    lin = read_lineage(wd)
    assert lin[-1]["kind"] == "promote"
    assert lin[-1]["new_sha256"] == res["new_sha256"]
    assert load_anchors(wd) == []  # no incumbent -> anchors skipped honestly

    rb = rollback(wd, reason="test")
    assert (wd / "tiny-gpt.pt").read_bytes() == b"LIVE-WEIGHTS"
    assert rb["restored_from"] == backups[0].name
    lin = read_lineage(wd)
    assert lin[-1]["kind"] == "rollback"


def test_rollback_restores_portable_export(tmp_path):
    """Regression: rollback must restore the portable export to its
    pre-promote content, not just the .pt weights.

    The torch-free runtime serves the portable export, so a rollback that
    restored weights but left the candidate's portable in place would
    silently keep serving the rejected model. The shared
    ``_weights_tree`` fixture uses identical ``{}`` manifests for live and
    candidate portables, so this needs its own tree with distinct ones."""
    wd = tmp_path / "weights"
    wd.mkdir()
    (wd / "tiny-gpt.pt").write_bytes(b"LIVE-WEIGHTS")
    live_port = wd / "tiny-gpt-portable"
    live_port.mkdir()
    (live_port / "manifest.json").write_text('{"origin": "live"}')
    cand_pt = tmp_path / "cand.pt"
    cand_pt.write_bytes(b"CANDIDATE-WEIGHTS")
    cand_port = tmp_path / "cand-portable"
    cand_port.mkdir()
    (cand_port / "manifest.json").write_text('{"origin": "candidate"}')

    promote(
        candidate_pt=cand_pt,
        candidate_portable_dir=cand_port,
        weights_dir=wd,
        lineage_entry={"corpus_id": "x"},
        incumbent=None,
        validate_fn=lambda d: None,
    )
    assert json.loads((live_port / "manifest.json").read_text()) == {
        "origin": "candidate"
    }

    rb = rollback(wd, reason="regression probe")
    assert rb["portable_restored"] is True
    assert (wd / "tiny-gpt.pt").read_bytes() == b"LIVE-WEIGHTS"
    # The live portable must be the pre-promote one again — not the
    # candidate's.
    assert json.loads((live_port / "manifest.json").read_text()) == {"origin": "live"}


def test_rollback_no_backups_raises(tmp_path):
    wd = tmp_path / "weights"
    wd.mkdir()
    with pytest.raises(BrainLoopError, match="no previous weights"):
        rollback(wd)


def test_promote_missing_live_weights_raises(tmp_path):
    wd = tmp_path / "weights"
    wd.mkdir()
    cand = tmp_path / "c.pt"
    cand.write_bytes(b"x")
    with pytest.raises(BrainLoopError, match="no live weights"):
        promote(
            candidate_pt=cand,
            candidate_portable_dir=tmp_path,
            weights_dir=wd,
            lineage_entry={},
            incumbent=None,
            validate_fn=lambda d: None,
        )


def test_lineage_roundtrip(tmp_path):
    wd = tmp_path / "w"
    wd.mkdir()
    append_lineage(wd, {"kind": "promote", "note": "x"})
    assert read_lineage(wd)[-1]["kind"] == "promote"


# ---------------------------------------------------------------- learn_loop: cycles


def test_cycle_empty_observations(tmp_path):
    cfg, obs = make_cfg(tmp_path)
    obs.write_text("")
    rep = run_cycle(cfg)
    assert rep.status == "empty"
    assert rep.decision == "none"
    assert Path(rep.receipt_path).is_file()


def test_cycle_missing_store_is_empty_not_crash(tmp_path):
    cfg, _obs = make_cfg(tmp_path)  # obs file never created
    rep = run_cycle(cfg)
    assert rep.status == "empty"


def test_cycle_dry_run_writes_no_weights(tmp_path):
    cfg, obs = make_cfg(tmp_path)
    write_obs(obs, big_records(40))
    rep = run_cycle(cfg)
    assert rep.status == "dry-run"
    assert rep.mode == "dry-run"
    assert rep.decision == "dry-run"
    assert not (cfg.loop_dir / "staging").exists()
    assert Path(rep.receipt_path).is_file()
    assert rep.stages["corpus"]["train_chars"] >= 10_000


def test_cycle_blocked_small_corpus(tmp_path):
    cfg, obs = make_cfg(tmp_path)
    write_obs(obs, [make_obs()])
    rep = run_cycle(cfg)
    assert rep.status == "blocked"
    assert any("too small" in r for r in rep.reasons)


def _live_fakes(promote_scores=True):
    def fake_train(**kw):
        out = Path(kw["out_dir"])
        (out / "tiny-gpt.pt").write_bytes(b"CANDIDATE")
        return {"weights_pt": str(out / "tiny-gpt.pt"), "train_log": {"loss_last": 1.0}}

    def fake_export(pt, out_dir):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "manifest.json").write_text("{}")
        return {}

    scores = passing_scores(
        heldout_candidate=1.5 if promote_scores else 2.5,
        heldout_incumbent=2.0,
    )

    def fake_measure(**kw):
        return scores

    return {
        "train_fn": fake_train,
        "export_fn": fake_export,
        "measure_fn": fake_measure,
        "model_fn": lambda d: FakeModel(),
        "validate_fn": lambda d: None,
    }


def test_cycle_live_promotes_with_fakes(tmp_path):
    cfg, obs = make_cfg(tmp_path, dry_run=False)
    (cfg.weights_dir / "tiny-gpt.pt").write_bytes(b"LIVE")
    write_obs(obs, big_records(40))
    rep = run_cycle(cfg, **_live_fakes(promote_scores=True))
    assert rep.status == "promoted", rep.reasons
    assert rep.decision == "promote"
    assert (cfg.weights_dir / "tiny-gpt.pt").read_bytes() == b"CANDIDATE"
    assert len(list_rollbacks(cfg.weights_dir)) == 1
    lin = read_lineage(cfg.weights_dir)
    assert lin[-1]["kind"] == "promote"
    assert lin[-1]["corpus_id"] == rep.stages["corpus"]["corpus_id"]


def test_cycle_live_rejects_with_fakes(tmp_path):
    cfg, obs = make_cfg(tmp_path, dry_run=False)
    (cfg.weights_dir / "tiny-gpt.pt").write_bytes(b"LIVE")
    write_obs(obs, big_records(40))
    rep = run_cycle(cfg, **_live_fakes(promote_scores=False))
    assert rep.status == "rejected"
    assert rep.decision == "reject"
    assert (cfg.weights_dir / "tiny-gpt.pt").read_bytes() == b"LIVE"
    assert list_rollbacks(cfg.weights_dir) == []


def test_cycle_blocked_without_torch_and_no_fake(tmp_path):
    cfg, obs = make_cfg(tmp_path, dry_run=False)
    write_obs(obs, big_records(40))
    rep = run_cycle(cfg)
    # torch is not installed in this environment; with no injected
    # train_fn the cycle must stop honestly after the corpus stage.
    assert rep.status == "blocked"
    assert any("torch" in r for r in rep.reasons)


# ---------------------------------------------------------------- scheduler + receipts + CLI


def test_tick_no_schedule(tmp_path):
    cfg, _ = make_cfg(tmp_path)
    assert tick(cfg) == {
        "ran": False,
        "reason": "no schedule registered (learn schedule)",
    }


def test_schedule_tick_roundtrip(tmp_path):
    cfg, obs = make_cfg(tmp_path)
    write_obs(obs, big_records(40))
    entry = schedule_loop(cfg.loop_dir, every_seconds=3600, mode="dry-run")
    assert entry["mode"] == "dry-run"
    assert load_schedule(cfg.loop_dir)["every_seconds"] == 3600
    res = tick(cfg)
    assert res["ran"] is True
    assert res["report"]["status"] == "dry-run"
    sched = load_schedule(cfg.loop_dir)
    assert sched["next_run"] > entry["next_run"]
    assert unschedule_loop(cfg.loop_dir) is True
    assert load_schedule(cfg.loop_dir) is None
    assert tick(cfg)["ran"] is False


def test_tick_not_due(tmp_path):
    cfg, _ = make_cfg(tmp_path)
    schedule_loop(cfg.loop_dir, every_seconds=999999, mode="dry-run")
    sched = load_schedule(cfg.loop_dir)
    sched["next_run"] = 9999999999.0
    (cfg.loop_dir / "schedule.json").write_text(json.dumps(sched))
    assert tick(cfg)["ran"] is False


def test_schedule_validation():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        with pytest.raises(BrainLoopError):
            schedule_loop(Path(td), every_seconds=0)
        with pytest.raises(BrainLoopError):
            schedule_loop(Path(td), every_seconds=60, mode="bogus")


def test_write_and_read_receipts(tmp_path):
    cfg, _ = make_cfg(tmp_path)
    p = write_receipt(cfg.loop_dir, {"cycle_id": "abc", "status": "dry-run"})
    assert p.is_file()
    recs = read_receipts(cfg.loop_dir)
    assert recs[-1]["kind"] == "learn-cycle"
    assert recs[-1]["cycle_id"] == "abc"


def test_status_shape(tmp_path):
    cfg, obs = make_cfg(tmp_path)
    write_obs(obs, [make_obs()])
    st = status(cfg)
    assert st["observations"]["records"] == 1
    assert st["schedule"] is None
    assert st["weights_present"] is False
    assert st["dry_run_default"] is True


def test_cli_status_and_schedule(tmp_path):
    cfg, obs = make_cfg(tmp_path)
    loop = str(cfg.loop_dir)
    common = [
        "--loop-dir",
        loop,
        "--observations",
        str(obs),
        "--weights-dir",
        str(cfg.weights_dir),
    ]
    assert main_cli(["status", *common]) == 0
    assert main_cli(["schedule", "--every", "60", *common]) == 0
    assert main_cli(["unschedule", *common]) == 0
    assert main_cli(["history", *common]) == 0


def test_cli_tick_runs_due_schedule(tmp_path):
    cfg, obs = make_cfg(tmp_path)
    write_obs(obs, big_records(40))
    loop = str(cfg.loop_dir)
    common = [
        "--loop-dir",
        loop,
        "--observations",
        str(obs),
        "--weights-dir",
        str(cfg.weights_dir),
    ]
    assert main_cli(["schedule", "--every", "60", *common]) == 0
    assert main_cli(["tick", *common]) == 0
    recs = read_receipts(cfg.loop_dir)
    assert recs and recs[-1]["status"] == "dry-run"


def test_cli_rollback_no_backups(tmp_path):
    cfg, _ = make_cfg(tmp_path)
    assert (
        main_cli(
            [
                "rollback",
                "--loop-dir",
                str(cfg.loop_dir),
                "--weights-dir",
                str(cfg.weights_dir),
            ]
        )
        == 1
    )
