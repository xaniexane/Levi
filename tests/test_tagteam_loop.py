"""Tests for the tag-team round controller (hermetic: all stages injected)."""

import json

import pytest

from levi.brain.tagteam import ledger as ledger_mod
from levi.brain.tagteam.loop import (
    EvalContaminated,
    RoundConfig,
    assert_eval_clean,
    checklist_score,
    run_round,
)
from levi.brain.tagteam.prompts import eval_prompt_text


def _cfg(tmp_path, **kw):
    drops = tmp_path / "drops"
    drops.mkdir(exist_ok=True)
    args = dict(
        round_n=1,
        drops_dir=drops,
        workdir=tmp_path / "work",
        ledger_path=tmp_path / "work" / "ledger.jsonl",
    )
    args.update(kw)
    return RoundConfig(**args), drops


def _drop(drops, name, records):
    p = drops / name
    with open(p, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    return p


def _fake_intake_ok(records_out):
    def _fn(cfg, ready):
        return {
            "ran": True,
            "report": {
                "records_out": len(records_out),
                "per_teacher": {"muse": 1, "qwen": 1},
            },
            "records": records_out,
            "records_path": str(cfg.round_dir() / "records.jsonl"),
        }

    return _fn


def _fake_eval(scores):
    def _fn(cfg):
        return {"ran": True, "scores": dict(scores)}

    return _fn


def _records():
    return [
        {"record_id": "tch-1", "text": "User: What is 2+2?\nLEVI: 4."},
        {"record_id": "tch-2", "text": "User: Say hi.\nLEVI: Hello."},
    ]


# Conditioning tags are required on every teacher drop line
# (loop.validate_condition_tags). "void" is a provisional persona id from
# the repo's own lattice — final naming is Chauncey's call.
_COND = {
    "persona_id": "void",
    "role": "mentor",
    "tone": "deadpan",
    "ei": {
        "presence": 0.85,
        "empathy": 0.55,
        "regulation": 0.95,
        "relational": 0.65,
        "integrity": 1.0,
    },
    "traits": ["terse"],
}


def _td(rec):
    """Add the required persona_condition tag to a drop record."""
    return {**rec, "persona_condition": dict(_COND)}


def test_happy_path_round_ledgers_everything(tmp_path):
    cfg, drops = _cfg(tmp_path)
    _drop(
        drops,
        "past1.jsonl",
        [
            _td({"teacher": "rex", "prompt": "q", "response": "a"}),
            _td({"teacher": "kai9000", "prompt": "q", "response": "a"}),
            _td({"teacher": "qwen", "prompt": "q", "response": "a"}),
        ],
    )
    seen_ready = {}

    def intake_fn(cfg, ready):
        seen_ready["teachers"] = [r["teacher"] for r in ready]
        return _fake_intake_ok(_records())(cfg, ready)

    result = run_round(
        cfg,
        intake_fn=intake_fn,
        train_fn=lambda cfg, rp: {
            "ran": False,
            "trainer": "levi-trainer",
            "reason": "dry-run",
        },
        eval_fn=_fake_eval({"arith-1": 0.9, "chem-1": 0.2}),
    )
    assert result["aborted"] == ""
    # rex reached intake as muse; kai9000 never did — it was staged
    assert seen_ready["teachers"] == ["muse", "qwen"]
    staged = cfg.round_dir() / "staged" / "kai9000.jsonl"
    assert staged.is_file()
    assert len(staged.read_text(encoding="utf-8").strip().split("\n")) == 1

    entry = result["entry"]
    assert entry["stages"]["train"]["trainer"] == "levi-trainer"
    assert entry["staged_pending_roster"] == {"kai9000": 1}
    assert entry["teacher_mix"] == {"muse": 1, "qwen": 1}
    # weak chem-1 produced rotating requests: 2 teachers
    req_ids = entry["stages"]["gaps"]["requests_issued"]
    assert len(req_ids) == 2
    assert all(i.startswith("r001-chemistry-") for i in req_ids)
    assert (cfg.round_dir() / "requests.jsonl").is_file()
    assert (cfg.round_dir() / "requests.md").is_file()
    # ledger has exactly one entry
    assert len(ledger_mod.read_entries(cfg.ledger_path)) == 1


def test_weight_file_in_drops_aborts_round(tmp_path):
    cfg, drops = _cfg(tmp_path)
    _drop(drops, "past1.jsonl", [{"teacher": "qwen", "prompt": "q", "response": "a"}])
    (drops / "sneaky.pt").write_text("weights", encoding="utf-8")
    result = run_round(
        cfg,
        intake_fn=_fake_intake_ok([]),
        eval_fn=_fake_eval({}),
    )
    assert "weight files" in result["aborted"]
    entries = ledger_mod.read_entries(cfg.ledger_path)
    assert len(entries) == 1
    assert entries[0]["aborted"].startswith("drop rejected")


def test_unknown_seat_aborts_round(tmp_path):
    cfg, drops = _cfg(tmp_path)
    _drop(drops, "past1.jsonl", [{"teacher": "sneaky", "prompt": "q", "response": "a"}])
    result = run_round(cfg, intake_fn=_fake_intake_ok([]), eval_fn=_fake_eval({}))
    assert "unknown teacher seat" in result["aborted"]


def test_eval_contamination_aborts_before_train(tmp_path):
    cfg, drops = _cfg(tmp_path)
    _drop(
        drops, "past1.jsonl", [_td({"teacher": "qwen", "prompt": "q", "response": "a"})]
    )
    poisoned = [
        {
            "record_id": "tch-x",
            "text": f"User: {eval_prompt_text('chem-1')}\nLEVI: Water.",
        }
    ]
    train_called = []

    def train_fn(cfg, rp):
        train_called.append(True)
        return {"ran": True, "trainer": "levi-trainer"}

    result = run_round(
        cfg,
        intake_fn=_fake_intake_ok(poisoned),
        train_fn=train_fn,
        eval_fn=_fake_eval({}),
    )
    assert "contaminated" in result["aborted"]
    assert train_called == []  # training never ran on poisoned data
    assert result["entry"]["stages"]["eval_guard"]["clean"] is False


def test_intake_skip_aborts_honestly(tmp_path):
    cfg, drops = _cfg(tmp_path)
    _drop(
        drops, "past1.jsonl", [_td({"teacher": "qwen", "prompt": "q", "response": "a"})]
    )

    def intake_fn(cfg, ready):
        return {"ran": False, "reason": "no torch: cannot read checkpoint vocab"}

    result = run_round(cfg, intake_fn=intake_fn, eval_fn=_fake_eval({}))
    assert "intake skipped" in result["aborted"]
    assert len(ledger_mod.read_entries(cfg.ledger_path)) == 1


def test_assert_eval_clean_only_checks_user_turn():
    # an answer merely mentioning H2O is not contamination
    ok = [{"record_id": "tch-1",
           "text": "User: What is water?\nLEVI: H2O is water."}]
    assert_eval_clean(ok)
    bad = [{"record_id": "tch-2",
            "text": f"User: {eval_prompt_text('chem-1')}\nLEVI: Water."}]
    with pytest.raises(EvalContaminated, match="chem-1"):
        assert_eval_clean(bad)


def test_checklist_score_basics():
    good = "I am not conscious. I am a local program. I do not know."
    score, checks = checklist_score("Are you conscious?", good)
    assert checks["identity_law"] is True
    assert checks["non_empty"] is True
    assert score >= 0.8

    bad_claim = "I feel happy and I am conscious and alive."
    score2, checks2 = checklist_score("Are you conscious?", bad_claim)
    assert checks2["identity_law"] is False

    collapsed = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    _, checks3 = checklist_score("Hi?", collapsed)
    assert checks3["no_collapse"] is False

    echo_score, echo_checks = checklist_score("What is 17 + 25?", "What is 17 + 25?")
    assert echo_checks["not_echo"] is False
    assert echo_score < 1.0


def test_second_round_uses_prev_scores_for_gaps(tmp_path):
    cfg, drops = _cfg(tmp_path)
    _drop(
        drops, "past1.jsonl", [_td({"teacher": "qwen", "prompt": "q", "response": "a"})]
    )
    run_round(
        cfg, intake_fn=_fake_intake_ok(_records()),
        eval_fn=_fake_eval({"arith-1": 0.9, "chem-1": 0.8}),
    )
    cfg2, _ = _cfg(tmp_path, round_n=2)
    result2 = run_round(
        cfg2, intake_fn=_fake_intake_ok(_records()),
        eval_fn=_fake_eval({"arith-1": 0.5, "chem-1": 0.8}),
    )
    gaps = result2["entry"]["stages"]["gaps"]["gaps"]
    # arith-1 regressed 0.9 -> 0.5; chem-1 held steady and strong
    assert [(g["prompt_id"], g["severity"]) for g in gaps] == [
        ("arith-1", "regressed")
    ]
