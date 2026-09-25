"""L.W.P. Chronicle — canon-consistency machinery for the writing engine.

The Living Bible is the world's memory; the Chronicle is its *causality*.
Built from the pattern description only — original work, no external
code or text consulted. (Working title; final naming is Chauncey's.)

Four pieces, one binding law — propose, don't declare:

1. **Causal timeline.** Events carry causes and consequences. Recording an
   event with causes propagates it: the cause events gain it as a
   consequence. Chains are queryable both ways (``upstream`` /
   ``downstream``), with cycle guards so a tangled draft can't loop the
   engine.
2. **Chronicle documents + rolling summary.** Each session records a
   Markdown chronicle doc (details live there). ``fold_session`` carries
   the doc's key facts into a rolling summary, so a long campaign
   outlives any single context window: the summary travels, the docs
   stay home. Old facts compact into one line; the newest stay verbatim.
3. **Rules as data.** Rule packs are plain JSON files in ``rules/``.
   Delete the file and the rule is gone — no code changes, no rebuild.
   The engine re-reads the directory on every load.
4. **Canon-as-constraint.** CONFIRMED Living Bible entries are the
   constraint set. ``check_proposal`` rejects (with cited reasons) any
   proposed character / event / rule / fact that contradicts confirmed
   canon; ``propose`` writes clean proposals into the bible as PROPOSED
   and writes nothing for contradictions. Contradictions are *reported*,
   never auto-resolved — the writer disposes.

Honest contract
---------------
* Contradiction detection is lexical and heuristic, documented below —
  content-word overlap with a crude stemmer and a negation window. It is
  a tripwire for the writer, not a proof engine. False positives are
  possible; that is why nothing is ever auto-resolved.
* Everything is local and deterministic: sha1-derived ids, explicit
  ordering, no RNG, no network. ``home`` is caller-supplied (the
  echoverse entry pattern) — nothing writes the real ``~/.levi`` unless
  the caller points it there. Records are mode 0600.
* Mythos stays poetry: this module makes no sentience-adjacent claims.
* Nothing here touches publishing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from levi.lwp.living_bible import (
    CONFIRMED,
    PROPOSED,
    CharacterEntry,
    LivingBible,
    TimelineEntry,
    WorldRuleEntry,
)

_RECORD_MODE = 0o600
ROLLING_MAX_FACTS = 40

# ---------------------------------------------------------------------------
# Honest lexical machinery (documented heuristics, not NLP)
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "these", "those", "he", "she", "they",
    "his", "her", "their", "who", "which", "what", "when", "where",
    "may", "can", "could", "shall", "should", "must", "will", "would",
    "over", "under", "into", "out", "up", "down", "than", "then", "so",
    "but", "if",
}
_NEGATIONS = {
    "not", "no", "never", "cannot", "can't", "couldn't", "won't",
    "don't", "doesn't", "didn't", "isn't", "aren't", "wasn't",
    "weren't", "neither", "nor", "without", "forbidden", "n't",
}
_WORD = re.compile(r"[a-z']+")


def _stem(word: str) -> str:
    """Crude stemmer: strip common suffixes so 'flies' meets 'fly'.

    Documented imperfection: 'dies' -> 'dy', 'dances' -> 'danc'. The
    stemmer only needs to be *consistent* across the rule text and the
    proposal text, not correct English.
    """
    if word.endswith("ies") and len(word) - 3 >= 2:
        return word[:-3] + "y"
    for suffix in ("ing", "es", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> List[str]:
    return _WORD.findall((text or "").lower())


def _content_words(text: str) -> Set[str]:
    """Stemmed content words: no stopwords, no negations, length > 2."""
    out: Set[str] = set()
    for tok in _tokens(text):
        if tok in _STOPWORDS or tok in _NEGATIONS or len(tok) <= 2:
            continue
        out.add(_stem(tok))
    return out


def _is_negated(text: str, phrase_words: Set[str]) -> bool:
    """True if a negation token sits within 4 tokens before the phrase.

    Heuristic: "dragons cannot fly" should NOT contradict "dragons can
    never fly" — the proposal agrees with the denial.
    """
    toks = _tokens(text)
    targets = {_stem(w) for w in phrase_words}
    for i, tok in enumerate(toks):
        if _stem(tok) in targets:
            window = toks[max(0, i - 4) : i]
            if any(w in _NEGATIONS for w in window):
                return True
    return False


# "X can never Y" -> subject "X", denied clause "Y".
_DENIAL_PATTERNS = [
    re.compile(r"^(?P<subj>.+?)\s+(?:can|could)\s+never\s+(?P<denied>.+)$", re.I),
    re.compile(r"^(?P<subj>.+?)\s+can(?:not|'t)\s+(?P<denied>.+)$", re.I),
    re.compile(r"^(?P<subj>.+?)\s+must\s+never\s+(?P<denied>.+)$", re.I),
    re.compile(r"^no\s+one\s+(?P<denied>.+)$", re.I),
    re.compile(r"^nobody\s+(?P<denied>.+)$", re.I),
    re.compile(r"^(?P<subj>.+?)\s+is\s+forbidden\s+(?:to\s+)?(?P<denied>.+)$", re.I),
]


def _denies_from_rule_text(rule_text: str) -> Optional[Dict[str, Set[str]]]:
    """Extract (subject words, denied words) from a rule's phrasing.

    Returns None when the rule isn't phrased as a denial — only denials
    can be contradicted, so non-denial rules simply don't participate.
    """
    text = (rule_text or "").strip().rstrip(".")
    for pat in _DENIAL_PATTERNS:
        m = pat.match(text)
        if m:
            denied = _content_words(m.group("denied"))
            if not denied:
                return None
            subj = _content_words(m.group("subj")) if "subj" in m.groupdict() else set()
            return {"subject": subj, "denied": denied}
    return None


def _contradicts_denial(proposal_text: str, denial: Dict[str, Set[str]]) -> bool:
    """A proposal contradicts a denial when it asserts the denied thing.

    Requires: all denied content words present, at least one subject
    word present (when the rule names a subject), and no negation
    shielding the assertion.
    """
    prop_words = _content_words(proposal_text)
    if not denial["denied"] <= prop_words:
        return False
    if denial["subject"] and not (denial["subject"] & prop_words):
        return False
    return not _is_negated(proposal_text, denial["denied"])


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]


# ---------------------------------------------------------------------------
# Events — the causal ledger
# ---------------------------------------------------------------------------


@dataclass
class CauseEvent:
    id: str
    doc_id: str
    order: int
    summary: str
    causes: List[str] = field(default_factory=list)
    consequences: List[str] = field(default_factory=list)
    characters: List[str] = field(default_factory=list)
    created_at: str = ""


@dataclass
class ChronicleDoc:
    id: str
    title: str
    event_ids: List[str] = field(default_factory=list)
    opened_at: str = ""
    closed_at: Optional[str] = None


# ---------------------------------------------------------------------------
# The Chronicle
# ---------------------------------------------------------------------------


class Chronicle:
    """Causal timeline + chronicle docs + rule packs + canon checking.

    Persisted under ``<home>/.levi/lwp/chronicle/<slug>/``::

        chronicle.json      the event ledger (0600)
        docs/<doc>.md       one Markdown doc per session (0600)
        rules/*.json        rule packs as data — delete = rule gone
        rolling_summary.md  key facts carried forward (0600)

    ``bible`` is an optional :class:`LivingBible`; its CONFIRMED
    entries are the canon constraint set for :meth:`check_proposal`.
    """

    def __init__(
        self,
        slug: str,
        home: Path,
        bible: Optional[LivingBible] = None,
    ):
        self.slug = slug
        self.home = Path(home)
        self.bible = bible
        self._dir = self.home / ".levi" / "lwp" / "chronicle" / slug
        self._docs_dir = self._dir / "docs"
        self._rules_dir = self._dir / "rules"
        self._store = self._dir / "chronicle.json"
        self._summary_path = self._dir / "rolling_summary.md"
        self.events: Dict[str, CauseEvent] = {}
        self.docs: Dict[str, ChronicleDoc] = {}
        self._seq = 0
        self.load()

    # -- persistence ------------------------------------------------------

    def _payload(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "format": "lwp-chronicle/1",
            "updated_at": _utcnow(),
            "seq": self._seq,
            "events": {k: asdict(v) for k, v in self.events.items()},
            "docs": {k: asdict(v) for k, v in self.docs.items()},
        }

    def _write_0600(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        os.chmod(path, _RECORD_MODE)

    def save(self) -> None:
        self._write_0600(self._store, json.dumps(self._payload(), indent=2))

    def load(self) -> None:
        if not self._store.exists():
            return
        try:
            data = json.loads(self._store.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        self._seq = int(data.get("seq", 0))
        for eid, raw in (data.get("events") or {}).items():
            if isinstance(raw, dict) and isinstance(raw.get("id"), str):
                try:
                    self.events[eid] = CauseEvent(
                        **{
                            k: raw.get(k, getattr(CauseEvent, k, None))
                            for k in CauseEvent.__dataclass_fields__
                        }
                    )
                except TypeError:
                    continue
        for did, raw in (data.get("docs") or {}).items():
            if isinstance(raw, dict) and isinstance(raw.get("id"), str):
                try:
                    self.docs[did] = ChronicleDoc(
                        **{
                            k: raw.get(k, getattr(ChronicleDoc, k, None))
                            for k in ChronicleDoc.__dataclass_fields__
                        }
                    )
                except TypeError:
                    continue

    # -- chronicle docs ----------------------------------------------------

    def open_doc(self, title: str) -> ChronicleDoc:
        self._seq += 1
        did = "doc-" + _slug(self.slug, title, str(self._seq))
        doc = ChronicleDoc(id=did, title=title, opened_at=_utcnow())
        self.docs[did] = doc
        self._render_doc(doc)
        self.save()
        return doc

    def close_doc(self, doc_id: str) -> ChronicleDoc:
        doc = self.docs[doc_id]
        doc.closed_at = _utcnow()
        self._render_doc(doc)
        self.save()
        return doc

    def _doc_path(self, doc: ChronicleDoc) -> Path:
        safe = re.sub(r"[^a-z0-9]+", "-", doc.title.lower()).strip("-") or "untitled"
        return self._docs_dir / f"{doc.id}-{safe[:40]}.md"

    def _render_doc(self, doc: ChronicleDoc) -> Path:
        lines = [f"# Chronicle — {doc.title}", ""]
        lines.append(f"_Opened {doc.opened_at}._")
        if doc.closed_at:
            lines.append(f"_Closed {doc.closed_at}._")
        lines.append("")
        for eid in doc.event_ids:
            ev = self.events.get(eid)
            if ev is None:
                continue
            lines.append(f"- [{ev.created_at}] {ev.summary}")
            if ev.causes:
                lines.append(f"  - because: {', '.join(ev.causes)}")
            if ev.characters:
                lines.append(f"  - who: {', '.join(ev.characters)}")
        lines.append("")
        path = self._doc_path(doc)
        self._write_0600(path, "\n".join(lines))
        return path

    # -- causal timeline ----------------------------------------------------

    def record(
        self,
        doc_id: str,
        summary: str,
        causes: Optional[List[str]] = None,
        characters: Optional[List[str]] = None,
    ) -> CauseEvent:
        """Record an event; propagate it as a consequence of its causes."""
        doc = self.docs[doc_id]
        causes = list(causes or [])
        for cid in causes:
            if cid not in self.events:
                raise KeyError(f"unknown cause event {cid!r}")
        self._seq += 1
        eid = "evt-" + _slug(self.slug, doc_id, str(self._seq), summary)
        ev = CauseEvent(
            id=eid,
            doc_id=doc_id,
            order=len(doc.event_ids),
            summary=summary,
            causes=causes,
            characters=list(characters or []),
            created_at=_utcnow(),
        )
        self.events[eid] = ev
        doc.event_ids.append(eid)
        for cid in causes:  # propagation: consequences flow forward
            if eid not in self.events[cid].consequences:
                self.events[cid].consequences.append(eid)
        self._render_doc(doc)
        self.save()
        return ev

    def upstream(self, event_id: str) -> List[str]:
        """All causes, transitively — nearest first. Cycle-guarded."""
        seen: Set[str] = set()
        out: List[str] = []
        frontier = list(self.events[event_id].causes)
        while frontier:
            cid = frontier.pop(0)
            if cid in seen or cid not in self.events:
                continue
            seen.add(cid)
            out.append(cid)
            frontier.extend(self.events[cid].causes)
        return out

    def downstream(self, event_id: str) -> List[str]:
        """All consequences, transitively — nearest first. Cycle-guarded."""
        seen: Set[str] = set()
        out: List[str] = []
        frontier = list(self.events[event_id].consequences)
        while frontier:
            cid = frontier.pop(0)
            if cid in seen or cid not in self.events:
                continue
            seen.add(cid)
            out.append(cid)
            frontier.extend(self.events[cid].consequences)
        return out

    # -- rolling summary ----------------------------------------------------

    def _read_summary_facts(self) -> List[str]:
        if not self._summary_path.exists():
            return []
        facts: List[str] = []
        for line in self._summary_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("- "):
                facts.append(line[2:])
        return facts

    def fold_session(self, doc_id: str) -> int:
        """Fold a session's key facts into the rolling summary.

        Returns the number of new facts folded. Details stay in the
        chronicle doc; the summary carries forward. When the fact list
        grows past ROLLING_MAX_FACTS, the oldest compact into one line —
        the newest stay verbatim.
        """
        doc = self.docs[doc_id]
        facts = self._read_summary_facts()
        new = 0
        for eid in doc.event_ids:
            ev = self.events.get(eid)
            if ev is None:
                continue
            if ev.summary not in facts:
                facts.append(ev.summary)
                new += 1
        if len(facts) > ROLLING_MAX_FACTS:
            overflow = facts[: len(facts) - ROLLING_MAX_FACTS]
            facts = facts[len(facts) - ROLLING_MAX_FACTS :]
            facts.insert(
                0,
                f"_Earlier: {len(overflow)} facts folded {_utcnow()} — "
                f"{overflow[0][:80]}…_",
            )
        lines = [f"# Rolling summary — {self.slug}", ""]
        lines.append(f"_Updated {_utcnow()}. Details live in the chronicle docs._")
        lines.append("")
        lines.extend(f"- {f}" for f in facts)
        lines.append("")
        self._write_0600(self._summary_path, "\n".join(lines))
        return new

    # -- rules as data ------------------------------------------------------

    def load_rules(self) -> List[Dict[str, Any]]:
        """Read every rule pack in rules/. Fresh read each call: delete
        the file and the rule is gone — no code change, no rebuild."""
        packs: List[Dict[str, Any]] = []
        if not self._rules_dir.is_dir():
            return packs
        for path in sorted(self._rules_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue  # one malformed pack never aborts the load
            if not isinstance(raw, dict):
                continue
            constraints = raw.get("constraints") or []
            if not isinstance(constraints, list):
                continue
            packs.append(
                {
                    "pack_id": raw.get("id") or path.stem,
                    "title": raw.get("title", ""),
                    "source": path.name,
                    "constraints": [
                        c
                        for c in constraints
                        if isinstance(c, dict) and isinstance(c.get("id"), str)
                    ],
                }
            )
        return packs

    def write_rule_pack(
        self, pack_id: str, title: str, constraints: List[Dict[str, Any]]
    ) -> Path:
        """Author a rule pack as data. (Deleting the file removes it.)"""
        path = self._rules_dir / f"{pack_id}.json"
        payload = {"id": pack_id, "title": title, "constraints": constraints}
        self._write_0600(path, json.dumps(payload, indent=2))
        return path

    # -- canon-as-constraint --------------------------------------------------

    def _canon_denials(self) -> List[Dict[str, Any]]:
        """Denials from CONFIRMED bible world-rules + loaded rule packs."""
        denials: List[Dict[str, Any]] = []
        if self.bible is not None:
            for entry in self.bible.world_rules.values():
                if entry.status != CONFIRMED:
                    continue
                parsed = _denies_from_rule_text(entry.rule)
                if parsed:
                    denials.append(
                        {
                            "source": f"bible:{entry.id}",
                            "asserts": entry.rule,
                            **parsed,
                        }
                    )
        for pack in self.load_rules():
            for c in pack["constraints"]:
                for denied_text in c.get("denies") or []:
                    denied = _content_words(denied_text)
                    if denied:
                        denials.append(
                            {
                                "source": f"rules:{pack['pack_id']}/{c['id']}",
                                "asserts": c.get("asserts", ""),
                                "subject": _content_words(c.get("asserts", "")),
                                "denied": denied,
                            }
                        )
        return denials

    def check_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Check a proposal against confirmed canon. Never auto-resolves.

        Proposal shapes (``kind`` required):
          character: {name, description, aliases?}
          event:     {summary, order?}
          rule:      {statement}
          fact:      {subject, statement}

        Returns {"accepted": bool, "reasons": [str]}. Reasons cite the
        conflicting canon source. A contradiction is reported — the
        writer decides what happens next.
        """
        reasons: List[str] = []
        kind = proposal.get("kind")

        if kind == "character":
            reasons.extend(self._check_character(proposal))
        elif kind == "event":
            reasons.extend(self._check_event(proposal))
        elif kind in ("rule", "fact"):
            text = proposal.get("statement", "") or ""
            reasons.extend(self._check_text_against_denials(text))
        else:
            reasons.append(f"unknown proposal kind {kind!r}")

        return {"accepted": not reasons, "reasons": reasons}

    def _check_text_against_denials(self, text: str) -> List[str]:
        reasons: List[str] = []
        for denial in self._canon_denials():
            if _contradicts_denial(text, denial):
                reasons.append(
                    f"contradicts {denial['source']}: "
                    f"canon asserts {denial['asserts']!r}"
                )
        return reasons

    def _check_character(self, proposal: Dict[str, Any]) -> List[str]:
        reasons: List[str] = []
        name = (proposal.get("name") or "").strip()
        desc = proposal.get("description") or ""
        aliases = [a.lower() for a in (proposal.get("aliases") or [])]
        if self.bible is not None:
            for entry in self.bible.characters.values():
                if entry.status != CONFIRMED:
                    continue
                known = {entry.name.lower()} | {a.lower() for a in entry.aliases}
                if name.lower() in known or any(a in known for a in aliases):
                    mine = _content_words(desc)
                    theirs = _content_words(entry.description)
                    overlap = (
                        len(mine & theirs) / max(len(mine | theirs), 1)
                    )
                    if overlap < 0.25:
                        reasons.append(
                            f"identity conflict with confirmed character "
                            f"{entry.name!r} (bible:{entry.id}): descriptions "
                            f"diverge — same name, different person?"
                        )
        reasons.extend(self._check_text_against_denials(f"{name} {desc}"))
        return reasons

    def _check_event(self, proposal: Dict[str, Any]) -> List[str]:
        reasons: List[str] = []
        summary = proposal.get("summary") or ""
        order = proposal.get("order")
        if self.bible is not None and order is not None:
            for beat in self.bible.timeline.values():
                if beat.status == CONFIRMED and beat.order == order:
                    if _content_words(summary) != _content_words(beat.summary):
                        reasons.append(
                            f"ordering conflict with confirmed timeline beat "
                            f"(bible:{beat.id}) at order {order}: "
                            f"canon says {beat.summary!r}"
                        )
        reasons.extend(self._check_text_against_denials(summary))
        return reasons

    def propose(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """Check, then write clean proposals into the bible as PROPOSED.

        Contradictions write nothing — the verdict is returned for the
        writer to dispose of.
        """
        verdict = self.check_proposal(proposal)
        if not verdict["accepted"] or self.bible is None:
            return verdict
        kind = proposal.get("kind")
        if kind == "character":
            self.bible.add_character(
                proposal.get("name", ""),
                description=proposal.get("description", ""),
                aliases=proposal.get("aliases"),
            )
        elif kind in ("rule", "fact"):
            entry = WorldRuleEntry(
                id="rule-" + _slug(proposal.get("statement", "")),
                rule=proposal.get("statement", ""),
                scope="fact" if kind == "fact" else "world",
            )
            self.bible.world_rules[entry.id] = entry
            self.bible.save()
        elif kind == "event":
            entry = TimelineEntry(
                id="beat-" + _slug(proposal.get("summary", "")),
                order=int(proposal.get("order", len(self.bible.timeline))),
                summary=proposal.get("summary", ""),
            )
            self.bible.timeline[entry.id] = entry
            self.bible.save()
        verdict["written"] = True
        return verdict

    # -- status ---------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "events": len(self.events),
            "docs": len(self.docs),
            "rule_packs": len(self.load_rules()),
            "summary_facts": len(self._read_summary_facts()),
        }
