"""Pollen — Hicomb's from-scratch formatter. "Pollen's the work: raw
material in, refined code out."

LAWS (declared up front, machine-checked in tests/test_hicomb_studio.py):
  I1 POLLEN-ABORT   format_text raising FormatterError means the save
                    pipeline MUST abort; target file bytes stay identical.
  I2 IDEMPOTENT     format(format(x)) == format(x) for every language.
  I3 SAFE-ONLY      formatters never delete code lines; they only normalize
                    whitespace/encoding (nothing-thrown-away law).

Stdlib only. Deterministic: identical bytes in, identical bytes out.
A formatter is a pure function text -> text that either returns refined
text or raises FormatterError. The pipeline (pipeline.py) owns the
abort-on-failure gate — this module only formats.
"""

from __future__ import annotations

import io
import json
import re
import tokenize

from levi.hicomb.highlight import LANG_BY_EXT, detect_language

MAX_BLANK_RUN = 2  # collapse longer blank-line runs to this many


class FormatterError(Exception):
    """Pollen refused the text. The save pipeline must abort on this."""


# ------------------------------------------------------------------ registry
_FORMATTERS: dict[str, object] = {}


def register(language: str, func) -> None:
    """Register a formatter for a language name. Re-registration replaces."""
    if not language or not isinstance(language, str):
        raise FormatterError(f"bad language name: {language!r}")
    if not callable(func):
        raise FormatterError(f"formatter for {language!r} is not callable")
    _FORMATTERS[language] = func


def languages() -> list[str]:
    return sorted(_FORMATTERS)


# ------------------------------------------------------------ base passes
def _base_pass(text: str) -> str:
    """Whitespace normalization shared by every language. Idempotent.

    - CRLF/CR -> LF
    - tabs -> 4 spaces (never silently dropped)
    - trailing whitespace stripped on every line
    - blank-line runs collapsed to MAX_BLANK_RUN
    - exactly one trailing newline
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", "    ")
    lines = [line.rstrip() for line in text.split("\n")]
    out: list[str] = []
    blanks = 0
    for line in lines:
        if line.strip():
            out.append(line)
            blanks = 0
        else:
            blanks += 1
            if blanks <= MAX_BLANK_RUN:
                out.append("")
    # Drop trailing blank lines; keep exactly one final newline.
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


# ------------------------------------------------------------ per-language
def _fmt_python(text: str) -> str:
    refined = _base_pass(text)
    # Syntax gate: broken Python never gets "formatted" — it gets refused,
    # and the pipeline aborts the write instead of corrupting the file.
    try:
        compile(refined, "<pollen>", "exec")
    except (SyntaxError, ValueError) as exc:
        raise FormatterError(f"python syntax invalid, refusing: {exc}") from exc
    return refined


def _fmt_json(text: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FormatterError(f"json invalid, refusing: {exc}") from exc
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _brace_scan(text: str) -> None:
    """Refuse JS/TS/CSS with unbalanced brackets outside strings/comments."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":  # line comment
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and nxt == "*":  # block comment
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if ch in ("'", '"', "`"):  # string / template literal
            quote = ch
            i += 1
            while i < n:
                c = text[i]
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    break
                i += 1
            i += 1
            continue
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() != pairs[ch]:
                raise FormatterError(f"unbalanced {ch!r} in source")
            # (pop already validated)
        i += 1
    if stack:
        raise FormatterError(f"unclosed {stack[-1]!r} in source")


def _fmt_braced(text: str) -> str:
    refined = _base_pass(text)
    _brace_scan(refined)
    return refined


def _fmt_plain(text: str) -> str:
    return _base_pass(text)


register("python", _fmt_python)
register("json", _fmt_json)
register("javascript", _fmt_braced)
register("typescript", _fmt_braced)
register("css", _fmt_braced)
register("html", _fmt_plain)
register("markdown", _fmt_plain)
register("shell", _fmt_plain)
register("plain", _fmt_plain)


# ------------------------------------------------------------------ entry
def format_text(language: str, text: str) -> str:
    """Format text for a language. Raises FormatterError on refusal.

    Unknown languages fall back to the safe base pass — Pollen never
    refuses a language it doesn't know, it just normalizes whitespace.
    """
    if not isinstance(text, str):
        raise FormatterError("pollen formats text, not bytes")
    func = _FORMATTERS.get(language, _fmt_plain)
    try:
        result = func(text)
    except FormatterError:
        raise
    except Exception as exc:  # a formatter must never crash the pipeline
        raise FormatterError(f"formatter for {language!r} failed: {exc}") from exc
    if not isinstance(result, str):
        raise FormatterError(f"formatter for {language!r} returned non-text")
    return result


def language_for_path(path: str) -> str:
    """Language name for a file path, defaulting to plain."""
    try:
        return detect_language(path)
    except Exception:
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        return LANG_BY_EXT.get(ext, "plain")
