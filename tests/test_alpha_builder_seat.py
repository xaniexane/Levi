"""Alpha builder-seat tests: canon identity + NL build routing.

Canon (Chauncey): ALPHA is the builder (builds things); Alpha and Omega
are the same individual with two personalities, twin facets of Echo
("Omega powered by Alpha"; "Alpha echoes Omega; the builder is the
daemon's echo").

The deliberation machinery is preserved as the build-planning
deliberation (plan-first); the seat's engine routes natural-language
build intent into E3-E6 tiered plans, in the shape of the original
alphaEngine (NL -> route -> build).

Hermetic: temp HOME; HITLGate pointed at a temp file.
"""

from __future__ import annotations

import argparse

import pytest

import levi.alpha as alpha
import levi.project.hitl as hitl_mod
from levi.alpha import build as alpha_build
from levi.alpha.cli import cmd_alpha


@pytest.fixture()
def hermetic(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(hitl_mod, "DEFAULT_PATH", home / ".levi" / "hitl.json")
    return home


# ---- canon identity ------------------------------------------------------------


def test_alpha_seat_is_builder():
    assert alpha.ALPHA_SEAT == "builder"
    assert alpha.ALPHA_ROLE == "alpha"  # substrate contract unchanged


def test_canon_markers_in_package_doc():
    doc = alpha.__doc__ or ""
    assert "Omega powered by Alpha" in doc
    assert "Echo" in doc
    assert "the builder" in doc


def test_deliberator_still_serves_build_planning():
    # The machinery is preserved: probe contract + result shape intact.
    reasoner = alpha.probe_alpha()
    assert reasoner is not None
    out = reasoner.reason("plan: scaffold a notes app; which tier?")
    assert set(out) >= {"answer", "substrate", "limits"}
    assert out["substrate"] in (
        "rules-engine",
        "native-brain",
        "rules-engine + native-brain",
    )


# ---- NL intent parsing (original alphaEngine forms) ------------------------------


@pytest.mark.parametrize(
    "text,kind,name",
    [
        ("build engine auth", "engine", "auth"),
        ("build module billing extra words here", "module", "billing"),
        ("build service payments", "service", "payments"),
        ("BUILD ENGINE caps", "engine", "caps"),
    ],
)
def test_parse_build_intent_command_forms(text, kind, name):
    parsed = alpha_build.parse_build_intent(text)
    assert parsed["kind"] == kind
    assert parsed["name"] == name
    assert parsed["goal"]


def test_parse_build_intent_bare_build():
    parsed = alpha_build.parse_build_intent("build a todo list app")
    assert parsed["kind"] == "project"
    assert parsed["goal"] == "a todo list app"


def test_parse_build_intent_plain_text():
    parsed = alpha_build.parse_build_intent("a todo list app")
    assert parsed["kind"] == "project"
    assert parsed["goal"] == "a todo list app"


def test_parse_build_intent_rejects_empty():
    with pytest.raises(ValueError):
        alpha_build.parse_build_intent("   ")


# ---- routing into E3-E6 -------------------------------------------------------------


def test_plan_build_routes_to_emergency_builder(hermetic):
    job = alpha_build.plan_build("a todo list app", tier="E4")
    assert job.tier == "E4"
    assert job.status == "planned"
    assert "todo list app" in job.goal


def test_plan_build_command_form_names_project(hermetic):
    job = alpha_build.plan_build("build module auth", tier="E4")
    assert job.target.endswith(":auth")


def test_plan_build_rejects_invalid_tier(hermetic):
    with pytest.raises(ValueError, match="tier must be one of"):
        alpha_build.plan_build("a todo app", tier="X9")


def test_plan_build_rejects_empty_intent(hermetic):
    with pytest.raises(ValueError):
        alpha_build.plan_build("   ", tier="E4")


def test_plan_build_e5_requires_hitl(hermetic):
    job = alpha_build.plan_build("an mvp slice", tier="E5")
    assert job.requires_hitl
    assert job.status == "awaiting_hitl"


def test_apply_build_e4_writes_artifacts(hermetic, tmp_path):
    ws = tmp_path / "ws"
    job = alpha_build.plan_build("a notes app", tier="E4", workspace=ws)
    out = alpha_build.apply_build(job.id, workspace=ws)
    assert "Applied job" in out
    assert (ws / job.target.split(":")[-1] / "README.md").is_file()


def test_apply_build_e5_refused_without_approval(hermetic, tmp_path):
    ws = tmp_path / "ws"
    job = alpha_build.plan_build("an mvp slice", tier="E5", workspace=ws)
    out = alpha_build.apply_build(job.id, workspace=ws)
    assert "Applied job" not in out
    assert not (ws / job.target.split(":")[-1]).exists()


def test_route_summary_names_kind_and_tier():
    parsed = alpha_build.parse_build_intent("build service payments")
    s = alpha_build.route_summary(parsed, "E4")
    assert "kind=service" in s and "tier=E4" in s


# ---- CLI ------------------------------------------------------------------------------


def _ns(**kw):
    base = dict(
        alpha_cmd="build",
        intent=["a todo list app"],
        tier="E4",
        name=None,
        target="independent",
        apply=False,
        force=False,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def test_cli_build_plans(hermetic, capsys):
    assert cmd_alpha(_ns()) == 0
    out = capsys.readouterr().out
    assert "Emergency Builder Job" in out
    assert "Tier: E4" in out


def test_cli_build_rejects_empty_intent(hermetic, capsys):
    assert cmd_alpha(_ns(intent=["  "])) == 1
    assert "refused" in capsys.readouterr().out


def test_cli_build_apply_e4(hermetic, capsys):
    assert cmd_alpha(_ns(apply=True)) == 0
    assert "Applied job" in capsys.readouterr().out


def test_cli_build_apply_e5_refused_without_approval(hermetic, capsys):
    assert cmd_alpha(_ns(tier="E5", apply=True)) == 2
    out = capsys.readouterr().out
    assert "Applied job" not in out
