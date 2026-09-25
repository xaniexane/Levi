"""Tests for the rebuilt Quetta-Pan: v10.0 mechanics + REIM/RIEM loop.

Hermetic: every store (backups, history, compost, genome) lives under
tmp_path. Loop invariants under test:
1. no write without backup | 2. no apply without evaluation |
3. failures always composted | 4. genome consulted before generation |
5. dry-run default | 6. fail-closed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from levi.quetta_pan import (
    QuettaPanEngine,
    ReimCompost,
    RiemGenome,
    context_key_for,
    derive_inverse_lesson,
)
from levi.quetta_pan.evaluate import evaluate_mutation


def _mk(tmp_path: Path, **kw) -> QuettaPanEngine:
    proj = tmp_path / "proj"
    proj.mkdir(exist_ok=True)
    store = tmp_path / "store"
    store.mkdir(exist_ok=True)
    return QuettaPanEngine(project_root=proj, store_dir=store, **kw)


def _write(proj: Path, name: str, content: str) -> Path:
    p = proj / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ---- scanner ---------------------------------------------------------------


def test_scanner_finds_and_excludes(tmp_path):
    eng = _mk(tmp_path)
    proj = eng.project_root
    _write(proj, "a.py", "x = 1\n")
    _write(proj, "sub/b.ts", "let x = 1;\n")
    _write(proj, "node_modules/x.py", "x = 1\n")
    _write(proj, ".git/y.py", "x = 1\n")
    _write(proj, "dist/z.js", "x = 1;\n")
    found = {p.name for p in eng.scan()}
    assert found == {"a.py", "b.ts"}


# ---- v10.0 heuristics carried forward ----------------------------------------

PY_SMELLY = (
    "def f(items=[]):\n"
    "    out = []\n"
    "    for i in items:\n"
    "        out.append(i)\n"
    "    try:\n"
    "        return out\n"
    "    except:\n"
    "        return []\n"
    "msg = 'hello %s' % 'world'\n"
    "x = 'a'.format()\n"
)

TS_SMELLY = (
    "var count = 0;\n"
    "if (count == 0) { console.log('zero'); }\n"
    "function Cmp() { useEffect(() => { fetch(); }); }\n"
    "let data: any = {};\n"
)


def test_python_heuristics_all_four_rules(tmp_path):
    eng = _mk(tmp_path)
    ids = {s["id"] for s in eng.python_ast_heuristics(PY_SMELLY, ".py")}
    assert ids == {
        "PY_FSTRING",
        "PY_BARE_EXCEPT",
        "PY_LIST_COMP",
        "PY_MUTABLE_DEFAULTS",
    }


def test_typescript_heuristics_rules(tmp_path):
    eng = _mk(tmp_path)
    ids = {s["id"] for s in eng.typescript_react_heuristics(TS_SMELLY, ".ts")}
    assert {
        "TS_VAR_USAGE",
        "TS_LOOSE_EQUALITY",
        "TS_EFFECT_LOOP",
        "TS_LOOSE_TYPING",
        "TS_CONSOLE_POLLUTION",
    } <= ids


def test_projections_ten_tiers_match_v10(tmp_path):
    eng = _mk(tmp_path)
    projs = eng.generate_forward_projections(Path("x.py"))
    assert len(projs) == 10
    assert projs[0]["description"] == "Syntactic Safety Gates"
    assert projs[-1]["description"] == "Autogenous Self-Upgrading Core"
    assert [p["risk_level"] for p in projs] == [
        0.05,
        0.10,
        0.18,
        0.25,
        0.35,
        0.45,
        0.55,
        0.65,
        0.75,
        0.88,
    ]


# ---- invariant 5: dry-run default ---------------------------------------------


def test_dry_run_writes_nothing(tmp_path):
    eng = _mk(tmp_path)
    target = _write(eng.project_root, "a.py", PY_SMELLY)
    before = target.read_text(encoding="utf-8")
    stats = eng.run(dry_run=True, approve=lambda s: "y")
    assert target.read_text(encoding="utf-8") == before
    assert stats["applied"] == 0
    assert list(eng.backup_dir.glob("*.bak")) == []
    assert eng.history["approvals"] == []


# ---- invariants 1+2: backup before write, evaluation gates apply ---------------


def test_apply_creates_backup_and_records_genome_win(tmp_path):
    eng = _mk(tmp_path)
    target = _write(eng.project_root, "a.py", PY_SMELLY)
    original = target.read_text(encoding="utf-8")
    suggestion = eng.suggest_upgrades(target)
    assert suggestion["has_changes"]
    result = eng.apply_suggestion(suggestion)
    assert result.ok
    # invariant 1: backup of the pre-image exists
    baks = list(eng.backup_dir.glob("a.py_*.bak"))
    assert len(baks) == 1
    assert baks[0].read_text(encoding="utf-8") == original
    # file now carries the safe fix
    assert "except Exception:" in target.read_text(encoding="utf-8")
    # success folded into the genome
    assert eng.genome.consult("PY_BARE_EXCEPT", "py") in ("boost", "unknown")
    assert eng.history["approvals"]


# ---- invariants 2+3+6: failure -> rollback + compost, fail-closed ---------------


def test_failed_mutation_rolls_back_and_composts(tmp_path):
    eng = _mk(tmp_path)
    target = _write(eng.project_root, "a.py", "x = 1\n")
    original = target.read_text(encoding="utf-8")
    suggestion = eng.suggest_upgrades(target)
    # force a broken mutation through the guarded path
    suggestion = dict(suggestion)
    suggestion["new_content"] = "def broken(:\n"
    suggestion["suggestions"] = [
        {"id": "FORCED", "title": "forced", "desc": "test", "severity": "error"}
    ]
    suggestion["fix_ids"] = ["FORCED"]
    result = eng.apply_suggestion(suggestion, mutation_id="qp-test-1")
    assert not result.ok
    assert "parse" in result.failure_reason
    # fail-closed: pre-image restored
    assert target.read_text(encoding="utf-8") == original
    # invariant 3: composted, never dropped
    assert eng.compost.count() == 1
    entry = eng.compost.recent(1)[0]
    for key in (
        "mutation_id",
        "rule_id",
        "file",
        "context",
        "tried_what",
        "failed_why",
        "inverse_lesson",
    ):
        assert entry[key], f"missing {key}"
    assert entry["mutation_id"] == "qp-test-1"
    assert "instead:" in entry["inverse_lesson"]
    # compost folded into the genome
    slot = eng.genome.stats("FORCED", "py")
    assert slot["failures"] == 1
    assert eng.history["rejections"]


def test_evaluate_mutation_parse_failure():
    res = evaluate_mutation("x.py", "x = 1\n", "def broken(:\n")
    assert not res.ok and not res.parse_ok
    assert "parse" in res.failure_reason


def test_evaluate_mutation_test_command_failure(tmp_path):
    res = evaluate_mutation(tmp_path / "x.py", "x = 1\n", "x = 2\n", test_cmd=["false"])
    assert not res.ok
    assert res.parse_ok and res.test_ok is False
    assert "test command" in res.failure_reason


# ---- invariant 4: genome consulted before generation ---------------------------


def test_genome_suppresses_repeated_failures(tmp_path):
    eng = _mk(tmp_path)
    target = _write(eng.project_root, "a.py", "try:\n    f()\nexcept:\n    pass\n")
    eng.genome.learn("PY_BARE_EXCEPT", "py", False, "lesson one")
    eng.genome.learn("PY_BARE_EXCEPT", "py", False, "lesson two")
    assert eng.genome.consult("PY_BARE_EXCEPT", "py") == "suppress"
    suggestion = eng.suggest_upgrades(target)
    ids = {s["id"] for s in suggestion["suggestions"]}
    assert "PY_BARE_EXCEPT" not in ids
    withheld = {s["id"] for s in suggestion["suppressed_by_genome"]}
    assert "PY_BARE_EXCEPT" in withheld
    reason = suggestion["suppressed_by_genome"][0]["suppressed_reason"]
    assert "genome" in reason and "2/2" in reason
    # the withheld rule's fix is not applied either
    assert "except Exception:" not in suggestion["new_content"]


def test_genome_boosts_recorded_success(tmp_path):
    eng = _mk(tmp_path)
    target = _write(eng.project_root, "a.py", "try:\n    f()\nexcept:\n    pass\n")
    eng.genome.record_success("PY_BARE_EXCEPT", "py", "clean apply before")
    suggestion = eng.suggest_upgrades(target)
    marked = {s["id"]: s["genome"] for s in suggestion["suggestions"]}
    assert marked.get("PY_BARE_EXCEPT") == "boost"


def test_riem_consult_policy_matrix(tmp_path):
    g = RiemGenome(tmp_path / "g.json")
    assert g.consult("R", "py") == "unknown"
    g.learn("R", "py", False, "bad")
    assert g.consult("R", "py") == "unknown"  # one failure: not yet a pattern
    g.learn("R", "py", False, "bad again")
    assert g.consult("R", "py") == "suppress"
    g2 = RiemGenome(tmp_path / "g2.json")
    g2.record_success("S", "py", "good")
    assert g2.consult("S", "py") == "boost"


# ---- REIM: inverse lessons -----------------------------------------------------


def test_reim_inverse_lesson_shape_and_validation():
    failure = {
        "mutation_id": "m1",
        "rule_id": "PY_BARE_EXCEPT",
        "file": "a.py",
        "context": "py",
        "tried_what": "bare-except fix",
        "failed_why": "parse check failed: python parse failed",
    }
    lesson = derive_inverse_lesson(failure)
    assert "Tried bare-except fix on a.py" in lesson
    assert "instead:" in lesson
    assert "do not apply PY_BARE_EXCEPT in context py" in lesson
    with pytest.raises(ValueError):
        derive_inverse_lesson({"mutation_id": "m1"})  # never drops silently


def test_reim_compost_roundtrip(tmp_path):
    compost = ReimCompost(tmp_path / "c.jsonl")
    entry = compost.compost(
        {
            "mutation_id": "m1",
            "rule_id": "R",
            "file": "a.py",
            "context": "py",
            "tried_what": "t",
            "failed_why": "test command failed: exited 1",
        }
    )
    assert entry["failure_class"] == "test"
    assert compost.count() == 1
    assert list(compost.lessons(rule_id="R"))[0]["mutation_id"] == "m1"
    assert list(compost.lessons(rule_id="OTHER")) == []


# ---- run() approval flow --------------------------------------------------------


def test_run_approval_flow_respects_answers(tmp_path):
    eng = _mk(tmp_path)
    t1 = _write(eng.project_root, "a.py", PY_SMELLY)
    t2 = _write(eng.project_root, "b.py", PY_SMELLY)
    calls = []

    def approve(suggestion):
        calls.append(suggestion["file"])
        return "n" if len(calls) == 1 else "q"

    stats = eng.run(dry_run=False, approve=approve)
    assert stats["applied"] == 0
    assert "except Exception:" not in t1.read_text(encoding="utf-8")
    assert "except Exception:" not in t2.read_text(encoding="utf-8")
    # 'q' on the second file stopped the run: exactly two prompts
    assert len(calls) == 2


def test_run_applies_on_yes(tmp_path):
    eng = _mk(tmp_path)
    target = _write(eng.project_root, "a.py", PY_SMELLY)
    stats = eng.run(dry_run=False, approve=lambda s: "y")
    assert stats["applied"] == 1
    assert "except Exception:" in target.read_text(encoding="utf-8")


def test_context_key_for():
    assert context_key_for("x.py") == "py"
    assert context_key_for("x.tsx") == "js-ts"
    assert context_key_for("x.js") == "js-ts"


def test_failed_bundle_learns_per_rule(tmp_path):
    # Coherence: consultation is per rule, so a failed bundle must teach
    # each member rule — otherwise suppression could never trigger.
    eng = _mk(tmp_path)
    target = _write(eng.project_root, "a.py", "x = 1\n")
    suggestion = eng.suggest_upgrades(target)
    suggestion = dict(suggestion)
    suggestion["new_content"] = "def broken(:\n"
    suggestion["suggestions"] = [
        {"id": "R1", "title": "r1", "desc": "d", "severity": "error"},
        {"id": "R2", "title": "r2", "desc": "d", "severity": "error"},
    ]
    suggestion["fix_ids"] = ["R1", "R2"]
    result = eng.apply_suggestion(suggestion)
    assert not result.ok
    assert eng.genome.stats("R1", "py")["failures"] == 1
    assert eng.genome.stats("R2", "py")["failures"] == 1
    assert eng.genome.stats("R1+R2", "py")["failures"] == 1


def test_success_bundle_learns_per_rule(tmp_path):
    eng = _mk(tmp_path)
    target = _write(eng.project_root, "a.py", PY_SMELLY)
    suggestion = eng.suggest_upgrades(target)
    result = eng.apply_suggestion(suggestion)
    assert result.ok
    for rid in [s["id"] for s in suggestion["suggestions"]]:
        assert eng.genome.stats(rid, "py")["successes"] == 1
