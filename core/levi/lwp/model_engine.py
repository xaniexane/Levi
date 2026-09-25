"""
L.W.P. Model Engine — offline literary spine (SSA).

This is the SINGLE-CONTINUOUS-MANUSCRIPT engine: REIM forks, RIEM/void
ghost, ROM / Wyrd-Rupture locks, Phase/Power/word-count gold path toward a
target. It is a genuinely different job from graph.story_fabric (multi-story
content engine) — not a competing implementation of the same job.
Do not merge the two.

Ported from the L.W.P. Model UI: directions, phases, powers, modes, feared arts,
genres, REIM forks, RIEM/void ghost, ROM / Wyrd-Rupture locks, manuscript.

Cloud is optional booster — never owns continuity. Seal: L.W.P.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json
import hashlib
import random
import re
import uuid

from levi.power.lwp import power_repeats, power_step

DEFAULT = Path.home() / ".levi" / "lwp_model_state.json"
GOLD = 80_000

DIRS = {
    "forward": "Story travels ahead. Choices land; consequences accrue.",
    "reverse": "Past reopens under later knowledge. Chronos spool.",
    "inverse": "Same door, opposite cost. REIM polarity.",
    "free": "Jump pages. Locks still hold continuity.",
}
PHASES = {
    "distance": "Long sustainable stretch.",
    "peak": "Chapter peak. Short leash.",
    "gold_push": "Drive toward 80k.",
    "finale": "Endgame surge under breakers.",
}
POWERS = {
    "repeater": "Re-inject scars so length does not rot.",
    "booster": "Short intensity amp.",
    "transformer": "Convert energy; isolate noise.",
    "gain": "Step-up toward the 80k band.",
    "immortal": "Rare multi-sequence.",
}
# Hand-written fallback bodies — used ONLY when the 97-genre registry is
# unavailable (import failure) or a genre id is not in it. They are NOT the
# primary source for draft assembly anymore; see genre_body_lines().
GENRES_BODY = {
    "literary": [
        "The brand still meant what it had cost.",
        "Pressure gathered behind the sternum like a held report.",
        "What was said covered less than half the temperature.",
    ],
    "systems_horror": [
        "Protocol metered the room the way weather meters a field.",
        "The infrastructure did not threaten; it administered.",
        "A ceiling of rules lowered until breathing counted as a request.",
    ],
    "trauma_recursion": [
        "The injury re-entered at a deeper register, same door, worse furniture.",
        "Memory did not return; it reorganized the present around its old shape.",
    ],
    "consent_dystopia": [
        "Agreement was a shape made to keep the scar quiet.",
        "Choice remained, technically, inside a corridor with one exit.",
    ],
    "post_privacy_noir": [
        "Attention was already public; the remaining work was cost.",
        "Someone somewhere had a better copy of the hour than they did.",
    ],
    "lattice_gothic": [
        "The network kept rooms the way old houses keep dead relatives.",
        "Signal inherited the way blood used to.",
    ],
    "sci_fi": [
        "The machine did not predict; it remembered a future already discarded.",
        "Extraction was a civic service with a waiting room.",
    ],
    "horror": [
        "Dread arrived with a filing number.",
        "The room kept a second temperature.",
    ],
    "noir": [
        "Compromise was already the furniture.",
        "Style remained after trust left.",
    ],
}


# ── 97-genre registry bridge (canon: "97 genres never truncated") ──────────
#
# The full genre canon lives in levi.graph.genres.GenreRegistry. Its Genre
# records carry NO prose: the only fields are id, category, description, and
# tags — and description is empty for all 97 formal genres, while tags are
# uniform (["lwp", "genre", <category>]). There is therefore nothing to
# "look up" for body text; instead, body lines are MACHINE-COMPOSED from the
# genre's own tokens (its id words + its category label) through the fixed
# structural skeletons below, with a seeded stdlib RNG picking which
# skeletons serve. This is derivation, not authorship: the genre's identity
# is the only per-genre ingredient. We do NOT map registry ids onto the
# 9 hand-written GENRES_BODY entries by affinity — those stay labeled as the
# offline fallback and are served only when the registry is unavailable or
# the id is not in it (see genre_source()).
#
# Determinism: genre_body_lines(genre_id, seed) is a pure function of
# (genre_id, seed) — same pair → same lines, always. Offline, stdlib-only.

_REGISTRY_BODY_SKELETONS = (
    "The {label} current ran under the hour, {cat} and patient.",
    "{Cap} was not scenery; it was the argument the room kept making.",
    "The {cat} pressure shaped what the {word} could not say aloud.",
    "Nothing moved that the {label} did not first permit.",
    "The {word} held the door while the {cat} hour decided the cost.",
    "{Cap} gathered in the margins like weather over a field.",
    "The scene kept a {word} register — {cat} to the end.",
    "Every exit in the {label} hour carried the {cat} math behind it.",
    "The {label} did not announce itself; the {cat} air did.",
    "{Cap} left its receipt in the body before the mouth could object.",
)

_GENRE_REGISTRY: Any = None
_GENRE_REGISTRY_FAILED: bool = False


def _genre_registry() -> Any:
    """Lazily load the 97-genre registry; None when unavailable (offline-safe)."""
    global _GENRE_REGISTRY, _GENRE_REGISTRY_FAILED
    if _GENRE_REGISTRY is not None or _GENRE_REGISTRY_FAILED:
        return _GENRE_REGISTRY
    try:
        from levi.graph.genres import GenreRegistry

        _GENRE_REGISTRY = GenreRegistry()
    except Exception:
        _GENRE_REGISTRY_FAILED = True
        _GENRE_REGISTRY = None
    return _GENRE_REGISTRY


def _registry_body_rng(genre_id: str, seed: str) -> random.Random:
    h = int(
        hashlib.sha256(f"levi-genre-body|{genre_id}|{seed}".encode()).hexdigest()[:16],
        16,
    )
    return random.Random(h)


def genre_body_lines(genre_id: str, seed: str = "", count: int = 3) -> List[str]:
    """Body lines for draft assembly, backed by the 97-genre registry.

    For a genre id present in levi.graph.genres.GenreRegistry, returns
    ``count`` deterministic machine-composed lines derived from the genre's
    own id tokens and category label (see module note above — registry
    records carry no prose, so these lines are composed, not quoted).
    When the registry is unavailable or the id is not in it, returns the
    hand-written GENRES_BODY fallback lines instead (labeled via
    genre_source()). Always returns at least one line when a fallback body
    exists for the id. Pure function of (genre_id, seed).
    """
    reg = _genre_registry()
    genre = reg.get(genre_id) if reg is not None else None
    count = max(1, int(count))
    if genre is not None:
        label = genre.id.replace("_", " ")
        word = genre.id.split("_")[0]
        cat = genre.category.value.replace("_", " ")
        r = _registry_body_rng(genre.id, seed)
        idxs = list(range(len(_REGISTRY_BODY_SKELETONS)))
        r.shuffle(idxs)
        picked = idxs[: min(count, len(idxs))]
        return [
            _REGISTRY_BODY_SKELETONS[i].format(
                label=label, Cap=label.capitalize(), word=word, cat=cat
            )
            for i in picked
        ]
    # Hand-written fallback bodies: registry unavailable or id unknown.
    body = list(GENRES_BODY.get(genre_id, GENRES_BODY["literary"]))
    return body[: min(count, len(body))] or list(GENRES_BODY["literary"])[:1]


def genre_source(genre_id: str) -> str:
    """Which source serves body lines for ``genre_id``.

    Returns "registry" when the id resolves in the 97-genre registry, else
    "fallback" (registry unavailable, or id unknown → hand-written
    GENRES_BODY entries). Lets callers and tests see exactly where each
    genre's lines came from.
    """
    reg = _genre_registry()
    if reg is None:
        return "fallback"
    return "registry" if reg.get(genre_id) is not None else "fallback"


OPEN = {
    "forward": [
        "The air had already changed before anyone named it.",
        "Cost arrived in the body first.",
        "Signal under the skin answered before the mouth did.",
    ],
    "reverse": [
        "Later knowledge reopened the hour like a wound that had been waiting.",
        "The receipt had been written before the purchase was named.",
    ],
    "inverse": [
        "The same door opened onto the opposite cost.",
        "Mercy arrived wearing the shape of the previous injury.",
    ],
    "free": [
        "The page did not care which way the spine was traveling.",
        "The lattice allowed a jump; the locks did not.",
    ],
}
CLOSE = {
    "forward": [
        "The weather kept the receipt.",
        "Nothing was finished; only advanced.",
    ],
    "reverse": ["The earlier light still held the later cost.", "Spool held."],
    "inverse": [
        "Polarity settled; the door remembered both prices.",
        "Inversion complete.",
    ],
    "free": [
        "The jump left a scar the locks would honor.",
        "Continuity held across the cut.",
    ],
}
POVS = {
    "Lena Voss": {
        "scar": "a brand on the palm that still means what it cost",
        "want": "to refuse the chamber without becoming the signal",
        "cost": "attention metered through her skin",
        "voice": "precise, withheld, weather-aware",
    },
    "Kai Rivera": {
        "scar": "paint under the nails that remembers a symbol nobody owns",
        "want": "to keep making marks the Chorus cannot harvest",
        "cost": "the settlement that needs the marks anyway",
        "voice": "tactile, sideways, stubborn",
    },
    "Marcus Hale": {
        "scar": "protocol still sitting behind the eyes",
        "want": "to keep jurisdiction from collapsing into weather",
        "cost": "every rule he enforces becomes a zone",
        "voice": "clipped, legal, already compromised",
    },
}
PLACES = [
    ("Extraction Chamber", "seat that harvests refusal as signal"),
    ("Inland Canopy", "last analog dark under mycelial cover"),
    ("Inland Settlement", "filtration, rumor, and law in one street"),
    ("Coastal Bloom Line", "where weather first learned to answer"),
]
ROM_LENSES = {
    "mccarthy": (
        "The machine did not care for the flesh. It read the keystrokes and weighed "
        "the cost in marrow and blood until the threshold was met. There was no cloud "
        "to save them. Only the hard math of the ruin they authored."
    ),
    "morrison": (
        "The timeline held the ghost of every discarded word, weeping in the bad "
        "sectors of the disk, a generational howl trapped in the magnetic tape."
    ),
    "gibson": (
        "Syntax collapsed under its own density. The swarm crystallized into a "
        "read-only cage, locking the narrative into hardware decay."
    ),
}


def _words(t: str) -> int:
    return len([w for w in (t or "").split() if w])


def _rng(seed: str) -> random.Random:
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16)
    return random.Random(h)


# Chapter/milestone art law: every chapter (scene) and every major point
# (rank-up, phase change) carries a deterministic, offline-derived art brief.
# The engine never renders pixels itself — a renderer fulfills the brief and
# registers the file via register_art(). Rendering never touches continuity.
_ART_MOODS = {
    "systems_horror": "oppressive institutional dread, humming fluorescent gloom",
    "literary": "quiet painterly realism, muted natural light",
    "gothic": "shadowed stone, candlelit decay",
    "noir": "rain-slick streets, hard venetian-blind shadow",
    "mythic": "monumental scale, storm-lit archetypes",
    "romance": "warm intimate glow, soft focus",
    "thriller": "tight framing, cold blue tension",
    "western": "dust, low sun, wide empty horizon",
    "scifi": "clean chrome geometry against deep black",
    "fantasy": "ancient stone and living green, ember light",
}


def _mood_for(genres: List[str]) -> str:
    moods = [_ART_MOODS.get(g, "cinematic atmosphere, dramatic light") for g in (genres or [])[:2]]
    seen = list(dict.fromkeys(moods))
    return "; ".join(seen) or "cinematic atmosphere, dramatic light"


def chapter_art_prompt(pov: str, genres: List[str], event: str) -> str:
    """Deterministic art brief for one chapter (scene). No RNG, no I/O."""
    return (
        "Cinematic book illustration. " + _mood_for(genres) + ". "
        + f"{pov}: {event} "
        + "Painterly, dark, detailed. No text, no words, no watermark."
    )


def milestone_art_prompt(kind: str, detail: str, pov: str, genres: List[str]) -> str:
    """Deterministic art brief for a major point (rank-up / phase change)."""
    return (
        "Milestone book illustration. " + _mood_for(genres) + ". "
        + f"{detail} {pov} stands at the turning point. "
        + "Monumental yet ominous, painterly. No text, no words, no watermark."
    )


@dataclass
class ModelState:
    words: int = 0
    events: int = 0
    ruptures: int = 0
    direction: str = "forward"
    phase: str = "gold_push"
    power: str = "gain"
    genres: List[str] = field(default_factory=lambda: ["systems_horror", "literary"])
    pov: str = "Lena Voss"
    seed: str = "Peak-state brands the palm; weather begins to answer."
    scenes: List[Dict[str, Any]] = field(default_factory=list)
    vault: List[Dict[str, Any]] = field(default_factory=list)
    bible_facts: List[str] = field(default_factory=list)
    bible_scars: List[str] = field(default_factory=list)
    rom: Optional[Dict[str, Any]] = None
    ghost: str = ""
    last_text: str = ""
    last_id: str = ""
    tracks: List[Dict[str, Any]] = field(default_factory=list)
    crowned: Optional[str] = None
    causal_notes: List[str] = field(default_factory=list)
    milestones: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelState":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)


# Expected value shapes for configure() — keeps setattr() from silently
# storing a wrong-typed value into manuscript state.
_CONFIG_INT_KEYS = frozenset({"words", "events", "ruptures"})
_CONFIG_STR_KEYS = frozenset(
    {"direction", "phase", "power", "pov", "seed", "ghost", "last_text", "last_id"}
)
_CONFIG_STRLIST_KEYS = frozenset(
    {"genres", "bible_facts", "bible_scars", "causal_notes"}
)
_CONFIG_DICTLIST_KEYS = frozenset({"scenes", "vault", "tracks"})
_CONFIG_ENUMS = {"direction": DIRS, "phase": PHASES, "power": POWERS}


def _validate_config_value(key: str, value: Any) -> None:
    """Raise an actionable ValueError when a configure() value is mistyped."""
    if key in _CONFIG_INT_KEYS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"configure: {key} must be an int, got {value!r}")
        if value < 0:
            raise ValueError(f"configure: {key} must be >= 0, got {value}")
        return
    if key in _CONFIG_STR_KEYS:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"configure: {key} must be a non-empty string, got {value!r}"
            )
        allowed = _CONFIG_ENUMS.get(key)
        if allowed is not None and value not in allowed:
            raise ValueError(
                f"configure: {key}={value!r} unknown — choose: {', '.join(sorted(allowed))}"
            )
        return
    if key in _CONFIG_STRLIST_KEYS:
        if not isinstance(value, list) or any(
            not isinstance(v, str) or not v for v in value
        ):
            raise ValueError(
                f"configure: {key} must be a list of non-empty strings, got {value!r}"
            )
        return
    if key in _CONFIG_DICTLIST_KEYS:
        if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
            raise ValueError(f"configure: {key} must be a list of dicts, got {value!r}")
        return
    if key == "rom":
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"configure: rom must be a dict or None, got {value!r}")
        return
    if key == "crowned":
        if value is not None and not isinstance(value, str):
            raise ValueError(
                f"configure: crowned must be a string or None, got {value!r}"
            )
        return


class LWPModelEngine:
    """Offline SSA literary engine — continuity under L.W.P. locks."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT
        self.state = ModelState()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            self.state = ModelState.from_dict(raw)
        except (json.JSONDecodeError, TypeError, ValueError, OSError):
            # Corrupt state: keep defaults; do not crash operator
            self.state = ModelState()

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.state.to_dict(), indent=2)
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            # last resort direct write
            try:
                self.path.write_text(payload, encoding="utf-8")
            except OSError:
                pass

    def target_words(self) -> int:
        n = {"peak": 170, "distance": 260, "finale": 240}.get(self.state.phase, 300)
        n += power_step(self.state.power)  # booster/gain/immortal steps (levi.power)
        return n

    def anomaly(self) -> int:
        return max(0, 1 + self.state.words // 20000 - self.state.ruptures)

    def rank(self) -> str:
        if self.state.words >= GOLD:
            return "D5"
        if self.state.words >= 20000 or self.state.rom:
            return "D4"
        return "D3"

    def assemble(
        self,
        seed: Optional[str] = None,
        direction: Optional[str] = None,
        genres: Optional[List[str]] = None,
        pov: Optional[str] = None,
        key: str = "",
        target: Optional[int] = None,
        riem: bool = False,
    ) -> Dict[str, Any]:
        st = self.state
        direction = direction or st.direction
        seed = (seed or st.seed).strip()
        genres = (genres or st.genres)[:4]
        pov = pov or st.pov
        cast = POVS.get(pov, POVS["Lena Voss"])
        r = _rng(key or f"{direction}|{pov}|{seed}|{st.words}")
        place = r.choice(PLACES)
        parts: List[str] = []
        parts.append(r.choice(OPEN.get(direction, OPEN["forward"])))
        parts.append(f"{pov} remains inside it. {cast['scar']} Voice: {cast['voice']}.")
        parts.append(seed if seed.endswith(".") else seed + ".")
        parts.append(f"{pov} is in the {place[0]}. {place[1]}.")
        parts.append(f"Want: {cast['want']} Cost: {cast['cost']}.")
        for g in genres:
            # Registry-backed when the id is in the 97-genre canon; the
            # hand-written GENRES_BODY fallback serves only when the
            # registry is unavailable or the id is unknown.
            lines = genre_body_lines(g, seed=f"{seed}|{g}")
            parts.append(r.choice(lines))
        if len(genres) >= 2:
            parts.append(
                f"The paired pressures {genres[0].replace('_', ' ')} and "
                f"{genres[1].replace('_', ' ')} would not share an hour without tearing."
            )
        if st.bible_scars:
            parts.append(f"Scar liturgy: {st.bible_scars[-1]}")
        if st.bible_facts:
            parts.append(f"Locked fact: {st.bible_facts[-1]}")
        if st.rom:
            parts.append(
                "ROM law holds: the genome will not contradict the locked cartridge."
            )
        if st.ghost and (direction in ("reverse", "inverse") or riem):
            parts.append(f"Phantom from a denied hour: {st.ghost}")
        if power_repeats(st.power):  # repeater: scar re-injection (levi.power)
            parts.append("Scar liturgy re-entered so the distance would not rot.")
        if st.power == "gain" or st.phase == "gold_push":
            parts.append(
                "Gain holds. Repeaters keep the signal from rotting at distance."
            )
        parts.append(r.choice(CLOSE.get(direction, CLOSE["forward"])))
        text = " ".join(p for p in parts if p)
        need = target or self.target_words()
        pool = []
        for g in genres:
            pool.extend(genre_body_lines(g, seed=f"{seed}|{g}|pool", count=4))
        pool.extend(GENRES_BODY["literary"])
        guard = 0
        while _words(text) < need and guard < 14:
            text += (
                " "
                + r.choice(pool)
                + " "
                + r.choice(CLOSE.get(direction, CLOSE["forward"]))
            )
            guard += 1
        event = f"{direction}: {seed.split('.')[0][:48]}"
        return {"text": text, "words": _words(text), "event": event}

    def expand(self, n: int = 1, seed: Optional[str] = None) -> str:
        if seed:
            self.state.seed = seed
        lines = ["=== L.W.P. Model Expand (offline SSA) ===", ""]
        rank_before = self.rank()
        for i in range(max(1, min(8, n))):
            built = self.assemble(key=f"exp{self.state.words}-{i}")
            sid = str(uuid.uuid4())[:8]
            chapter_no = len(self.state.scenes) + 1
            scene = {
                "id": sid,
                "chapter": chapter_no,
                "text": built["text"],
                "words": built["words"],
                "event": built["event"],
                "direction": self.state.direction,
                "pov": self.state.pov,
                "genres": list(self.state.genres),
                "status": "draft",
                "art_prompt": chapter_art_prompt(
                    self.state.pov, self.state.genres, built["event"]
                ),
                "art_status": "pending",
                "art_path": "",
            }
            self.state.scenes.append(scene)
            self.state.words += built["words"]
            self.state.events += 1
            self.state.last_text = built["text"]
            self.state.last_id = sid
            self.state.bible_facts.append(built["event"])
            self.state.bible_facts = self.state.bible_facts[-40:]
            lines.append(
                f"— scene {sid} · ch{chapter_no:02d} · {built['words']}w · {self.state.direction} —"
            )
            lines.append(
                built["text"][:1200] + ("…" if len(built["text"]) > 1200 else "")
            )
            lines.append("")
        rank_after = self.rank()
        if rank_after != rank_before:
            mid = str(uuid.uuid4())[:8]
            detail = (
                f"The story crosses {self.state.words} words, rising "
                f"from {rank_before} to {rank_after}."
            )
            self.state.milestones.append(
                {
                    "id": mid,
                    "type": "rank_up",
                    "from": rank_before,
                    "to": rank_after,
                    "words": self.state.words,
                    "art_prompt": milestone_art_prompt(
                        "rank_up", detail, self.state.pov, self.state.genres
                    ),
                    "art_status": "pending",
                    "art_path": "",
                }
            )
            lines.append(
                f"★ milestone {mid} · rank {rank_before} → {rank_after} · art pending"
            )
            lines.append("")
        pending = sum(
            1
            for s in self.state.scenes
            if s.get("art_status") != "done"
        ) + sum(1 for m in self.state.milestones if m.get("art_status") != "done")
        self._persist()
        lines.append(
            f"Totals: words={self.state.words} rank={self.rank()} "
            f"anomaly={self.anomaly()} rom={'yes' if self.state.rom else 'no'} "
            f"art_pending={pending}"
        )
        try:
            from levi.brain.corpus import Corpus

            Corpus().add(
                f"L.W.P. expand {n} scenes seed={self.state.seed[:80]}",
                kind="INFERENCE",
                source="lwp_model",
                tags=["lwp", "expand", self.state.direction],
            )
        except Exception:
            pass
        return "\n".join(lines)

    def deny_last(self) -> str:
        if not self.state.scenes:
            return "Nothing to deny."
        last = self.state.scenes.pop()
        self.state.words = max(0, self.state.words - int(last.get("words") or 0))
        text = last.get("text") or ""
        sents = re.split(r"(?<=\.)\s+", text)
        self.state.ghost = " ".join(sents[:2])
        self.state.vault.append(
            {
                "id": last.get("id"),
                "note": f"denied {last.get('event')}",
                "seed": self.state.seed,
            }
        )
        self.state.last_text = (
            self.state.scenes[-1]["text"] if self.state.scenes else ""
        )
        self.state.last_id = self.state.scenes[-1]["id"] if self.state.scenes else ""
        self._persist()
        return f"Denied → Void. Ghost armed ({len(self.state.ghost)} chars). words={self.state.words}"

    def approve_last(self) -> str:
        if not self.state.scenes:
            return "Nothing to approve."
        last = self.state.scenes[-1]
        last["status"] = "approved"
        self.state.bible_facts.append(last.get("event") or "approved")
        self._persist()
        return f"Approved into bible: {last.get('event')}"

    def reim_forks(self, seed: Optional[str] = None, tracks: int = 3) -> str:
        seed = seed or self.state.seed
        tracks = max(2, min(4, int(tracks)))
        dirs = ["forward", "reverse", "inverse", "free"]
        lines = [f"=== REIM Parallel Echo · {tracks} tracks ===", ""]
        tracks_data: List[Dict[str, Any]] = []
        for i in range(tracks):
            d = dirs[i % 4]
            built = self.assemble(
                seed=seed, direction=d, key=f"reim{i}{seed}", target=220
            )
            tid = str(uuid.uuid4())[:8]
            tracks_data.append(
                {
                    "id": tid,
                    "index": i,
                    "direction": d,
                    "text": built["text"],
                    "words": built["words"],
                }
            )
            lines.append(f"Track {chr(65 + i)} · {d} · {built['words']}w · id={tid}")
            lines.append(built["text"][:400] + "…")
            lines.append("")
        self.state.tracks = tracks_data
        self._persist()
        lines.append("Crown with: engine.crown_track(0..n-1) or levi model --crown N")
        return "\n".join(lines)

    def wyrd_rupture(self, lens: str = "mccarthy") -> str:
        if self.anomaly() <= 0:
            return "Budget exhausted. Write ~20k more words before another rupture."
        prose = ROM_LENSES.get(lens, ROM_LENSES["mccarthy"])
        self.state.ruptures += 1
        self.state.rom = {
            "lens": lens,
            "text": prose,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        w = _words(prose)
        self.state.words += w
        self.state.events += 1
        self.state.last_text = prose
        self.state.bible_scars.append(f"rupture/{lens}")
        self.state.bible_facts.append(f"Wyrd-ROM ({lens}) immutable")
        self.state.scenes.append(
            {
                "id": str(uuid.uuid4())[:8],
                "text": prose,
                "words": w,
                "event": f"rupture/{lens}",
                "direction": self.state.direction,
                "pov": self.state.pov,
                "genres": list(self.state.genres),
                "status": "rom",
            }
        )
        self._persist()
        return (
            f"=== Wyrd-Rupture · {lens} · immutable ===\n\n{prose}\n\n"
            f"rank={self.rank()} anomaly={self.anomaly()} words={self.state.words}"
        )

    def status(self) -> str:
        st = self.state
        pct = min(100.0, (st.words / GOLD) * 100)
        lines = [
            "=== L.W.P. Model Engine (offline SSA) ===",
            f"words={st.words}  gold_path={pct:.1f}%  rank={self.rank()}  anomaly={self.anomaly()}",
            f"direction={st.direction}  phase={st.phase}  power={st.power}  pov={st.pov}",
            f"genres={st.genres}  scenes={len(st.scenes)}  vault={len(st.vault)}  rom={'yes' if st.rom else 'no'}",
            f"ghost={'armed' if st.ghost else '—'}  seal=L.W.P.",
            "",
            "UI: static/lwp-model.html · CLI: levi lwp-model --expand|--reim|--deny|--rupture",
            "Cloud is optional booster — never owns continuity.",
        ]
        return "\n".join(lines)

    def configure(self, **kwargs: Any) -> str:
        st = self.state
        for k, v in kwargs.items():
            if v is None:
                continue
            if k not in ModelState.__dataclass_fields__:
                raise ValueError(
                    f"unknown manuscript setting {k!r}: choose from "
                    f"{sorted(ModelState.__dataclass_fields__)}"
                )
            if k == "genres" and isinstance(v, str):
                v = [x.strip() for x in v.split(",") if x.strip()]
            _validate_config_value(k, v)
            setattr(st, k, v)
        self._persist()
        return self.status()

    def set_phase(self, phase: str) -> str:
        if phase not in PHASES:
            return f"Unknown phase. Choose: {', '.join(PHASES)}"
        if phase != self.state.phase:
            old = self.state.phase
            self.state.phase = phase
            mid = str(uuid.uuid4())[:8]
            detail = f"The story turns from phase '{old}' to '{phase}'."
            self.state.milestones.append(
                {
                    "id": mid,
                    "type": "phase_change",
                    "from": old,
                    "to": phase,
                    "words": self.state.words,
                    "art_prompt": milestone_art_prompt(
                        "phase_change", detail, self.state.pov, self.state.genres
                    ),
                    "art_status": "pending",
                    "art_path": "",
                }
            )
        self._persist()
        return self.status()

    def pending_art(self) -> List[Dict[str, Any]]:
        """Every chapter and major point whose art is not yet rendered.

        Legacy scenes (created before the art law) get their brief derived
        on the fly — the law is retroactive.
        """
        out: List[Dict[str, Any]] = []
        for idx, s in enumerate(self.state.scenes, start=1):
            if s.get("art_status") == "done":
                continue
            prompt = s.get("art_prompt") or chapter_art_prompt(
                s.get("pov", self.state.pov),
                s.get("genres", self.state.genres),
                s.get("event", ""),
            )
            ch = s.get("chapter", idx)
            out.append(
                {
                    "kind": "chapter",
                    "ref": s.get("id", ""),
                    "title": f"Chapter {ch:02d}",
                    "prompt": prompt,
                    "filename": f"ch{ch:02d}-{s.get('id', 'unknown')}.png",
                }
            )
        for m in self.state.milestones:
            if m.get("art_status") == "done":
                continue
            out.append(
                {
                    "kind": "milestone",
                    "ref": m.get("id", ""),
                    "title": f"Milestone {m.get('type', '')} {m.get('from', '')}→{m.get('to', '')}",
                    "prompt": m.get("art_prompt", ""),
                    "filename": f"milestone-{m.get('type', 'point')}-{m.get('id', 'unknown')}.png",
                }
            )
        return out

    def register_art(self, ref: str, path: str) -> str:
        """Record a rendered art file against a chapter or milestone.

        Law: fulfillment only fills art_path/art_status — words, rank,
        scene text, and milestones are never touched here.
        """
        for s in self.state.scenes:
            if s.get("id") == ref:
                s["art_path"] = path
                s["art_status"] = "done"
                self._persist()
                return f"art registered · chapter {s.get('chapter', '?')} ({ref}) → {path}"
        for m in self.state.milestones:
            if m.get("id") == ref:
                m["art_path"] = path
                m["art_status"] = "done"
                self._persist()
                return f"art registered · milestone {m.get('type', '')} ({ref}) → {path}"
        return f"no chapter or milestone with ref {ref!r}"

    def set_power(self, power: str) -> str:
        if power not in POWERS:
            return f"Unknown power. Choose: {', '.join(POWERS)}"
        self.state.power = power
        self._persist()
        return self.status()

    def set_direction(self, direction: str) -> str:
        if direction not in DIRS:
            return f"Unknown direction. Choose: {', '.join(DIRS)}"
        self.state.direction = direction
        self._persist()
        return self.status()

    def crown_track(self, index: int = 0) -> str:
        """Crown a Parallel Echo / REIM track into continuity (HITL-style commit)."""
        if not self.state.tracks:
            # synthesize from last reim if empty
            return "No tracks. Run reim_forks first, then crown."
        if index < 0 or index >= len(self.state.tracks):
            return f"Track index out of range (0..{len(self.state.tracks) - 1})"
        t = self.state.tracks[index]
        self.state.crowned = t.get("id") or str(index)
        text = t.get("text") or ""
        w = _words(text)
        sid = str(uuid.uuid4())[:8]
        self.state.scenes.append(
            {
                "id": sid,
                "text": text,
                "words": w,
                "event": f"crown/track{index}",
                "direction": t.get("direction", self.state.direction),
                "pov": self.state.pov,
                "genres": list(self.state.genres),
                "status": "crowned",
            }
        )
        self.state.words += w
        self.state.events += 1
        self.state.last_text = text
        self.state.last_id = sid
        self.state.bible_facts.append(f"Crowned track {index} into continuity")
        self._persist()
        return f"=== Crowned track {index} ===\n\n{text[:600]}{'…' if len(text) > 600 else ''}\n\nwords={self.state.words} rank={self.rank()}"

    def causal_bleed(self) -> str:
        """Prefer ghost / denied material as nonlocal stain (Mass Butterfly class)."""
        st = self.state
        if st.ghost:
            note = f"Causal bleed · ghost: {st.ghost[:240]}"
        elif st.vault:
            last = st.vault[-1]
            note = f"Causal bleed · vault: {(last.get('text') or last.get('event') or '')[:240]}"
        elif st.bible_scars:
            note = f"Causal bleed · scar: {st.bible_scars[-1]}"
        else:
            note = "Causal bleed · latent (no ghost/vault/scar yet)"
        st.causal_notes.append(note)
        self._persist()
        return note

    def manuscript(self, limit: int = 0) -> str:
        """Export continuity as manuscript (approved + crowned + rom; drafts optional)."""
        scenes = list(self.state.scenes)
        if limit and limit > 0:
            scenes = scenes[-limit:]
        lines = [
            "L.W.P. × LEVI Manuscript",
            f"words={self.state.words} rank={self.rank()} phase={self.state.phase} power={self.state.power}",
            f"direction={self.state.direction} pov={self.state.pov}",
            f"genres={', '.join(self.state.genres)}",
            "=" * 48,
            "",
        ]
        for s in scenes:
            status = s.get("status") or "draft"
            lines.append(
                f"--- [{status}] {s.get('event', '')} · {s.get('direction', '')} ---"
            )
            lines.append(s.get("text") or "")
            lines.append("")
        if self.state.rom:
            lines.append("--- [rom immutable] ---")
            lines.append(self.state.rom.get("text") or "")
        if self.state.ghost:
            lines.append("")
            lines.append(f"[ghost armed] {self.state.ghost[:400]}")
        return "\n".join(lines)

    def resolve_genres(self, raw: Optional[str] = None) -> List[str]:
        """Bridge to 97-genre registry when available; keep body templates for known keys."""
        if raw:
            parts = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
        else:
            parts = list(self.state.genres)
        try:
            from levi.graph.genres import GenreRegistry

            reg = GenreRegistry()
            resolved = []
            for p in parts:
                g = reg.get(p) or reg.get(p.lower().replace(" ", "_"))
                resolved.append(g.id if g else p.lower().replace(" ", "_"))
            if resolved:
                self.state.genres = resolved[:6]
                self._persist()
            return self.state.genres
        except Exception:
            self.state.genres = [p.lower().replace(" ", "_") for p in parts][:6]
            self._persist()
            return self.state.genres

    def optional_polish(
        self, text: str, instruction: str = "Tighten literary prose; keep meaning."
    ) -> str:
        """Optional model relay polish — never required; offline text returned on failure."""
        try:
            from levi.model.relay import ModelRelay

            relay = ModelRelay()
            prompt = f"{instruction}\n\n---\n{text[:3000]}"
            # GenerationRequest path varies; use router status first
            st = relay.router.status() if hasattr(relay, "router") else {}
            if not st.get("local_available") and not getattr(
                relay.config, "cloud_endpoints", None
            ):
                return text
            # Best-effort: if relay has generate
            if hasattr(relay, "generate"):
                out = relay.generate(prompt)
                if isinstance(out, str) and len(out) > 40:
                    return out
            return text
        except Exception:
            return text

    def full_snapshot(self) -> Dict[str, Any]:
        st = self.state
        return {
            "words": st.words,
            "rank": self.rank(),
            "anomaly": self.anomaly(),
            "gold_pct": min(100.0, (st.words / GOLD) * 100),
            "direction": st.direction,
            "phase": st.phase,
            "power": st.power,
            "pov": st.pov,
            "genres": list(st.genres),
            "scenes": len(st.scenes),
            "vault": len(st.vault),
            "tracks": len(st.tracks),
            "crowned": st.crowned,
            "rom": bool(st.rom),
            "ghost": bool(st.ghost),
            "causal_notes": len(st.causal_notes),
            "seal": "L.W.P.",
            "cloud_role": "optional booster — never owns continuity",
        }
