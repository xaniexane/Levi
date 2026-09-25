"""Tests for levi.circles — Dunbar-bounded trust circles."""

from __future__ import annotations

import os
import stat

import pytest

from levi.circles import CircleError, LAYERS
from levi.circles.model import CircleStore, cap_for, layer_names


@pytest.fixture()
def store(tmp_path):
    return CircleStore(home=tmp_path)


def test_layer_names_and_caps():
    assert layer_names() == ["inner", "close", "friends", "tribe"]
    assert dict(LAYERS) == {"inner": 5, "close": 15, "friends": 50, "tribe": 150}
    assert cap_for("inner") == 5
    with pytest.raises(CircleError):
        cap_for("strangers")


def test_add_and_list(store):
    m = store.add("alice", name="Alice", layer="inner")
    assert m.id == "alice" and m.layer == "inner"
    assert [x.id for x in store.members("inner")] == ["alice"]


def test_inner_cap_is_hard(store):
    for i in range(5):
        store.add("p%d" % i, layer="inner")
    with pytest.raises(CircleError) as ei:
        store.add("p5", layer="inner")
    assert "FULL" in str(ei.value)
    assert store.layer_count("inner") == 5


def test_other_layers_have_own_caps(store):
    # close layer cap 15: fill inner to its cap, close still accepts
    for i in range(5):
        store.add("i%d" % i, layer="inner")
    with pytest.raises(CircleError):
        store.add("i5", layer="inner")
    store.add("c0", layer="close")  # independent cap, not blocked
    assert store.layer_count("close") == 1


def test_duplicate_and_bad_ids_refused(store):
    store.add("bob", layer="close")
    with pytest.raises(CircleError):
        store.add("bob", layer="close")
    with pytest.raises(CircleError):
        store.add("not a valid id!!", layer="close")


def test_remove_frees_headroom(store):
    for i in range(5):
        store.add("p%d" % i, layer="inner")
    with pytest.raises(CircleError):
        store.add("p5", layer="inner")
    store.remove("p0")
    store.add("p5", layer="inner")  # now fits
    assert store.layer_count("inner") == 5
    with pytest.raises(CircleError):
        store.remove("nobody")


def test_move_respects_caps(store):
    for i in range(5):
        store.add("i%d" % i, layer="inner")
    store.add("c0", layer="close")
    with pytest.raises(CircleError):
        store.move("c0", "inner")  # inner is full
    moved = store.move("c0", "tribe")
    assert moved.layer == "tribe"
    with pytest.raises(CircleError):
        store.move("ghost", "close")


def test_share_records_member_snapshot(store):
    store.add("a", layer="friends")
    store.add("b", layer="friends")
    store.add("z", layer="inner")
    r = store.share("hello", "body text", "friends")
    assert r.id.startswith("shr-")
    assert r.member_ids == ["a", "b"]  # snapshot of that circle only
    assert r.layer == "friends"
    with pytest.raises(CircleError):
        store.share("   ", "no title", "friends")
    with pytest.raises(CircleError):
        store.share("x", "", "strangers")


def test_audit_headroom(store):
    store.add("a", layer="inner")
    rows = {r["layer"]: r for r in store.audit()}
    assert rows["inner"]["used"] == 1
    assert rows["inner"]["headroom"] == 4
    assert rows["inner"]["full"] is False
    assert rows["close"]["used"] == 0
    assert rows["tribe"]["cap"] == 150


def test_persistence_round_trip(tmp_path):
    s1 = CircleStore(home=tmp_path)
    s1.add("alice", name="Alice", layer="inner")
    s1.share("note", "body", "inner")
    s2 = CircleStore(home=tmp_path)
    assert [m.id for m in s2.members("inner")] == ["alice"]
    assert s2.shares("inner")[0].title == "note"
    assert s2.shares("inner")[0].member_ids == ["alice"]


def test_store_file_permissions(tmp_path):
    s = CircleStore(home=tmp_path)
    s.add("alice", layer="inner")
    f = tmp_path / "circles" / "circles.json"
    mode = stat.S_IMODE(os.stat(f).st_mode)
    assert mode == 0o600
    assert stat.S_IMODE(os.stat(tmp_path / "circles").st_mode) == 0o700


def test_corrupt_store_fails_closed(tmp_path):
    d = tmp_path / "circles"
    d.mkdir(parents=True)
    (d / "circles.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(CircleError):
        CircleStore(home=tmp_path)
