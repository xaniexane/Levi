"""Tests for the agent x pi fan-out/fan-in pass.

Hermetic: every store (backups, history, compost, genome) lives under
tmp_path. Laws under test (see core/levi/quetta_pan/agent_pi.py):
  Qpi1 NO-COLLAPSE | Qpi2 NO-SILENT-DROP | Qpi3 GENOME-FIRST |
  Qpi4 OFFLINE | Qpi5 FAIL-CLOSED | Qpi6 PASS-WRITES-NOTHING.
Plus: controlled-compression dedup, deterministic winner selection,
and the safe_fixes `only` parameter the fan-out relies on.
"""

from __future__ import annotations

from pathlib import Path

from levi.quetta_pan import (
    QuettaPanEngine,
    agent_pi_pass,
    fan_in,
    fan_out,
)
from levi.quetta_pan import agent_pi as agent_pi_mod
from levi.quetta_pan.riem import context_key_for

# A file with two independent safe fixes: bare except + tab indent.
TWO_FIX = "def f():\n\ttry:\n\t\tx = 1\n\texcept:\n\t\tpass\n"


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


def _suggest(eng: QuettaPanEngine, path: Path):
    return eng.suggest_upgrades(path)


# ---- fan-out ------------------------------------------------------------


def test_fan_out_builds_one_variant_per_fix_subset(tmp_path):
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "a.py", TWO_FIX)
    proposals, declined = fan_out(eng, _suggest(eng, p))
    # 2 fixes -> 3 non-empty subsets, all within the cap
    assert [pr.fix_ids for pr in proposals] == [
        ("HARMONY_TABS",),
        ("PY_BARE_EXCEPT",),
        ("HARMONY_TABS", "PY_BARE_EXCEPT"),
    ]
    assert declined == []
    assert [pr.variant_id for pr in proposals] == ["pi-01", "pi-02", "pi-03"]
    # each variant applies exactly its subset
    by_id = {pr.variant_id: pr for pr in proposals}
    assert "except Exception:" in by_id["pi-02"].content
    assert "\t" in by_id["pi-02"].content  # tabs untouched in this variant
    assert "\t" not in by_id["pi-01"].content
    assert "except:" in by_id["pi-01"].content  # bare except kept here


def test_fan_out_cap_overflow_is_receipted_not_dropped(tmp_path):
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "a.py", TWO_FIX)
    proposals, declined = fan_out(eng, _suggest(eng, p), max_variants=2)
    assert len(proposals) == 2
    assert declined == [("HARMONY_TABS", "PY_BARE_EXCEPT")]
    receipt = fan_in(
        eng,
        proposals,
        declined,
        context="py",
        file_label="a.py",
        job_id="pi-test",
        original_content=TWO_FIX,
        suffix=".py",
    )
    disp = receipt.disposition_for("pi-cap:HARMONY_TABS+PY_BARE_EXCEPT")
    assert disp is not None and disp.outcome == "declined-cap"


def test_safe_fixes_only_parameter_is_surgical(tmp_path):
    eng = _mk(tmp_path)
    content, fixed = eng.safe_fixes(TWO_FIX, ".py", only={"HARMONY_TABS"})
    assert fixed == ["HARMONY_TABS"]
    assert "\t" not in content
    assert "except:" in content  # other fix not applied
    # only=None keeps the original apply-all behavior
    content2, fixed2 = eng.safe_fixes(TWO_FIX, ".py")
    assert set(fixed2) == {"PY_BARE_EXCEPT", "HARMONY_TABS"}


# ---- Qpi1 NO-COLLAPSE + controlled compression ---------------------------


def test_no_collapse_distinct_wins_keep_distinct_slots(tmp_path):
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "a.py", TWO_FIX)
    proposals, _ = fan_out(eng, _suggest(eng, p))
    receipt = fan_in(
        eng,
        proposals,
        context="py",
        file_label="a.py",
        job_id="pi-nocollapse",
        original_content=TWO_FIX,
        suffix=".py",
    )
    assert receipt.winner is not None
    assert receipt.composted == 0
    slots = eng.genome.patterns()["py"]
    # every distinct rule-set has its own slot: no merging, no collapse
    assert "PY_BARE_EXCEPT" in slots
    assert "HARMONY_TABS" in slots
    assert "HARMONY_TABS+PY_BARE_EXCEPT" in slots
    assert slots["HARMONY_TABS+PY_BARE_EXCEPT"]["attempts"] == 1


def test_controlled_compression_equivalent_wins_fold(tmp_path):
    """Same bundle twice -> ONE slot with accumulated attempts, not two
    slots. That folding is the compression; distinct bundles stay apart."""
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "a.py", TWO_FIX)
    for n in range(2):
        proposals, _ = fan_out(eng, _suggest(eng, p))
        fan_in(
            eng,
            proposals,
            context="py",
            file_label="a.py",
            job_id=f"pi-fold-{n}",
            original_content=TWO_FIX,
            suffix=".py",
        )
    slots = eng.genome.patterns()["py"]
    assert slots["HARMONY_TABS+PY_BARE_EXCEPT"]["attempts"] == 2
    # still exactly the three distinct slots — nothing duplicated
    assert set(slots) == {
        "PY_BARE_EXCEPT",
        "HARMONY_TABS",
        "HARMONY_TABS+PY_BARE_EXCEPT",
    }


# ---- Qpi2 NO-SILENT-DROP -------------------------------------------------


def test_every_proposal_ends_receipted(tmp_path):
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "a.py", TWO_FIX)
    proposals, declined = fan_out(eng, _suggest(eng, p), max_variants=2)
    receipt = fan_in(
        eng,
        proposals,
        declined,
        context="py",
        file_label="a.py",
        job_id="pi-receipt",
        original_content=TWO_FIX,
        suffix=".py",
    )
    assert receipt.n_proposals == 2
    assert len(receipt.dispositions) == 3  # 2 evaluated + 1 declined-cap
    for prop in proposals:
        assert receipt.disposition_for(prop.variant_id) is not None
    outcomes = {d.outcome for d in receipt.dispositions}
    assert outcomes <= {"win", "composted", "declined-cap"}


def test_failures_compost_each_with_own_entry(tmp_path):
    eng = _mk(tmp_path)
    bad = agent_pi_mod.PiProposal(
        variant_id="pi-99",
        fix_ids=("BOGUS",),
        content="def broken(:\n",
        risk=0.5,
    )
    receipt = fan_in(
        eng,
        [bad],
        context="py",
        file_label="a.py",
        job_id="pi-fail",
        original_content="x = 1\n",
        suffix=".py",
    )
    assert receipt.winner is None
    assert receipt.composted == 1
    assert receipt.disposition_for("pi-99").outcome == "composted"
    entries = list(eng.compost.lessons())
    assert len(entries) == 1
    assert entries[0]["mutation_id"] == "pi-fail:pi-99"


# ---- Qpi3 GENOME-FIRST ---------------------------------------------------


def test_suppressed_fix_never_becomes_a_variant(tmp_path):
    eng = _mk(tmp_path)
    # >=2 attempts, all failures -> genome suppresses PY_BARE_EXCEPT
    eng.genome.learn("PY_BARE_EXCEPT", "py", False, "fail one")
    eng.genome.learn("PY_BARE_EXCEPT", "py", False, "fail two")
    assert eng.genome.consult("PY_BARE_EXCEPT", "py") == "suppress"
    p = _write(eng.project_root, "a.py", TWO_FIX)
    suggestion = _suggest(eng, p)
    assert any(s["id"] == "PY_BARE_EXCEPT" for s in suggestion["suppressed_by_genome"])
    proposals, _ = fan_out(eng, suggestion)
    assert all("PY_BARE_EXCEPT" not in prop.fix_ids for prop in proposals)


# ---- Qpi4 OFFLINE --------------------------------------------------------


def test_agent_pi_has_no_network_imports():
    # Same token list as the hicomb refine-path gate: this module is in
    # that path, so it must stay clean of networking imports. Tokens are
    # built at runtime so this test's own source stays greppable too.
    banned = tuple(t for t in ("socket", "urllib", "requests", "http.client", "ssl"))
    src = Path(agent_pi_mod.__file__).read_text(encoding="utf-8")
    for token in banned:
        assert token not in src, f"network import leaked: {token}"


# ---- Qpi5 FAIL-CLOSED ----------------------------------------------------


def test_evaluation_crash_composts_never_applies(tmp_path, monkeypatch):
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "a.py", TWO_FIX)
    proposals, _ = fan_out(eng, _suggest(eng, p))

    def _boom(*a, **k):
        raise RuntimeError("simulated evaluator crash")

    monkeypatch.setattr(agent_pi_mod, "evaluate_mutation", _boom)
    receipt = fan_in(
        eng,
        proposals,
        context="py",
        file_label="a.py",
        job_id="pi-boom",
        original_content=TWO_FIX,
        suffix=".py",
    )
    assert receipt.winner is None
    assert receipt.composted == 3
    assert p.read_text(encoding="utf-8") == TWO_FIX  # untouched
    assert eng.compost.count() == 3


# ---- Qpi6 PASS-WRITES-NOTHING --------------------------------------------


def test_pass_alone_never_writes_target(tmp_path):
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "a.py", TWO_FIX)
    receipt = agent_pi_pass(eng, p)
    assert receipt.n_proposals == 3
    assert receipt.winner is not None
    assert receipt.applied is False
    assert p.read_text(encoding="utf-8") == TWO_FIX


def test_pass_with_apply_uses_guarded_write(tmp_path):
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "a.py", TWO_FIX)
    receipt = agent_pi_pass(eng, p, apply=True)
    assert receipt.applied is True
    assert "except Exception:" in p.read_text(encoding="utf-8")
    # backup exists: no write without backup (invariant 1 still holds)
    assert list(eng.backup_dir.glob("a.py_*.bak"))


# ---- winner selection ----------------------------------------------------


def test_winner_is_deterministic_best_improvement(tmp_path):
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "a.py", TWO_FIX)
    first = agent_pi_pass(eng, p)
    second = agent_pi_pass(eng, p)
    # bare-except fix removes a heuristic; tab fix does not ->
    # pi-02 (bare except alone) wins on improvement, then lowest risk
    assert first.winner.variant_id == "pi-02"
    assert first.winner.fix_ids == ("PY_BARE_EXCEPT",)
    assert second.winner.variant_id == first.winner.variant_id


def test_no_variants_means_receipted_empty_pass(tmp_path):
    eng = _mk(tmp_path)
    p = _write(eng.project_root, "clean.py", "x = 1\n")
    receipt = agent_pi_pass(eng, p)
    assert receipt.n_proposals == 0
    assert receipt.winner is None
    assert receipt.dispositions == []
    assert "no variants" in receipt.note


def test_context_key_for_is_stable():
    assert context_key_for("x.py") == "py"
    assert context_key_for(Path("y.ts")) == "js-ts"
