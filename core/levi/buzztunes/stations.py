"""Radio-style stations — artist, genre, and song seeds.

Chauncey's spec (2026-09-29): "Station s by artist geners like songs".
Pick an artist, a genre, or a song; get an endless generated station of
similar music, built on the real catalog through the DJ/forge/curation
engines. Nothing is invented, nothing is hidden.

LAWS
----
S-L1 HONEST CATALOG. Every station track comes from the catalog passed
     in. The station never invents an artist, title, or genre.
S-L2 DETERMINISTIC. Same seed + same catalog => identical sequence,
     track for track, forever. Proven by the determinism test.
S-L3 SEED-TRANSPARENT. The seed is a human-readable string
     (``"artist:Kendrick Lamar"``) and the station shows it; every track
     carries a plain-speech reason ("same artist", "shares the genre
     boom-bap", ...). Per the DemandPulse/KFX2 honesty rules: the user
     can see exactly why the station plays what it plays.
S-L4 NO REPEATS WITHIN A CYCLE. A station never replays a track until
     every eligible track has played once. When the pool is exhausted
     the order reshuffles deterministically (seed + round number) and
     the cycle restarts — still endless, still S-L2.

HOW IT WORKS
------------
``make_station(kind, seed_text, catalog)`` scores the catalog against the
seed (artist match > genre match > token overlap, DJ-style scoring),
orders the pool deterministically with ``random.Random(seed)``, and
returns a Station. ``next_tracks(station, catalog, count, after)`` walks
the endless sequence: position p plays pool[(p + round_offset) ...]
with a per-round deterministic reshuffle. The phone renders the seed,
the reason per track, and a "more" button — endless radio.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .providers import Track

VALID_KINDS = ("song", "artist", "genre")


class StationError(ValueError):
    """Structured refusal — plain speech, never silent."""


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t]


def _genre_of(track: Track) -> str:
    g = (track.meta or {}).get("genre", "")
    return str(g).strip().lower()


def _catalog_hash(catalog: List[Track]) -> str:
    h = hashlib.sha256()
    for t in sorted(catalog, key=lambda t: t.id):
        h.update(f"{t.id}|{t.artist}|{t.title}".encode("utf-8"))
    return h.hexdigest()[:12]


@dataclass
class StationTrack:
    """One station entry: the track plus its plain-speech reason."""
    track: Track
    reason: str


@dataclass
class Station:
    """A deterministic, seed-transparent station."""
    kind: str               # "song" | "artist" | "genre"
    seed_text: str           # what the user picked, verbatim
    seed: str                # transparent seed string, shown in the UI
    catalog_hash: str
    pool: List[str] = field(default_factory=list)  # track ids, round-0 order
    rounds: Dict[int, List[str]] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.pool)

    def fingerprint(self) -> str:
        return hashlib.sha256(
            f"{self.seed}|{self.catalog_hash}".encode("utf-8")).hexdigest()[:16]


def make_station(kind: str, seed_text: str,
                 catalog: List[Track]) -> Station:
    """Build a station. Laws S-L1, S-L2, S-L3."""
    kind = (kind or "").strip().lower()
    if kind not in VALID_KINDS:
        raise StationError(
            f"station kind must be one of {', '.join(VALID_KINDS)}")
    seed_text = (seed_text or "").strip()
    if not seed_text:
        raise StationError("pick an artist, genre, or song to seed the station")
    if not catalog:
        raise StationError("the catalog is empty — nothing to build a station from")

    scored = _score_pool(kind, seed_text, catalog)  # S-L1: catalog only
    if not scored:
        raise StationError(
            f'nothing in the catalog matches "{seed_text}" '
            f"as a {kind} station — try another seed")

    chash = _catalog_hash(catalog)
    seed = f"{kind}:{seed_text.lower()}@{chash}"  # S-L3: readable seed
    rng = random.Random(seed)                     # S-L2: seeded RNG
    # Deterministic shuffle within score tiers (best tier first).
    tiers: Dict[float, List[Tuple[str, str]]] = {}
    for tid, score, reason in scored:
        tiers.setdefault(score, []).append((tid, reason))
    pool: List[str] = []
    reasons: Dict[str, str] = {}
    for score in sorted(tiers, reverse=True):
        tier = tiers[score]
        rng.shuffle(tier)
        for tid, reason in tier:
            pool.append(tid)
            reasons[tid] = reason
    st = Station(kind=kind, seed_text=seed_text, seed=seed,
                 catalog_hash=chash, pool=pool)
    st.rounds[0] = pool
    # stash reasons on the instance for next_tracks
    st._reasons = reasons  # noqa: SLF001 (internal, same module)
    return st


def _score_pool(kind: str, seed_text: str,
                catalog: List[Track]) -> List[Tuple[str, float, str]]:
    """Score every catalog track against the seed. Returns
    (track_id, score, reason). S-L1: only catalog tracks, scored."""
    seed_toks = set(_tokens(seed_text))
    seed_low = seed_text.strip().lower()
    out: List[Tuple[str, float, str]] = []
    seed_track: Optional[Track] = None
    if kind == "song":
        # Find the seed song: best token overlap on artist+title.
        best: Optional[Track] = None
        best_n = 0
        for t in catalog:
            n = len(seed_toks & set(_tokens(f"{t.artist} {t.title}")))
            if n > best_n:
                best, best_n = t, n
        if best is None or best_n == 0:
            return []
        seed_track = best

    for t in catalog:
        artist_low = (t.artist or "").strip().lower()
        genre = _genre_of(t)
        toks = set(_tokens(f"{t.artist} {t.title} {genre}"))
        score = 0.0
        reason = ""
        if kind == "artist":
            if artist_low == seed_low or seed_low in artist_low:
                score = 100.0
                reason = f"same artist — {t.artist}"
            elif seed_toks & set(_tokens(t.artist)):
                score = 40.0
                reason = f"close to {seed_text} — {t.artist}"
            elif genre and genre in seed_toks:
                score = 10.0
                reason = f"shares the {genre} lane"
            else:
                continue
        elif kind == "genre":
            if genre == seed_low:
                score = 100.0
                reason = f"{genre} station pick"
            elif seed_low in genre or genre in seed_low:
                score = 40.0
                reason = f"near the {genre} shelf"
            else:
                continue
        else:  # song
            assert seed_track is not None
            if t.id == seed_track.id:
                score = 200.0
                reason = "the seed song itself"
            else:
                seed_toks_full = set(_tokens(
                    f"{seed_track.artist} {seed_track.title} "
                    f"{_genre_of(seed_track)}"))
                overlap = len(seed_toks_full & toks)
                if t.artist == seed_track.artist:
                    score = 100.0 + overlap
                    reason = f"more {t.artist}, like the seed"
                elif _genre_of(t) and _genre_of(t) == _genre_of(seed_track):
                    score = 50.0 + overlap
                    reason = (f"same {_genre_of(t)} frequency "
                              f"as the seed")
                elif overlap >= 2:
                    score = 10.0 + overlap
                    reason = "echoes the seed song"
                else:
                    continue
        # Prefer finished tracks (real duration metadata) — DJ-style.
        if t.duration:
            score += 0.5
        out.append((t.id, score, reason))
    return out


def _round_order(st: Station, rnd: int) -> List[str]:
    """Deterministic per-round order. S-L2, S-L4."""
    if rnd in st.rounds:
        return st.rounds[rnd]
    rng = random.Random(f"{st.seed}#round{rnd}")
    order = list(st.pool)
    rng.shuffle(order)
    st.rounds[rnd] = order
    return order


def next_tracks(st: Station, catalog: List[Track], count: int,
                after: int = 0) -> List[StationTrack]:
    """The endless sequence: ``count`` tracks starting at position
    ``after``. Never repeats within a cycle (S-L4); deterministic
    forever (S-L2)."""
    if count <= 0:
        raise StationError("count must be positive")
    if after < 0:
        raise StationError("position can't be negative")
    if not st.pool:
        raise StationError("station pool is empty")
    by_id = {t.id: t for t in catalog}
    reasons = getattr(st, "_reasons", {})
    out: List[StationTrack] = []
    n = len(st.pool)
    for p in range(after, after + count):
        rnd, idx = divmod(p, n)
        tid = _round_order(st, rnd)[idx]
        track = by_id.get(tid)
        if track is None:  # catalog changed under us — skip honestly
            continue
        out.append(StationTrack(
            track=track,
            reason=reasons.get(tid, "station pick")))
    return out


def station_receipt(st: Station) -> Dict:
    """The audit trail for one station (S-L3)."""
    return {
        "kind": "station",
        "station_kind": st.kind,
        "seed_text": st.seed_text,
        "seed": st.seed,
        "catalog_hash": st.catalog_hash,
        "pool_size": st.size,
        "fingerprint": st.fingerprint(),
    }


def describe() -> Dict:
    return {
        "feature": "radio stations",
        "kinds": list(VALID_KINDS),
        "laws": [
            "S-L1 every track comes from the catalog, never invented",
            "S-L2 same seed + same catalog => identical sequence",
            "S-L3 seed is human-readable and shown; every track has a reason",
            "S-L4 no repeats until the whole pool has played",
        ],
    }
