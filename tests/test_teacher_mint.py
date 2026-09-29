"""Tests for the hardened teacher generator (teacher_mint, teacher_score)."""

import json

import pytest

from levi.brain.train import teacher_mint as tm
from levi.brain.train import teacher_score as ts
from levi.brain.train import teacher_intake as ti


def test_pack_requires_known_teacher_and_kind():
    with pytest.raises(ValueError):
        tm.build_pack("skynet", "qa", 3, "r1")
    with pytest.raises(ValueError):
        tm.build_pack("qwen", "sonnet", 3, "r1")


def test_pack_carries_prompts_only_no_responses():
    pack = tm.build_pack("deepseek", "trace", 5, "r1")
    assert len(pack) == 5
    for line in pack:
        assert line["teacher"] == "deepseek"
        assert line["kind"] == "trace"
        assert line["round"] == "r1"
        assert line["prompt"]  # a request, never a fabricated answer
        assert "response" not in line
    # deterministic: same inputs -> identical pack
    assert tm.build_pack("deepseek", "trace", 5, "r1") == pack


def test_pack_default_kind_follows_seat_role():
    assert (
        tm.build_pack("deepseek", tm.SEAT_ROLES["deepseek"], 1, "r")[0]["kind"]
        == "trace"
    )
    assert tm.build_pack("qwen", tm.SEAT_ROLES["qwen"], 1, "r")[0]["kind"] == "qa"
    assert tm.build_pack("grok", tm.SEAT_ROLES["grok"], 1, "r")[0]["kind"] == "canon"


def test_calibration_record_is_deterministic_per_index():
    a = tm._calib_record(7, 42, "tput", "r1")
    b = tm._calib_record(7, 42, "tput", "r1")
    assert a["record_id"] == b["record_id"]
    assert a["text"] == b["text"]
    assert tm._calib_record(8, 42, "tput", "r1")["record_id"] != a["record_id"]
    assert a["source"].startswith("calibration:")
    assert a["calibration"] is True


def test_calibration_rejected_by_teacher_intake():
    # L2: a calibration record forced through the curator gate must fail
    # the teacher roster — it can never silently enter the teacher corpus.
    rec = tm._calib_record(7, 1, "tput", "r1")
    with pytest.raises(ti.Rejected):
        ti.intake_record(
            "calibration:tput",
            rec["raw"]["prompt"],
            rec["raw"]["response"],
            mode="bpe",
        )


def test_mint_refuses_corpus_paths(tmp_path):
    out = tmp_path / "corpus_teacher_train.jsonl"
    with pytest.raises(SystemExit):  # diag.abort: loud exit, fixed code
        tm.mint(out, 10, seed=7, label="tput")


def test_mint_resume_never_duplicates_or_skips(tmp_path):
    out = tmp_path / "calib.jsonl"
    r1 = tm.mint(out, 60, seed=7, label="tput", round="r1")
    assert r1["minted"] == 60 and r1["total"] == 60
    # simulate a kill: mint again with resume=True (progress file intact)
    r2 = tm.mint(out, 60, seed=7, label="tput", round="r1", resume=True)
    assert r2["resumed"] is True
    assert r2["start"] == 60
    assert r2["total"] == 120
    recs = [json.loads(line) for line in open(out, encoding="utf-8") if line.strip()]
    assert len(recs) == 120
    ids = [r["record_id"] for r in recs]
    assert len(set(ids)) == 120  # zero duplicates
    idx = sorted(r["provenance"][0]["index"] for r in recs)
    assert idx == list(range(120))  # zero skips
    # calibration species has its own verifier (never the teacher one)
    assert tm.verify_calibration(recs) == []
    # the verifier is not vacuous: tampering is caught
    tampered = dict(recs[0])
    tampered["text"] = recs[0]["text"] + " extra"
    assert tm.verify_calibration([tampered]) != []


def test_mint_resume_refuses_foreign_file(tmp_path):
    out = tmp_path / "calib.jsonl"
    tm.mint(out, 10, seed=7, label="tput")
    out.with_suffix(out.suffix + ".progress").unlink()  # progress lost
    with pytest.raises(SystemExit):  # refuses to append blindly
        tm.mint(out, 10, seed=99, label="other", resume=True)


def test_measure_throughput_reports_measured_numbers():
    stats = tm.measure_throughput(seconds=2, seed=7)
    assert stats["records"] > 0
    assert stats["tokens"] > 0
    assert stats["tokens_per_sec"] > 0
    # the projection is arithmetic on measured numbers, nothing estimated
    assert stats["projection_100M_tokens_hours"] == round(
        100_000_000 / stats["tokens_per_sec"] / 3600, 2
    )
    assert "this machine" in stats["note"]


def test_scorer_components_are_pipeline_measurements(tmp_path):
    # build a small batch through the real minter, score it
    out = tmp_path / "batch.jsonl"
    tm.mint(out, 40, seed=7, label="score-test")
    recs = [json.loads(line) for line in open(out, encoding="utf-8")]
    s = ts.score_records(recs)
    assert s["n"] == 40
    assert s["identity_pass_rate"] == 1.0  # synthetic LEVI turns obey the law
    assert 0.0 < s["trace_density"] < 1.0  # ~40% carry trace markers
    assert s["dedup_uniqueness"] == 1.0
    assert 0.0 <= s["composite"] <= 1.0
    assert s["note"].startswith("triage only")


def test_scorer_penalizes_identity_violations():
    ok = tm._calib_record(7, 1, "t", "r")
    bad_text = "User: hi\nLEVI: I feel happy and I am alive and conscious."
    bad = dict(ok)
    bad["text"] = bad_text
    bad["record_id"] = ti.record_id_for(bad_text)
    s_ok = ts.score_records([ok])
    s_bad = ts.score_records([ok, bad])
    assert s_bad["identity_pass_rate"] == 0.5
    assert s_bad["composite"] < s_ok["composite"]


def test_scorer_ranks_batches_deterministically(tmp_path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    tm.mint(a, 20, seed=7, label="x")
    tm.mint(b, 20, seed=8, label="y")
    ranked = ts.rank_batches([a, b])
    comps = [r["composite"] for r in ranked]
    assert comps == sorted(comps, reverse=True)
    # same inputs, different argument order -> same ranking
    ranked2 = ts.rank_batches([b, a])
    assert [r["path"] for r in ranked2] == [r["path"] for r in ranked]
