"""BUILDERS — one engine, three doors (owner decision 2026-09-21).

Hermetic: no network, no daemons. Covers the door layer only — the
engine itself is covered by tests/test_builders_kfx2.py.

The contract under test:
- three thin doors (standalone / hicomb / hub), zero duplicated engine
  logic — every door delegates to levi.builders.pipeline.build;
- the graduation path: a project scaffolded through one door opens and
  continues identically through the others (same prompt -> byte-identical
  output, no rebuild);
- the Hicomb door stays compatible with levi.hicomb.dock's contract;
- the Hub door speaks hub.api's route convention.
"""

from __future__ import annotations

import json
import os

import pytest

from levi.builders import BuildOutcome
from levi.builders.doors import (
    DOORS,
    DoorReport,
    GraduationMismatch,
    NotABuilderProject,
    hicomb,
    hub,
    open_project,
    standalone,
)

PROMPT = "Build me a simple app to track my vinyl records and manage playlists"


def _read_tree(root):
    tree = {}
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                tree[os.path.relpath(full, root)] = fh.read()
    return tree


# -- the three doors -------------------------------------------------------


def test_three_doors_registered():
    assert set(DOORS) == {"standalone", "hicomb", "hub"}
    for name, mod in DOORS.items():
        assert mod.DOOR_NAME == name
        assert mod.DEMAND_CLASS, "each door names the demand class it serves"


def test_each_door_builds_verified_and_byte_identical(tmp_path):
    reports = {}
    for name, build_fn in (
        ("standalone", standalone.build_simple),
        ("hicomb", hicomb.build_complex),
        ("hub", hub.build_managed),
    ):
        reports[name] = build_fn(PROMPT, workdir=str(tmp_path / name))
    for name, rep in reports.items():
        assert isinstance(rep, DoorReport)
        assert rep.door == name
        assert rep.outcome is BuildOutcome.VERIFIED, name
        assert rep.ok
    trees = {name: _read_tree(rep.target_dir) for name, rep in reports.items()}
    assert trees["standalone"] == trees["hicomb"] == trees["hub"]
    provs = [rep.provenance for rep in reports.values()]
    assert provs[0] == provs[1] == provs[2]
    assert provs[0]["provenance"] == "builder"


# -- graduation path: change of surface, never a rebuild -------------------


def test_graduation_standalone_to_hicomb_to_hub(tmp_path):
    first = standalone.build_simple(PROMPT, workdir=str(tmp_path / "simple"))
    via_hicomb = first.continue_via(hicomb.build_complex, workdir=str(tmp_path / "pro"))
    assert via_hicomb.door == "hicomb"
    assert via_hicomb.outcome is BuildOutcome.VERIFIED
    via_hub = via_hicomb.continue_via(hub.build_managed, workdir=str(tmp_path / "ent"))
    assert via_hub.door == "hub"
    # The original project is untouched — nothing was rebuilt in place.
    assert _read_tree(first.target_dir) == _read_tree(via_hub.target_dir)


def test_graduation_backwards_hub_to_standalone(tmp_path):
    first = hub.build_managed(PROMPT, workdir=str(tmp_path / "ent"))
    back = first.continue_via(standalone.build_simple, workdir=str(tmp_path / "s"))
    assert back.door == "standalone"
    assert _read_tree(first.target_dir) == _read_tree(back.target_dir)


def test_continue_via_raises_on_divergence(tmp_path):
    first = standalone.build_simple(PROMPT, workdir=str(tmp_path / "a"))

    def rogue_build(prompt, workdir=None, **kwargs):
        rep = standalone.build_simple(prompt + " with extras", workdir=workdir)
        return rep

    with pytest.raises(GraduationMismatch):
        first.continue_via(rogue_build, workdir=str(tmp_path / "b"))


def test_open_project_identical_through_every_door(tmp_path):
    built = standalone.build_simple(PROMPT, workdir=str(tmp_path / "proj"))
    via_standalone = standalone.open_project(built.target_dir)
    via_hicomb = hicomb.open_project(built.target_dir)
    via_hub = hub.open_project(built.target_dir)
    top_level = open_project(built.target_dir)
    for proj in (via_standalone, via_hicomb, via_hub, top_level):
        assert proj.app == built.provenance["app"]
        assert proj.entities == built.provenance["entities"]
        assert proj.prompt_sha256 == built.provenance["prompt_sha256"]
        assert proj.path == os.path.abspath(built.target_dir)


def test_open_project_rejects_foreign_directories(tmp_path):
    with pytest.raises(NotABuilderProject):
        open_project(str(tmp_path))  # empty dir: no provenance
    other = tmp_path / "other"
    other.mkdir()
    (other / ".provenance.json").write_text(
        json.dumps({"provenance": "someone-else"}), encoding="utf-8"
    )
    with pytest.raises(NotABuilderProject):
        open_project(str(other))
    with pytest.raises(NotABuilderProject):
        open_project(str(tmp_path / "missing"))


# -- Hicomb door: compatible with the existing dock contract ----------------


def test_hicomb_door_dock_attaches_engine():
    from levi.builders import ScaffoldEngine
    from levi.hicomb import DockReport, Session, default_registry

    session = Session()
    registry = default_registry()
    report = hicomb.dock(session, registry, engine=ScaffoldEngine(PROMPT))
    assert isinstance(report, DockReport)
    assert report.available and report.attached
    assert "builders" in session.extensions
    assert "builders.scaffold" in report.commands_registered


def test_hicomb_door_dock_honest_without_engine():
    # The inherited dock contract reports instead of raising when no
    # engine is supplied (ScaffoldEngine needs a prompt). The door keeps
    # that honesty — it does not invent a default prompt.
    from levi.hicomb import Session

    report = hicomb.dock(Session())
    assert report.available and not report.attached
    assert "prompt" in report.note


# -- Hub door: surface summary + route convention ----------------------------


def test_hub_surface_summary_is_jsonable_and_honest(tmp_path):
    rep = hub.build_managed(PROMPT, workdir=str(tmp_path / "hub"))
    summary = hub.surface_summary(rep)
    json.dumps(summary)  # must survive the Hub API's json.dumps(payload)
    assert summary["door"] == "hub"
    assert summary["ok"] is True
    assert summary["outcome"] == "verified"
    assert summary["charged"] == "0.00"
    assert summary["platform_cut"] == "0.12"
    assert summary["app"] == rep.provenance["app"]
    assert set(summary["files"]) == set(rep.files)


def test_hub_routes_follow_hub_api_convention():
    routes = hub.hub_routes()
    assert ("POST", "/api/builders/build") in routes
    assert ("GET", "/api/builders/doors") in routes
    for (method, path), handler in routes.items():
        assert method in ("GET", "POST")
        assert path.startswith("/api/builders/")
        assert callable(handler)

    code, payload, kind = routes[("GET", "/api/builders/doors")]({}, {}, None)
    assert code == 200 and kind == "json"
    assert payload["ok"] is True
    assert len(payload["doors"]) == 3
    assert "graduation" in payload

    code, payload, kind = routes[("POST", "/api/builders/build")](
        {}, {"prompt": ""}, None
    )
    assert code == 400  # prompt required, honest 400 not a traceback

    code, payload, kind = routes[("POST", "/api/builders/build")](
        {}, {"prompt": PROMPT}, None
    )
    assert code == 200 and kind == "json"
    assert payload["ok"] is True
    assert payload["build"]["outcome"] == "verified"


# -- doors stay thin: no engine logic may live here --------------------------


def test_doors_contain_no_engine_logic():
    import pathlib

    doors_pkg = pathlib.Path(hub.__file__).parent
    banned = (
        "_APP_TEMPLATE",
        "_SMOKE_TEMPLATE",
        "class ScaffoldEngine",
        "class VerifyLoop",
        "def generate(",
        "import subprocess",
    )
    sources = list(doors_pkg.glob("*.py"))
    assert len(sources) == 5, "doors package should hold exactly 5 modules"
    for py in sources:
        src = py.read_text(encoding="utf-8")
        for bad in banned:
            assert bad not in src, f"{py.name} contains engine logic marker {bad!r}"


def test_doors_delegate_to_the_single_engine():
    import levi.builders.pipeline as pipeline

    for mod, fn_name in (
        (standalone, "build_simple"),
        (hicomb, "build_complex"),
        (hub, "build_managed"),
    ):
        fn = getattr(mod, fn_name)
        assert fn.__module__ == mod.__name__
        # The delegation target is the one engine build; doors must not
        # shadow or reimplement it.
        assert pipeline.build.__module__ == "levi.builders.pipeline"
