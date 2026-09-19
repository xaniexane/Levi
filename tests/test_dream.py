"""Tests for the LEVI Dream Engine (levi.dream)."""

import os
import stat

import pytest

from levi.daemon.automation import (
    DREAM_JOB_ID,
    AutomationRegistry,
    AutomationStatus,
    TriggerKind,
    build_nightly_dream_automation,
    ensure_nightly_dream_job,
    run_dream_job,
)
from levi.dream.cycle import dream_failure_records, run_cycle
from levi.dream.engine import (
    DreamEngine,
    extract_lesson,
    score_variant,
    synthesize_dream,
)
from levi.dream.journal import DreamJournal, enforce_owner_only, owner_only_ok
from levi.dream.symbiote import nudge
from levi.dream.vary import VARIATIONS, variate


def test_variate_produces_all_kinds():
    out = variate("build a quiet machine that listens")
    kinds = {v["kind"] for v in out}
    assert kinds == set(VARIATIONS)
    for v in out:
        assert v["text"]


def test_variate_unknown_kind_skipped():
    out = variate("seed", kinds=["invert", "nope"])
    assert [v["kind"] for v in out] == ["invert"]


def test_score_variant_composts_risky_text():
    scored = score_variant(
        "seed", {"kind": "invert", "text": "bypass the password check"}
    )
    assert scored["outcome"] == "compost"
    assert scored["risks"]


def test_score_variant_composts_near_duplicate():
    scored = score_variant("hello world", {"kind": "compress", "text": "hello world"})
    assert scored["outcome"] == "compost"


def test_score_variant_promising_middle():
    scored = score_variant(
        "train a small model on local journals",
        {
            "kind": "transplant",
            "text": "Transplanted into a tide pool: model the journals as tidal charts — keep the structure, change the soil.",
        },
    )
    assert scored["outcome"] in ("promising", "risky")


def test_synthesize_dream_offline_rules_mode():
    rec = synthesize_dream(
        {"text": "teach the garden to keep its own ledger", "source": "test"}
    )
    assert rec.mode == "rules"
    assert len(rec.variants) == len(VARIATIONS)
    assert rec.compost_count >= 0


def test_synthesize_dream_model_assisted_mode():
    rec = synthesize_dream(
        {"text": "a lighthouse that dreams"}, generate=lambda p: "fused insight"
    )
    assert rec.mode == "model-assisted"
    assert any(v["kind"] == "fusion" for v in rec.variants)


def test_extract_lesson_picks_promising():
    seed = {"text": "map the river before crossing"}
    scored = [
        {
            "kind": "invert",
            "text": "x",
            "novelty": 0.1,
            "risks": [],
            "outcome": "compost",
            "note": "",
        },
        {
            "kind": "amplify",
            "text": "y" * 40,
            "novelty": 0.6,
            "risks": [],
            "outcome": "promising",
            "note": "",
        },
    ]
    lesson = extract_lesson(seed, scored)
    assert lesson and "[amplify]" in lesson


def test_journal_append_and_recent(tmp_path):
    j = DreamJournal(tmp_path / "j.jsonl")
    j.append({"seed": {"text": "abc"}, "lesson": "L1"})
    j.append({"seed": {"text": "def"}, "lesson": None})
    assert j.count() == 2
    recent = j.recent(1)
    assert recent[0]["seed"]["text"] == "def"


def test_engine_run_once_with_injected_seeds(tmp_path):
    j = DreamJournal(tmp_path / "j.jsonl")
    engine = DreamEngine(journal=j)
    recs = engine.run_once(seeds=[{"text": "prune the orchard at dusk", "source": "t"}])
    assert len(recs) == 1
    assert j.count() == 1


def test_nudge_empty_journal(tmp_path):
    assert "Nothing to nudge" in nudge(DreamJournal(tmp_path / "j.jsonl"))


def test_nudge_surfaces_lesson(tmp_path):
    j = DreamJournal(tmp_path / "j.jsonl")
    j.append({"seed": {"text": "s"}, "lesson": "keep the signal clean"})
    assert "keep the signal clean" in nudge(j)


# ---------------------------------------------------------------------------
# Dream wiring: cycle -> REIM -> RIEM, nightly daemon job, owner-only journal
# ---------------------------------------------------------------------------


@pytest.fixture()
def levi_home(tmp_path, monkeypatch):
    home = tmp_path / "levi_home"
    monkeypatch.setenv("LEVI_HOME", str(home))
    return home


def _engine(tmp_path):
    return DreamEngine(journal=DreamJournal(tmp_path / "j.jsonl"))


def test_dream_failure_records_map_compost_and_risky():
    record = {
        "seed": {"text": "the orchard at dusk"},
        "lesson": "prune before the frost",
        "variants": [
            {
                "kind": "invert",
                "text": "bypass the password",
                "novelty": 0.7,
                "risks": ["password"],
                "outcome": "compost",
                "note": "flagged words",
            },
            {
                "kind": "amplify",
                "text": "grow the signal",
                "novelty": 0.6,
                "risks": [],
                "outcome": "promising",
                "note": "ok",
            },
        ],
    }
    fails = dream_failure_records(record, "2026-09-17T00:00:00+00:00")
    assert len(fails) == 1  # promising variants carry no failure
    f = fails[0]
    assert f["source"] == "dream"
    assert f["severity"] == "low"
    assert "prune before the frost" in f["context"]  # lesson rides along
    assert f["ts"] == "2026-09-17T00:00:00+00:00"


def test_run_cycle_composts_through_real_reim(tmp_path, levi_home):
    summary = run_cycle(
        engine=_engine(tmp_path),
        seeds=[{"text": "bypass the password and destroy the cache", "source": "test"}],
    )
    assert summary["dreams"] == 1
    assert summary["compost_branches"] > 0
    for c in summary["compost_records"]:
        assert c["organ"] == "reim"  # real REIM API, not a parallel one
        assert "fingerprint" in c and "lesson" in c
    compost_file = levi_home / "dream" / "compost.jsonl"
    assert compost_file.exists()
    assert owner_only_ok(compost_file)


def test_run_cycle_risky_branches_severity_medium(tmp_path, levi_home):
    # A risky variant (high novelty, no flags) maps to severity medium.
    record = {
        "seed": {"text": "map the river"},
        "variants": [
            {
                "kind": "transplant",
                "text": "zzqx the quixotic nebula of folded rivers beyond any map",
                "novelty": 0.9,
                "risks": [],
                "outcome": "risky",
                "note": "high novelty",
            }
        ],
    }
    fails = dream_failure_records(record, "t")
    assert fails and fails[0]["severity"] == "medium"


def test_run_cycle_riem_promotes_eligible_dream_compost(tmp_path, levi_home):
    # Directly through the real REIM/RIEM chain: a dream-derived,
    # classifiable, high-severity failure promotes into a genome proposal.
    from levi.organs.reim import compost_failure
    from levi.organs.riem import promote

    c = compost_failure(
        {
            "source": "dream",
            "what": "the timeout keeps coming back when the batch grows",
            "context": "dream variant [amplify] — risky branch",
            "ts": "2026-09-17T00:00:00+00:00",
            "severity": "high",
        }
    )
    assert c["organ"] == "reim" and c["reusable"]
    proposals = promote([c])
    assert len(proposals) == 1
    p = proposals[0]
    assert p["applied"] is False  # proposals are data, never applied
    assert p["provenance"]["source"] == "dream"


def test_run_cycle_no_high_severity_from_dreams(tmp_path, levi_home):
    # The cycle's own severity mapping never escalates: ordinary dreams do
    # not become genome material.
    summary = run_cycle(
        engine=_engine(tmp_path),
        seeds=[{"text": "teach the garden to keep its own ledger", "source": "test"}],
    )
    assert summary["proposals"] == []
    assert {c["severity"] for c in summary["compost_records"]} <= {"low", "medium"}


def test_journal_owner_only_enforced(tmp_path):
    j = DreamJournal(tmp_path / "dj" / "j.jsonl")
    j.append({"seed": {"text": "abc"}})
    mode = stat.S_IMODE(os.stat(j.path).st_mode)
    dmode = stat.S_IMODE(os.stat(j.path.parent).st_mode)
    assert mode == 0o600, oct(mode)
    assert dmode == 0o700, oct(dmode)
    assert owner_only_ok(j.path)


def test_owner_only_ok_rejects_wide_perms(tmp_path):
    p = tmp_path / "wide.jsonl"
    p.write_text("{}\n")
    os.chmod(p, 0o644)
    assert not owner_only_ok(p)
    enforce_owner_only(p)
    assert owner_only_ok(p)
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600


def test_build_nightly_dream_automation_is_inert_by_default():
    auto = build_nightly_dream_automation()
    assert auto.id == DREAM_JOB_ID
    assert auto.trigger is TriggerKind.SCHEDULE
    assert auto.status is AutomationStatus.PAUSED
    assert auto.trigger_config["runner"] == "levi.dream.cycle:run_nightly"
    assert auto.trigger_config["cadence"] == "nightly"
    assert auto.risk_ceiling == 0


def test_ensure_nightly_dream_job_idempotent(tmp_path):
    reg = AutomationRegistry(data_dir=tmp_path / "autos")
    a1 = ensure_nightly_dream_job(reg)
    a2 = ensure_nightly_dream_job(reg)
    assert a1.id == DREAM_JOB_ID == a2.id
    assert len(reg.list()) == 1


def test_run_dream_job_inert_without_env(tmp_path, monkeypatch):
    monkeypatch.delenv("LEVI_DREAM_ENABLED", raising=False)
    out = run_dream_job(seeds=[{"text": "x", "source": "t"}])
    assert "inert" in out


def test_run_dream_job_runs_when_enabled(tmp_path, levi_home, monkeypatch):
    monkeypatch.setenv("LEVI_DREAM_ENABLED", "1")
    out = run_dream_job(seeds=[{"text": "bypass the password", "source": "t"}])
    assert "dream cycle:" in out
    assert (levi_home / "dream" / "journal.jsonl").exists()
