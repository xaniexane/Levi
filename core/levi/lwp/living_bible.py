"""L.W.P. Living Bible — the world's memory, built FROM the manuscript.

KFX2 reversal of Sudowrite's Story Bible / NovelAI's Lorebook: they make the
writer key the world's memory in by hand (and Sudowrite refuses to export
it). Ours reads the draft you already wrote, *proposes* bible entries, and
the writer confirms or rejects each one. The bible is a local JSON file at
``~/.levi/lwp_machine/`` and it leaves with the writer in every export —
always, bible included.

Paired-mind shape: ingestion is the *proposer*; the writer is the *verifier*.
Nothing the proposer suggests enters the canon until the verifier says so.
``reject_all()`` is one call.

The ternary shows up in the entry lifecycle: an entry is never just
in-or-out; it is PROPOSED (the skipped third state — neither canon nor
trash, waiting on the writer), CONFIRMED, or REJECTED. No binary
accepted/ignored trap.

Everything here is deterministic, offline, stdlib-only. Mythos (tarot arc
frames, spreads) is poetry and belongs to later phases; this module makes
no mythic or sentience-adjacent claims. The press proposes; the writer
disposes — that is the binding law coded, not the law described.
"""

from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

LWP_MACHINE_DIR = Path.home() / ".levi" / "lwp_machine"

# ---------------------------------------------------------------------------
# Ternary entry lifecycle: PROPOSED is the third state.
# ---------------------------------------------------------------------------

PROPOSED = "proposed"
CONFIRMED = "confirmed"
REJECTED = "rejected"
STATUSES = (PROPOSED, CONFIRMED, REJECTED)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(text: str) -> str:
    """Deterministic short id from text (stable across runs)."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------


@dataclass
class CharacterEntry:
    id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    status: str = PROPOSED
    evidence: List[str] = field(default_factory=list)
    confirmed_at: Optional[str] = None


@dataclass
class RelationEntry:
    id: str
    source: str  # character id
    target: str  # character id
    relation: str = "linked"
    status: str = PROPOSED
    evidence: List[str] = field(default_factory=list)
    confirmed_at: Optional[str] = None


@dataclass
class WorldRuleEntry:
    id: str
    rule: str
    scope: str = "world"
    status: str = PROPOSED
    evidence: List[str] = field(default_factory=list)
    confirmed_at: Optional[str] = None


@dataclass
class TimelineEntry:
    id: str
    order: int = 0
    summary: str = ""
    characters: List[str] = field(default_factory=list)  # character ids
    status: str = PROPOSED
    evidence: List[str] = field(default_factory=list)
    confirmed_at: Optional[str] = None


ENTRY_KINDS = {
    "characters": CharacterEntry,
    "relations": RelationEntry,
    "world_rules": WorldRuleEntry,
    "timeline": TimelineEntry,
}


# ---------------------------------------------------------------------------
# Deterministic manuscript ingestion (the proposer half of the pair)
# ---------------------------------------------------------------------------

# Dialogue attribution lines:  `Name:`  `Name --`  `"..." Name said`
_DIALOGUE_SPEAKER = re.compile(
    r"""^\s*
    (?P<speaker>[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,2})
    \s*(?::|--|—)\s*\S""",
    re.VERBOSE,
)
_ATTRIBUTION = re.compile(
    r"""\b(?P<speaker>[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+){0,2})
    \s+(?:said|says|asked|asks|replied|replies|whispered|shouted|muttered|answered)\b""",
    re.VERBOSE,
)
_CAPITALIZED = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")
# World-rule scent: sentences that smell like a law of the world.
_RULE_SCENT = re.compile(
    r"\b(must never|must always|can never|cannot|forbidden|no one|nobody|"
    r"never allowed|the law is|the rule is)\b",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")


def _paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _sentences(paragraph: str) -> List[str]:
    parts = [s.strip() for s in _SENTENCE_END.split(paragraph) if s.strip()]
    return parts


def _name_candidates(text: str) -> Dict[str, List[str]]:
    """speaker mentions -> evidence snippets. Deterministic, offline."""
    found: Dict[str, List[str]] = {}
    for line in text.splitlines():
        m = _DIALOGUE_SPEAKER.match(line) or _ATTRIBUTION.search(line)
        if m:
            name = " ".join(m.group("speaker").split())
            found.setdefault(name, []).append(line.strip()[:160])
    for para in _paragraphs(text):
        for m in _CAPITALIZED.finditer(para):
            name = " ".join(m.group(1).split())
            start = max(0, m.start() - 40)
            found.setdefault(name, []).append(para[start : start + 120].strip())
    return found


def _relation_candidates(text: str, char_ids: Dict[str, str]) -> List[Dict[str, Any]]:
    """Two characters named in the same paragraph -> a linked proposal."""
    out: List[Dict[str, Any]] = []
    names = {name.lower(): cid for name, cid in char_ids.items()}
    for para in _paragraphs(text):
        present = [
            cid
            for lname, cid in names.items()
            if re.search(r"\b" + re.escape(lname) + r"\b", para, re.IGNORECASE)
        ]
        for i, a in enumerate(present):
            for b in present[i + 1 :]:
                rid = "rel-" + _slug(a + ">" + b)
                if not any(r["id"] == rid for r in out):
                    out.append(
                        {
                            "id": rid,
                            "source": a,
                            "target": b,
                            "relation": "linked",
                            "evidence": [para[:160].strip()],
                        }
                    )
    return out


def _rule_candidates(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for para in _paragraphs(text):
        for sentence in _sentences(para):
            if _RULE_SCENT.search(sentence):
                rid = "rule-" + _slug(sentence[:80])
                if not any(r["id"] == rid for r in out):
                    out.append(
                        {
                            "id": rid,
                            "rule": sentence.strip()[:300],
                            "scope": "world",
                            "evidence": [sentence.strip()[:160]],
                        }
                    )
    return out


def _timeline_candidates(text: str, char_ids: Dict[str, str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for order, para in enumerate(_paragraphs(text)):
        sentences = _sentences(para)
        summary = sentences[0][:220] if sentences else para[:220]
        names = {name.lower(): cid for name, cid in char_ids.items()}
        present = [
            cid
            for lname, cid in names.items()
            if re.search(r"\b" + re.escape(lname) + r"\b", para, re.IGNORECASE)
        ]
        out.append(
            {
                "id": f"beat-{order:03d}",
                "order": order,
                "summary": summary.strip(),
                "characters": present,
                "evidence": [para[:160].strip()],
            }
        )
    return out


# ---------------------------------------------------------------------------
# The Living Bible
# ---------------------------------------------------------------------------


class LivingBible:
    """A durable, local, writer-verified memory of one fictional world.

    Persisted at ``~/.levi/lwp_machine/living_bible_<slug>.json``. Never
    leaves the device; never metered; exported with the manuscript, bible
    included — the export Sudowrite refuses to give.
    """

    def __init__(self, slug: str, store: Optional[Path] = None):
        self.slug = slug
        self.store = store or (LWP_MACHINE_DIR / f"living_bible_{slug}.json")
        self.characters: Dict[str, CharacterEntry] = {}
        self.relations: Dict[str, RelationEntry] = {}
        self.world_rules: Dict[str, WorldRuleEntry] = {}
        self.timeline: Dict[str, TimelineEntry] = {}
        self.ingest_count = 0
        self.load()

    # -- persistence ------------------------------------------------------

    def _payload(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "format": "lwp-living-bible/1",
            "updated_at": _utcnow(),
            "ingest_count": self.ingest_count,
            "characters": {k: asdict(v) for k, v in self.characters.items()},
            "relations": {k: asdict(v) for k, v in self.relations.items()},
            "world_rules": {k: asdict(v) for k, v in self.world_rules.items()},
            "timeline": {k: asdict(v) for k, v in self.timeline.items()},
        }

    def save(self) -> Path:
        self.store.parent.mkdir(parents=True, exist_ok=True)
        self.store.write_text(json.dumps(self._payload(), indent=2), encoding="utf-8")
        return self.store

    def load(self) -> None:
        if not self.store.exists():
            return
        data = json.loads(self.store.read_text(encoding="utf-8"))
        self.ingest_count = int(data.get("ingest_count", 0))
        for key, cls in ENTRY_KINDS.items():
            table = getattr(self, key)
            for eid, raw in data.get(key, {}).items():
                table[eid] = cls(
                    **{
                        k: raw.get(k, getattr(cls, k, None))
                        for k in cls.__dataclass_fields__
                    }
                )

    # -- proposer: ingest manuscript, propose entries ----------------------

    def ingest_manuscript(self, text: str, min_mentions: int = 2) -> Dict[str, int]:
        """Read the draft; propose bible entries. Returns proposal counts.

        Characters appearing fewer than ``min_mentions`` times stay
        un-proposed (no noise canonized as canon — the writer can still add
        anyone by hand via :meth:`add_character`).
        """
        text = text or ""
        counts: Dict[str, int] = {
            "characters": 0,
            "relations": 0,
            "world_rules": 0,
            "timeline": 0,
        }

        candidates = _name_candidates(text)
        char_ids: Dict[str, str] = {}
        for name, evidence in candidates.items():
            cid = "char-" + _slug(name.lower())
            char_ids[name] = cid
            mention_count = len(
                [
                    m
                    for m in re.finditer(
                        r"\b" + re.escape(name) + r"\b", text, re.IGNORECASE
                    )
                ]
            )
            if mention_count < min_mentions and cid not in self.characters:
                continue
            if cid not in self.characters:
                self.characters[cid] = CharacterEntry(
                    id=cid, name=name, evidence=evidence[:3]
                )
                counts["characters"] += 1
            else:
                merged = self.characters[cid].evidence + evidence[:1]
                self.characters[cid].evidence = merged[:3]

        for rel in _relation_candidates(text, char_ids):
            if rel["id"] not in self.relations:
                self.relations[rel["id"]] = RelationEntry(**rel)
                counts["relations"] += 1

        for rule in _rule_candidates(text):
            if rule["id"] not in self.world_rules:
                self.world_rules[rule["id"]] = WorldRuleEntry(**rule)
                counts["world_rules"] += 1

        # Timeline beats are proposed fresh per ingest of new paragraphs;
        # re-ingest replaces the proposal set so the bible tracks the draft.
        proposed_beats = _timeline_candidates(text, char_ids)
        for beat in proposed_beats:
            if beat["id"] not in self.timeline:
                self.timeline[beat["id"]] = TimelineEntry(**beat)
                counts["timeline"] += 1

        self.ingest_count += 1
        self.save()
        return counts

    def add_character(
        self, name: str, description: str = "", aliases: Optional[List[str]] = None
    ) -> CharacterEntry:
        """Writer adds a character by hand — always enters as PROPOSED."""
        cid = "char-" + _slug(name.lower())
        entry = self.characters.get(cid) or CharacterEntry(id=cid, name=name)
        entry.description = description
        entry.aliases = aliases or []
        entry.status = PROPOSED
        self.characters[cid] = entry
        self.save()
        return entry

    # -- verifier: writer confirms or rejects -----------------------------

    def _entry(self, entry_id: str) -> Any:
        for table in (self.characters, self.relations, self.world_rules, self.timeline):
            if entry_id in table:
                return table[entry_id]
        raise KeyError(f"no bible entry {entry_id!r}")

    def confirm(self, entry_id: str) -> Any:
        """Writer says yes — the proposal becomes canon."""
        entry = self._entry(entry_id)
        entry.status = CONFIRMED
        entry.confirmed_at = _utcnow()
        self.save()
        return entry

    def reject(self, entry_id: str) -> Any:
        """Writer says no — the proposal leaves the bible."""
        entry = self._entry(entry_id)
        entry.status = REJECTED
        self.save()
        return entry

    def reject_all(self, kind: Optional[str] = None) -> int:
        """Reject every proposal, in one key. (kind: characters/relations/
        world_rules/timeline or None for all.)"""
        tables = {
            "characters": self.characters,
            "relations": self.relations,
            "world_rules": self.world_rules,
            "timeline": self.timeline,
        }
        targets = [tables[kind]] if kind else list(tables.values())
        n = 0
        for table in targets:
            for entry in table.values():
                if entry.status == PROPOSED:
                    entry.status = REJECTED
                    n += 1
        self.save()
        return n

    def proposals(
        self, kind: Optional[str] = None, status: str = PROPOSED
    ) -> List[Any]:
        tables = {
            "characters": self.characters,
            "relations": self.relations,
            "world_rules": self.world_rules,
            "timeline": self.timeline,
        }
        picked = [tables[kind]] if kind else list(tables.values())
        return [e for t in picked for e in t.values() if e.status == status]

    # -- export: the bible always leaves with the manuscript --------------

    def export(self, path: Path | str) -> Path:
        """Plain-data export of the whole bible — the file Sudowrite keeps."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._payload(), indent=2), encoding="utf-8")
        return path

    def export_markdown(self, path: Path | str) -> Path:
        """Human-readable export — readable as plain data, no tooling needed."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Living Bible — {self.slug}",
            "",
            f"_Exported {_utcnow()}. Format: lwp-living-bible/1_",
            "_Confirmed entries are canon; proposed ones await the writer._",
            "",
        ]
        lines.append("## Characters")
        for c in sorted(self.characters.values(), key=lambda e: e.name):
            mark = (
                "✓" if c.status == CONFIRMED else ("·" if c.status == PROPOSED else "✗")
            )
            lines.append(f"- [{mark}] **{c.name}** ({c.status})")
            if c.aliases:
                lines.append(f"  - aliases: {', '.join(c.aliases)}")
            if c.description:
                lines.append(f"  - {c.description}")
        lines.append("")
        lines.append("## Relations")
        for r in sorted(self.relations.values(), key=lambda e: e.id):
            a = self.characters.get(r.source)
            b = self.characters.get(r.target)
            an = a.name if a else r.source
            bn = b.name if b else r.target
            lines.append(f"- {an} —{r.relation}→ {bn} ({r.status})")
        lines.append("")
        lines.append("## World rules")
        for w in sorted(self.world_rules.values(), key=lambda e: e.id):
            lines.append(f"- ({w.status}) {w.rule}")
        lines.append("")
        lines.append("## Timeline")
        for t in sorted(self.timeline.values(), key=lambda e: e.order):
            lines.append(f"- [{t.order}] ({t.status}) {t.summary}")
        lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def summary(self) -> Dict[str, Any]:
        counts: Dict[str, Any] = {}
        for key in ENTRY_KINDS:
            table = getattr(self, key)
            by = {s: 0 for s in STATUSES}
            for e in table.values():
                by[e.status] = by.get(e.status, 0) + 1
            counts[key] = {"total": len(table), **by}
        counts["slug"] = self.slug
        counts["ingests"] = self.ingest_count
        return counts
