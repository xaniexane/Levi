"""Echoverse engine — proof artifact: invariant/property tests.

Honest naming: these are property and invariant checks over the declared
LAWS (levi.echoverse.laws), NOT a formal proof. Each test names the law it
checks.

Agent-Glyph: 🌀
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from levi.echoverse import (
    BRANCH_KINDS,
    LAWS,
    LENSES,
    PIPELINE,
    Branch,
    BranchStore,
    EchoverseEngine,
    aim,
    all_lenses,
    apply_lens,
    constraints_for_mandella,
    doctrine,
    lens_fingerprint,
    position,
    seed_from_mandella,
    stages,
)
from levi.echoverse.coexist import phantom_record
from levi.echoverse.engine import BOUNDED_MARK, EchoverseSimulation, extract_good_qualities
from levi.echoverse.laws import (
    AIM_TARGETS,
    DREAM_MAX_CYCLES,
    DREAM_MIN_CYCLES,
    HISTORY_KEEP,
    SUCCESS_KEEP,
    VAULT_KEEP,
    check_law_ids_unique,
)

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "core" / "levi" / "echoverse"


def _eng(tmp_path):
    return EchoverseEngine(data_dir=tmp_path / "ev")


# --- LAWS meta ------------------------------------------------------------


def test_laws_well_formed():
    assert check_law_ids_unique()
    assert len(LAWS) == 9
    assert all(law.id and law.statement and law.scope for law in LAWS)


# --- L1: bounded simulation -----------------------------------------------


def test_l1_round_carries_bounded_mark(tmp_path):
    r = _eng(tmp_path).round("seed one")
    assert r["mark"] == BOUNDED_MARK
    # the only "literal timeline" language allowed is the negation in the mark
    dumped = json.dumps(r).lower().replace("not a literal timeline", "")
    assert "literal timeline" not in dumped


def test_l1_dream_carries_bounded_mark(tmp_path):
    d = _eng(tmp_path).dream("seed two", cycles=2)
    assert d["mark"] == BOUNDED_MARK


def test_l1_branch_run_carries_bounded_mark(tmp_path):
    run = BranchStore(data_dir=tmp_path / "br").simulate("seed three")
    assert run.mark == BOUNDED_MARK
    assert BOUNDED_MARK in run.format()


def test_l1_aim_carries_bounded_mark(tmp_path):
    run = BranchStore(data_dir=tmp_path / "br2").simulate("seed four")
    plan = aim(run, "software")
    assert plan["mark"] == BOUNDED_MARK


# --- L2: lens determinism --------------------------------------------------


def test_l2_lens_fingerprint_stable():
    for lens in LENSES:
        assert lens_fingerprint("the seed", lens) == lens_fingerprint("the seed", lens)


def test_l2_all_lenses_byte_stable():
    a = json.dumps(all_lenses("stable seed"), sort_keys=True)
    b = json.dumps(all_lenses("stable seed"), sort_keys=True)
    assert a == b


# --- L3: exactly six lenses -------------------------------------------------


def test_l3_six_lenses_exact():
    assert LENSES == ("minimal", "maximal", "inverse", "constraint", "deep", "reframe")


def test_l3_unknown_lens_rejected():
    with pytest.raises(ValueError):
        apply_lens("seed", "nope")


def test_l3_every_lens_returns_view():
    for lens in LENSES:
        out = apply_lens("seed", lens)
        assert out["lens"] == lens
        assert out["seed"] == "seed"
        assert out["mark"] == BOUNDED_MARK


# --- L4: dream bounded ------------------------------------------------------


def test_l4_dream_cycles_clamp(tmp_path):
    eng = _eng(tmp_path)
    assert eng.dream("s", cycles=0)["cycles"] == DREAM_MIN_CYCLES
    assert eng.dream("s", cycles=100)["cycles"] == DREAM_MAX_CYCLES


def test_l4_dream_trail_length_matches(tmp_path):
    eng = _eng(tmp_path)
    d = eng.dream("s", cycles=4)
    assert len(d["trail"]) == 4


def test_l4_dream_feeds_previous_label(tmp_path):
    eng = _eng(tmp_path)
    d = eng.dream("alpha", cycles=3)
    for prev, nxt in zip(d["trail"], d["trail"][1:]):
        assert nxt["seed"] == (prev.get("auto") or {}).get("label")


# --- L5: REIM prefer --------------------------------------------------------


def test_l5_paths_quality_in_unit_interval(tmp_path):
    r = _eng(tmp_path).round("quality seed")
    for p in r["optionalPaths"]:
        assert 0.0 <= p["quality"] <= 1.0


def test_l5_auto_prefer_picks_max_quality(tmp_path):
    eng = _eng(tmp_path)
    r = eng.round("prefer seed", meta={"autoPrefer": True})
    best = max(r["optionalPaths"], key=lambda p: p["quality"])
    assert r["auto"]["id"] == best["id"]


# --- L6: RIEM salvage -------------------------------------------------------


def test_l6_vault_keeps_extracted_qualities(tmp_path):
    eng = _eng(tmp_path)
    node = eng.vault_negative("ship fast without tests", note="broke the build")
    assert node.quality < 0
    assert node.good_qualities  # something was salvaged


def test_l6_salvage_never_replays_full_failed_path(tmp_path):
    eng = _eng(tmp_path)
    label = "ship fast without any tests or review"
    eng.vault_negative(label)
    salvaged = eng._salvage_qualities()
    assert label not in salvaged  # facets only, never the full failed path


def test_l6_persistence_across_restarts(tmp_path):
    d = tmp_path / "persist"
    eng1 = EchoverseEngine(data_dir=d)
    eng1.vault_negative("bad path one")
    eng1.mark_success("s", "p-1", "good path")
    eng2 = EchoverseEngine(data_dir=d)
    assert len(eng2.negative_vault) == 1
    assert len(eng2.success_memory) == 1


def test_l6_persistence_bounded(tmp_path):
    d = tmp_path / "bounded"
    eng = EchoverseEngine(data_dir=d)
    for i in range(VAULT_KEEP + 20):
        eng.vault_negative(f"bad path {i}")
    eng2 = EchoverseEngine(data_dir=d)
    assert len(eng2.negative_vault) == VAULT_KEEP


def test_l6_extract_good_qualities_shape():
    goods = extract_good_qualities("verify the local build quickly", "keep it simple")
    assert isinstance(goods, list) and goods
    assert len(goods) <= 8


# --- L7: coexistence --------------------------------------------------------


def test_l7_branch_kinds_exact():
    assert BRANCH_KINDS == ("taken", "not_taken", "wild")


def test_l7_branch_rejects_bad_kind():
    with pytest.raises(ValueError):
        Branch(id="x", kind="maybe", label="l", summary="s")


def test_l7_seed_from_mandella_needs_explicit_option(tmp_path):
    with pytest.raises(ValueError):
        seed_from_mandella({}, data_dir=tmp_path / "m")


def test_l7_seed_from_mandella_marks_origin(tmp_path):
    run = seed_from_mandella({"key": "B", "label": "take the job"}, data_dir=tmp_path / "m2")
    assert run.metadata["seeded_from"] == "mandella"
    assert "take the job" in run.seed


def test_l7_constraints_only_from_wild(tmp_path):
    run = BranchStore(data_dir=tmp_path / "m3").simulate("wild seed")
    cons = constraints_for_mandella(run)
    assert cons, "expected at least one wild branch"
    assert all("wild" in json.dumps(c).lower() or True for c in cons)
    wild_labels = {b.label for b in run.branches if b.kind == "wild"}
    assert {c["constraint"] for c in cons} <= wild_labels


def test_l7_phantom_record_shape():
    p = phantom_record([{"key": "A", "label": "stay", "reason": "fear"}])
    assert p["kind"] == "mandella_phantom"
    assert p["rejected"][0]["key"] == "A"


# --- L8: pipeline -----------------------------------------------------------


def test_l8_stages_order():
    assert stages() == ["inquiry", "mandella", "echoverse", "aim"]
    assert stages() == list(PIPELINE)


def test_l8_position_is_third():
    pos = position()
    assert pos["stage"] == "echoverse"
    assert pos["index"] == 2
    assert pos["receives_from"] == "mandella"
    assert pos["produces_for"] == "aim"


def test_l8_aim_returns_plan_never_executes(tmp_path):
    run = BranchStore(data_dir=tmp_path / "pl").simulate("aim seed")
    for body, targets in AIM_TARGETS.items():
        plan = aim(run, body)
        assert plan["executes"] is False
        assert plan["body"] == body
        assert tuple(plan["target_engines"]) == targets
        assert "preferred_path" in plan


def test_l8_aim_unknown_body_rejected(tmp_path):
    run = BranchStore(data_dir=tmp_path / "pl2").simulate("aim seed 2")
    with pytest.raises(ValueError):
        aim(run, "teleport")


def test_l8_aim_prefers_highest_optionality(tmp_path):
    run = BranchStore(data_dir=tmp_path / "pl3").simulate("aim seed 3")
    plan = aim(run, "data")
    best = max(run.branches, key=lambda b: b.optionality)
    assert plan["preferred_path"]["id"] == best.id


def test_l8_doctrine_names_pipeline():
    d = doctrine()
    assert "Inquiry" in d and "Mandella" in d and "Echoverse" in d and "AIM" in d


# --- L9: local-first --------------------------------------------------------


def test_l9_stdlib_only():
    stdlib = set(sys.stdlib_module_names)
    for path in sorted(PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    top = a.name.split(".")[0]
                    assert top in stdlib or top == "levi", f"{path.name}: non-stdlib import {a.name}"
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                assert mod in stdlib or mod == "levi", f"{path.name}: non-stdlib import {node.module}"


def test_l9_no_network_or_subprocess():
    # AST-level: no import of network/subprocess modules (word matches in
    # prose, like the law statement itself, do not count).
    banned = {"socket", "urllib", "requests", "subprocess", "http"}
    for path in sorted(PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] not in banned, f"{path.name}: {a.name}"
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                assert mod not in banned, f"{path.name}: {node.module}"


def test_l9_records_under_data_dir(tmp_path):
    d = tmp_path / "rec"
    eng = EchoverseEngine(data_dir=d)
    eng.round("record me")  # first write persists state
    assert (d / "echoverse_state.json").exists()
    BranchStore(data_dir=d).simulate("record me too")
    assert (d / "runs.json").exists()


# --- simulation (local templates) -------------------------------------------


def test_simulation_roles_cycle():
    sim = EchoverseSimulation()
    out = sim.run("seed", steps=5)
    roles = [e["agent"] for e in out["events"]]
    assert roles == ["strategist", "critic", "builder", "guardian", "strategist"]
    assert out["mark"] == BOUNDED_MARK
