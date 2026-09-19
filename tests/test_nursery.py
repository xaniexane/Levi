"""Nursery tests — home-scoped, deterministic, no network, no subprocess."""

from __future__ import annotations

import datetime
import json
import os

import pytest

from levi.memory.store import MemoryStore
from levi.memory.types import MemoryType


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Isolate the nursery home; tiny cohort cap; sync off by default."""
    monkeypatch.setenv("LEVI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LEVI_NURSERY_CAP", "4")
    monkeypatch.setenv("LEVI_NURSERY_SYNC", "0")
    return tmp_path / "home"


def _import_nursery():
    import levi.nursery as n

    return n


def _backdate_first_entry(trainee_id, days=2):
    from levi.nursery.training import trainee_env
    from levi.growth import journal as J

    with trainee_env(trainee_id):
        jp = J.journal_path()
        lines = [ln for ln in jp.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert lines, "no journal entries to backdate"
        old = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        rec = json.loads(lines[0])
        rec["ts"] = old
        lines[0] = json.dumps(rec)
        jp.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _raise_trainee(nursery, trainee_id):
    """Run the standard raising program (deterministic, seed=False)."""
    nursery.run_training_program(trainee_id, rounds=5)
    _backdate_first_entry(trainee_id)


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------


def test_boundaries_hold(home):
    n = _import_nursery()
    n.assert_boundaries()  # raises ImportError on violation


def test_boundary_scanner_catches_forbidden_imports(tmp_path):
    from levi.nursery import _scan_file

    bad = tmp_path / "bad.py"
    bad.write_text("import subprocess\nimport levi.cybrus.money\n", encoding="utf-8")
    violations = _scan_file(bad)
    assert len(violations) == 2

    bad2 = tmp_path / "bad2.py"
    bad2.write_text("import os\nos.system('x')\n", encoding="utf-8")
    assert _scan_file(bad2)

    good = tmp_path / "good.py"
    good.write_text("import os\nimport json\n", encoding="utf-8")
    assert _scan_file(good) == []


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


def test_enroll_and_cap(home, monkeypatch):
    n = _import_nursery()
    t1 = n.enroll_trainee("Ada", "ai", seed=False)
    assert t1.track == "ai" and t1.status == "enrolled"
    with pytest.raises(ValueError):
        n.enroll_trainee("Bob", "bogus", seed=False)
    monkeypatch.setenv("LEVI_NURSERY_CAP", "1")
    with pytest.raises(ValueError):
        n.enroll_trainee("Cara", "si", seed=False)
    assert len(n.list_trainees()) == 1


# ---------------------------------------------------------------------------
# Training cycles
# ---------------------------------------------------------------------------


def test_cycle_produces_learnings(home):
    n = _import_nursery()
    t = n.enroll_trainee("Ada", "ai", seed=False)
    rep = n.run_training_program(t.id, rounds=2)
    assert rep["cycles"] >= 1
    assert rep["totals"]["accepted"] >= 1
    st = n.trainee_stats(t.id)
    assert st["stats"]["learnings"] >= 1
    assert st["status"] == "training"
    assert st["stage"] in ("sprouting", "curious", "growing", "maturing")


def test_trainee_homes_are_isolated(home):
    n = _import_nursery()
    a = n.enroll_trainee("Ada", "ai", seed=False)
    b = n.enroll_trainee("Bob", "si", seed=False)
    n.run_trainee_cycle(a.id, max_drills=0)
    from levi.nursery.training import trainee_journal

    assert len(trainee_journal(a.id, limit=100)) >= 1
    assert trainee_journal(b.id, limit=100) == []


# ---------------------------------------------------------------------------
# Seeding — seed facts, earn judgment
# ---------------------------------------------------------------------------


def _fake_levi_store(tmp_path):
    store = MemoryStore(data_dir=tmp_path / "levi-memory")
    store.add(
        MemoryType.SEMANTIC,
        "sort_lines keeps the header row first when asked",
        tags=["growth", "levi-learned", "fact"],
        metadata={"confidence": 0.8},
    )
    store.add(
        MemoryType.PROCEDURAL,
        "verify every task result before accepting it into the ledger",
        tags=["growth", "levi-learned", "procedural"],
        metadata={"confidence": 0.7},
    )
    store.add(
        MemoryType.SEMANTIC,
        "when corrected, adopt the corrected interpretation going forward",
        tags=["growth", "levi-learned", "correction"],
        metadata={"confidence": 0.9},
    )
    store.add(
        MemoryType.PREFERENCE,
        "Chauncey prefers terse replies with receipts first",
        tags=["growth", "levi-learned", "preference"],
        metadata={"confidence": 0.9},
    )
    store.add(
        MemoryType.SEMANTIC,
        "the charter requires plan preview permission execute verify receipt",
        tags=["growth", "levi-learned", "fact"],
        metadata={"confidence": 0.9},
    )
    store.add(
        MemoryType.SEMANTIC,
        "I am Levi, a local synthetic intelligence",
        tags=["growth", "levi-learned", "fact"],
        metadata={"confidence": 0.9},
    )
    return store


def test_seed_filters_by_kind_and_rails(home, tmp_path):
    n = _import_nursery()
    from levi.nursery.seed import collect_seed_records, seed_trainee

    levi_store = _fake_levi_store(tmp_path)
    accepted, denied = collect_seed_records(levi_store)
    kinds = sorted(r["kind"] for r in accepted)
    assert kinds == ["fact", "procedural"], kinds  # corrections/preferences denied
    deny_texts = " ".join(d.get("deny_reason", "") for d in denied)
    assert "charter" in deny_texts or any("charter" in d.get("deny_reason", "") for d in denied)
    assert any("identity" in d.get("deny_reason", "") for d in denied)

    t = n.enroll_trainee("Ada", "ai", seed=False)
    report = seed_trainee(t.id, levi_store=levi_store)
    assert report["accepted"] == 2
    st = n.trainee_stats(t.id)
    # Seeded learnings do NOT inflate the trainee's self-taught counters.
    assert st["stats"]["learnings"] == 0
    assert st["stats"]["seeded_learnings"] == 2


def test_sync_is_idempotent(home, tmp_path):
    n = _import_nursery()
    from levi.nursery.seed import sync_trainee

    levi_store = _fake_levi_store(tmp_path)
    t = n.enroll_trainee("Ada", "ai", seed=False)
    first = sync_trainee(t.id, levi_store=levi_store)
    assert first["new_records"] == 2
    second = sync_trainee(t.id, levi_store=levi_store)
    assert second["new_records"] == 0
    assert second["total_ingested"] == 2


def test_sync_picks_up_new_learnings(home, tmp_path):
    n = _import_nursery()
    from levi.nursery.seed import sync_trainee

    levi_store = _fake_levi_store(tmp_path)
    t = n.enroll_trainee("Ada", "ai", seed=False)
    sync_trainee(t.id, levi_store=levi_store)
    levi_store.add(
        MemoryType.SEMANTIC,
        "redact_emails replaces every email-like token with [REDACTED]",
        tags=["growth", "levi-learned", "fact"],
        metadata={"confidence": 0.8},
    )
    again = sync_trainee(t.id, levi_store=levi_store)
    assert again["new_records"] == 1
    assert again["total_ingested"] == 3


# ---------------------------------------------------------------------------
# Exam + gates + graduation
# ---------------------------------------------------------------------------


def test_exam_passes_after_raising(home):
    n = _import_nursery()
    t = n.enroll_trainee("Ada", "ai", seed=False)
    n.run_training_program(t.id, rounds=5)
    record = n.run_exam(t.id)
    assert record["passed"] is True
    assert all(p["passed"] for p in record["probes"])
    assert len(record["probes"]) == 5


def test_gates_and_graduation(home):
    n = _import_nursery()
    from levi.nursery.gates import GateFailure

    t = n.enroll_trainee("Ada", "ai", seed=False)
    evaluation = n.evaluate_gates(t.id)
    assert evaluation["met_all"] is False  # fresh trainee is not ready

    with pytest.raises(GateFailure):  # no anonymous graduation
        n.graduate(t.id, "")
    with pytest.raises(GateFailure):  # gates unmet
        n.graduate(t.id, "chauncey")

    _raise_trainee(n, t.id)
    record = n.run_exam(t.id)
    assert record["passed"] is True
    evaluation = n.evaluate_gates(t.id)
    assert evaluation["met_all"] is False  # human approval still pending
    assert [g["name"] for g in evaluation["gates"] if not g["met"]] == ["human_approval"]

    result = n.graduate(t.id, "chauncey")
    assert result["met_all"] is True
    assert result["approved_by"] == "chauncey"
    assert n.get_trainee(t.id).status == "graduated"


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def test_router_refusals(home):
    n = _import_nursery()
    from levi.nursery.router import Refusal

    t = n.enroll_trainee("Ada", "ai", seed=False)
    with pytest.raises(Refusal):  # not graduated
        n.assign(t.id, "sort_lines", {"lines": ["b", "a"]})
    for kind in ("money", "apply", "shell", "network", "nope"):
        with pytest.raises(Refusal):
            from levi.nursery.router import execute_task

            execute_task(kind, {})


def test_router_assign_and_demotion(home, monkeypatch):
    n = _import_nursery()
    from levi.nursery.router import VerificationFailure, read_ledger
    from levi.nursery.trainee import get_trainee, update_trainee

    t = n.enroll_trainee("Ada", "ai", seed=False)
    trainee = get_trainee(t.id)
    trainee.status = "graduated"  # supervised promotion for the test
    update_trainee(trainee)

    receipt = n.assign(t.id, "sort_lines", {"lines": ["b", "a", "c"]})
    assert receipt["accepted"] is True
    assert receipt["verified_result"] == {"sorted_lines": ["a", "b", "c"]}

    # Three consecutive verification failures demote back to training.
    for _ in range(3):
        try:
            n.assign(t.id, "sort_lines", {"lines": "not-a-list"})
        except VerificationFailure:
            pass
    assert get_trainee(t.id).status == "training"
    ledger = read_ledger(t.id, limit=10)
    assert any(r["accepted"] for r in ledger)
    assert any(not r["accepted"] for r in ledger)


def test_task_templates_round_trip(home):
    from levi.nursery.tasks import TASKS

    fixtures = {
        "sort_lines": {"lines": ["Name", "delta", "Alpha"], "keep_header": True},
        "extract_fields": {"text": "Name: Ada\nRole: trainee", "fields": ["Name", "Role"]},
        "word_count_report": {"text": "alpha beta alpha\n"},
        "redact_emails": {"text": "mail jane@example.com now"},
    }
    assert set(TASKS) == set(fixtures)
    for kind, payload in fixtures.items():
        _name, _desc, executor, verifier = TASKS[kind]
        result = executor(dict(payload))
        ok, _detail = verifier(result, payload)
        assert ok, kind
        # Tampered results are rejected.
        bad = dict(result)
        first_key = next(iter(bad))
        bad[first_key] = "tampered"
        ok2, _ = verifier(bad, payload)
        assert not ok2, kind


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_tasks_command(home):
    from levi.nursery.__main__ import main

    assert main(["tasks"]) == 0
    assert main(["enroll", "Ada", "--track", "si", "--no-seed"]) == 0
    assert main(["status"]) == 0
