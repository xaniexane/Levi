"""Tests for the Buzz Tunes SI DJ + Ultimate Mix Engine + Spotify seam.

Laws under test:
  DJ-L1 honest catalog — every picked track comes from the passed catalog.
  DJ-L2 nano-first, fallback-clean — voice attempted via nano-bit seat;
          refusal/error falls back; path recorded; never raises.
  DJ-L3 deterministic — same inputs + catalog => same pick.
  F-L1 uniqueness — 20,000 forged playlists => 20,000 unique hashes.
  F-L2 non-generic — every concept has >= 5 taxonomy tokens, no banned
          generic fragments, no trailing numbers.
  F-L3 honest catalog — every forged track id is in the source catalog;
          empty catalog refuses (no empty shells, no invented songs).
  F-L4 determinism — same seed + catalog => identical forge.
  F-L5 cap — counts < 1 or > 20,000 refuse.
  S-L1 seam honesty — configured() is False; play/search raise
          SpotifyNotConfigured with a linkage contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from levi.buzztunes import dj as DJ
from levi.buzztunes import forge as F
from levi.buzztunes import youtube as YT
from levi.buzztunes.cli import cmd_buzztunes
from levi.buzztunes.engine import BuzzEngine
from levi.buzztunes.providers import FakeProvider, Track


def _catalog() -> list[Track]:
    return FakeProvider().search("", limit=10000)


def _args(**kw):
    class A:
        pass
    a = A()
    for k, v in kw.items():
        setattr(a, k, v)
    return a


# ---------------------------------------------------------------- DJ

def test_dj_pick_honest_and_deterministic(tmp_path):
    cat = _catalog()
    p1 = DJ.pick_song("rainy-night", "coding", cat, energy="low",
                      era="2010s")
    p2 = DJ.pick_song("rainy-night", "coding", cat, energy="low",
                      era="2010s")
    assert p1.track.id == p2.track.id  # DJ-L3
    assert p1.track.id in {t.id for t in cat}  # DJ-L1
    assert p1.voice_line.strip()
    assert p1.reason.strip()
    assert "coding" in p1.concept and "rainy-night" in p1.concept
    assert p1.voice_path in ("nano-bit", "dj-fallback")  # DJ-L2


def test_dj_pick_requires_inputs_and_catalog():
    cat = _catalog()
    with pytest.raises(ValueError):
        DJ.pick_song("", "coding", cat)
    with pytest.raises(ValueError):
        DJ.pick_song("rainy-night", "", cat)
    with pytest.raises(KeyError):
        DJ.pick_song("rainy-night", "coding", [])


def test_dj_nano_fallback_clean(monkeypatch):
    # Simulate the nano-bit seat being unreachable: fallback must be
    # clean and recorded. DJ-L2.
    monkeypatch.setattr(DJ, "_nano_voice", lambda line: None)
    pick = DJ.pick_song("sunrise", "driving", _catalog())
    assert pick.voice_path == "dj-fallback"
    assert pick.track.artist in pick.voice_line
    assert pick.track.title in pick.voice_line


def test_dj_nano_attempt_recorded_on_receipt(tmp_path):
    eng = BuzzEngine(tmp_path / "store")
    pick = DJ.pick_song("focused", "studying", _catalog(),
                        receipts=eng.receipts)
    recs = eng.receipts.read_all()
    dj_recs = [r for r in recs if r.get("action") == "dj.pick"]
    assert dj_recs and dj_recs[0]["details"]["voice_path"] == pick.voice_path


# ---------------------------------------------------------------- forge

def test_forge_20k_unique_hashes():
    # F-L1: 20,000 playlists => 20,000 unique content hashes.
    # F-L3: every playlist is a real tracklist of catalog songs.
    cat = _catalog()
    cat_ids = {t.id for t in cat}
    pls = F.forge_playlists(20000, cat, seed="proof")
    assert len(pls) == 20000
    hashes = [pl.content_hash for pl in pls]
    assert len(set(hashes)) == 20000
    for pl in pls:
        assert len(pl.tracks) >= 1, "empty shell leaked"
        assert len({t.id for t in pl.tracks}) == len(pl.tracks), \
            "within-playlist repeat leaked"
        assert all(t.id in cat_ids for t in pl.tracks), \
            "non-catalog track leaked"


def test_forge_concepts_non_generic():
    # F-L2: specific concepts only.
    pls = F.forge_playlists(500, _catalog(), seed="generic-check")
    for pl in pls:
        assert not F.is_generic(pl.concept), f"generic: {pl.concept}"
        toks = set(F._tokens(pl.concept))
        assert len(toks) >= 5, f"thin concept: {pl.concept}"


def test_forge_unique_concepts():
    pls = F.forge_playlists(20000, _catalog(), seed="concepts")
    assert len({pl.concept for pl in pls}) == 20000


def test_forge_deterministic():
    a = F.forge_playlists(100, _catalog(), seed="same")
    b = F.forge_playlists(100, _catalog(), seed="same")
    assert [p.content_hash for p in a] == [p.content_hash for p in b]
    assert [p.concept for p in a] == [p.concept for p in b]
    c = F.forge_playlists(100, _catalog(), seed="different")
    assert [p.content_hash for p in c] != [p.content_hash for p in a]


def test_forge_refuses_empty_catalog_and_bad_counts():
    with pytest.raises(ValueError):
        F.forge_playlists(10, [])
    with pytest.raises(ValueError):
        F.forge_playlists(0, _catalog())
    with pytest.raises(ValueError):
        F.forge_playlists(F.MAX_FORGE + 1, _catalog())


def test_forge_export_writes_m3u_and_manifest(tmp_path):
    pls = F.forge_playlists(5, _catalog(), seed="export")
    summary = F.export_forge(pls, tmp_path / "out")
    assert summary["count"] == 5
    assert summary["unique_hashes"] == 5
    man = tmp_path / "out" / "manifest.jsonl"
    assert man.exists()
    recs = [json.loads(l) for l in man.read_text(encoding="utf-8")
            .splitlines() if l.strip()]
    assert len(recs) == 5
    for r in recs:
        assert (tmp_path / "out" / r["file"]).exists()
        assert len(r["track_ids"]) >= 1
        assert r["content_hash"]


# ---------------------------------------------------------------- youtube

def test_youtube_seam_honest():
    assert YT.configured() is False
    t = _catalog()[0]
    with pytest.raises(YT.YouTubeNotConfigured):
        YT.play(t)
    with pytest.raises(YT.YouTubeNotConfigured):
        YT.search("anything")
    st = YT.status()
    assert st["configured"] is False and st["needs"]


# ---------------------------------------------------------------- CLI smoke

def test_cli_dj_smoke(tmp_path, capsys):
    args = _args(buzztunes_cmd="dj", mood="wired", activity="gaming",
                 energy="surging", era=None, library=None,
                 store=str(tmp_path / "s"))
    assert cmd_buzztunes(args) == 0
    out = capsys.readouterr().out
    assert "concept:" in out and "dj [" in out and "why:" in out


def test_cli_forge_smoke(tmp_path, capsys):
    args = _args(buzztunes_cmd="forge", count=5,
                 out=str(tmp_path / "forge"), seed="smoke", library=None,
                 store=str(tmp_path / "s"))
    assert cmd_buzztunes(args) == 0
    out = capsys.readouterr().out
    assert "forged 5 playlists" in out
    assert (tmp_path / "forge" / "manifest.jsonl").exists()


def test_cli_play_m3u_smoke(tmp_path, capsys):
    forge_args = _args(buzztunes_cmd="forge", count=3,
                       out=str(tmp_path / "forge"), seed="playsmoke",
                       library=None, store=str(tmp_path / "s"))
    assert cmd_buzztunes(forge_args) == 0
    m3u = tmp_path / "forge" / "playlist-00000.m3u"
    play_args = _args(buzztunes_cmd="play", ref=str(m3u), manifest=None,
                      store=str(tmp_path / "s"))
    assert cmd_buzztunes(play_args) == 0
    out = capsys.readouterr().out
    assert "queued" in out and "YouTube not linked" in out
