"""Deterministic syntax highlighting for Hicomb's Phase-0 core languages.

Pure-Python, regex-driven, no network, no model — the reversal of Acode's
plugin-lottery LSP: language intelligence built into the daemon, offline,
identical bytes in for identical tokens out. Windowed highlighting
(``highlight(lines, lang, start, end)``) keeps 50k-line files smooth; the
buffer itself is never truncated.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

TOKEN_KINDS = (
    "keyword",
    "string",
    "comment",
    "number",
    "builtin",
    "decorator",
    "function",
    "tag",
    "attr",
    "variable",
    "text",
    "punct",
    "heading",
    "bold",
    "italic",
    "code",
    "link",
)

LANG_BY_EXT = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".md": "markdown",
    ".markdown": "markdown",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".txt": "plain",
    ".json": "json",
    ".yaml": "plain",
    ".yml": "plain",
    ".toml": "plain",
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(
    r"0[xX][0-9a-fA-F_]+|0[bB][01_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?"
)
_WS = re.compile(r"\s+")


@dataclass
class LangSpec:
    keywords: frozenset = frozenset()
    builtins: frozenset = frozenset()
    line_comment: str = ""
    block_comment: tuple[str, ...] = ()
    string_delims: tuple[str, ...] = ('"', "'")
    triple_delims: tuple[str, ...] = ()
    decorators: bool = False
    html_mode: bool = False
    css_mode: bool = False


def _specs() -> dict[str, LangSpec]:
    py_kw = frozenset(
        "False None True and as assert async await break class continue def del "
        "elif else except finally for from global if import in is lambda nonlocal "
        "not or pass raise return try while with yield match case".split()
    )
    py_bi = frozenset(
        "abs all any ascii bin bool bytearray bytes callable chr classmethod "
        "compile complex dict dir divmod enumerate eval exec filter float format "
        "frozenset getattr globals hasattr hash help hex id input int isinstance "
        "issubclass iter len list locals map max memoryview min next object oct "
        "open ord pow print property range repr reversed round set setattr slice "
        "sorted staticmethod str sum super tuple type vars zip self cls".split()
    )
    js_kw = frozenset(
        "await break case catch class const continue debugger default delete do "
        "else enum export extends false finally for function if implements import "
        "in instanceof interface let new null return super switch this throw true "
        "try typeof var void while with yield async of static get set".split()
    )
    js_bi = frozenset(
        "console window document Array Object String Number Boolean Promise "
        "JSON Math Date RegExp Error Map Set undefined NaN Infinity "
        "parseInt parseFloat".split()
    )
    sh_kw = frozenset(
        "if then else elif fi for while until do done case esac in function "
        "return exit local export readonly declare select time coproc".split()
    )
    return {
        "python": LangSpec(
            keywords=py_kw,
            builtins=py_bi,
            line_comment="#",
            string_delims=('"', "'"),
            triple_delims=('"""', "'''"),
            decorators=True,
        ),
        "javascript": LangSpec(
            keywords=js_kw,
            builtins=js_bi,
            line_comment="//",
            block_comment=("/*", "*/"),
            string_delims=('"', "'", "`"),
        ),
        "typescript": LangSpec(
            keywords=js_kw
            | frozenset("type readonly abstract namespace declare".split()),
            builtins=js_bi,
            line_comment="//",
            block_comment=("/*", "*/"),
            string_delims=('"', "'", "`"),
            decorators=True,
        ),
        "html": LangSpec(
            line_comment="",
            block_comment=("<!--", "-->"),
            string_delims=('"', "'"),
            html_mode=True,
        ),
        "css": LangSpec(
            keywords=frozenset(
                "@media @import @keyframes @font-face @supports".split()
            ),
            block_comment=("/*", "*/"),
            string_delims=('"', "'"),
            css_mode=True,
        ),
        "shell": LangSpec(
            keywords=sh_kw,
            builtins=frozenset("echo printf cd ls cat grep sed awk test".split()),
            line_comment="#",
            string_delims=('"', "'"),
        ),
        "json": LangSpec(
            keywords=frozenset("true false null".split()),
            string_delims=('"',),
        ),
        "plain": LangSpec(),
    }


_SPECS = _specs()
_FENCE = "```"

# markdown inline spans, precompiled once (were rebuilt per line)
_MD_INLINE = (
    ("code", re.compile(r"`[^`]+`")),
    ("link", re.compile(r"\[[^\]]*\]\([^)]*\)")),
    ("bold", re.compile(r"\*\*[^*]+\*\*|__[^_]+__")),
    ("italic", re.compile(r"(?<!\*)\*[^*]+\*(?!\*)|(?<!_)_+[^_]+_+(?!_)")),
)
_DECORATOR = re.compile(r"@[\w.]+")
_SHELL_VAR = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*|\$[@*#?$!0-9]")
_TAG_OPEN = re.compile(r"</?[A-Za-z][\w.:-]*")


def detect_language(path: str | None) -> str:
    """Language id from file extension; 'plain' when unknown or no path."""
    if not path:
        return "plain"
    _, ext = os.path.splitext(path.lower())
    return LANG_BY_EXT.get(ext, "plain")


@dataclass
class Token:
    kind: str
    start: int
    end: int

    def text_of(self, line: str) -> str:
        return line[self.start : self.end]


@dataclass
class _State:
    str_delim: str | None = None
    triple: bool = False
    block: bool = False
    fence: bool = False  # markdown code fence


def _close_quote(line: str, i: int, delim: str) -> int:
    """Index just past the closing delim, or -1 if unterminated."""
    n = len(line)
    j = i + len(delim)
    while j < n:
        if line.startswith(delim, j):
            return j + len(delim)
        if line[j] == "\\" and len(delim) == 1:
            j += 2
            continue
        j += 1
    return -1


def _parse_tag(line: str, i: int, toks: list[Token]) -> int:
    """Parse <tag attr="v" ...> starting at i. Returns new index."""
    m = _TAG_OPEN.match(line, i)
    if not m:
        toks.append(Token("punct", i, i + 1))
        return i + 1
    toks.append(Token("tag", i, m.end()))
    j = m.end()
    n = len(line)
    while j < n:
        if line.startswith("/>", j) or line[j] == ">":
            toks.append(Token("punct", j, j + (2 if line.startswith("/>", j) else 1)))
            return j + (2 if line.startswith("/>", j) else 1)
        if line[j] in "\"'":
            end = _close_quote(line, j, line[j])
            end = n if end == -1 else end
            toks.append(Token("string", j, end))
            j = end
            continue
        im = _IDENT.match(line, j)
        if im:
            toks.append(Token("attr", im.start(), im.end()))
            j = im.end()
            continue
        if line[j] == "=":
            toks.append(Token("punct", j, j + 1))
        j += 1
    return j


def _flush_text(toks: list[Token], start: int, end: int) -> None:
    if end > start:
        toks.append(Token("text", start, end))


def _tokenize_line(line: str, spec: LangSpec, state: _State) -> list[Token]:
    toks: list[Token] = []
    n = len(line)
    i = 0
    text_start: int | None = None

    def text_to(j: int) -> None:
        nonlocal text_start
        if text_start is not None:
            _flush_text(toks, text_start, j)
            text_start = None

    while i < n:
        # --- continuations from previous lines ---
        if state.str_delim is not None:
            end = _close_quote(line, i, state.str_delim)
            if end == -1:
                toks.append(Token("string", i, n))
                i = n
            else:
                toks.append(Token("string", i, end))
                state.str_delim = None
                state.triple = False
                i = end
            continue
        if state.block:
            bstart, bend = spec.block_comment
            k = line.find(bend, i)
            if k == -1:
                toks.append(Token("comment", i, n))
                i = n
            else:
                toks.append(Token("comment", i, k + len(bend)))
                state.block = False
                i = k + len(bend)
            continue

        # --- fresh scanning ---
        if spec.block_comment:
            bstart, bend = spec.block_comment
            if line.startswith(bstart, i):
                text_to(i)
                k = line.find(bend, i + len(bstart))
                if k == -1:
                    toks.append(Token("comment", i, n))
                    state.block = True
                    i = n
                else:
                    toks.append(Token("comment", i, k + len(bend)))
                    i = k + len(bend)
                continue
        if spec.line_comment and line.startswith(spec.line_comment, i):
            # '#' inside shell ${} etc. is rare; keep the simple rule.
            text_to(i)
            toks.append(Token("comment", i, n))
            break
        # strings (triple delims first — longest match wins)
        opened = False
        for delim in spec.triple_delims:
            if line.startswith(delim, i):
                text_to(i)
                end = _close_quote(line, i, delim)
                if end == -1:
                    toks.append(Token("string", i, n))
                    state.str_delim = delim
                    state.triple = True
                    i = n
                else:
                    toks.append(Token("string", i, end))
                    i = end
                opened = True
                break
        if opened:
            continue
        for delim in spec.string_delims:
            if line.startswith(delim, i):
                text_to(i)
                end = _close_quote(line, i, delim)
                if end == -1:
                    toks.append(Token("string", i, n))
                    state.str_delim = delim
                    i = n
                else:
                    toks.append(Token("string", i, end))
                    i = end
                opened = True
                break
        if opened:
            continue
        # html tags
        if spec.html_mode and line[i] == "<":
            text_to(i)
            i = _parse_tag(line, i, toks)
            continue
        # decorators (@name at line start, python/ts)
        if spec.decorators and line[i] == "@" and (i == 0 or line[i - 1].isspace()):
            text_to(i)
            m = _DECORATOR.match(line, i)
            if m is None:  # lone "@" — punctuation, not a decorator
                toks.append(Token("punct", i, i + 1))
                i += 1
            else:
                toks.append(Token("decorator", i, m.end()))
                i = m.end()
            continue
        # shell variables
        if spec.line_comment == "#" and line[i] == "$":
            text_to(i)
            m = _SHELL_VAR.match(line, i)
            if m:
                toks.append(Token("variable", i, m.end()))
                i = m.end()
            else:
                text_start = i if text_start is None else text_start
                i += 1
            continue
        # numbers
        nm = _NUMBER.match(line, i)
        if nm and (i == 0 or not (line[i - 1].isalnum() or line[i - 1] == "_")):
            # don't split identifiers like v2 or hex handled by the pattern
            if i == 0 or not line[i - 1] == ".":
                text_to(i)
                toks.append(Token("number", nm.start(), nm.end()))
                i = nm.end()
                continue
        # css property names: ident followed by ':'
        if spec.css_mode:
            im = _IDENT.match(line, i)
            if im:
                rest = line[im.end() :].lstrip()
                if rest.startswith(":") and not rest.startswith("::"):
                    text_to(i)
                    toks.append(Token("attr", im.start(), im.end()))
                    i = im.end()
                    continue
        # identifiers
        im = _IDENT.match(line, i)
        if im:
            text_to(i)
            word = im.group(0)
            if word in spec.keywords:
                kind = "keyword"
            elif word in spec.builtins:
                kind = "builtin"
            else:
                after = line[im.end() :].lstrip()
                kind = "function" if after.startswith("(") else "text"
            toks.append(Token(kind, im.start(), im.end()))
            i = im.end()
            continue
        # punctuation vs text run
        if line[i] in " \t":
            if text_start is None:
                text_start = i
            i += 1
            continue
        text_to(i)
        toks.append(Token("punct", i, i + 1))
        i += 1

    text_to(n)
    return toks


def _tokenize_markdown_line(line: str, state: _State) -> list[Token]:
    toks: list[Token] = []
    stripped = line.lstrip()
    if stripped.startswith(_FENCE):
        state.fence = not state.fence
        return [Token("code", 0, len(line))]
    if state.fence:
        return [Token("code", 0, len(line))]
    m = re.match(r"(#{1,6})(\s+|$)", stripped)
    if m:
        off = len(line) - len(stripped)
        toks.append(Token("heading", off, off + m.end()))
        i = off + m.end()
    else:
        i = 0
    # inline spans: `code`, **bold**, *italic*, [text](url)
    spans: list[Token] = []
    for kind, rx in _MD_INLINE:
        for mm in rx.finditer(line, i):
            spans.append(Token(kind, mm.start(), mm.end()))
    spans.sort(key=lambda t: (t.start, t.end))
    # drop overlapping (first pattern wins by position)
    kept: list[Token] = []
    last_end = -1
    for t in spans:
        if t.start >= last_end:
            kept.append(t)
            last_end = t.end
    pos = i
    for t in kept:
        if t.start > pos:
            toks.append(Token("text", pos, t.start))
        toks.append(t)
        pos = t.end
    if pos < len(line):
        toks.append(Token("text", pos, len(line)))
    return toks or [Token("text", 0, len(line))]


def tokenize(lines: list[str], language: str) -> list[list[Token]]:
    """Tokenize every line. Deterministic: same lines -> same tokens."""
    if language == "markdown":
        state = _State()
        return [_tokenize_markdown_line(ln, state) for ln in lines]
    spec = _SPECS.get(language, _SPECS["plain"])
    state = _State()
    return [_tokenize_line(ln, spec, state) for ln in lines]


def highlight(
    lines: list[str],
    language: str,
    start: int = 0,
    end: int | None = None,
) -> list[list[Token]]:
    """Windowed highlighting for large files.

    NOTE: multi-line states (block comments, triple-quoted strings) are
    tracked from line 0, so a window starting mid-file still tokenizes
    correctly; only the returned slice is windowed.
    """
    if start < 0 or (end is not None and end < start):
        raise ValueError("bad highlight window")
    if language == "markdown":
        state = _State()
        all_toks = [_tokenize_markdown_line(ln, state) for ln in lines]
    else:
        spec = _SPECS.get(language, _SPECS["plain"])
        state = _State()
        all_toks = [_tokenize_line(ln, spec, state) for ln in lines]
    return all_toks[start:end]


def token_kinds_used(tokens: list[list[Token]]) -> set[str]:
    kinds: set[str] = set()
    for line_toks in tokens:
        for tok in line_toks:
            kinds.add(tok.kind)
    return kinds
