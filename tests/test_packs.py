"""Hermetic tests for levi.packs.

No network (packs are pure files), no real HOME: PackStore() resolves
paths at call time, so monkeypatched HOME isolates everything.
"""

from __future__ import annotations

import json

import pytest

from levi.packs.__main__ import main as cli_main
from levi.packs.packs import PackError, PackStore, validate_manifest


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return PackStore()


def _write(st, name, instructions="do the thing", content=None, scope=None):
    d = st.init(name, scope=scope)
    (d / "instructions.md").write_text(instructions)
    if content:
        (d / "content" / "notes.md").write_text(content)
    return d


# --------------------------------------------------------------------------
# init / validation
# --------------------------------------------------------------------------


def test_init_creates_structure(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    d = st.init("research", "my research pack")
    assert (d / "manifest.json").exists()
    assert (d / "instructions.md").exists()
    assert (d / "content").is_dir()
    m = json.loads((d / "manifest.json").read_text())
    assert m["format"] == "levi_pack_v1" and m["name"] == "research"


def test_init_duplicate_rejected(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.init("x")
    with pytest.raises(PackError):
        st.init("x")


def test_bad_names_rejected(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    for bad in ["../evil", ".hidden", "-dash", "has space", ""]:
        with pytest.raises(PackError):
            st.init(bad)


def test_validate_manifest_rejects_junk():
    with pytest.raises(PackError):
        validate_manifest({"name": "x"})  # no format
    with pytest.raises(PackError):
        validate_manifest({"format": "other", "name": "x"})
    with pytest.raises(PackError):
        validate_manifest(
            {"format": "levi_pack_v1", "name": "x", "scope": {"tags": "notalist"}}
        )


def test_broken_pack_skipped_not_fatal(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    st.init("good")
    (st.root / "broken").mkdir()  # no manifest
    assert [p.name for p in st.list_packs()] == ["good"]


# --------------------------------------------------------------------------
# scoping
# --------------------------------------------------------------------------


def test_always_scope(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    _write(st, "a", scope={"always": True})
    asm = st.assemble()
    assert [p["name"] for p in asm["packs"]] == ["a"]
    assert asm["packs"][0]["rule"] == "always"


def test_project_scope(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    _write(st, "levi", scope={"projects": ["levi"]})
    assert st.assemble(project="levi")["packs"]
    assert not st.assemble(project="other")["packs"]


def test_path_glob_scope(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    _write(st, "code", scope={"paths": ["*/workspace/*"]})
    assert st.assemble(cwd="/home/u/workspace/levi")["packs"]
    assert not st.assemble(cwd="/tmp")["packs"]


def test_tag_scope_precedence(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    _write(st, "ops", scope={"tags": ["ops"], "always": True})
    asm = st.assemble(tags=["ops"])
    assert asm["packs"][0]["rule"] == "tags"  # tags beats always


def test_priority_ordering(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    d1 = st.init("zz", scope={"always": True})
    _d2 = st.init("aa", scope={"always": True})
    m = json.loads((d1 / "manifest.json").read_text())
    m["priority"] = 1
    (d1 / "manifest.json").write_text(json.dumps(m))
    asm = st.assemble()
    assert [p["name"] for p in asm["packs"]] == ["zz", "aa"]


def test_assembly_has_provenance_and_instructions(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    _write(st, "kb", instructions="be terse", content="fact: sky is blue")
    asm = st.assemble(project=None)
    # always=False default -> need tags to match; fix scope instead
    assert asm["packs"] == []
    d = st.root / "kb"
    m = json.loads((d / "manifest.json").read_text())
    m["scope"]["always"] = True
    (d / "manifest.json").write_text(json.dumps(m))
    asm = st.assemble()
    assert "# pack: kb" in asm["text"]
    assert "be terse" in asm["text"]
    assert "sky is blue" in asm["text"]


def test_budget_truncation_reported(monkeypatch, tmp_path):
    st = _herm(monkeypatch, tmp_path)
    _write(st, "big", instructions="i", content="x" * 1000, scope={"always": True})
    asm = st.assemble(budget_chars=50)
    assert asm["truncated"]
    assert "truncated" in asm["text"]


def test_instructions_never_truncated_silently(monkeypatch, tmp_path):
    # instructions are always fully included; only content is budgeted
    st = _herm(monkeypatch, tmp_path)
    _write(
        st,
        "big",
        instructions="CRITICAL: always obey",
        content="y" * 5000,
        scope={"always": True},
    )
    asm = st.assemble(budget_chars=60)
    assert "CRITICAL: always obey" in asm["text"]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_cli_init_list_assemble(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert cli_main(["init", "dev", "--scope-always"]) == 0
    assert cli_main(["list"]) == 0
    assert "dev" in capsys.readouterr().out
    assert cli_main(["assemble"]) == 0
    out = capsys.readouterr().out
    assert "# pack: dev" in out


def test_cli_validate_and_delete(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert cli_main(["init", "dev"]) == 0
    assert cli_main(["validate"]) == 0
    assert "ok: dev" in capsys.readouterr().out
    assert cli_main(["delete", "dev"]) == 0
    capsys.readouterr()
    assert cli_main(["list"]) == 0
    assert "dev" not in capsys.readouterr().out


def test_cli_show_missing_fails(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    assert cli_main(["show", "nope"]) == 1
