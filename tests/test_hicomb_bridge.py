"""Hicomb Android bridge tests — the exact JSON API the APK's Java shell
calls. Hermetic: temp workspace, no network, no device.

Laws:
  1. Every bridge function returns parseable JSON (or plain text for alpha_plan).
  2. Dry-run (qp_scan / qp_suggest) never writes to the workspace.
  3. qp_apply writes only through the engine's guarded flow and leaves a backup.
  4. surgeon_repair only touches the target file and always leaves a .elite.bak.
  5. alpha_build writes only under builds/<name>/.
"""

import importlib.util
import json
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BRIDGE_SRC = REPO / "apps" / "hicomb-android" / "python-src" / "hicomb_bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("hicomb_bridge_test", BRIDGE_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bridge(tmp_path):
    mod = load_bridge()
    ws = tmp_path / "ws"
    assert mod.set_workspace(str(ws)) == "true"
    assert mod.seed_workspace() == json.dumps({"ok": True})
    mod.qp_set_target(False)
    return mod, ws


def snapshot(ws: Path) -> dict:
    return {
        p.relative_to(ws).as_posix(): p.read_bytes()
        for p in ws.rglob("*")
        if p.is_file()
    }


def test_files_roundtrip(bridge):
    mod, ws = bridge
    files = json.loads(mod.list_files())
    assert "main.py" in files and "notes.md" in files

    assert json.loads(mod.write_file("sub/dir.py", "x = 1\n"))["ok"] is True
    rd = json.loads(mod.read_file("sub/dir.py"))
    assert rd["ok"] is True and rd["text"] == "x = 1\n"
    assert rd["language"] == "python"


def test_highlight_spans_shape(bridge):
    mod, ws = bridge
    spans = json.loads(mod.highlight_spans("main.py", 'def f():\n    return "hi" # c\n'))
    assert isinstance(spans, list) and spans
    for st, en, kind in spans:
        assert isinstance(st, int) and isinstance(en, int) and en > st
        assert isinstance(kind, str) and kind != "plain"


def test_search(bridge):
    mod, ws = bridge
    hits = json.loads(mod.search_in_file("main.py", "greet"))
    assert hits and all(len(h) == 2 for h in hits)
    assert json.loads(mod.search_in_file("main.py", "zzz-no-such-token")) == []


def test_themes(bridge):
    mod, ws = bridge
    names = json.loads(mod.theme_list())
    assert "void" in names
    t = json.loads(mod.theme_get("void"))
    assert "ui" in t and "syntax" in t and t["syntax"]


def test_qp_dry_run_never_writes(bridge):
    mod, ws = bridge
    mod.qp_set_target(True)
    before = snapshot(ws)
    out = json.loads(mod.qp_scan())
    assert out["ok"] is True and isinstance(out["results"], list)
    after = snapshot(ws)
    # Engine bookkeeping (.qp store) may exist; project files must be untouched.
    proj_before = {k: v for k, v in before.items() if not k.startswith(".qp")}
    proj_after = {k: v for k, v in after.items() if not k.startswith(".qp")}
    assert proj_before == proj_after


def test_qp_apply_guarded_with_backup(bridge):
    mod, ws = bridge
    target = ws / "messy.py"
    target.write_text(
        "result = []\nfor i in range(10):\n    result.append(i * 2)\n", encoding="utf-8"
    )
    sug = json.loads(mod.qp_suggest("messy.py"))
    assert sug["ok"] is True
    res = json.loads(mod.qp_apply("messy.py"))
    assert res["ok"] is True and res["applied"] is True
    # guarded flow leaves the timestamped backup beside the file's store
    hist = json.loads(mod.qp_history("messy.py"))
    assert hist["ok"] is True and len(hist["backups"]) >= 1
    assert all(b.startswith("messy.py_") and b.endswith(".bak") for b in hist["backups"])


def test_qp_iterate_terminates(bridge):
    mod, ws = bridge
    mod.qp_set_target(True)
    (ws / "it.py").write_text("x=1\nprint( x )\n", encoding="utf-8")
    out = json.loads(mod.qp_iterate(3))
    assert out["ok"] is True
    assert 1 <= out["passes"] <= 3
    assert isinstance(out["log"], list)


def test_surgeon_check_and_repair(bridge):
    mod, ws = bridge
    bad = ws / "broken.py"
    bad.write_text("def f(:\n    pass\n", encoding="utf-8")
    chk = json.loads(mod.surgeon_check_text(bad.read_text()))
    assert chk["ok"] is True and chk["error"]

    good = json.loads(mod.surgeon_check_text("x = 1\n"))
    assert good["ok"] is True and not good["error"]

    rep = json.loads(mod.surgeon_repair("broken.py"))
    assert rep["ok"] is True
    assert isinstance(rep["fixes"], list)
    assert (ws / "broken.py.elite.bak").exists()


def test_alpha_build_scoped(bridge):
    mod, ws = bridge
    before = set(snapshot(ws))
    plan = mod.alpha_plan("a tiny landing page", "static", "landing")
    assert "landing" in plan
    out = json.loads(mod.alpha_build("a tiny landing page", "static", "landing"))
    assert out["ok"] is True
    assert out["dest"] == "builds/landing" and out["files"]
    after = set(snapshot(ws))
    new = {k for k in (after - before) if not k.startswith(".qp")}
    assert new and all(k.startswith("builds/landing/") for k in new)


def test_laws_are_built_in(bridge):
    """The operating laws ship inside the app, not just in docs."""
    mod, ws = bridge
    laws = json.loads(mod.laws())
    names = [law["name"] for law in laws]
    assert names == [
        "law-guard-prove",
        "originals-first",
        "honesty-over-polish",
        "nothing-thrown-away",
        "one-organism",
    ]
    assert all(law["text"].strip() for law in laws)


def test_alpha_originals_first(bridge):
    """An existing original is never overwritten — the build is refused loudly."""
    mod, ws = bridge
    first = json.loads(mod.alpha_build("a tiny page", "static", "site"))
    assert first["ok"] is True
    dest = ws / first["dest"]
    before = {
        p.relative_to(ws).as_posix(): p.read_bytes()
        for p in dest.rglob("*")
        if p.is_file()
    }
    assert before, "expected the first build to write files"
    second = json.loads(mod.alpha_build("a DIFFERENT idea", "static", "site"))
    assert second["ok"] is False
    assert second["error"] == "original exists"
    assert "never overwritten" in second["detail"]
    after = {
        p.relative_to(ws).as_posix(): p.read_bytes()
        for p in dest.rglob("*")
        if p.is_file()
    }
    assert before == after, "the original must stand untouched"
