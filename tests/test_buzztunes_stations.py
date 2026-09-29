"""Proof for the stations laws (core/levi/buzztunes/stations.py).

S-L1 honest catalog — every station track is a catalog track.
S-L2 deterministic — same seed + same catalog => identical sequence.
S-L3 seed-transparent — seed string is readable and shown; tracks carry reasons.
S-L4 no repeats within a cycle — full pool plays before any replay.
"""

from __future__ import annotations

import pytest

from levi.buzztunes import stations
from levi.buzztunes.providers import Track
from levi.buzztunes.stations import (
    StationError,
    make_station,
    next_tracks,
    station_receipt,
)


def _catalog() -> list:
    def T(i, artist, title, genre=None, duration=180.0):
        meta = {"genre": genre} if genre else {}
        return Track(id=f"t{i}", artist=artist, title=title,
                     duration=duration, meta=meta)
    return [
        T(1, "Kendrick Lamar", "HUMBLE.", "hip-hop"),
        T(2, "Kendrick Lamar", "DNA.", "hip-hop"),
        T(3, "Kendrick Lamar", "Alright", "hip-hop"),
        T(4, "J. Cole", "No Role Modelz", "hip-hop"),
        T(5, "J. Cole", "Middle Child", "hip-hop"),
        T(6, "Miles Davis", "So What", "jazz"),
        T(7, "John Coltrane", "Blue Train", "jazz"),
        T(8, "Daft Punk", "One More Time", "dance"),
        T(9, "Daft Punk", "Get Lucky", "dance"),
        T(10, "Adele", "Hello", "soul"),
    ]


# ---- construction ----

def test_artist_station_leads_with_the_artist():
    st = make_station("artist", "Kendrick Lamar", _catalog())
    first = next_tracks(st, _catalog(), 3)
    artists = [s.track.artist for s in first]
    assert artists == ["Kendrick Lamar"] * 3
    assert all("Kendrick Lamar" in s.reason for s in first)


def test_genre_station_only_that_genre():
    st = make_station("genre", "jazz", _catalog())
    assert st.size == 2  # pool is 2 deep
    got = next_tracks(st, _catalog(), 10)  # endless: cycles the pool
    assert len(got) == 10
    assert {s.track.meta["genre"] for s in got} == {"jazz"}


def test_song_station_starts_with_seed_song():
    st = make_station("song", "HUMBLE Kendrick", _catalog())
    first = next_tracks(st, _catalog(), 1)[0]
    assert first.track.title == "HUMBLE."
    assert "seed song" in first.reason


def test_seed_is_transparent():
    st = make_station("artist", "Kendrick Lamar", _catalog())
    assert st.seed.startswith("artist:kendrick lamar@")
    r = station_receipt(st)
    assert r["seed"] == st.seed
    assert r["pool_size"] == st.size > 0


@pytest.mark.parametrize("bad_kind", ["podcast", "", "ARTIST "])
def test_bad_kind_refused(bad_kind):
    if bad_kind.strip().lower() == "artist":
        pytest.skip("covered elsewhere")
    with pytest.raises(StationError):
        make_station(bad_kind, "x", _catalog())


def test_empty_seed_refused():
    with pytest.raises(StationError):
        make_station("artist", "   ", _catalog())


def test_no_match_refused():
    with pytest.raises(StationError):
        make_station("genre", "polka", _catalog())


def test_empty_catalog_refused():
    with pytest.raises(StationError):
        make_station("artist", "Kendrick Lamar", [])


# ---- S-L1 honest catalog ----

def test_every_track_is_catalog():
    cat = _catalog()
    ids = {t.id for t in cat}
    for kind, seed in [("artist", "Kendrick Lamar"),
                       ("genre", "hip-hop"),
                       ("song", "So What Miles")]:
        st = make_station(kind, seed, cat)
        for s in next_tracks(st, cat, 40):
            assert s.track.id in ids  # never invented (S-L1)


# ---- S-L2 deterministic ----

def test_deterministic_sequence():
    cat = _catalog()
    a = make_station("genre", "hip-hop", cat)
    b = make_station("genre", "hip-hop", cat)
    sa = [s.track.id for s in next_tracks(a, cat, 60)]
    sb = [s.track.id for s in next_tracks(b, cat, 60)]
    assert sa == sb  # identical, track for track (S-L2)


def test_different_seed_different_order():
    cat = _catalog()
    a = [s.track.id for s in next_tracks(
        make_station("genre", "hip-hop", cat), cat, 5)]
    b = [s.track.id for s in next_tracks(
        make_station("genre", "jazz", cat), cat, 5)]
    assert a != b


# ---- S-L4 no repeats within a cycle ----

def test_no_repeat_within_cycle():
    cat = _catalog()
    st = make_station("artist", "Kendrick Lamar", cat)
    n = st.size
    first_cycle = [s.track.id for s in next_tracks(st, cat, n)]
    assert len(set(first_cycle)) == n  # every track exactly once (S-L4)


def test_endless_cycles_reshuffle_deterministically():
    cat = _catalog()
    st = make_station("genre", "hip-hop", cat)
    n = st.size
    c1 = [s.track.id for s in next_tracks(st, cat, n, after=0)]
    c2 = [s.track.id for s in next_tracks(st, cat, n, after=n)]
    assert sorted(c1) == sorted(c2) == sorted(st.pool)
    # second cycle replays the pool, reshuffled — still no intra-cycle dupes
    assert len(set(c2)) == n
    # and it is stable across rebuilds (S-L2 across cycles)
    st2 = make_station("genre", "hip-hop", cat)
    c2b = [s.track.id for s in next_tracks(st2, cat, n, after=n)]
    assert c2 == c2b


# ---- reasons ----

def test_every_track_has_a_reason():
    cat = _catalog()
    st = make_station("artist", "Daft Punk", cat)
    for s in next_tracks(st, cat, 20):
        assert isinstance(s.reason, str) and s.reason  # S-L3


def test_describe_lists_laws():
    d = stations.describe()
    assert d["kinds"] == ["song", "artist", "genre"]
    assert len(d["laws"]) == 4
