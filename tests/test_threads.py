"""Hermetic tests for levi.threads — no network, tmp HOME."""

from __future__ import annotations


import pytest

from levi.threads import SHELF
from levi.threads.threads import ThreadError, ThreadStore
from levi.threads.__main__ import main


def _herm(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LEVI_HOME", raising=False)


def _seed(store: ThreadStore):
    """Two camps; factional comment with MORE raw upvotes vs bridging comment
    with cross-camp upvotes."""
    d = store.new_discussion("test", discussion_id="d1", community_id="haven")
    factional = store.add_comment("d1", "a1", "our side is right and that's that")
    bridge = store.add_comment(
        "d1", "b1", "both sides make fair points; here's the evidence"
    )
    for v in ("a1", "a2", "a3", "a4"):
        store.vote("d1", factional.id, v, "up")
    store.vote("d1", factional.id, "b1", "down")  # net +3, 4 up-votes
    for v in ("a1", "b1", "b2"):
        store.vote("d1", bridge.id, v, "up")  # net +3, 3 up-votes, cross-camp
    return d, factional, bridge


def test_shelf_shape():
    assert SHELF["name"] == "threads"
    assert SHELF["summary"]
    assert isinstance(SHELF["items"], list) and SHELF["items"]


def test_bridging_beats_raw_upvotes(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = ThreadStore()
    _, factional, bridge = _seed(store)
    store.set_rank_weight("quality", 0.0)
    store.set_rank_weight("bridging", 1.0)
    rows = store.rank("d1")
    by_id = {r["comment"].id: r for r in rows}
    # cross-camp comment outranks the factional one despite fewer raw up-votes
    assert by_id[bridge.id]["score"] > by_id[factional.id]["score"]
    assert rows[0]["comment"].id == bridge.id


def test_ranking_is_explainable(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = ThreadStore()
    _seed(store)
    rows = store.rank("d1")
    for r in rows:
        assert 0.0 <= r["score"] <= 1.0 + 1e-9
        assert 0.0 <= r["bridging"] <= 1.0
        assert abs(r["score"] - (0.5 * r["quality"] + 0.5 * r["bridging"])) < 1e-9


def test_threading_and_depth(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = ThreadStore()
    store.new_discussion("t", discussion_id="d1")
    top = store.add_comment("d1", "u1", "top level")
    reply = store.add_comment("d1", "u2", "a reply", parent_id=top.id)
    rows = store.rank("d1")
    depths = {r["comment"].id: r["depth"] for r in rows}
    assert depths[top.id] == 0 and depths[reply.id] == 1
    tree = store.render_tree("d1")
    assert "top level" in tree and "a reply" in tree
    with pytest.raises(ThreadError):
        store.add_comment("d1", "u3", "orphan", parent_id="nope")


def test_profile_export_verify_roundtrip(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = ThreadStore()
    store.new_profile("ada", "Ada", bio="test pilot")
    doc = store.export_profile("ada")
    assert doc["format"] == "levi-profile/1"
    assert doc["algorithm"] == "HMAC-SHA256"
    assert store.verify_profile(doc).display_name == "Ada"


def test_profile_tamper_detected(monkeypatch, tmp_path):
    _herm(monkeypatch, tmp_path)
    store = ThreadStore()
    store.new_profile("ada", "Ada")
    doc = store.export_profile("ada")
    doc["profile"]["display_name"] = "Mallory"
    with pytest.raises(ThreadError, match="signature mismatch"):
        store.verify_profile(doc)


def test_profile_key_is_owner_only(monkeypatch, tmp_path):
    import stat

    _herm(monkeypatch, tmp_path)
    store = ThreadStore()
    store.new_profile("ada", "Ada")
    store.export_profile("ada")  # generates the key
    mode = stat.S_IMODE(
        (tmp_path / ".levi" / "threads" / "identity.key").stat().st_mode
    )
    assert mode == 0o600


def test_cli_roundtrip(monkeypatch, tmp_path, capsys):
    _herm(monkeypatch, tmp_path)
    assert main(["new", "--title", "Hello", "--id", "d9"]) == 0
    assert main(["reply", "d9", "--author", "ada", "--text", "first!"]) == 0
    assert main(["tree", "d9"]) == 0
    assert "Hello" in capsys.readouterr().out
    assert main(["profile-new", "ada", "--name", "Ada"]) == 0
    out = tmp_path / "ada.profile.json"
    assert main(["profile-export", "ada", "--out", str(out)]) == 0
    assert main(["profile-verify", "--in", str(out)]) == 0
    assert "VALID" in capsys.readouterr().out
    # explain path
    store = ThreadStore()
    cid = next(iter(store.comments["d9"]))
    assert main(["explain", "d9", cid[:8]]) == 0
    assert "bridging=" in capsys.readouterr().out
