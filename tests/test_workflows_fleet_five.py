"""Hermetic tests for the fleet-five workflow (capped delegation).

Hermetic: tmp LEVI home, no network, no model, no daemon. Contributions are
fixture text — fleet-five folds real contributions; it never fabricates them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from levi.workflows import list_workflows, run_workflow
from levi.workflows.fleet_five import (
    FleetError,
    MAX_SPECIALISTS,
    run_fleet,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _levi_home(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / "levi-home"
    monkeypatch.setenv("HOME", str(tmp_path))
    return home


_FULL_TEXT = {
    "architect": "interfaces: CLI run_fleet(task, specialists) -> report dict; "
    "plan: validate -> fold -> disband.",
    "implementer": "smallest slice: _check_specialists + _fold_report, "
    "200 lines, stdlib only.",
    "critic": "weakness: cap bypass if callers pre-merge roles; mitigation: "
    "duplicate-role rejection.",
    "scope_warden": "IN: folding. OUT: running models, persistent fleets, "
    "network calls.",
    "scribe": "digest: five sections, one report, fleet gone.",
}


def _specs(*roles, **over):
    out = []
    for r in roles:
        spec = {"role": r, "contribution": _FULL_TEXT[r]}
        spec.update(over)
        out.append(spec)
    return out


_FIVE = _specs("architect", "implementer", "critic", "scope_warden", "scribe")


# ---------------------------------------------------------------------------
# registry contract
# ---------------------------------------------------------------------------


def test_fleet_five_registered():
    wf = {w["name"]: w for w in list_workflows()}["fleet-five"]
    assert wf["steps"] == [
        "summon",
        "architect",
        "implementer",
        "critic",
        "scope_warden",
        "scribe",
        "fold",
    ]
    assert "capped delegation" in wf["summary"].lower()
    assert set(wf.keys()) == {"name", "summary", "steps"}


# ---------------------------------------------------------------------------
# the hard cap: a 6th specialist raises a clear error
# ---------------------------------------------------------------------------


def test_sixth_specialist_refused_clear_error():
    six = _specs(
        "architect", "implementer", "critic", "scope_warden", "scribe", "architect"
    )  # 6, with a duplicate too
    with pytest.raises(FleetError) as ei:
        run_fleet("cap test", six)
    msg = str(ei.value)
    assert "HARD CAP" in msg
    assert "6" in msg and str(MAX_SPECIALISTS) in msg
    assert isinstance(ei.value, ValueError)


def test_sixth_specialist_distinct_roles_still_refused():
    # six *distinct* roles is impossible (only 5 roles exist); the cap is
    # what fires, not role validation — duplicate the critic to get 6.
    six = _specs(
        "architect", "implementer", "critic", "scope_warden", "scribe", "critic"
    )
    with pytest.raises(FleetError) as ei:
        run_fleet("cap test", six)
    assert "HARD CAP" in str(ei.value)


def test_run_workflow_sixth_fails_honestly(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    six = _specs(
        "architect", "implementer", "critic", "scope_warden", "scribe", "scribe"
    )
    result = run_workflow("fleet-five", home=home, task="cap test", specialists=six)
    assert result["ok"] is False
    assert [s["name"] for s in result["steps"]] == ["summon"]
    assert result["steps"][0]["ok"] is False
    assert "HARD CAP" in result["steps"][0]["reason"]


def test_max_is_five_not_four():
    # sanity: the cap constant really is 5
    assert MAX_SPECIALISTS == 5
    report = run_fleet("five is fine", list(_FIVE))
    assert report["fleet_size"] == 5


# ---------------------------------------------------------------------------
# one folded report, five sections, no truncation
# ---------------------------------------------------------------------------


def test_full_fleet_folds_single_report(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow(
        "fleet-five", home=home, task="Fold the sky", specialists=list(_FIVE)
    )

    assert result["ok"] is True
    assert result["workflow"] == "fleet-five"
    assert [s["name"] for s in result["steps"]] == [
        "summon",
        "architect",
        "implementer",
        "critic",
        "scope_warden",
        "scribe",
        "fold",
    ]
    assert all(s["ok"] for s in result["steps"])

    report = result["artifacts"]["report"]
    # ONE report, not five
    assert report["report"] == "fleet-five"
    assert report["task"] == "Fold the sky"
    assert report["fleet_size"] == 5
    assert report["folded"] is True
    # each specialist contributed exactly one section
    assert [s["role"] for s in report["sections"]] == [
        "architect",
        "implementer",
        "critic",
        "scope_warden",
        "scribe",
    ]
    for section in report["sections"]:
        assert section["content"] == _FULL_TEXT[section["role"]]
    # the scribe's digest is the folded summary
    assert report["digest"] == _FULL_TEXT["scribe"]
    assert report["roles_missing"] == []
    assert report["roles_present"] == [s["role"] for s in report["sections"]]


def test_roles_reordered_to_canon(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    shuffled = _specs("scribe", "critic", "architect")
    result = run_workflow("fleet-five", home=home, task="order", specialists=shuffled)
    assert result["ok"] is True
    assert [s["role"] for s in result["artifacts"]["report"]["sections"]] == [
        "architect",
        "critic",
        "scribe",
    ]
    assert result["artifacts"]["report"]["roles_missing"] == [
        "implementer",
        "scope_warden",
    ]


def test_single_specialist_partial_fleet_ok(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow(
        "fleet-five", home=home, task="small job", specialists=_specs("scribe")
    )
    assert result["ok"] is True
    report = result["artifacts"]["report"]
    assert report["fleet_size"] == 1
    assert report["roles_missing"] == [
        "architect",
        "implementer",
        "critic",
        "scope_warden",
    ]


# ---------------------------------------------------------------------------
# empty task handled honestly
# ---------------------------------------------------------------------------


def test_empty_task_raises(monkeypatch, tmp_path):
    with pytest.raises(FleetError) as ei:
        run_fleet("   ", _specs("scribe"))
    assert "empty task" in str(ei.value)


def test_run_workflow_empty_task_fails_honestly(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow(
        "fleet-five", home=home, task="", specialists=_specs("scribe")
    )
    assert result["ok"] is False
    assert result["steps"][0]["name"] == "summon"
    assert "empty task" in result["steps"][0]["reason"]
    # no artifacts leaked on a failed run
    assert "report" not in result["artifacts"]


def test_missing_task_fails_honestly(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow("fleet-five", home=home, specialists=_specs("scribe"))
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# oversize task refused with split guidance (never silently truncated)
# ---------------------------------------------------------------------------


def test_oversized_task_refused_with_split_guidance():
    with pytest.raises(FleetError) as ei:
        run_fleet("too big", _specs("scribe"), task_size="large")
    msg = str(ei.value)
    assert "Split" in msg or "split" in msg
    assert "5" in msg


def test_run_workflow_oversized_task_refused(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    result = run_workflow(
        "fleet-five",
        home=home,
        task="big one",
        specialists=list(_FIVE),
        task_size="large",
    )
    assert result["ok"] is False
    reason = result["steps"][0]["reason"]
    assert "split" in reason.lower()
    assert "report" not in result["artifacts"]


# ---------------------------------------------------------------------------
# bad specs refused
# ---------------------------------------------------------------------------


def test_empty_specialists_refused():
    with pytest.raises(FleetError) as ei:
        run_fleet("task", [])
    assert "zero" in str(ei.value)


def test_bad_role_refused():
    with pytest.raises(FleetError) as ei:
        run_fleet("task", [{"role": "hero", "contribution": "x"}])
    assert "hero" in str(ei.value)


def test_duplicate_role_refused():
    with pytest.raises(FleetError) as ei:
        run_fleet("task", _specs("scribe", "scribe"))
    assert "duplicate" in str(ei.value)


def test_missing_contribution_refused():
    with pytest.raises(FleetError) as ei:
        run_fleet("task", [{"role": "architect"}])
    assert "never fabricates" in str(ei.value)


def test_non_dict_spec_refused():
    with pytest.raises(FleetError):
        run_fleet("task", ["architect"])


# ---------------------------------------------------------------------------
# no state left behind after fold
# ---------------------------------------------------------------------------


def test_no_state_left_behind_after_fold(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    run_workflow("fleet-five", home=home, task="ghost fleet", specialists=list(_FIVE))
    run_fleet("ghost fleet", list(_FIVE))
    # the fleet disbanded: nothing written to the hermetic home
    if home.exists():
        files = [p for p in home.rglob("*") if p.is_file()]
        assert files == [], files
    # and fleet-five left no fleet state dir anywhere in the tmp tree
    assert not list(tmp_path.rglob("fleet"))


def test_run_twice_no_accumulation(monkeypatch, tmp_path):
    home = _levi_home(monkeypatch, tmp_path)
    r1 = run_workflow("fleet-five", home=home, task="one", specialists=list(_FIVE))
    r2 = run_workflow("fleet-five", home=home, task="two", specialists=list(_FIVE))
    assert r1["ok"] and r2["ok"]
    assert r1["artifacts"]["report"]["task"] == "one"
    assert r2["artifacts"]["report"]["task"] == "two"
    assert len(r2["artifacts"]["report"]["sections"]) == 5  # not 10
