"""Inline pipe codes for scriptable colored display.

Studied from: dead-networks-20260916/report.md (Renegade BBS).

The old mechanism: sysops embedded short inline codes (``|01`` …
``|23``) in menus and messages, giving scripts direct control over the
caller's colored screen — foreground, background, emphasis — without
leaving the text stream. LEVI's reimplementation is that shape: a code
table, a parser that turns coded text into attribute spans, and
renderers for ANSI terminals, plain text, and raw spans. Sysops can
define their own codes at runtime ("scriptable" kept honest: codes are
data, not behavior).

Honest limits: rendering only emits ANSI escape sequences; terminal
capabilities are not probed. Unknown codes are left literal in the
output — never dropped, never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/pipe_colors"

# The built-in foreground palette: code -> color name.
PALETTE: Dict[str, str] = {
    "01": "black",
    "02": "blue",
    "03": "green",
    "04": "cyan",
    "05": "red",
    "06": "magenta",
    "07": "brown",
    "08": "grey",
    "09": "darkgrey",
    "10": "lightblue",
    "11": "lightgreen",
    "12": "lightcyan",
    "13": "lightred",
    "14": "lightmagenta",
    "15": "yellow",
    "16": "white",
}

# Toggle codes understood in addition to the palette.
BOLD_ON = "b"
BOLD_OFF = "n"  # also the universal reset
RESET = "n"

# ANSI foreground numbers for the palette, in the classic 8+bright set.
_ANSI_FG: Dict[str, int] = {
    "black": 30,
    "red": 31,
    "green": 32,
    "brown": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "grey": 37,
    "darkgrey": 90,
    "lightred": 91,
    "lightgreen": 92,
    "yellow": 93,
    "lightblue": 94,
    "lightmagenta": 95,
    "lightcyan": 96,
    "white": 97,
}


@dataclass(frozen=True)
class Attr:
    """The display attribute in force for a span of text."""

    color: Optional[str] = None  # palette color name
    bold: bool = False

    def ansi(self) -> str:
        parts: List[str] = []
        if self.bold:
            parts.append("1")
        if self.color and self.color in _ANSI_FG:
            parts.append(str(_ANSI_FG[self.color]))
        return f"\x1b[{';'.join(parts)}m" if parts else ""


@dataclass(frozen=True)
class Span:
    text: str
    attr: Attr


class PipeTable:
    """The sysop's code table: the built-in palette plus any codes the
    sysop defines. Defining a code rebinds it; the built-ins can be
    shadowed but the shadow is recorded."""

    def __init__(self) -> None:
        self.codes: Dict[str, Attr] = {
            code: Attr(color=name) for code, name in PALETTE.items()
        }
        self.codes[BOLD_ON] = Attr(bold=True)
        self.codes[RESET] = Attr()
        self.shadowed: List[str] = []

    def define(
        self, code: str, color: Optional[str] = None, bold: bool = False
    ) -> None:
        """Bind ``|code`` to an attribute. Codes are 1-2 word characters
        (the ``|`` prefix is implied)."""
        if not code or len(code) > 2 or not code.isalnum():
            raise ValueError("code must be 1-2 alphanumeric characters")
        if color is not None and color not in PALETTE.values():
            raise ValueError(f"unknown color {color!r}")
        if code in self.codes and code not in self.shadowed:
            self.shadowed.append(code)
        self.codes[code.lower()] = Attr(color=color, bold=bold)

    def lookup(self, code: str) -> Optional[Attr]:
        return self.codes.get(code.lower())


def parse(text: str, table: Optional[PipeTable] = None) -> List[Span]:
    """Split coded text into attribute spans. A ``|`` followed by a known
    code switches attributes; a ``|`` followed by anything else (or a
    trailing lone ``|``) is emitted literally. Never raises."""
    table = table or PipeTable()
    spans: List[Span] = []
    buf: List[str] = []
    cur = Attr()

    def flush() -> None:
        if buf:
            spans.append(Span("".join(buf), cur))
            buf.clear()

    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "|" and i + 1 < n:
            # Prefer the two-char code, then the one-char code.
            hit: Optional[Tuple[str, Attr]] = None
            for size in (2, 1):
                code = text[i + 1 : i + 1 + size]
                attr = table.lookup(code)
                if attr is not None:
                    hit = (code, attr)
                    break
            if hit is not None:
                flush()
                code, attr = hit
                if code.lower() == RESET:
                    cur = Attr()
                elif code.lower() == BOLD_ON:
                    cur = Attr(color=cur.color, bold=True)
                else:
                    cur = Attr(color=attr.color, bold=cur.bold or attr.bold)
                i += 1 + len(code)
                continue
        buf.append(ch)
        i += 1
    flush()
    return spans


def render(text: str, table: Optional[PipeTable] = None) -> str:
    """Render coded text with ANSI escapes; ends with a reset so the
    caller's screen is left clean."""
    spans = parse(text, table)
    out = "".join((s.attr.ansi() + s.text) if s.text else "" for s in spans)
    return out + ("\x1b[0m" if spans else "")


def strip(text: str, table: Optional[PipeTable] = None) -> str:
    """Plain text with every recognized code removed. Unknown ``|`` runs
    are kept as-is."""
    return "".join(s.text for s in parse(text, table))


def visible_len(text: str, table: Optional[PipeTable] = None) -> int:
    """Screen columns the text occupies — codes excluded. What the old
    menu painters needed for column math."""
    return sum(len(s.text) for s in parse(text, table))


def codes_used(text: str, table: Optional[PipeTable] = None) -> List[str]:
    """List the distinct recognized codes present in the text."""
    found: List[str] = []
    table = table or PipeTable()
    i, n = 0, len(text)
    while i < n:
        if text[i] == "|" and i + 1 < n:
            for size in (2, 1):
                code = text[i + 1 : i + 1 + size]
                if table.lookup(code) is not None:
                    if code.lower() not in found:
                        found.append(code.lower())
                    i += 1 + size
                    break
            else:
                i += 1
        else:
            i += 1
    return found
