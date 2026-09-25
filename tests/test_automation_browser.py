"""Hermetic tests for browser plans and the primitive registry.

Plans only — nothing here touches the network or a browser.
"""

import pytest

from levi.automation.browser import (
    BrowserPlan,
    emit_termux_helper,
    format_plan,
    plan_browser_job,
)
from levi.automation.primitives import (
    GREEN,
    RED,
    YELLOW,
    get_primitive,
    list_primitives,
    match_nl,
    red_primitives,
)


def test_plan_has_seven_steps():
    plan = plan_browser_job("extract the title", url="https://example.com")
    assert isinstance(plan, BrowserPlan)
    assert len(plan.steps) == 7
    assert plan.url == "https://example.com"
    assert plan.id.startswith("BR-")


def test_login_gate_is_hitl():
    plan = plan_browser_job("do the thing")
    gate = [s for s in plan.steps if s["action"] == "optional_login_gate"]
    assert len(gate) == 1 and gate[0]["hitl"] is True


def test_plan_rejects_empty_goal():
    with pytest.raises(ValueError, match="goal must not be empty"):
        plan_browser_job("   ")


def test_plan_goal_truncated():
    plan = plan_browser_job("x" * 600)
    assert len(plan.goal) == 500


def test_plan_fields_recorded():
    plan = plan_browser_job("fill it", fields=["name", "email"])
    fill = [s for s in plan.steps if s["action"] == "extract_or_fill"][0]
    assert fill["fields"] == ["name", "email"]


def test_emit_termux_helper_is_script_text():
    plan = plan_browser_job("extract the title", url="https://example.com")
    script = emit_termux_helper(plan)
    assert script.startswith("#!/data/data/com.termux/files/usr/bin/bash")
    assert "https://example.com" in script
    assert "HITL" in script
    assert plan.id in script


def test_emit_rejects_non_plan():
    with pytest.raises(ValueError, match="expected a BrowserPlan"):
        emit_termux_helper({"id": "x"})


def test_format_plan_marks_hitl():
    text = format_plan(plan_browser_job("g"))
    assert "## Browser Automation Plan" in text
    assert "_(HITL)_" in text
    assert "never silent in-app browsing" in text


# --- primitives ----------------------------------------------------------


def test_primitive_ids_unique():
    ids = [p.id for p in list_primitives()]
    assert len(ids) == len(set(ids)) and len(ids) >= 12


def test_get_primitive_case_insensitive():
    assert get_primitive("ap-007").name == "CDP session"
    assert get_primitive("AP-007").name == "CDP session"
    assert get_primitive("AP-999") is None


def test_band_filter():
    reds = list_primitives(RED)
    assert reds and all(p.band == RED for p in reds)
    greens = list_primitives(GREEN)
    assert greens and all(p.band == GREEN for p in greens)


def test_red_primitives_require_hitl():
    for p in red_primitives():
        assert p.hitl_required is True


def test_cdp_is_yellow_but_auth_paths_hitl():
    cdp = get_primitive("AP-007")
    assert cdp.band == YELLOW  # session attach itself…
    fill = get_primitive("AP-008")
    assert fill.hitl_required is True  # …but form fill always confirms


def test_match_nl_login_maps_to_hitl_primitives():
    found = match_nl("help me log in to the portal")
    assert found
    assert any(p.hitl_required for p in found)


def test_match_nl_no_match():
    assert match_nl("quantum banana") == []


def test_primitive_dict_shape():
    d = get_primitive("AP-001").to_dict()
    assert set(d) == {
        "id",
        "name",
        "platforms",
        "band",
        "hitl_required",
        "description",
        "notes",
    }
