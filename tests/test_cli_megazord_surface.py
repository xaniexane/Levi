"""Axis-1 surface tests: the `levi` CLI reaches every landed subsystem.

Hermetic: HOME is redirected to tmp_path; import-time Path.home() bindings
are patched where they exist; heavy subsystem entry points are mocked.
Never touches the real ~/.levi.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import levi.cli.main as climain

ROOT = Path(__file__).resolve().parents[1]

AXIS1_SUBCOMMANDS = [
    "archive",
    "galaxy",
    "methods",
    "revival",
    "perpetual",
    "oath",
    "forge",
    "megazord",
    "atlas",
    "workflow",
    "warehouse",
    "bloodstream",
]


def _block_module(monkeypatch, dotted):
    """Simulate an unlanded axis: make ``import dotted`` raise ImportError.

    ``from pkg import sub`` short-circuits via the already-bound package
    attribute, so both sys.modules AND the package attribute must go.
    """
    monkeypatch.setitem(sys.modules, dotted, None)
    pkg_name, _, sub_name = dotted.rpartition(".")
    if pkg_name:
        monkeypatch.delattr(sys.modules[pkg_name], sub_name, raising=False)


def _herm_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    # Modules that bound Path.home() at import time must be repointed too.
    try:
        from levi.perpetual import hunt as _hunt

        monkeypatch.setattr(
            _hunt,
            "perpetual_home",
            lambda home=None: tmp_path / ".levi" / "perpetual",
            raising=False,
        )
    except Exception:
        pass


def _run_help():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "core"), *sys.path])
    return subprocess.run(
        [sys.executable, "-m", "levi.cli.main", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_help_lists_axis1_subcommands():
    proc = _run_help()
    assert proc.returncode == 0, proc.stderr
    for sub in AXIS1_SUBCOMMANDS:
        assert sub in proc.stdout, f"subcommand {sub!r} missing from --help"


# -- passthrough delegation (archive/galaxy/perpetual/oath) --------------------
# (forge is wired by the Forge crew itself; only asserted present in --help.)

_DELEGATES = {
    "archive": climain.cmd_archive,
    "galaxy": climain.cmd_galaxy,
    "perpetual": climain.cmd_perpetual,
    "oath": climain.cmd_oath,
}


@pytest.mark.parametrize("pkg,cmd", list(_DELEGATES.items()))
def test_delegate_passes_argv_through(monkeypatch, pkg, cmd):
    import importlib

    mod = importlib.import_module(f"levi.{pkg}.__main__")
    seen = {}

    def fake(argv=None):
        seen["argv"] = list(argv or [])
        return 0

    monkeypatch.setattr(mod, "main", fake)
    cmd(argparse.Namespace(argv=["stats", "--limit", "5"]))
    assert seen["argv"] == ["stats", "--limit", "5"]


@pytest.mark.parametrize("pkg,cmd", list(_DELEGATES.items()))
def test_delegate_propagates_exit_code(monkeypatch, pkg, cmd):
    import importlib

    mod = importlib.import_module(f"levi.{pkg}.__main__")
    monkeypatch.setattr(mod, "main", lambda argv=None: 3)
    with pytest.raises(SystemExit) as exc:
        cmd(argparse.Namespace(argv=[]))
    assert exc.value.code == 3


# -- methods / revival shelf adapters -----------------------------------------


def test_methods_list_names_shelves(capsys):
    climain.cmd_methods(argparse.Namespace(methods_action="list", methods_name=None))
    out = capsys.readouterr().out
    assert "Methods warehouse" in out
    assert "loci" in out and "triz" in out


def test_methods_show_prints_doc(capsys):
    climain.cmd_methods(argparse.Namespace(methods_action="show", methods_name="loci"))
    assert "Method of Loci" in capsys.readouterr().out


def test_methods_show_unknown_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        climain.cmd_methods(
            argparse.Namespace(methods_action="show", methods_name="nope")
        )
    assert exc.value.code == 2


def test_revival_list_names_shelves(capsys):
    climain.cmd_revival(argparse.Namespace(revival_action="list", revival_name=None))
    out = capsys.readouterr().out
    assert "Revivals warehouse" in out
    assert "telescript" in out


# -- megazord status ------------------------------------------------------------


def test_megazord_status_checklist(monkeypatch, tmp_path, capsys):
    _herm_home(monkeypatch, tmp_path)
    climain.cmd_megazord(argparse.Namespace(megazord_action="status"))
    out = capsys.readouterr().out
    assert "MEGAZORD" in out
    for i in range(1, 11):
        assert f"axis {i:2d}:" in out, f"axis {i} missing"
    assert "lifepack format version:" in out
    assert "atlas path:" in out
    assert "warehouses:" in out
    assert "axes landed:" in out


# -- atlas / workflow / warehouse (defensive + live) -----------------------------


def test_atlas_export_grouped_by_warehouse(monkeypatch, tmp_path, capsys):
    _herm_home(monkeypatch, tmp_path)
    climain.cmd_atlas(argparse.Namespace(atlas_action="export", out=None))
    out = capsys.readouterr().out
    assert "warehouse" in out.lower()
    assert "methods" in out


def test_atlas_export_to_file(monkeypatch, tmp_path):
    _herm_home(monkeypatch, tmp_path)
    out = tmp_path / "atlas.json"
    climain.cmd_atlas(argparse.Namespace(atlas_action="export", out=str(out)))
    assert out.is_file()


def test_atlas_not_landed_is_honest(monkeypatch, capsys):
    _block_module(monkeypatch, "levi.interop.atlas")
    with pytest.raises(SystemExit) as exc:
        climain.cmd_atlas(argparse.Namespace(atlas_action="export", out=None))
    assert exc.value.code == 2
    assert "not yet landed" in capsys.readouterr().err


def test_workflow_list_shows_workflows(monkeypatch, tmp_path, capsys):
    _herm_home(monkeypatch, tmp_path)
    climain.cmd_workflow(argparse.Namespace(workflow_action="list", name=None))
    out = capsys.readouterr().out
    assert "hunt-archive-publish" in out


def test_workflow_run_without_name_exits_2(monkeypatch, tmp_path, capsys):
    _herm_home(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as exc:
        climain.cmd_workflow(argparse.Namespace(workflow_action="run", name=None))
    assert exc.value.code == 2


def test_workflow_not_landed_is_honest(monkeypatch, capsys):
    _block_module(monkeypatch, "levi.workflows")
    with pytest.raises(SystemExit) as exc:
        climain.cmd_workflow(argparse.Namespace(workflow_action="list", name=None))
    assert exc.value.code == 2
    assert "not yet landed" in capsys.readouterr().err


def test_warehouse_list_browse_inventory_pull(monkeypatch, tmp_path, capsys):
    _herm_home(monkeypatch, tmp_path)
    climain.cmd_warehouse(
        argparse.Namespace(warehouse_action="list", name=None, item=None, limit=20)
    )
    assert "LEVI warehouses" in capsys.readouterr().out

    climain.cmd_warehouse(
        argparse.Namespace(
            warehouse_action="browse", name="methods", item=None, limit=20
        )
    )
    out = capsys.readouterr().out
    assert "Methods Warehouse" in out

    climain.cmd_warehouse(
        argparse.Namespace(
            warehouse_action="inventory", name="methods", item=None, limit=3
        )
    )
    out = capsys.readouterr().out
    assert "methods.ach" in out

    climain.cmd_warehouse(
        argparse.Namespace(
            warehouse_action="pull", name="methods", item="methods.loci", limit=20
        )
    )
    out = capsys.readouterr().out
    assert "methods.loci" in out and "invoke" in out


def test_warehouse_pull_unknown_item_exits_1(monkeypatch, tmp_path, capsys):
    _herm_home(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as exc:
        climain.cmd_warehouse(
            argparse.Namespace(
                warehouse_action="pull", name="methods", item="methods.bogus", limit=20
            )
        )
    assert exc.value.code == 1
    assert "pull failed" in capsys.readouterr().err


def test_warehouse_not_landed_is_honest(monkeypatch, capsys):
    _block_module(monkeypatch, "levi.interop.warehouses")
    with pytest.raises(SystemExit) as exc:
        climain.cmd_warehouse(
            argparse.Namespace(warehouse_action="list", name=None, item=None, limit=20)
        )
    assert exc.value.code == 2
    assert "not yet landed" in capsys.readouterr().err


# -- bloodstream -----------------------------------------------------------------


def _fake_turn_result(**kw):
    base = dict(
        reply="fake reply",
        route="model",
        behavior="none",
        persona_id="normal",
        risk_level=1,
        trace_id="abc123",
        ok=True,
    )
    base.update(kw)
    res = SimpleNamespace(**base)
    res.stage_names = lambda: ["companion_ei", "persona", "governor"]
    return res


def test_bloodstream_turn_dispatches(monkeypatch, capsys):
    import levi.bloodstream.turn as _turn

    seen = {}

    def fake(text, ctx=None):
        seen["text"] = text
        return _fake_turn_result()

    monkeypatch.setattr(_turn, "run_turn", fake)
    climain.cmd_bloodstream(
        argparse.Namespace(bloodstream_action="turn", text=["hello", "levi"])
    )
    assert seen["text"] == "hello levi"
    out = capsys.readouterr().out
    assert "fake reply" in out and "abc123" in out


def test_bloodstream_bus_test_reports_stages(monkeypatch, capsys):
    import levi.bloodstream.turn as _turn

    monkeypatch.setattr(_turn, "run_turn", lambda text, ctx=None: _fake_turn_result())
    climain.cmd_bloodstream(argparse.Namespace(bloodstream_action="bus-test", text=[]))
    out = capsys.readouterr().out
    assert "bus-test: PASS" in out and "companion_ei" in out


def test_bloodstream_turn_without_text_exits_2(capsys):
    with pytest.raises(SystemExit) as exc:
        climain.cmd_bloodstream(argparse.Namespace(bloodstream_action="turn", text=[]))
    assert exc.value.code == 2


# -- factory status (production line + waymaker law) -------------------------------


def test_factory_status_stages_with_mocked_readers(monkeypatch, tmp_path, capsys):
    _herm_home(monkeypatch, tmp_path)
    from levi.perpetual import hunt as _hunt
    from levi.archive import store as _store
    from levi.galaxy import registry as _greg

    wave = SimpleNamespace(
        id="wave-001",
        theme_id="retired-software",
        completed_at="2026-09-15T00:00:00",
        findings_count=7,
        status="completed",
    )
    state = SimpleNamespace(waves=[wave], next_due="2026-09-16T05:00:00")
    monkeypatch.setattr(_hunt, "load_state", lambda *a, **k: state)
    monkeypatch.setattr(
        _hunt, "read_build_queue", lambda *a, **k: [{"wave": "wave-001"}] * 3
    )

    class _FakeStore:
        def count(self):
            return 42

    monkeypatch.setattr(_store, "ArchiveStore", _FakeStore)

    class _FakeReg:
        def __init__(self, home):
            pass

        def list(self):
            return [{"id": "p1"}, {"id": "p2"}]

    monkeypatch.setattr(_greg, "GalaxyRegistry", _FakeReg)
    # warehouses axis absent -> honest placeholder for the stocking stage.
    _block_module(monkeypatch, "levi.interop.warehouses")

    climain.cmd_factory_status(argparse.Namespace())
    out = capsys.readouterr().out
    assert "Waymaker law: where there isn't a way, LEVI creates one." in out
    assert "[intake]" in out and "waves completed: 1" in out
    assert "wave-001" in out and "7 findings" in out
    assert "[processing]" in out and "records: 42" in out
    assert "[manufacture]" in out and "queued builds: 3" in out
    assert "waymaker queue: not yet exposed" in out
    assert "[stocking]" in out and "not yet landed" in out
    assert "[distribution]" in out and "installed packages: 2" in out


def test_factory_status_waymaker_queue_live(monkeypatch, tmp_path, capsys):
    """If levi.workflows exposes waymaker_jobs, the count is shown."""
    _herm_home(monkeypatch, tmp_path)
    import levi.workflows as _wf

    monkeypatch.setattr(_wf, "waymaker_jobs", lambda: 5, raising=False)
    climain.cmd_factory_status(argparse.Namespace())
    assert "waymaker queue: 5 job(s)" in capsys.readouterr().out


# -- lifepack preview (gap fill) -----------------------------------------------------


def test_lifepack_preview_is_read_only(monkeypatch, tmp_path, capsys):
    from levi.lifepack import pack as _pack

    monkeypatch.setenv("HOME", str(tmp_path))
    home = tmp_path / ".levi"
    pack = _pack.export_pack(home)
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack), encoding="utf-8")
    before = sorted(home.rglob("*")) if home.exists() else []

    climain._cmd_lifepack_preview(
        argparse.Namespace(file=str(path), lifepack_action="preview")
    )
    out = capsys.readouterr().out
    assert "(preview only — nothing was written)" in out
    after = sorted(home.rglob("*")) if home.exists() else []
    assert before == after  # nothing written


def test_lifepack_preview_missing_file_exits_1(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(SystemExit) as exc:
        climain._cmd_lifepack_preview(
            argparse.Namespace(
                file=str(tmp_path / "nope.json"), lifepack_action="preview"
            )
        )
    assert exc.value.code == 1


# -- daemon services (axis 4, wired by axis 1) -----------------------------------------


def test_daemon_services_lists_catalog(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    climain.cmd_daemon_services(argparse.Namespace(action="services", target=None))
    out = capsys.readouterr().out
    assert "daemon services" in out
    assert "control-daemon" in out


def test_daemon_services_single_target(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    climain.cmd_daemon_services(
        argparse.Namespace(action="services", target="heartbeat")
    )
    out = capsys.readouterr().out
    assert "heartbeat:" in out
