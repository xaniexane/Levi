"""Source-included licensing with hand-merged plain-text mods.

Studied from: dead-networks-20260916/report.md (WWIV BBS).

The old mechanism: every sysop received the full source and a compiler,
and customizations ("mods") circulated as plain text. A sysop read the
mod, found the matching spot in their own tree, and merged it by hand —
exact when the context matched, careful when it almost matched, refused
when it didn't. LEVI's reimplementation is that merge discipline as a
function: hunks with context lines, applied exactly, tolerated with a
small documented fuzz, or reported as conflicts for a human. Nothing is
ever applied silently on a guess.

Honest limits: the fuzz match is a heuristic (context may appear in
several places; the report says where it landed). Merge never deletes
or rewrites tree content on its own — it only inserts/replaces at a
positively identified anchor. This is a text-merge engine, not a
compiler or a license lawyer; the grant record is paperwork modeling.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/source_included_bbs"

APPLIED = "applied"
FUZZED = "applied-with-fuzz"
CONFLICT = "conflict"
SKIPPED = "skipped"

FUZZ_RADIUS = 2  # lines of drift tolerated before calling it a conflict


@dataclass
class Hunk:
    """One plain-text change: ``context`` lines must surround the spot,
    ``remove`` lines are taken out, ``add`` lines go in. ``at`` is the
    1-based expected line number (a hint only — context decides)."""

    target: str
    context: List[str]
    remove: List[str] = field(default_factory=list)
    add: List[str] = field(default_factory=list)
    at: int = 0
    note: str = ""


@dataclass
class Mod:
    """A circulated modification: title, author, and its hunks."""

    mod_id: str
    title: str
    author: str
    hunks: List[Hunk]
    notes: str = ""

    def fingerprint(self) -> str:
        body = "\n".join(
            [self.mod_id, self.title, self.author]
            + [
                h.target + "|" + "\n".join(h.context + h.remove + h.add)
                for h in self.hunks
            ]
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


@dataclass
class HunkResult:
    hunk_index: int
    target: str
    status: str
    line: int = 0  # 1-based line where the hunk landed
    detail: str = ""


@dataclass
class MergeReport:
    mod_id: str
    results: List[HunkResult] = field(default_factory=list)

    @property
    def applied(self) -> int:
        return sum(1 for r in self.results if r.status in (APPLIED, FUZZED))

    @property
    def conflicts(self) -> int:
        return sum(1 for r in self.results if r.status == CONFLICT)

    @property
    def clean(self) -> bool:
        return self.conflicts == 0 and all(r.status != SKIPPED for r in self.results)

    def summary(self) -> str:
        lines = [f"mod {self.mod_id}: {self.applied}/{len(self.results)} hunks"]
        for r in self.results:
            lines.append(f"  [{r.hunk_index}] {r.target}: {r.status} {r.detail}")
        return "\n".join(lines)


def _find_anchor(lines: List[str], context: List[str], hint: int) -> Optional[int]:
    """Return the 0-based index where ``context`` matches, or None.
    Tries the hinted position first, then the whole file, tolerating up
    to FUZZ_RADIUS lines of drift. Contexts shorter than 1 line never
    match (no guessing)."""
    if not context:
        return None

    def matches(at: int) -> bool:
        return lines[at : at + len(context)] == context

    n = len(lines)
    if hint and 1 <= hint <= n and matches(hint - 1):
        return hint - 1
    # Exact scan first.
    for i in range(n - len(context) + 1):
        if matches(i):
            return i
    # Fuzz scan: within FUZZ_RADIUS of the hint, tolerate all-but-one
    # context lines differing. Anything looser is a conflict for a human.
    if hint and len(context) > 1:
        lo = max(0, hint - 1 - FUZZ_RADIUS)
        hi = min(n - len(context), hint - 1 + FUZZ_RADIUS)
        for i in range(lo, hi + 1):
            window = lines[i : i + len(context)]
            if window == context:
                continue  # strict scan above already covers exact hits
            close = sum(1 for c, w in zip(context, window, strict=True) if c == w)
            if close >= len(context) - 1:
                return i
    return None


class SourceTree:
    """A sysop's local source tree: files as line lists, merged by hand
    rules. Files are created on demand by the first hunk that targets
    them."""

    def __init__(self) -> None:
        self.files: Dict[str, List[str]] = {}
        self.applied_mods: List[str] = []

    def set_file(self, path: str, text: str) -> None:
        self.files[path] = text.splitlines()

    def get_file(self, path: str) -> str:
        return "\n".join(self.files.get(path, []))

    def apply_mod(self, mod: Mod) -> MergeReport:
        report = MergeReport(mod_id=mod.mod_id)
        for idx, hunk in enumerate(mod.hunks):
            report.results.append(self._apply_hunk(idx, hunk))
        if report.clean:
            self.applied_mods.append(mod.mod_id)
        return report

    def _apply_hunk(self, idx: int, hunk: Hunk) -> HunkResult:
        lines = self.files.setdefault(hunk.target, [])
        anchor = _find_anchor(lines, hunk.context, hunk.at)
        if anchor is None:
            return HunkResult(
                idx,
                hunk.target,
                CONFLICT,
                hunk.at,
                "context not found — left for the sysop",
            )
        # Verify the remove-block really sits right after the context.
        head = anchor + len(hunk.context)
        if hunk.remove and lines[head : head + len(hunk.remove)] != hunk.remove:
            return HunkResult(
                idx,
                hunk.target,
                CONFLICT,
                anchor + 1,
                "remove-block mismatch — left for the sysop",
            )
        splice = hunk.add
        if hunk.remove:
            lines[head : head + len(hunk.remove)] = splice
        else:
            lines[head:head] = splice
        drifted = hunk.at and (anchor + 1) != hunk.at
        status = FUZZED if drifted else APPLIED
        detail = f"line {anchor + 1}"
        if drifted:
            detail += f" (hint said {hunk.at} — verify by hand)"
        return HunkResult(idx, hunk.target, status, anchor + 1, detail)


@dataclass
class Grant:
    """Paperwork model of source-included licensing: a sysop holds the
    full source under plain-text terms."""

    sysop: str
    terms: str
    revoked: bool = False

    def summary(self) -> str:
        state = "REVOKED" if self.revoked else "active"
        return f"{self.sysop}: {state} — {self.terms[:60]}"


class ModRegistry:
    """The circulating library: every mod on file with its fingerprint,
    plus the license grants of the sysops holding source."""

    def __init__(self) -> None:
        self.mods: Dict[str, Mod] = {}
        self.grants: Dict[str, Grant] = {}

    def register(self, mod: Mod) -> str:
        if mod.mod_id in self.mods:
            raise ValueError(f"mod {mod.mod_id} already registered")
        self.mods[mod.mod_id] = mod
        return mod.fingerprint()

    def by_author(self, author: str) -> List[Mod]:
        return [m for m in self.mods.values() if m.author == author]

    def grant_source(self, sysop: str, terms: str) -> Grant:
        if not sysop or not terms.strip():
            raise ValueError("sysop and terms required")
        grant = Grant(sysop=sysop, terms=terms)
        self.grants[sysop] = grant
        return grant

    def revoke_source(self, sysop: str) -> None:
        if sysop not in self.grants:
            raise ValueError(f"no grant for {sysop}")
        self.grants[sysop].revoked = True

    def holds_source(self, sysop: str) -> bool:
        g = self.grants.get(sysop)
        return g is not None and not g.revoked
