"""
L.W.P. Character Graph — unbounded character generation.

Axes interpenetrate (drive × wound × method × voice × domain × era × bond).
Each node is a stable id; edges are relation types. Unlimited types via
combinatorics — LEVI-original, not a stock NPC table dump.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import random


DEFAULT = Path.home() / ".levi" / "lwp_character_graph.json"

DRIVES = [
    "belonging",
    "mastery",
    "justice",
    "freedom",
    "legacy",
    "curiosity",
    "safety",
    "status",
    "care",
    "truth",
    "creation",
    "redemption",
]
WOUNDS = [
    "abandonment",
    "humiliation",
    "betrayal",
    "powerlessness",
    "erasure",
    "debt",
    "exile",
    "broken_promise",
    "witnessed_harm",
    "failed_duty",
]
METHODS = [
    "strategy",
    "charm",
    "force",
    "service",
    "withdrawal",
    "analysis",
    "humor",
    "ritual",
    "craft",
    "network",
    "sabotage",
    "endurance",
]
VOICES = [
    "spare",
    "lyrical",
    "clinical",
    "ironic",
    "tender",
    "blunt",
    "archaic",
    "street",
    "scholarly",
    "fragmented",
    "musical",
    "silent_heavy",
]
DOMAINS = [
    "city_under",
    "coastal",
    "archive",
    "frontier",
    "court",
    "lab",
    "temple",
    "market",
    "war_camp",
    "station",
    "forest_edge",
    "orbital",
]
ERAS = [
    "mythic",
    "industrial",
    "digital",
    "collapse",
    "reconstruction",
    "eternal_night",
    "high_summer",
    "deep_winter",
]
BONDS = [
    "rival",
    "mentor",
    "debtor",
    "kin",
    "mirror",
    "hunter",
    "ward",
    "co_conspirator",
    "ex",
    "patron",
    "witness",
    "stranger_who_knows",
]


def _cid(*parts: str) -> str:
    return "char." + hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


@dataclass
class CharacterNode:
    id: str
    name: str
    drive: str
    wound: str
    method: str
    voice: str
    domain: str
    era: str
    want: str
    need: str
    tells: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def blurb(self) -> str:
        return (
            f"{self.name} — drive:{self.drive} wound:{self.wound} method:{self.method} "
            f"voice:{self.voice} in {self.domain}/{self.era}. Want: {self.want}. Need: {self.need}."
        )


@dataclass
class CharacterEdge:
    a: str
    b: str
    relation: str
    tension: str


def _name_from_axes(drive: str, wound: str, method: str, seed: int) -> str:
    roots = [
        "Ash",
        "Nyx",
        "Quill",
        "Vesper",
        "Reed",
        "Sable",
        "Iota",
        "Kestrel",
        "Morrow",
        "Pell",
        "Wren",
        "Cass",
        "Orin",
        "Lumen",
        "Harrow",
        "Syl",
    ]
    suffixes = ["e", "an", "is", "el", "or", "yn", "a", ""]
    random.seed(seed)
    return random.choice(roots) + random.choice(suffixes) + "-" + drive[:3].title()


class CharacterGraph:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT
        self.nodes: Dict[str, CharacterNode] = {}
        self.edges: List[CharacterEdge] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        for n in raw.get("nodes") or []:
            # One malformed node never aborts the whole load.
            if isinstance(n, dict) and isinstance(n.get("id"), str) and n["id"]:
                try:
                    self.nodes[n["id"]] = CharacterNode(**n)
                except TypeError:
                    continue
        for e in raw.get("edges") or []:
            if isinstance(e, dict):
                try:
                    self.edges.append(CharacterEdge(**e))
                except TypeError:
                    continue

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for e in self.edges],
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def theoretical_types(self) -> int:
        return (
            len(DRIVES)
            * len(WOUNDS)
            * len(METHODS)
            * len(VOICES)
            * len(DOMAINS)
            * len(ERAS)
        )

    def mint(
        self,
        drive: Optional[str] = None,
        wound: Optional[str] = None,
        method: Optional[str] = None,
        voice: Optional[str] = None,
        domain: Optional[str] = None,
        era: Optional[str] = None,
        seed: Optional[str] = None,
    ) -> CharacterNode:
        axes = {
            "drive": (drive, DRIVES),
            "wound": (wound, WOUNDS),
            "method": (method, METHODS),
            "voice": (voice, VOICES),
            "domain": (domain, DOMAINS),
            "era": (era, ERAS),
        }
        for axis, (value, options) in axes.items():
            if value is not None and value not in options:
                raise ValueError(f"unknown {axis} {value!r}: choose one of {options}")
        if seed is not None and not isinstance(seed, str):
            raise ValueError(f"seed must be a string or None, got {seed!r}")
        rng = hashlib.sha1((seed or str(len(self.nodes))).encode()).hexdigest()

        def pick(opts, i):
            return opts[int(rng[i : i + 2], 16) % len(opts)]

        drive = drive or pick(DRIVES, 0)
        wound = wound or pick(WOUNDS, 2)
        method = method or pick(METHODS, 4)
        voice = voice or pick(VOICES, 6)
        domain = domain or pick(DOMAINS, 8)
        era = era or pick(ERAS, 10)
        cid = _cid(drive, wound, method, voice, domain, era, seed or rng)
        name = _name_from_axes(drive, wound, method, int(rng[:6], 16))
        want = f"to secure {drive} without admitting the {wound}"
        need = f"to face {wound} using {method} without losing {drive}"
        tells = [
            f"voice leans {voice}",
            f"default method: {method}",
            f"places that hurt: reminders of {wound}",
        ]
        node = CharacterNode(
            id=cid,
            name=name,
            drive=drive,
            wound=wound,
            method=method,
            voice=voice,
            domain=domain,
            era=era,
            want=want,
            need=need,
            tells=tells,
            tags=["lwp", "character_graph"],
        )
        self.nodes[cid] = node
        self._persist()
        return node

    def mint_batch(self, n: int = 5, seed: Optional[str] = None) -> List[CharacterNode]:
        if isinstance(n, bool) or not isinstance(n, int):
            raise ValueError(f"mint_batch n must be an int, got {n!r}")
        if seed is not None and not isinstance(seed, str):
            raise ValueError(f"seed must be a string or None, got {seed!r}")
        out = []
        for i in range(max(1, min(n, 50))):
            out.append(self.mint(seed=f"{seed or 'batch'}-{i}"))
        return out

    def link(self, a: str, b: str, relation: Optional[str] = None) -> CharacterEdge:
        for label, node_id in (("a", a), ("b", b)):
            if not isinstance(node_id, str) or not node_id:
                raise ValueError(f"link {label} must be a non-empty node id string")
            if node_id not in self.nodes:
                raise ValueError(
                    f"link {label}: unknown character {node_id!r} "
                    f"(known: {len(self.nodes)} nodes)"
                )
        if relation is not None and relation not in BONDS:
            raise ValueError(f"unknown relation {relation!r}: choose one of {BONDS}")
        relation = relation or BONDS[len(self.edges) % len(BONDS)]
        tension = f"{relation} under competing drives"
        e = CharacterEdge(a=a, b=b, relation=relation, tension=tension)
        self.edges.append(e)
        self._persist()
        return e

    def weave(self, n_chars: int = 4) -> str:
        if isinstance(n_chars, bool) or not isinstance(n_chars, int):
            raise ValueError(f"weave n_chars must be an int, got {n_chars!r}")
        chars = self.mint_batch(n_chars)
        lines = [
            "=== L.W.P. Character Graph Weave ===",
            f"Theoretical axis types: {self.theoretical_types():,}",
            "",
        ]
        for c in chars:
            lines.append(c.blurb())
            lines.append(f"  id={c.id}")
        if len(chars) >= 2:
            for i in range(len(chars) - 1):
                e = self.link(chars[i].id, chars[i + 1].id)
                lines.append(
                    f"Edge: {chars[i].name} —{e.relation}→ {chars[i + 1].name} ({e.tension})"
                )
        lines.append("")
        lines.append(f"Graph size: {len(self.nodes)} nodes, {len(self.edges)} edges")
        lines.append(
            "Unlimited further types via axis remix — unique L.W.P. combinatorics."
        )
        return "\n".join(lines)

    def format_status(self) -> str:
        return (
            f"=== Character Graph ===\n"
            f"Nodes: {len(self.nodes)}  Edges: {len(self.edges)}\n"
            f"Theoretical distinct axis combos: {self.theoretical_types():,}\n"
            f"Axes: drive×wound×method×voice×domain×era\n"
            f"Mint: levi characters --mint\n"
            f"Weave: levi characters --weave -n 5\n"
        )
