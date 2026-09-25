"""Guards for the Omega engine -> pool skill mapping — law-guard-prove.

Proves: all 32 unique engines appear exactly once (E1); every mapped
skill id is real (E2); unmapped engines are explicitly flagged with
missing notes, never absent (E3); coverage_report numbers are computed
from the data and sum correctly (E4); legion_action_react maps to
Context + Tone + Task + Execution engines; the engine list is historic
canon (2026-09-22) while the mapping judgments stay provisional analysis;
the 32×64×128 tensor spec is declared; nothing else in the pool regressed.
"""

import pytest

from levi.legion.skill_pool import (
    coverage_report,
    engines_for,
    skills_for_engine,
    unmapped_engines,
)
from levi.legion.skill_pool.definitions import SKILL_DEFINITIONS
from levi.legion.skill_pool.engine_map import ENGINE_INVARIANTS, ENGINE_MAP

REAL_IDS = {d["id"] for d in SKILL_DEFINITIONS}

# the 32 unique engines, grouped by source set — the contract
EXPECTED_ENGINES = {
    "SET 1 — Identity Dimensions": [
        "Canon Engine",
        "Founder Alignment Engine",
        "System Identity Engine",
        "User Identity Engine",
    ],
    "SET 2 — Logic Dimensions": [
        "Knowledge Engine",
        "Reasoning Engine",
        "Clarification Protocol",
        "Structural Logic Engine",
    ],
    "SET 3 — Emotion Dimensions": [
        "Emotional Engine",
        "Tone Engine",
        "Humor Engine",
        "Context Engine",
    ],
    "SET 4 — Action Dimensions": [
        "Automation Engine",
        "Task Engine",
        "Physical Integration Engine",
        "Execution Engine",
    ],
    "SET 5 — Negative / Shadow Dimensions": [
        "Shadow Engine",
        "Anti-Structure Engine",
        "Paradox Engine",
        "Depth Engine",
    ],
    "DIMENSION 21 — The Single Canon Dimension": ["Canon Plane"],
    "CORE ENGINE STACK": [
        "Teaching Engine",
        "Assistance Engine",
        "Opportunity Engine",
        "Demandpulse Engine",
        "Internal Engine",
        "World Engine",
        "Data Engine",
        "Communication Engine",
        "Creator Engine",
        "Security Engine",
        "Successor Engine",
    ],
}


def _expected_unique():
    seen = []
    for engines in EXPECTED_ENGINES.values():
        for e in engines:
            if e not in seen:
                seen.append(e)
    return seen


# -- E1: every engine appears exactly once --------------------------------


def test_32_unique_engines_exactly_once():
    names = [e["engine"] for e in ENGINE_MAP]
    assert len(names) == 32, f"expected 32 unique engines, got {len(names)}"
    assert len(set(names)) == 32, "duplicate engine in map"
    assert sorted(names) == sorted(_expected_unique())


def test_automation_engine_dual_listing_mapped_once():
    entry = next(e for e in ENGINE_MAP if e["engine"] == "Automation Engine")
    assert "SET 4 — Action Dimensions" in entry["sets"]
    assert "CORE ENGINE STACK" in entry["sets"]
    assert not entry["unmapped"]


def test_engine_invariants_declared():
    assert len(ENGINE_INVARIANTS) == 4


# -- E2: mapped skill ids are real ----------------------------------------


def test_every_link_skill_id_is_real():
    for entry in ENGINE_MAP:
        for link in entry["links"]:
            assert link["skill"] in REAL_IDS, (
                f"{entry['engine']} links unknown skill {link['skill']!r}"
            )
            assert link["how"].strip(), f"{entry['engine']} link has empty how-note"
            assert isinstance(link["partial"], bool)


# -- E3: unmapped engines flagged, never absent ----------------------------


EXPECTED_UNMAPPED = {
    "Canon Engine",
    "System Identity Engine",
    "User Identity Engine",
    "Clarification Protocol",
    "Physical Integration Engine",
    "Depth Engine",
    "Canon Plane",
    "Internal Engine",
    "World Engine",
    "Security Engine",
    "Successor Engine",
}


def test_unmapped_engines_flagged_with_missing_notes():
    got = {u["engine"] for u in unmapped_engines()}
    assert got == EXPECTED_UNMAPPED, f"unmapped set drifted: {got ^ EXPECTED_UNMAPPED}"
    for u in unmapped_engines():
        assert u["missing"].strip(), f"{u['engine']} has empty missing note"
        assert u["sets"] and u["function"].strip()


def test_security_engine_points_at_cyber_playbooks_not_a_pool_skill():
    u = next(u for u in unmapped_engines() if u["engine"] == "Security Engine")
    assert "covered_elsewhere" in u
    assert "playbooks/cyber" in u["covered_elsewhere"]


def test_mapped_engines_have_links():
    for entry in ENGINE_MAP:
        if not entry["unmapped"]:
            assert entry["links"], f"{entry['engine']} marked mapped, no links"


# -- Action mapping (Chauncey's folded-in requirement) --------------------


def test_action_react_maps_to_context_tone_task_execution():
    engines = engines_for("legion_action_react")
    for required in (
        "Context Engine",
        "Tone Engine",
        "Task Engine",
        "Execution Engine",
    ):
        assert required in engines, f"action_react missing {required}"


def test_skills_for_engine_roundtrip():
    links = skills_for_engine("Context Engine")
    assert any(link["skill"] == "legion_action_react" for link in links)
    for link in links:
        assert link["skill"] in REAL_IDS


def test_unknown_engine_and_skill_fail_loudly():
    with pytest.raises(ValueError):
        skills_for_engine("Nope Engine")
    with pytest.raises(ValueError):
        engines_for("legion_nope")


# -- E4: coverage_report computed from data --------------------------------


def test_coverage_report_sums_correctly():
    report = coverage_report()
    assert report["total_engines"] == 32
    assert report["mapped"] + report["unmapped"] == 32
    assert report["unmapped"] == len(unmapped_engines()) == 11
    assert report["mapped"] == 21
    # partial_only counted from the data
    partial = [
        e
        for e in ENGINE_MAP
        if not e["unmapped"]
        and e["links"]
        and all(link["partial"] for link in e["links"])
    ]
    assert report["partial_only"] == len(partial)
    assert sorted(report["partial_only_engines"]) == sorted(
        e["engine"] for e in partial
    )
    # zero-engine skills = real ids minus serving ids
    serving = {
        link["skill"] for e in ENGINE_MAP if not e["unmapped"] for link in e["links"]
    }
    assert report["skills_serving_engines"] == len(serving)
    assert sorted(report["skills_serving_zero_engines"]) == sorted(REAL_IDS - serving)
    assert (
        report["skills_serving_engines"] + len(report["skills_serving_zero_engines"])
        == 80
    )


def test_spot_check_known_mappings():
    assert "Founder Alignment Engine" in engines_for("legion_goals")
    assert "Communication Engine" in engines_for("legion_gmail")
    assert "Teaching Engine" in engines_for("legion_flashcard_generator")
    assert "Data Engine" in engines_for("legion_file_converter")
    # unmapped engines serve nothing
    assert "Knowledge Engine" in engines_for("legion_deep_research")
    assert "Canon Plane" not in engines_for("legion_goals")


# -- source status: engine list is historic canon; mapping is provisional -


def test_engine_list_is_historic_canon():
    import levi.legion.skill_pool.engine_map as mod

    doc = mod.__doc__
    assert "HISTORIC CANON" in doc
    assert "2026-09-22" in doc
    assert mod.ENGINE_SOURCE_STATUS == "historic canon per Chauncey's 2026-09-22 ruling"
    # the mapping judgments stay provisional, never presented as canon
    assert "provisional analysis" in doc
    # no proposed/essence language remains about the engine list
    assert "PROPOSED/ESSENCE" not in doc


def test_engine_tensor_shape_declared():
    import levi.legion.skill_pool.engine_map as mod

    assert mod.ENGINE_TENSOR_SHAPE == (32, 64, 128)
    assert mod.ENGINE_TENSOR_TOTAL == 262144
    assert len(ENGINE_MAP) == 32  # 32 engines, one matrix each


def test_tensor_axis_semantics_marked_pending_not_invented():
    import inspect

    import levi.legion.skill_pool.engine_map as mod

    # the meaning of the 64/128 axes is his to define — the source must
    # carry the pending marker, never an invented definition
    assert "SEMANTICS PENDING" in inspect.getsource(mod)


def test_world_engine_note_carries_canon_six_world_definition():
    u = next(u for u in unmapped_engines() if u["engine"] == "World Engine")
    text = (u["function"] + " " + u["missing"]).lower()
    for world in ("physical", "digital", "ar", "internal", "social", "opportunity"):
        assert world in text, f"World Engine note missing the {world} world"
    assert "reality synchronizer" in text
    assert "identity core" in text


def test_internal_engine_note_carries_canon_diagram_material():
    u = next(u for u in unmapped_engines() if u["engine"] == "Internal Engine")
    text = (u["function"] + " " + u["missing"]).lower()
    assert "resilience" in text


def test_automation_engine_note_carries_canon_internals():
    entry = next(e for e in ENGINE_MAP if e["engine"] == "Automation Engine")
    note = entry.get("note", "").lower()
    for part in (
        "workflow processor",
        "logic module",
        "routine generator",
        "execution hub",
    ):
        assert part in note, f"Automation Engine note missing {part}"
