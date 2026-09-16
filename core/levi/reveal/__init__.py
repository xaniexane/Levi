"""reveal — the Reveal-Codes inspector.

Clean-room LEVI-native revival of WordPerfect's load-bearing idea
(perpetual-hunt daily 2026-09-16b, record ``arch-retro-reveal-codes``):
formatting you can SEE. Modern editors (Word, Google Docs, Notion) hide
the document's true structure and invisible characters; reveal opens the
second screen and shows the codes.

This is NOT a WordPerfect clone: it inspects plain text / Markdown
documents and reports structural codes (headings, emphasis, links, lists,
tables, frontmatter) plus invisible characters (zero-width spaces,
trailing whitespace, stray tabs, BOM) that editors hide from the user.
Everything is stdlib-only and local-first.

Public API:
    reveal(text)   -> RevealReport  (inspect; never modifies input)
    exorcise(text) -> (cleaned, removed)  (strip invisibles, honestly
                                           reporting every removal)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

__all__ = [
    "CodeToken",
    "RevealReport",
    "reveal",
    "exorcise",
    "invisible_names",
]

# --------------------------------------------------------------------------
# The invisible alphabet: characters editors hide from you.
# --------------------------------------------------------------------------

_INVISIBLE: Dict[str, str] = {
    "\u200b": "ZWSP",  # zero width space
    "\u200c": "ZWNJ",  # zero width non-joiner
    "\u200d": "ZWJ",  # zero width joiner
    "\u2060": "WJ",  # word joiner
    "\u00ad": "SHY",  # soft hyphen
    "\u00a0": "NBSP",  # non-breaking space
    "\u2028": "LSEP",  # line separator
    "\u2029": "PSEP",  # paragraph separator
}

_INVISIBLE_RE = re.compile("[" + "".join(re.escape(c) for c in _INVISIBLE) + "]")

_BOM = "\ufeff"

# --------------------------------------------------------------------------
# Structure patterns (Markdown-flavoured; tolerant, never crashing).
# --------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_QUOTE_RE = re.compile(r"^\s*(>+)\s?")
_LIST_RE = re.compile(r"^(\s*)(?:([-*+])|(\d+)[.)])\s+")
_HR_RE = re.compile(r"^\s*(?:([-*_])\s*){3,}\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?[\s:|-]*\s*$")
_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]*)\)")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*|__([^_]+)__")
_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)|(?<!_)_([^_\n]+)_(?!_)")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_TRAILING_WS_RE = re.compile(r"([ \t]+)$")
_FRONTMATTER_DELIM = "---"


@dataclass(frozen=True)
class CodeToken:
    """One revealed code: kind, 1-based line, 0-based column, short label."""

    kind: str
    line: int
    col: int
    label: str
    detail: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind,
            "line": self.line,
            "col": self.col,
            "label": self.label,
            "detail": self.detail,
        }


@dataclass
class RevealReport:
    """The second screen: everything reveal() found, in document order."""

    text: str
    tokens: List[CodeToken] = field(default_factory=list)

    # -- views ---------------------------------------------------------

    def summary(self) -> Dict[str, object]:
        counts: Dict[str, int] = {}
        for t in self.tokens:
            counts[t.kind] = counts.get(t.kind, 0) + 1
        return {
            "lines": len(self.text.splitlines()),
            "tokens": len(self.tokens),
            "invisibles": sum(
                1
                for t in self.tokens
                if t.kind
                in (
                    "zero-width",
                    "nb-space",
                    "trailing-ws",
                    "bom",
                    "stray-tab",
                    "soft-break",
                )
            ),
            "by_kind": counts,
        }

    def render(self) -> str:
        """Two-pane text view: numbered lines, then the code listing."""
        lines = self.text.splitlines()
        by_line: Dict[int, List[CodeToken]] = {}
        for t in self.tokens:
            by_line.setdefault(t.line, []).append(t)
        out = ["=== REVEAL CODES ==="]
        for i, raw in enumerate(lines, 1):
            shown = _visualize_invisibles(raw)
            out.append("%4d| %s" % (i, shown))
            for t in by_line.get(i, []):
                marker = " " * (t.col + 6) + "^"
                out.append(
                    "%s  [%s]%s"
                    % (marker, t.label, (" %s" % t.detail) if t.detail else "")
                )
        out.append("=== %d codes on %d lines ===" % (len(self.tokens), len(lines)))
        return "\n".join(out)

    def to_dict(self) -> Dict[str, object]:
        return {
            "summary": self.summary(),
            "tokens": [t.to_dict() for t in self.tokens],
        }


def invisible_names() -> Dict[str, str]:
    """The invisible alphabet reveal() watches for (codepoint -> label)."""
    return dict(_INVISIBLE)


# --------------------------------------------------------------------------
# The inspector
# --------------------------------------------------------------------------


def _visualize_invisibles(line: str) -> str:
    """Make the invisible visible: glyphs for hidden characters."""
    out = []
    for ch in line:
        if ch == " ":
            out.append("·")
        elif ch == "\t":
            out.append("→")
        elif ch in _INVISIBLE:
            out.append("<%s>" % _INVISIBLE[ch])
        elif ch == _BOM:
            out.append("<BOM>")
        else:
            out.append(ch)
    return "".join(out)


def reveal(text: str) -> RevealReport:
    """Inspect *text* and return every code it carries. Never modifies."""
    tokens: List[CodeToken] = []
    lines = text.splitlines()

    def tok(kind: str, line: int, col: int, label: str, detail: str = "") -> None:
        tokens.append(CodeToken(kind, line, col, label, detail))

    in_fence = False
    in_frontmatter = False

    for ln, raw in enumerate(lines, 1):
        line = raw

        # -- BOM ---------------------------------------------------------
        if ln == 1 and line.startswith(_BOM):
            tok("bom", 1, 0, "BOM", "byte-order mark at document start")
            line = line[1:]

        # -- frontmatter -------------------------------------------------
        if ln == 1 and line.strip() == _FRONTMATTER_DELIM and not in_frontmatter:
            in_frontmatter = True
            tok("frontmatter", ln, 0, "FM-START", "document metadata block")
            continue
        if in_frontmatter:
            if line.strip() == _FRONTMATTER_DELIM:
                in_frontmatter = False
                tok("frontmatter", ln, 0, "FM-END", "")
            else:
                tok("frontmatter", ln, 0, "FM", line.strip()[:60])
            continue

        # -- fenced code blocks -------------------------------------------
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            tok(
                "fenced",
                ln,
                0,
                "FENCE-ON" if in_fence else "FENCE-OFF",
                line.strip()[:20],
            )
            continue
        if in_fence:
            _scan_invisibles(line, ln, tok)
            continue

        # -- block structure ----------------------------------------------
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            tok("heading", ln, 0, "H%d" % level, m.group(2).strip()[:60])
            line = _HEADING_RE.sub(r"\2", line, count=1)
        m = _QUOTE_RE.match(line)
        if m:
            tok("quote", ln, 0, "QUOTE", "depth %d" % len(m.group(1)))
        m = _LIST_RE.match(line)
        if m:
            indent, bullet, numbered = m.group(1), m.group(2), m.group(3)
            depth = len(indent.expandtabs(4)) // 2
            tok("list", ln, 0, "LIST:d%d" % depth, "bullet" if bullet else "numbered")
        if _HR_RE.match(line) and "|" not in line:
            tok("hr", ln, 0, "HR", "thematic break")
        if _TABLE_SEP_RE.match(line) and "|" in line and "-" in line:
            tok("table", ln, 0, "TABLE-SEP", "table separator row")

        # -- inline structure ----------------------------------------------
        _scan_inline(line, ln, tok)

        # -- invisibles (always scanned, even on plain lines) --------------
        _scan_invisibles(raw, ln, tok)

    tokens.sort(key=lambda t: (t.line, t.col))
    return RevealReport(text=text, tokens=tokens)


def _scan_inline(line: str, ln: int, tok) -> None:
    for m in _IMAGE_RE.finditer(line):
        tok("image", ln, m.start(), "IMG", m.group(2)[:80])
    # links (skip the image ones, already reported)
    img_spans = [(m.start(), m.end()) for m in _IMAGE_RE.finditer(line)]
    for m in _LINK_RE.finditer(line):
        if any(s <= m.start() < e for s, e in img_spans):
            continue
        tok("link", ln, m.start(), "LINK", m.group(1)[:80] or "(empty target)")
    for m in _BOLD_RE.finditer(line):
        tok("em", ln, m.start(), "B", (m.group(1) or m.group(2) or "")[:40])
    for m in _ITALIC_RE.finditer(line):
        tok("em", ln, m.start(), "I", (m.group(1) or m.group(2) or "")[:40])
    for m in _INLINE_CODE_RE.finditer(line):
        tok("code", ln, m.start(), "CODE", m.group(1)[:40])


def _scan_invisibles(raw: str, ln: int, tok) -> None:
    for m in _INVISIBLE_RE.finditer(raw):
        ch = m.group(0)
        label = _INVISIBLE[ch]
        kind = (
            "zero-width"
            if label in ("ZWSP", "ZWNJ", "ZWJ", "WJ")
            else ("nb-space" if label == "NBSP" else "soft-break")
        )
        tok(kind, ln, m.start(), label, "invisible U+%04X" % ord(ch))
    # trailing whitespace (spaces/tabs at end of line)
    m = _TRAILING_WS_RE.search(raw)
    if m:
        tok(
            "trailing-ws",
            ln,
            m.start(1),
            "WS:%d" % len(m.group(1)),
            "hard break" if m.group(1) == "  " else "trailing whitespace",
        )
    # stray tabs inside indentation
    body = _TRAILING_WS_RE.sub("", raw)
    m2 = re.match(r"^([ \t]*)\t", body)
    if m2:
        tok("stray-tab", ln, m2.start(), "TAB", "tab in indentation")


# --------------------------------------------------------------------------
# exorcise — remove invisibles, and say exactly what was removed.
# --------------------------------------------------------------------------


def exorcise(text: str) -> Tuple[str, List[CodeToken]]:
    """Strip invisible characters and trailing-whitespace hazards.

    Returns (cleaned_text, removed_tokens): every removal is a CodeToken
    so the caller can file a receipt. Bold honesty rule: never silent.
    """
    report = reveal(text)
    removable = [
        t
        for t in report.tokens
        if t.kind in ("zero-width", "nb-space", "soft-break", "bom", "trailing-ws")
    ]
    cleaned = _INVISIBLE_RE.sub("", text)
    if cleaned.startswith(_BOM):
        cleaned = cleaned[1:]
    cleaned_lines = []
    for line in cleaned.splitlines():
        cleaned_lines.append(_TRAILING_WS_RE.sub("", line))
    cleaned = "\n".join(cleaned_lines)
    if text.endswith("\n") and not cleaned.endswith("\n"):
        cleaned += "\n"
    return cleaned, removable
