"""Tests for levi.games.league — arcade cabinets and attract mode."""

from __future__ import annotations

import io

import pytest

from levi.games import league
from levi.games.charter import check_manifest


def _table(tmp_path, game="tictactoe", **kw):
    return league.ScoreTable(game, root=tmp_path / "league", **kw)


def test_sanitize_initials_ok():
    assert league.sanitize_initials("abc") == "ABC"
    assert league.sanitize_initials("R2D") == "R2D"


@pytest.mark.parametrize(
    "bad", ["", "ab", "abcd", "a b", "a!b", "12", "abcdef", 42, None]
)
def test_sanitize_initials_deny_closed(bad):
    with pytest.raises(league.LeagueError):
        league.sanitize_initials(bad)


def test_submit_and_rank(tmp_path):
    t = _table(tmp_path)
    r = t.submit("AAA", 100)
    assert r == 0
    r = t.submit("BBB", 200)
    assert r == 0
    assert [e.initials for e in t.table()] == ["BBB", "AAA"]


def test_lower_wins(tmp_path):
    t = _table(tmp_path, higher_is_better=False)
    t.submit("AAA", 30)
    t.submit("BBB", 10)
    assert [e.initials for e in t.table()] == ["BBB", "AAA"]


def test_table_trimmed_to_limit(tmp_path):
    t = _table(tmp_path, limit=3)
    for i in range(5):
        t.submit("P%02d" % i, i * 10)
    assert len(t.table()) == 3
    assert t.table()[0].score == 40


def test_submit_off_table_returns_minus_one(tmp_path):
    t = _table(tmp_path, limit=1)
    t.submit("AAA", 100)
    assert t.submit("BBB", 1) == -1


def test_submit_bad_score_type_refused(tmp_path):
    t = _table(tmp_path)
    with pytest.raises(league.LeagueError):
        t.submit("AAA", "lots")


def test_submit_bad_provenance_refused(tmp_path):
    t = _table(tmp_path)
    with pytest.raises(league.LeagueError):
        t.submit("AAA", 5, provenance="cloud")


def test_rank_of_does_not_submit(tmp_path):
    t = _table(tmp_path, limit=1)
    t.submit("AAA", 100)
    assert t.rank_of("BBB", 200) == 0
    assert len(t.table()) == 1
    assert t.rank_of("CCC", 1) == -1


def test_verified_and_seed_preserved(tmp_path):
    t = _table(tmp_path)
    t.submit("AAA", 50, seed=7, replay="0,4,8", verified=True)
    e = t.table()[0]
    assert e.verified and e.seed == 7 and e.replay == "0,4,8"


def test_persistence_round_trip(tmp_path):
    root = tmp_path / "league"
    t1 = league.ScoreTable("nim", root=root)
    t1.submit("ZZZ", 42)
    t2 = league.ScoreTable("nim", root=root)
    assert len(t2.table()) == 1 and t2.table()[0].initials == "ZZZ"


def test_files_owner_only(tmp_path):
    import os

    t = _table(tmp_path)
    t.submit("AAA", 1)
    mode = os.stat(t._path()).st_mode & 0o777
    assert mode == 0o600


def test_corrupt_table_refused(tmp_path):
    root = tmp_path / "league"
    root.mkdir(parents=True)
    (root / "tictactoe.json").write_text("{nope")
    with pytest.raises(league.LeagueError):
        league.ScoreTable("tictactoe", root=root)


def test_attract_plays_real_games():
    out = io.StringIO()
    winners = league.attract("tictactoe", rounds=2, seed=1, out=out)
    assert len(winners) == 2
    assert all(w in (0, 1, -1) for w in winners)
    text = out.getvalue()
    assert "attract tictactoe round 1" in text
    assert "PIX" in text or "BIT" in text or "DRAW" in text


def test_attract_unknown_game_refused():
    with pytest.raises(league.LeagueError):
        league.attract("pong", out=io.StringIO())


def test_attract_seeded_deterministic():
    a = io.StringIO()
    b = io.StringIO()
    league.attract("nim", rounds=2, seed=9, out=a)
    league.attract("nim", rounds=2, seed=9, out=b)
    assert a.getvalue() == b.getvalue()


def test_render_table_empty():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        t = league.ScoreTable("empty-game", root=Path(d))
        assert "empty" in league.render_table(t)


def test_league_manifest_passes_charter():
    problems = check_manifest(league.MANIFEST)
    assert problems == [], problems


def test_cli_table_and_submit(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    league.main(["submit", "bagatelle", "REX", "250"])
    league.main(["table", "bagatelle"])
    text = capsys.readouterr().out
    assert "REX" in text and "250" in text


def test_clear(tmp_path):
    t = _table(tmp_path)
    t.submit("AAA", 5)
    t.clear()
    assert t.table() == []
