"""Friction log — one-tap capture of annoyances, weekly review into fixes.

The Waymaker law says: where there isn't a way, LEVI creates one. The
friction log is where the *need* for a way is discovered: every small
annoyance is captured in under a second, and the weekly review groups
them into themes. A theme becomes a candidate fix; a promoted candidate
becomes a real change.

Honesty contract (binding):
  - Grouping is *simple keyword stemming*, documented as such. It does
    not pretend to understand semantics.
  - Items that share no stem with anything else stay "ungrouped" —
    they are never forced into a theme to make the review look tidy.
  - A candidate is not a fix. Only ``promote_to_fix`` with a written
    fix note moves an item to the fixes log.
  - The fix note is required and must be non-empty: "fixed it" is not
    an explanation.

stdlib-only. Local JSON only.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_STATE_DIR = "friction"
_STATE_FILE = "log.json"

# Small, honest stopword list: words that carry no theme signal.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "is",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "my",
        "me",
        "we",
        "you",
        "your",
        "at",
        "by",
        "from",
        "as",
        "be",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "not",
        "no",
        "so",
        "too",
        "very",
        "just",
        "again",
        "every",
        "each",
        "when",
        "where",
        "how",
        "why",
        "what",
        "which",
        "there",
        "here",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "keeps",
        "keep",
        "kept",
        "makes",
        "make",
        "made",
        "gets",
        "get",
        "got",
        "takes",
        "take",
        "took",
        "always",
        "never",
        "still",
        "already",
        "also",
    }
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def stem(word: str) -> str:
    """Tiny suffix-stripper. Deliberately naive — documented as such.

    Strips one common English suffix when the remaining stem is still
    meaningful (>= 3 chars), then collapses a doubled trailing
    consonant ("runn" -> "run"). "running" -> "run", "logins" ->
    "login", "deployments" -> "deployment".
    """
    w = word.lower()
    if len(w) < 4:
        return w
    stripped_ing_ed = False
    for suffix in (
        "ingly",
        "edly",
        "tion",
        "sion",
        "ment",
        "ness",
        "ies",
        "ing",
        "ed",
        "es",
        "ly",
        "s",
    ):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            core = w[: -len(suffix)]
            w = core + "y" if suffix == "ies" else core
            stripped_ing_ed = suffix in ("ingly", "edly", "ing", "ed")
            break
    # "running" -> "runn": stripping -ing created a doubled consonant.
    # Collapse it only in that case, so "classes" stays "class".
    if stripped_ing_ed and len(w) >= 4 and w[-1] == w[-2] and w[-1] not in "aeiou":
        w = w[:-1]
    return w


def _themes_of(note: str) -> List[str]:
    words = _WORD_RE.findall(note.lower())
    seen: List[str] = []
    for w in words:
        if w in _STOPWORDS:
            continue
        s = stem(w)
        if len(s) >= 3 and s not in seen:
            seen.append(s)
    return seen


def levi_home() -> Path:
    """LEVI state home: ``$LEVI_HOME`` when set (hermetic tests), else ``~/.levi``.

    Resolved at call time — never at import — so tests can redirect it.
    """
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


@dataclass
class FrictionEntry:
    id: str
    ts: str  # ISO-8601
    note: str


@dataclass
class FixCandidate:
    id: str
    theme: str
    count: int
    entry_ids: List[str]
    examples: List[str]
    status: str  # "candidate" | "promoted" | "dropped"
    fix_note: Optional[str] = None
    decided_at: Optional[str] = None


class FrictionLog:
    """One-tap friction capture + weekly theme review."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = Path(home).expanduser() if home is not None else levi_home()
        self._path = self.home / _STATE_DIR / _STATE_FILE

    # ------------------------------------------------------------------ I/O

    def _read(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {"entries": [], "candidates": [], "fixes": []}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"entries": [], "candidates": [], "fixes": []}
        if not isinstance(data, dict):
            return {"entries": [], "candidates": [], "fixes": []}
        data.setdefault("entries", [])
        data.setdefault("candidates", [])
        data.setdefault("fixes", [])
        return data

    def _write(self, data: Dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path)

    # ----------------------------------------------------------------- log

    def capture(self, note: str) -> FrictionEntry:
        """Capture an annoyance. Must be sub-second to type; nothing else."""
        text = str(note).strip()
        if not text:
            raise ValueError("note is required — an empty annoyance is not data")
        entry = FrictionEntry(
            id="fr-" + uuid.uuid4().hex[:8],
            ts=datetime.now().isoformat(timespec="seconds"),
            note=text,
        )
        data = self._read()
        data["entries"].append(asdict(entry))
        self._write(data)
        return entry

    def entries(self, since_days: Optional[float] = None) -> List[FrictionEntry]:
        data = self._read()
        out = []
        cutoff = (
            datetime.now() - timedelta(days=since_days)
            if since_days is not None
            else None
        )
        for r in data["entries"]:
            try:
                e = FrictionEntry(**{k: r[k] for k in ("id", "ts", "note")})
            except (KeyError, TypeError):
                continue
            if cutoff is not None:
                try:
                    if datetime.fromisoformat(e.ts) < cutoff:
                        continue
                except ValueError:
                    continue
            out.append(e)
        return out

    # ---------------------------------------------------------------- review

    def weekly_review(
        self,
        since_days: float = 7,
        min_group: int = 2,
    ) -> Dict[str, Any]:
        """Group recent entries into candidate fixes by shared word stems.

        Themes are stems appearing in ``min_group``+ entries. Entries with
        no shared stem stay "ungrouped" — honestly alone, never forced in.
        """
        entries = self.entries(since_days=since_days)
        by_id = {e.id: e for e in entries}
        stem_hits: Dict[str, List[str]] = {}
        for e in entries:
            for t in _themes_of(e.note):
                stem_hits.setdefault(t, []).append(e.id)
        candidates: List[Dict[str, Any]] = []
        grouped_ids: set = set()
        for theme, ids in sorted(
            stem_hits.items(), key=lambda kv: (-len(kv[1]), kv[0])
        ):
            if len(ids) < min_group:
                continue
            if len(ids) == len(entries) and len(entries) > min_group:
                # A stem in *every* entry is noise, not a theme.
                continue
            grouped_ids.update(ids)
            examples = [by_id[i].note for i in ids[:3]]
            candidates.append(
                asdict(
                    FixCandidate(
                        id="fx-" + uuid.uuid4().hex[:8],
                        theme=theme,
                        count=len(ids),
                        entry_ids=list(ids),
                        examples=examples,
                        status="candidate",
                    )
                )
            )
        ungrouped = [asdict(e) for e in entries if e.id not in grouped_ids]
        data = self._read()
        data["candidates"] = candidates
        self._write(data)
        return {
            "window_days": since_days,
            "n_entries": len(entries),
            "candidates": candidates,
            "ungrouped": ungrouped,
            "note": (
                "%d candidate fix(es); %d item(s) honestly ungrouped"
                % (len(candidates), len(ungrouped))
            ),
        }

    def promote_to_fix(self, candidate_id: str, fix_note: str) -> Dict[str, Any]:
        """Promote a candidate to a real fix. The fix note is required."""
        note = str(fix_note or "").strip()
        if not note:
            raise ValueError("fix_note is required — 'fixed it' is not an explanation")
        data = self._read()
        for c in data["candidates"]:
            if c["id"] == candidate_id:
                if c["status"] != "candidate":
                    raise ValueError(
                        "candidate %s is already %s" % (candidate_id, c["status"])
                    )
                c["status"] = "promoted"
                c["fix_note"] = note
                c["decided_at"] = datetime.now().isoformat(timespec="seconds")
                fix = {
                    "id": c["id"],
                    "theme": c["theme"],
                    "count": c["count"],
                    "fix_note": note,
                    "promoted_at": c["decided_at"],
                }
                data["fixes"].append(fix)
                self._write(data)
                return fix
        raise KeyError("no candidate %r" % candidate_id)

    def drop_candidate(self, candidate_id: str) -> Dict[str, Any]:
        """Decline a candidate without fixing it. Recorded, not deleted."""
        data = self._read()
        for c in data["candidates"]:
            if c["id"] == candidate_id:
                if c["status"] != "candidate":
                    raise ValueError(
                        "candidate %s is already %s" % (candidate_id, c["status"])
                    )
                c["status"] = "dropped"
                c["decided_at"] = datetime.now().isoformat(timespec="seconds")
                self._write(data)
                return c
        raise KeyError("no candidate %r" % candidate_id)

    def fixes(self) -> List[Dict[str, Any]]:
        return list(self._read()["fixes"])

    def format_review(self, review: Dict[str, Any]) -> str:
        lines = [
            "LEVI friction review — last %d day(s): %d entries"
            % (review["window_days"], review["n_entries"])
        ]
        for c in review["candidates"]:
            lines.append(
                "  [%s] theme=%r x%d — %s"
                % (c["id"], c["theme"], c["count"], c["examples"][0][:70])
            )
        if review["ungrouped"]:
            lines.append("  ungrouped (%d):" % len(review["ungrouped"]))
            for u in review["ungrouped"]:
                lines.append("    - %s" % u["note"][:70])
        lines.append("  " + review["note"])
        return "\n".join(lines)
