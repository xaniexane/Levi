"""Find / replace in-buffer and project-wide.

The ternary, everywhere the giants build binary: a project replace does
not return replaced/not-replaced. It returns per file one of REPLACED,
REVIEW_NEEDED (too many hits for a blind replace — the paired verifier
twin looks first), or SKIPPED (binary, oversize, undecodable).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum

from levi.hicomb.buffer import Buffer

MAX_SEARCH_FILE_BYTES = 2 * 1024 * 1024
REVIEW_THRESHOLD = 25  # hits in one file -> REVIEW_NEEDED, not blind replace
SKIP_DIRS = frozenset(
    {".git", ".hg", ".svn", "__pycache__", ".hicomb", "node_modules", ".venv"}
)


class FileVerdict(str, Enum):
    REPLACED = "replaced"
    REVIEW_NEEDED = "review_needed"
    SKIPPED = "skipped"
    CLEAN = "clean"  # searched, no hits


@dataclass(frozen=True)
class Match:
    line: int
    start: int
    end: int
    text: str


@dataclass
class ProjectHit:
    path: str
    matches: list[Match] = field(default_factory=list)


def _compile(
    pattern: str, regex: bool, case_sensitive: bool, whole_word: bool
) -> re.Pattern:
    if not pattern:
        raise ValueError("empty search pattern")
    src = pattern if regex else re.escape(pattern)
    if whole_word:
        src = r"\b" + src + r"\b"
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(src, flags)
    except re.error as exc:
        raise ValueError(f"bad regex: {pattern}") from exc


def find_all(
    lines: list[str],
    pattern: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> list[Match]:
    """All matches across lines. Case-insensitive by default (phone-first)."""
    rx = _compile(pattern, regex, case_sensitive, whole_word)
    hits: list[Match] = []
    for ln, line in enumerate(lines):
        for m in rx.finditer(line):
            hits.append(Match(ln, m.start(), m.end(), m.group(0)))
    return hits


def find_in_buffer(buf: Buffer, pattern: str, **kwargs) -> list[Match]:
    return find_all(buf.lines(), pattern, **kwargs)


def _expand_replacement(replacement: str, match: re.Match, regex: bool) -> str:
    if regex:
        try:
            return match.expand(replacement)
        except re.error:
            return replacement
    return replacement


def replace_all(
    buf: Buffer,
    pattern: str,
    replacement: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
    whole_word: bool = False,
) -> int:
    """Replace every hit in the buffer. One undo step. Returns hit count."""
    rx = _compile(pattern, regex, case_sensitive, whole_word)
    text = buf.get_text()
    new_text, count = rx.subn(
        lambda m: _expand_replacement(replacement, m, regex), text
    )
    if count:
        buf.set_text(new_text)
    return count


def _readable_text(path: str) -> str | None:
    """File text, or None when the file must be skipped (binary/huge)."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size > MAX_SEARCH_FILE_BYTES:
        return None
    try:
        with open(path, "rb") as fh:
            head = fh.read(8192)
            if b"\x00" in head:
                return None  # binary
            fh.seek(0)
            raw = fh.read()
        return raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return None


def _iter_project_files(root: str) -> list[str]:
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            found.append(os.path.join(dirpath, name))
    return found


def project_search(
    root: str,
    pattern: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
    whole_word: bool = False,
    max_hits: int = 5000,
) -> list[ProjectHit]:
    """Project-wide search. Deterministic order; skips VCS dirs and binaries."""
    rx = _compile(pattern, regex, case_sensitive, whole_word)
    hits: list[ProjectHit] = []
    total = 0
    for path in _iter_project_files(root):
        text = _readable_text(path)
        if text is None:
            continue
        file_hits: list[Match] = []
        for ln, line in enumerate(text.split("\n")):
            for m in rx.finditer(line):
                file_hits.append(Match(ln, m.start(), m.end(), m.group(0)))
                total += 1
                if total >= max_hits:
                    break
            if total >= max_hits:
                break
        if file_hits:
            hits.append(ProjectHit(path, file_hits))
        if total >= max_hits:
            break
    return hits


def project_replace(
    root: str,
    pattern: str,
    replacement: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
    whole_word: bool = False,
    auto_review: bool = True,
) -> dict[str, FileVerdict]:
    """Project-wide replace with ternary verdicts per file.

    - REPLACED: file had hits (<= REVIEW_THRESHOLD) and was rewritten.
    - REVIEW_NEEDED: file had MORE than REVIEW_THRESHOLD hits — left
      untouched for the paired verifier twin / the builder to review.
    - SKIPPED: binary, oversize, or undecodable.
    - CLEAN: searched, no hits.

    Rewrites are atomic (temp file + os.replace): a crash mid-replace
    never leaves a half-written file behind.
    """
    rx = _compile(pattern, regex, case_sensitive, whole_word)
    verdicts: dict[str, FileVerdict] = {}
    for path in _iter_project_files(root):
        text = _readable_text(path)
        if text is None:
            verdicts[path] = FileVerdict.SKIPPED
            continue
        count = sum(1 for _ in rx.finditer(text))
        if count == 0:
            verdicts[path] = FileVerdict.CLEAN
            continue
        if auto_review and count > REVIEW_THRESHOLD:
            verdicts[path] = FileVerdict.REVIEW_NEEDED
            continue
        new_text = rx.sub(lambda m: _expand_replacement(replacement, m, regex), text)
        try:
            tmp = path + ".hicomb-tmp"
            with open(tmp, "w", encoding="utf-8", newline="") as fh:
                fh.write(new_text)
            os.replace(tmp, path)
            verdicts[path] = FileVerdict.REPLACED
        except OSError:
            verdicts[path] = FileVerdict.SKIPPED
    return verdicts
