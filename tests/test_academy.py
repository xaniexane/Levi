"""Tests for the LEVI Academy 30-day 24/7 program.

Hermetic: no network (socket blocked), no user HOME writes — all state
goes to tmp dirs via LEVI_ACADEMY_DIR / LEVI_GROWTH_DIR /
LEVI_ACADEMY_CORPUS and a patched memory store dir.
"""

import json
import os
import socket
import sys
import types
from pathlib import Path

import pytest

from levi.academy import run_session as rs
from levi.academy import corpus_ingest as aci
from levi.academy import synthesize as asynth
from levi.academy import session_exercises as aex
from levi.academy import concepts as acon


@pytest.fixture
def no_network(monkeypatch):
    """Block all TCP connects; record attempts to prove zero network use."""
    calls = []

    def _blocked(self, addr, *a, **k):
        calls.append(addr)
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    yield calls


@pytest.fixture
def iso(tmp_path, monkeypatch):
    acad = tmp_path / "academy"
    growth = tmp_path / "growth"
    mem = tmp_path / "memory"
    corpus = tmp_path / "corpus_academy.jsonl"
    monkeypatch.setenv("LEVI_ACADEMY_DIR", str(acad))
    monkeypatch.setenv("LEVI_GROWTH_DIR", str(growth))
    monkeypatch.setenv("LEVI_ACADEMY_CORPUS", str(corpus))
    import levi.memory.store as mstore
    monkeypatch.setattr(mstore, "DEFAULT_DATA_DIR", mem)
    return {"academy": acad, "growth": growth, "memory": mem, "corpus": corpus}


DRY_RESEARCH = {
    "facts": ["Test fact: the defender's map orients detection work."],
    "sources": ["local:test-fixture"],
    "mode": "test",
    "key_terms": ["ATT&CK", "D3FEND", "telemetry"],
    "queries": [],
}


# ------------------------------------------------------------ syllabus
def test_syllabus_structure():
    syl = rs.load_syllabus()
    assert syl["days"] == 30
    assert syl["blocks_per_day"] == 4
    assert syl["sessions_total"] == 120
    assert syl["block_map"] == {"1": "A", "2": "B", "3": "C", "4": "S"}
    for track in ("A", "B", "C", "S"):
        days = syl["tracks"][track]["days"]
        assert len(days) == 30, track
        for d in range(1, 31):
            entry = days[str(d)]
            assert entry["title"], (track, d)
            assert len(entry["objectives"]) >= 2, (track, d)
            assert len(entry["key_questions"]) >= 2, (track, d)
            assert entry["exercise_type"] in aex.EXERCISE_RUNNERS or \
                entry["exercise_type"] == "graduation", (track, d)
    # graduation is session 120
    grad = syl["tracks"]["S"]["days"]["30"]
    assert grad["exercise_type"] == "graduation"
    assert "GRADUATION" in grad["title"]
    # weeks cover all 30 days
    covered = set()
    for w in syl["weeks"]:
        lo, hi = w["days"]
        covered.update(range(lo, hi + 1))
    assert covered == set(range(1, 31))
    assert [w["phase"] for w in syl["weeks"]] == [
        "Foundations", "Intermediate Methods",
        "Advanced Application", "Mastery + Synthesis"]


def test_day_block_arithmetic():
    assert rs.n_to_day_block(1) == (1, 1)
    assert rs.n_to_day_block(4) == (1, 4)
    assert rs.n_to_day_block(5) == (2, 1)
    assert rs.n_to_day_block(120) == (30, 4)
    assert rs.day_block_to_n(30, 4) == 120


# ------------------------------------------------- hermetic session run
def test_session_completes_hermetically(iso, no_network):
    result = rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    assert no_network == [], f"session used the network: {no_network}"
    assert result["day"] == 1 and result["block"] == 1
    assert result["track"] == "A"
    assert result["research_mode"] == "test"
    assert 0.0 <= result["exercise_score"] <= 1.0
    assert 0.0 <= result["mastery_score"] <= 1.0

    # progress recorded
    prog = json.loads((iso["academy"] / "progress.json").read_text())
    assert "d1b1" in prog["completed"]
    assert prog["sessions"]["d1b1"]["track"] == "A"

    # lesson artifact written
    lesson_path = iso["academy"] / "lessons" / "d1b1.md"
    assert lesson_path.exists()
    text = lesson_path.read_text()
    assert "The Defender's Map" in text

    # journal entry is growth-tagged
    from levi.growth import journal as gjournal
    entries = [e for e in gjournal.read_entries(limit=50)
               if e.get("kind") == "academy-session"]
    assert entries, "no academy-session journal entry"
    latest = entries[-1]
    assert "growth" in latest["tags"] and "levi-learned" in latest["tags"]
    assert "academy" in latest["tags"]

    # corpus ingested
    stats = aci.corpus_stats()
    assert stats["records"] >= 1
    assert stats["chars"] > 0
    assert stats["path"] == str(iso["corpus"])


def test_single_track_manual_run(iso, no_network):
    # Track C block exercises real LEVI modules hermetically.
    result = rs.run_one_session(2, 3, dry_research=DRY_RESEARCH)
    assert result["track"] == "C"
    assert result["exercise_score"] >= 0.0


def test_track_a_boundary_in_lesson(iso, no_network):
    result = rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    text = (iso["academy"] / "lessons" / "d1b1.md").read_text()
    assert "defensive" in text.lower()
    assert "defensive-only" in text.lower() or "defensive only" in text.lower()
    # No offensive *instruction* content: attack how-tos, bypass guides.
    low = text.lower()
    for banned in ("how to exploit", "to bypass ", "step-by-step attack",
                   "brute forc", "crack the password"):
        assert banned not in low, banned
    assert result["track"] == "A"


# ------------------------------------------------------- corpus ingest
def test_corpus_ingest_idempotent(iso, no_network):
    lesson = "# T\n\n" + ("Defensive analysis paragraph. " * 60)
    r1 = aci.ingest_lesson(1, 1, "A", "T", lesson)
    r2 = aci.ingest_lesson(1, 1, "A", "T", lesson)
    assert r1["added"] >= 1
    assert r2["added"] == 0
    assert r2["skipped_dupes"] == r1["added"]
    assert r1["records"] == r2["records"]


def test_corpus_format_matches_train_loader(iso, no_network, tmp_path):
    lesson = "# Format probe\n\n" + ("Detection engineering notes. " * 60)
    aci.ingest_lesson(3, 2, "B", "Format probe", lesson)

    # Exercise the REAL corpus loader from the training pipeline.
    # train.py needs torch for the model, but load_corpus is pure stdlib:
    # extract that exact function from the real source via ast and run it.
    import ast
    train_src = Path("core/levi/brain/train/train.py").read_text(encoding="utf-8")
    mod = ast.parse(train_src)
    fn_node = next(n for n in mod.body
                   if isinstance(n, ast.FunctionDef) and n.name == "load_corpus")
    ns: dict = {"Path": Path, "json": json}
    exec(compile(ast.Module(body=[fn_node], type_ignores=[]),
                   "train_loader_probe", "exec"), ns)
    text = ns["load_corpus"](iso["corpus"])
    assert "Format probe" in text
    assert "Detection engineering notes." in text


# ---------------------------------------------------------- graduation
def test_graduation_path(iso, no_network):
    # The crucible samples retained concepts: run one session per track first.
    for day, block in ((1, 1), (1, 2), (1, 3)):
        r = rs.run_one_session(day, block, dry_research=DRY_RESEARCH)
        assert r["gate_passed"] is True
    result = rs.run_one_session(30, 4, dry_research=DRY_RESEARCH)
    assert result["track"] == "S"
    assert result["gate_passed"] is True
    g = result["graduation"]
    assert g["verdict"] == "GRADUATED"
    assert set(g["per_track"]) == {"A", "B", "C"}
    assert g["weakest_track"] in ("A", "B", "C")
    assert len(g["post_graduation_focus"]) >= 1
    prog = json.loads((iso["academy"] / "progress.json").read_text())
    assert prog["graduated"] is True
    assert "d30b4" in prog["completed"]
    # retrain launch attempted; torch unavailable here -> honest skip
    assert result["graduation"]["retrain"]["launched"] is False

    from levi.growth import journal as gjournal
    grads = [e for e in gjournal.read_entries(limit=100)
             if e.get("kind") == "academy-graduation"]
    assert grads, "no academy-graduation journal entry"
    assert grads[-1].get("weakest_track") in ("A", "B", "C")


def test_graduation_without_curriculum_is_not_yet(iso, no_network):
    # Jumping straight to session 120 with no retained concepts: the
    # crucible is honest — NOT YET, weakest area named as drill focus.
    result = rs.run_one_session(30, 4, dry_research=DRY_RESEARCH)
    g = result["graduation"]
    assert g["verdict"] == "NOT YET"
    assert set(g["per_track"]) == {"A", "B", "C"}
    assert g["weakest_track"] in ("A", "B", "C")


def test_day_over_30_is_quiet_noop(iso, no_network, capsys):
    assert rs.main(["--day", "31", "--block", "1"]) == 0
    out = capsys.readouterr().out
    assert "nothing to run" in out


def test_next_uncompleted_advances(iso, no_network):
    rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    prog = rs.load_progress()
    assert rs.next_uncompleted(prog) == 2  # day 1, block 2


# ----------------------------------------------------------------- CLI
def test_academy_status_cli(iso, no_network, capsys):
    from levi.cli.main import cmd_academy
    rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    args = types.SimpleNamespace(academy_action="status", day=None, block=None)
    assert cmd_academy(args) == 0
    out = capsys.readouterr().out
    assert "30-day" in out
    assert "brain corpus" in out
    assert "1/120" in out


def test_academy_skills_register():
    from levi.skill.academy_skills import ACADEMY_SKILLS
    ids = [s.id for s in ACADEMY_SKILLS]
    assert "academy_session_brief" in ids
    assert "academy_status_brief" in ids
    assert "academy_teardown_brief" in ids
    assert "academy_detection_advisor" in ids


# ------------------------------------------------- boot-camp gates
def test_mastery_threshold_is_80():
    assert rs.MASTERY_THRESHOLD == 0.80
    assert rs.EXERCISE_THRESHOLD == 0.70


def test_failed_gate_queues_remediation_not_completion(iso, no_network, monkeypatch):
    monkeypatch.setattr(asynth, "synthesize_lesson", lambda *a, **k: "thin")
    result = rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    assert result["gate_passed"] is False
    assert result["mastery_score"] < 0.80
    prog = rs.load_progress()
    # failed gate: NOT completed, NOT ingested, streak reset, remedial queued
    assert "d1b1" not in prog["completed"]
    assert aci.corpus_stats()["records"] == 0
    assert acon.load_registry()["concepts"] == {}
    assert rs.get_streaks(prog)["A"] == {"current": 0, "best": 0}
    pending = prog["pending_remedial"]
    assert pending["day"] == 1 and pending["block"] == 1
    assert pending["attempts"] == 0
    assert len(pending["missed_questions"]) >= 1
    # honest failure journal entry
    from levi.growth import journal as gjournal
    fails = [e for e in gjournal.read_entries(limit=50)
             if e.get("kind") == "academy-session" and "gate-failed" in e.get("tags", [])]
    assert fails, "no honest gate-failed journal entry"
    assert "80%" in fails[-1]["summary"]


def test_remedial_pass_completes_original_gate(iso, no_network, monkeypatch):
    orig_synthesize = asynth.synthesize_lesson
    monkeypatch.setattr(asynth, "synthesize_lesson", lambda *a, **k: "thin")
    r1 = rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    assert r1["gate_passed"] is False
    # restore the real synthesis (not monkeypatch.undo: that would also
    # revert the test's env isolation)
    monkeypatch.setattr(asynth, "synthesize_lesson", orig_synthesize)
    pending = rs.load_progress()["pending_remedial"]
    r2 = rs.run_remedial(pending, dry_research=DRY_RESEARCH)
    assert r2["gate_passed"] is True
    assert r2["attempt"] == 1
    prog = rs.load_progress()
    assert "d1b1" in prog["completed"]
    assert prog["pending_remedial"] is None
    assert rs.get_streaks(prog)["A"] == {"current": 1, "best": 1}
    # the CORRECTED version is what enters durable memory, tagged
    assert len(acon.load_registry()["concepts"]) >= 6
    recs = [json.loads(line) for line in open(str(iso["corpus"]), encoding="utf-8")]
    assert len(recs) >= 1
    assert all(r["mastery"]["remediated"] is True for r in recs)
    assert all(r["mastery"]["mastery_score"] >= 0.8 for r in recs)
    # remedial lesson artifact kept
    assert (iso["academy"] / "lessons" / "d1b1-remedial1.md").exists()
    from levi.growth import journal as gjournal
    kinds = [e.get("kind") for e in gjournal.read_entries(limit=50)]
    assert "academy-remedial" in kinds


def test_remedial_failure_stays_queued(iso, no_network, monkeypatch):
    monkeypatch.setattr(asynth, "synthesize_lesson", lambda *a, **k: "thin")
    monkeypatch.setattr(asynth, "synthesize_remedial_lesson",
                        lambda *a, **k: "thin")
    r1 = rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    assert r1["gate_passed"] is False
    r2 = rs.run_remedial(rs.load_progress()["pending_remedial"],
                         dry_research=DRY_RESEARCH)
    assert r2["gate_passed"] is False
    prog = rs.load_progress()
    assert prog["pending_remedial"]["attempts"] == 1
    assert "d1b1" not in prog["completed"]


def test_main_prefers_pending_remediation(iso, no_network, monkeypatch, capsys):
    prog = rs.load_progress()
    prog["pending_remedial"] = {"day": 1, "block": 1, "track": "A", "n": 1,
                                "attempts": 0}
    rs.save_progress(prog)
    called = {}

    def fake(pending, **kw):
        called["pending"] = pending
        return {"gate_passed": True}

    monkeypatch.setattr(rs, "run_remedial", fake)
    assert rs.main([]) == 0
    assert called["pending"]["day"] == 1
    assert "remediation" in capsys.readouterr().out


def test_streaks_track_passes_and_resets(iso, no_network, monkeypatch):
    r1 = rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    assert r1["gate_passed"] is True
    assert r1["streak"] == {"current": 1, "best": 1}
    monkeypatch.setattr(asynth, "synthesize_lesson", lambda *a, **k: "thin")
    r2 = rs.run_one_session(1, 2, dry_research=DRY_RESEARCH)
    assert r2["gate_passed"] is False
    assert r2["streak"] == {"current": 0, "best": 0}
    prog = rs.load_progress()
    assert prog["streaks"]["A"] == {"current": 1, "best": 1}
    assert prog["streaks"]["B"] == {"current": 0, "best": 0}


def test_corpus_records_carry_mastery_tags(iso, no_network):
    rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    recs = [json.loads(line) for line in open(str(iso["corpus"]), encoding="utf-8")]
    assert recs, "post-mastery ingest produced no records"
    assert all(r.get("mastery", {}).get("mastery_score", 0) >= 0.8 for r in recs)
    assert all(r["mastery"]["remediated"] is False for r in recs)


# ------------------------------------------------- spaced repetition
def test_concept_review_schedule(iso, no_network):
    syl = rs.load_syllabus()
    _, entry = rs.entry_for(syl, 1, 1)
    added = acon.register_session(1, 1, "A", entry, DRY_RESEARCH, 1,
                                  mastery_score=0.9)
    assert added == 6  # 3 objectives + 3 key terms
    assert acon.due_concepts(1) == []  # nothing due before the first review
    due = acon.due_concepts(2)
    assert {c["id"] for c in due} == {
        "AD01B1O1", "AD01B1O2", "AD01B1O3",
        "AD01B1T1", "AD01B1T2", "AD01B1T3"}
    dues = sorted({r["due_session"]
                   for c in acon.load_registry()["concepts"].values()
                   for r in c["reviews"]})
    assert dues == [2, 5, 29, 57]  # next block, next day, day 7, day 14


def test_review_drills_pull_due_concepts(iso, no_network):
    r1 = rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    assert r1["gate_passed"] is True
    assert r1["review"]["reviewed"] == 0  # no prior concepts on session 1
    r2 = rs.run_one_session(1, 2, dry_research=DRY_RESEARCH)
    assert r2["gate_passed"] is True
    assert r2["review"]["reviewed"] >= 1
    # the registry shows session-1 concepts were drilled
    reg = acon.load_registry()["concepts"]
    drilled = [c for c in reg.values() if c["session"] == 1 and c["scores"]]
    assert drilled, "due concepts were not drilled"


def test_retention_score_math(iso, no_network):
    syl = rs.load_syllabus()
    _, entry = rs.entry_for(syl, 1, 1)
    acon.register_session(1, 1, "A", entry, DRY_RESEARCH, 1)
    ids = sorted(acon.load_registry()["concepts"])
    acon.record_review(ids[0], 2, 0.8)
    acon.record_review(ids[1], 2, 0.6)
    stats = acon.retention_stats()
    assert stats["A"]["concepts"] == 6
    assert stats["A"]["reviewed"] == 2
    assert stats["A"]["hit_rate"] == pytest.approx(0.7)
    assert stats["B"]["hit_rate"] == 0.0


def test_forgetting_requeues_and_pulls_strength_down(iso, no_network):
    syl = rs.load_syllabus()
    _, entry = rs.entry_for(syl, 1, 1)
    acon.register_session(1, 1, "A", entry, DRY_RESEARCH, 1)
    cid = sorted(acon.load_registry()["concepts"])[0]
    upd = acon.record_review(cid, 2, 0.1)
    assert upd["forgotten"] is True
    c = acon.load_registry()["concepts"][cid]
    requeues = [r for r in c["reviews"] if r.get("requeue")]
    assert len(requeues) == 1 and requeues[0]["due_session"] == 6
    assert c["strength"] < 0.8


def test_assessment_mode_reviews_more(iso, no_network):
    syl = rs.load_syllabus()
    for day, block, track in ((1, 1, "A"), (1, 2, "B"), (1, 3, "C"),
                              (2, 1, "A"), (2, 2, "B")):
        _, entry = rs.entry_for(syl, day, block)
        acon.register_session(day, block, track, entry, DRY_RESEARCH,
                              rs.day_block_to_n(day, block))
    rep_a = acon.run_reviews(9, assessment=True)
    assert rep_a["assessment"] is True
    assert rep_a["reviewed"] == acon.ASSESSMENT_REVIEWS
    rep_n = acon.run_reviews(9, assessment=False)
    assert rep_n["reviewed"] == acon.MAX_REVIEWS_PER_SESSION


def test_interleaving_in_sparring(iso, no_network):
    for day, block in ((1, 1), (1, 2), (1, 3)):
        r = rs.run_one_session(day, block, dry_research=DRY_RESEARCH)
        assert r["gate_passed"] is True
    r4 = rs.run_one_session(1, 4, dry_research=DRY_RESEARCH)
    assert r4["track"] == "S"
    assert len(r4["interleaved"]) == 2
    reg = acon.load_registry()["concepts"]
    tracks = {reg[cid]["track"] for cid in r4["interleaved"]}
    assert tracks <= {"A", "B", "C"} and tracks, \
        "sparring must interleave cross-track concepts"


def test_status_shows_retention_and_streaks(iso, no_network, capsys):
    from levi.cli.main import cmd_academy
    import types
    rs.run_one_session(1, 1, dry_research=DRY_RESEARCH)
    args = types.SimpleNamespace(academy_action="status", day=None, block=None)
    assert cmd_academy(args) == 0
    out = capsys.readouterr().out
    assert "LEVI Boot Camp" in out
    assert "retention" in out
    assert "streak" in out
    assert "1/120" in out
