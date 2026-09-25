"""Ultimate Mix Engine — up to 20,000 non-generic, non-duplicated playlists.

Chauncey's order: "create an ultimate mix engine instantly creating up
to 20k non-generic or duplicated quick play lists."

How it works: a combinatorial engine over a real taxonomy
(mood x activity x era x energy x genre-angle x vocal). Every playlist
gets a SPECIFIC concept — never "Chill Vibes 47" — AND a genuine
tracklist of real songs: every slot is a title/artist entry drawn from
the real catalog, deterministically ordered per concept. No empty
shells, no titles-only, no invented tracks. Dedupe is by content hash
(concept + ordered track ids), so no two playlists are ever identical.

Laws (declared up front; tests prove them):
  F-L1 uniqueness — N forged playlists => N unique content hashes.
  F-L2 non-generic — every concept carries >= 5 taxonomy tokens and
           matches no generic template. Proven by the concept test.
  F-L3 honest catalog — every track on every forged playlist comes from
           the passed catalog; the engine never invents artists/tracks.
           An empty catalog REFUSES to forge (ValueError) — a playlist
           of songs cannot be made from nothing, and the engine will
           not fake one.
  F-L4 determinism — same seed + same catalog => same playlists, same
           order, same tracklists.
  F-L5 cap — forge refuses counts above MAX_FORGE (20,000).

stdlib-only. Fast: 20k playlists forge in seconds (throughput is
measured and reported by the forge CLI / receipt, not asserted as a
gate — the gate is correctness).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from .m3u import write_m3u
from .providers import Track
from .receipts import ReceiptLog

MAX_FORGE = 20000
TRACKS_PER_PLAYLIST = 12

# ---------------------------------------------------------------------------
# The taxonomy — real words, specific combos. The anti-generic engine.
# ---------------------------------------------------------------------------
MOODS = (
    "rainy-night", "sunrise", "restless", "triumphant", "lonely",
    "euphoric", "focused", "nostalgic", "rebellious", "tender",
    "wired", "weightless",
)
ACTIVITIES = (
    "coding", "driving", "workout", "cooking", "studying", "running",
    "winding-down", "cleaning", "writing", "gaming", "commuting",
    "stargazing",
)
ERAS = (
    "60s", "70s", "80s", "90s", "2000s", "2010s", "2020s", "timeless",
)
ENERGIES = ("low", "simmering", "medium", "surging", "peak")
GENRE_ANGLES = (
    "synth", "guitar-driven", "piano-led", "bass-heavy", "acoustic",
    "orchestral", "lo-fi", "jazz-inflected", "electronic", "vocal-forward",
)
VOCALS = ("instrumental-only", "vocals-up-front", "mixed")

AXES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("mood", MOODS),
    ("activity", ACTIVITIES),
    ("era", ERAS),
    ("energy", ENERGIES),
    ("genre_angle", GENRE_ANGLES),
    ("vocal", VOCALS),
)

# Generic-sounding fragments that must NEVER appear in a concept.
_BANNED_GENERIC = (
    "chill vibes", "good vibes", "top hits", "best of", "ultimate mix",
    "playlist #", "mix #", "vol.", "various artists",
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def concept_for(axes: Dict[str, str]) -> str:
    """Build the specific concept string. Never generic by construction:
    it always names mood + activity + era + energy + genre angle + vocal."""
    return (f"{axes['mood']} {axes['activity']} \u2014 {axes['era']} "
            f"{axes['genre_angle']}, {axes['energy']} energy, "
            f"{axes['vocal']}")


def is_generic(concept: str) -> bool:
    """True if the concept smells generic. The F-L2 guard."""
    toks = _tokens(concept)
    if len(set(toks)) < 5:
        return True
    low = concept.lower()
    if any(b in low for b in _BANNED_GENERIC):
        return True
    if re.search(r"#?\d+\s*$", concept):
        return True
    return False


@dataclass
class ForgedPlaylist:
    """One forged quick playlist."""
    index: int
    concept: str
    axes: Dict[str, str]
    tracks: List[Track] = field(default_factory=list)
    content_hash: str = ""

    def to_record(self) -> Dict:
        return {
            "index": self.index,
            "concept": self.concept,
            "axes": dict(self.axes),
            "tracks": [t.to_record() for t in self.tracks],
            "track_ids": [t.id for t in self.tracks],
            "content_hash": self.content_hash,
        }


def content_hash(concept: str, track_ids: List[str]) -> str:
    return hashlib.sha256(
        (concept + "|" + ",".join(track_ids)).encode("utf-8")).hexdigest()[:16]


def _combo_space() -> Iterator[Dict[str, str]]:
    """Yield every taxonomy combination exactly once (172,800 total)."""
    for mood in MOODS:
        for activity in ACTIVITIES:
            for era in ERAS:
                for energy in ENERGIES:
                    for angle in GENRE_ANGLES:
                        for vocal in VOCALS:
                            yield {"mood": mood, "activity": activity,
                                   "era": era, "energy": energy,
                                   "genre_angle": angle, "vocal": vocal}


def _tracklist_for(axes: Dict[str, str], catalog: List[Track],
                   rng: random.Random) -> List[Track]:
    """Deterministic per-concept ordering of the REAL catalog.

    Honest catalog (F-L3): only catalog tracks, never invented, never
    repeated inside one playlist. The order is seeded per concept, so
    each of the 20k playlists gets its own genuine sequence.
    """
    order = list(catalog)
    rng.shuffle(order)
    return order[:min(TRACKS_PER_PLAYLIST, len(order))]


def forge_playlists(count: int, catalog: List[Track],
                    seed: str = "buzz") -> List[ForgedPlaylist]:
    """Forge `count` playlists of real songs. Deterministic from seed
    and catalog (F-L4).

    Raises ValueError for count < 1 or > MAX_FORGE (F-L5), and for an
    empty catalog (F-L3 — no empty shells, no invented songs).
    """
    if count < 1:
        raise ValueError("forge: count must be >= 1")
    if count > MAX_FORGE:
        raise ValueError(f"forge: cap is {MAX_FORGE}, asked {count}")
    if not catalog:
        raise ValueError(
            "forge: catalog is empty — a playlist of songs needs real "
            "songs. Import an .m3u (levi buzztunes m3u import) or point "
            "a library directory; the forge will not invent tracks.")
    rng = random.Random(seed)
    combos = list(_combo_space())
    rng.shuffle(combos)

    out: List[ForgedPlaylist] = []
    seen: set = set()
    for i, axes in enumerate(combos[:count]):
        concept = concept_for(axes)
        assert not is_generic(concept), f"generic concept leaked: {concept}"
        trng = random.Random(f"{seed}:{concept}")
        tracks = _tracklist_for(axes, catalog, trng)
        h = content_hash(concept, [t.id for t in tracks])
        if h in seen:
            continue  # F-L1: never emit a duplicate
        seen.add(h)
        out.append(ForgedPlaylist(index=i, concept=concept, axes=axes,
                                  tracks=tracks, content_hash=h))
    return out


def export_forge(playlists: List[ForgedPlaylist], out_dir: str | Path,
                 receipts: Optional[ReceiptLog] = None,
                 actor: str = "forge") -> Dict:
    """Write playlists as .m3u files + manifest.jsonl. Returns a summary."""
    t0 = time.perf_counter()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.jsonl"
    with open(manifest, "w", encoding="utf-8") as mh:
        for pl in playlists:
            fname = f"playlist-{pl.index:05d}.m3u"
            (out / fname).write_text(write_m3u(pl.tracks),
                                     encoding="utf-8")
            rec = pl.to_record()
            rec["file"] = fname
            mh.write(json.dumps(rec) + "\n")
    elapsed = time.perf_counter() - t0
    summary = {"count": len(playlists), "out_dir": str(out),
               "elapsed_s": round(elapsed, 2),
               "unique_hashes": len({pl.content_hash for pl in playlists})}
    if receipts is not None:
        receipts.emit("forge.export", actor=actor, details=summary)
    return summary
