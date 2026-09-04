"""
L.W.P. Model Engine — offline literary spine (SSA).

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
    "horror": ["Dread arrived with a filing number.", "The room kept a second temperature."],
    "noir": ["Compromise was already the furniture.", "Style remained after trust left."],
}
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
    "forward": ["The weather kept the receipt.", "Nothing was finished; only advanced."],
    "reverse": ["The earlier light still held the later cost.", "Spool held."],
    "inverse": ["Polarity settled; the door remembered both prices.", "Inversion complete."],
    "free": ["The jump left a scar the locks would honor.", "Continuity held across the cut."],
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelState":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)


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
        if self.state.power == "gain":
            n += 70
        if self.state.power == "immortal":
            n += 120
        if self.state.power == "booster":
            n += 30
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
            body = GENRES_BODY.get(g, GENRES_BODY["literary"])
            parts.append(r.choice(body))
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
            parts.append("ROM law holds: the genome will not contradict the locked cartridge.")
        if st.ghost and (direction in ("reverse", "inverse") or riem):
            parts.append(f"Phantom from a denied hour: {st.ghost}")
        if st.power == "repeater":
            parts.append("Scar liturgy re-entered so the distance would not rot.")
        if st.power == "gain" or st.phase == "gold_push":
            parts.append("Gain holds. Repeaters keep the signal from rotting at distance.")
        parts.append(r.choice(CLOSE.get(direction, CLOSE["forward"])))
        text = " ".join(p for p in parts if p)
        need = target or self.target_words()
        pool = []
        for g in genres:
            pool.extend(GENRES_BODY.get(g, []))
        pool.extend(GENRES_BODY["literary"])
        guard = 0
        while _words(text) < need and guard < 14:
            text += " " + r.choice(pool) + " " + r.choice(CLOSE.get(direction, CLOSE["forward"]))
            guard += 1
        event = f"{direction}: {seed.split('.')[0][:48]}"
        return {"text": text, "words": _words(text), "event": event}

    def expand(self, n: int = 1, seed: Optional[str] = None) -> str:
        if seed:
            self.state.seed = seed
        lines = ["=== L.W.P. Model Expand (offline SSA) ===", ""]
        for i in range(max(1, min(8, n))):
            built = self.assemble(key=f"exp{self.state.words}-{i}")
            sid = str(uuid.uuid4())[:8]
            scene = {
                "id": sid,
                "text": built["text"],
                "words": built["words"],
                "event": built["event"],
                "direction": self.state.direction,
                "pov": self.state.pov,
                "genres": list(self.state.genres),
                "status": "draft",
            }
            self.state.scenes.append(scene)
            self.state.words += built["words"]
            self.state.events += 1
            self.state.last_text = built["text"]
            self.state.last_id = sid
            self.state.bible_facts.append(built["event"])
            self.state.bible_facts = self.state.bible_facts[-40:]
            lines.append(f"— scene {sid} · {built['words']}w · {self.state.direction} —")
            lines.append(built["text"][:1200] + ("…" if len(built["text"]) > 1200 else ""))
            lines.append("")
        self._persist()
        lines.append(
            f"Totals: words={self.state.words} rank={self.rank()} "
            f"anomaly={self.anomaly()} rom={'yes' if self.state.rom else 'no'}"
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
        self.state.vault.append({"id": last.get("id"), "note": f"denied {last.get('event')}", "seed": self.state.seed})
        self.state.last_text = self.state.scenes[-1]["text"] if self.state.scenes else ""
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
            built = self.assemble(seed=seed, direction=d, key=f"reim{i}{seed}", target=220)
            tid = str(uuid.uuid4())[:8]
            tracks_data.append({
                "id": tid,
                "index": i,
                "direction": d,
                "text": built["text"],
                "words": built["words"],
            })
            lines.append(f"Track {chr(65+i)} · {d} · {built['words']}w · id={tid}")
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
        self.state.rom = {"lens": lens, "text": prose, "ts": datetime.now(timezone.utc).isoformat()}
        w = _words(prose)
        self.state.words += w
        self.state.events += 1
        self.state.last_text = prose
        self.state.bible_scars.append(f"rupture/{lens}")
        self.state.bible_facts.append(f"Wyrd-ROM ({lens}) immutable")
        self.state.scenes.append({
            "id": str(uuid.uuid4())[:8],
            "text": prose,
            "words": w,
            "event": f"rupture/{lens}",
            "direction": self.state.direction,
            "pov": self.state.pov,
            "genres": list(self.state.genres),
            "status": "rom",
        })
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
            if k == "genres" and isinstance(v, str):
                v = [x.strip() for x in v.split(",") if x.strip()]
            if hasattr(st, k):
                setattr(st, k, v)
        self._persist()
        return self.status()

    def set_phase(self, phase: str) -> str:
        if phase not in PHASES:
            return f"Unknown phase. Choose: {', '.join(PHASES)}"
        self.state.phase = phase
        self._persist()
        return self.status()

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
            return f"Track index out of range (0..{len(self.state.tracks)-1})"
        t = self.state.tracks[index]
        self.state.crowned = t.get("id") or str(index)
        text = t.get("text") or ""
        w = _words(text)
        sid = str(uuid.uuid4())[:8]
        self.state.scenes.append({
            "id": sid,
            "text": text,
            "words": w,
            "event": f"crown/track{index}",
            "direction": t.get("direction", self.state.direction),
            "pov": self.state.pov,
            "genres": list(self.state.genres),
            "status": "crowned",
        })
        self.state.words += w
        self.state.events += 1
        self.state.last_text = text
        self.state.last_id = sid
        self.state.bible_facts.append(f"Crowned track {index} into continuity")
        self._persist()
        return f"=== Crowned track {index} ===\n\n{text[:600]}{'…' if len(text)>600 else ''}\n\nwords={self.state.words} rank={self.rank()}"

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
            lines.append(f"--- [{status}] {s.get('event','')} · {s.get('direction','')} ---")
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

    def optional_polish(self, text: str, instruction: str = "Tighten literary prose; keep meaning.") -> str:
        """Optional model relay polish — never required; offline text returned on failure."""
        try:
            from levi.model.relay import ModelRelay
            relay = ModelRelay()
            prompt = f"{instruction}\n\n---\n{text[:3000]}"
            # GenerationRequest path varies; use router status first
            st = relay.router.status() if hasattr(relay, "router") else {}
            if not st.get("local_available") and not getattr(relay.config, "cloud_endpoints", None):
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

