"""Proof tests for the Vine/Digg loop-form module.

Laws: six seconds is a wall, the loop must close (declared loop point
with matching cue), bury never deletes.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

import levi.loopform as lf  # noqa: E402
from levi.loopform import Beat, LoopError, loop_script, make_loop, validate_loop  # noqa: E402


def _good_beats():
    return [
        Beat("phone buzzes on table", "huh?", 2.0),
        Beat("screen shows 47 missed calls", "from MOM", 2.0),
        Beat("phone buzzes on table", "", 2.0),  # the stitch: first frame again
    ]


def test_valid_loop_passes():
    loop = make_loop("callback", _good_beats(), loop_back_to=0,
                     loop_cue="phone buzzes on table")
    assert validate_loop(loop) == []
    assert loop.total_seconds == 6.0


def test_six_seconds_is_a_wall():
    beats = [Beat("a", seconds=2.5), Beat("b", seconds=2.5), Beat("c", seconds=2.0)]
    with pytest.raises(LoopError, match="six seconds is a wall"):
        make_loop("too long", beats, loop_back_to=0, loop_cue="a")


def test_loop_must_close():
    beats = _good_beats()
    with pytest.raises(LoopError, match="does not close"):
        make_loop("open", beats, loop_back_to=0, loop_cue="wrong cue")


def test_loop_back_to_must_point_at_a_beat():
    with pytest.raises(LoopError, match="points at no beat"):
        make_loop("bad", _good_beats(), loop_back_to=9, loop_cue="x")


def test_beat_needs_cue_and_sane_length():
    with pytest.raises(LoopError):
        Beat("", seconds=2.0)
    with pytest.raises(LoopError):
        Beat("x", seconds=0)
    with pytest.raises(LoopError):
        Beat("x", seconds=7)


def test_script_shows_loop_point():
    loop = make_loop("callback", _good_beats(), loop_back_to=0,
                     loop_cue="phone buzzes on table")
    script = loop_script(loop)
    assert "LOOP POINT" in script
    assert "6.0s loop" in script


# ------------------------------------------------------------------ Digg


@pytest.fixture()
def _store(tmp_path, monkeypatch):
    from levi.shelf.shelf import ShelfStore

    store = ShelfStore(shelf_dir=tmp_path / "shelf")
    monkeypatch.setattr(lf, "_shelf", lambda: store)
    return store


def test_digg_and_bury_round_trip(_store):
    item = _store.add("https://example.com/a", title="A")
    lf.digg(item.id)
    assert _store.get(item.id).starred is True
    lf.bury(item.id)
    assert _store.get(item.id).buried is True
    lf.unbury(item.id)
    lf.undigg(item.id)
    after = _store.get(item.id)
    assert after.buried is False and after.starred is False
    assert after.title == "A"  # the item survives bury, byte-for-byte


def test_frontpage_excludes_buried_orders_starred_first(_store):
    a = _store.add("https://example.com/a", title="A")
    b = _store.add("https://example.com/b", title="B")
    c = _store.add("https://example.com/c", title="C")
    lf.digg(b.id)
    lf.bury(c.id)
    page = lf.frontpage()
    titles = [i["title"] for i in page]
    assert titles[0] == "B"  # starred first
    assert "C" not in titles  # buried: off the page, not deleted
    assert _store.get(c.id).title == "C"  # still on the shelf
