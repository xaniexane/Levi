"""Quetta-Pan standalone bridge tests — the JSON API behind the QP APK.

Laws:
  1. scan (dry-run) never writes project files.
  2. Every apply path requires the call itself (the UI gates on explicit taps);
     the engine still backs up before writing and guard-evaluates after.
  3. iterate terminates and reports passes/applied/log.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BRIDGE_SRC = REPO / "apps" / "quetta-pan-android" / "python-src" / "qp_bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("qp_bridge_test", BRIDGE_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bridge(tmp_path):
    mod = load_bridge()
    ws = tmp_path / "ws"
    assert mod.set_workspace(str(ws)) == "true"
    assert mod.seed_workspace() == json.dumps({"ok": True})
    return mod, ws


def test_scan_is_read_only(bridge):
    mod, ws = bridge
    before = {
        p.relative_to(ws).as_posix(): p.read_bytes()
        for p in ws.rglob("*") if p.is_file() and ".qp" not in p.parts
    }
    out = json.loads(mod.scan())
    assert out["ok"] is True and isinstance(out["results"], list)
    after = {
        p.relative_to(ws).as_posix(): p.read_bytes()
        for p in ws.rglob("*") if p.is_file() and ".qp" not in p.parts
    }
    assert before == after


def test_detail_shape(bridge):
    mod, ws = bridge
    out = json.loads(mod.detail("sample.py"))
    assert out["ok"] is True
    sug = out["suggestion"]
    assert isinstance(sug["suggestions"], list)
    assert isinstance(sug["diff"], str)


def test_apply_one_and_iterate(bridge):
    mod, ws = bridge
    (ws / "t.py").write_text("def add(a,b):\n    return a+b\n", encoding="utf-8")
    res = json.loads(mod.apply_one("t.py"))
    assert res["ok"] is True
    assert (ws / "t.py").exists()

    out = json.loads(mod.iterate(2))
    assert out["ok"] is True
    assert 1 <= out["passes"] <= 2
    assert isinstance(out["applied"], int) and isinstance(out["log"], list)


def test_apply_all_reports(bridge):
    mod, ws = bridge
    out = json.loads(mod.apply_all())
    assert out["ok"] is True
    assert isinstance(out["applied"], int) and isinstance(out["failed"], int)
    assert isinstance(out["details"], list)


def test_laws_are_built_in(bridge):
    """The operating laws ship inside the app, not just in docs."""
    mod, ws = bridge
    laws = json.loads(mod.laws())
    names = [law["name"] for law in laws]
    assert names == [
        "law-guard-prove",
        "honesty-over-polish",
        "nothing-thrown-away",
        "one-organism",
    ]
    assert all(law["text"].strip() for law in laws)
