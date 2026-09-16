"""Hermetic tests for levi.canvas: tmp HOME, no network."""

import json
import tarfile

import pytest

from levi.canvas import SHELF
from levi.canvas.artifacts import ArtifactStore, CanvasError


@pytest.fixture()
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)
    return tmp_path / ".levi" / "canvas"


@pytest.fixture()
def store(home):
    return ArtifactStore(home)


def test_shelf_shape():
    assert SHELF["name"] and SHELF["summary"] and len(SHELF["items"]) >= 3


def test_create_and_show(store):
    store.create("essay", "doc", "My essay", content="first draft")
    got = store.get("essay")
    assert got["content"] == "first draft"
    assert got["version"]["n"] == 1
    assert got["title"] == "My essay"


def test_create_validates(store):
    with pytest.raises(CanvasError):
        store.create("essay", "video", "nope")
    with pytest.raises(CanvasError):
        store.create("essay", "doc", "ok")
        store.create("essay", "doc", "dup")
    with pytest.raises(CanvasError):
        store.create("../evil", "doc", "nope")


def test_edit_appends_immutable_versions(store):
    store.create("essay", "doc", "My essay", content="v1 text")
    n = store.edit("essay", "v2 text", note="tightened")
    assert n == 2
    assert store.get("essay", 1)["content"] == "v1 text"  # history intact
    assert store.get("essay", 2)["content"] == "v2 text"
    assert store.get("essay")["content"] == "v2 text"  # latest by default
    versions = store.versions("essay")
    assert [v["n"] for v in versions] == [1, 2]
    assert versions[1]["note"] == "tightened"


def test_diff(store):
    store.create("plan", "plan", "Launch", content="a\nb\nc\n")
    store.edit("plan", "a\nB2\nc\nd\n")
    d = store.diff("plan", 1, 2)
    assert "-b" in d and "+B2" in d and "+d" in d
    assert "plan@v1" in d and "plan@v2" in d
    assert store.diff("plan", 2, 2) == "(no differences)"


def test_diff_unknown_version(store):
    store.create("x", "doc", "X", content="hi")
    with pytest.raises(CanvasError):
        store.diff("x", 1, 9)


def test_rename_list_delete(store):
    store.create("a", "code", "Script", content="print(1)")
    store.create("b", "doc", "Note", content="n")
    store.rename("a", "Better script")
    ids = {i["id"]: i for i in store.list()}
    assert ids["a"]["title"] == "Better script"
    assert ids["a"]["versions"] == 1
    assert store.delete("a") is True
    assert store.delete("a") is False
    assert [i["id"] for i in store.list()] == ["b"]


def test_export_bundle(store, tmp_path):
    store.create("essay", "doc", "My essay", content="draft one")
    store.edit("essay", "draft two", note="revision")
    dest = tmp_path / "essay.levi-canvas.tar.gz"
    store.export("essay", dest)
    assert dest.exists()
    with tarfile.open(dest, "r:gz") as tf:
        names = tf.getnames()
        assert "manifest.json" in names
        assert "versions/v0001.md" in names
        assert "versions/v0002.md" in names
        manifest = json.loads(tf.extractfile("manifest.json").read())
        assert manifest["format"] == "levi-canvas/1"
        assert len(manifest["versions"]) == 2
        assert tf.extractfile("versions/v0001.md").read().decode() == "draft one"


def test_cli_roundtrip(home, capsys, monkeypatch):
    from levi.canvas.__main__ import main

    monkeypatch.setenv("LEVI_HOME", str(home.parent))
    assert (
        main(
            ["new", "cli", "--type", "plan", "--title", "CLI plan", "--text", "step 1"]
        )
        == 0
    )
    assert main(["edit", "cli", "--text", "step 1\nstep 2", "--note", "more"]) == 0
    assert main(["show", "cli"]) == 0
    assert "step 2" in capsys.readouterr().out
    assert main(["diff", "cli", "1", "2"]) == 0
    assert "+step 2" in capsys.readouterr().out
    assert main(["versions", "cli"]) == 0
    assert "v2" in capsys.readouterr().out
    dest = str(home.parent / "cli.tar.gz")
    assert main(["export", "cli", dest]) == 0
    assert main(["list"]) == 0
    assert "cli" in capsys.readouterr().out
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
