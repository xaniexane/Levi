"""dialects — one shared block syntax, many tiny languages.

Studied from: revival-50-more-20260916-0009/report-part1.md [entry #10].

The studied shape: code, data, and protocols share one uniform syntax,
so creating a tiny domain language ("dialect") is cheap — you define
what a block of words *means* instead of writing a parser. LEVI's
version, ``Dialect``, keeps the idea and rewrites the machinery:

* **Blocks** are the one syntax. Text like ``[draw box 10 20]`` parses
  to nested Python lists; a block is data until a dialect interprets it.
* **Words** are plain strings; the dialect decides which are commands.
* A **dialect** is a Python object: a registry of word -> handler plus
  an ``interpret`` loop. Three ship built-in: ``parlex`` (a tiny parsing
  dialect), ``sigil`` (a layout/UI dialect), and ``sketch`` (a drawing
  dialect). New ones are made with ``Dialect("name")`` and
  ``dialect.on("word", handler)``.

Interpretation is intentionally plain recursive evaluation — this is a
reference implementation, not a compiler. Blocks are homoiconic in the
limited sense that a block can be built, inspected, rewritten, and then
run, all with the same constructors.

This is an original, from-scratch implementation for LEVI. Not
artificial. Synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ORIGIN = "levi-revival/dialects"

Handler = Callable[["Dialect", List[Any], Dict[str, Any]], Any]


# ---------------------------------------------------------------------------
# Blocks: the one syntax
# ---------------------------------------------------------------------------


def tokenize(src: str) -> List[str]:
    """Split dialect source into tokens: brackets, strings, words, numbers."""
    toks: List[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c in "[]":
            toks.append(c)
            i += 1
            continue
        if c == '"':
            j = src.find('"', i + 1)
            if j == -1:
                raise SyntaxError("unterminated string")
            toks.append(src[i : j + 1])
            i = j + 1
            continue
        if c == ";":  # comment to end of line
            j = src.find("\n", i)
            i = n if j == -1 else j
            continue
        j = i
        while j < n and src[j] not in ' \t\r\n[]"':
            j += 1
        toks.append(src[i:j])
        i = j
    return toks


def _atom(tok: str) -> Any:
    if tok.startswith('"') and tok.endswith('"'):
        return tok[1:-1]
    try:
        return int(tok)
    except ValueError:
        pass
    try:
        return float(tok)
    except ValueError:
        pass
    return tok  # a word


def parse(src: str) -> List[Any]:
    """Parse source text into one top-level block (a Python list)."""
    toks = tokenize(src)
    stack: List[List[Any]] = [[]]
    for tok in toks:
        if tok == "[":
            stack.append([])
        elif tok == "]":
            if len(stack) < 2:
                raise SyntaxError("unmatched ]")
            blk = stack.pop()
            stack[-1].append(blk)
        else:
            stack[-1].append(_atom(tok))
    if len(stack) != 1:
        raise SyntaxError("unmatched [")
    return stack[0]


def render(block: List[Any]) -> str:
    """Render a block back to source text (round-trips through ``parse``)."""
    parts: List[str] = []
    for item in block:
        if isinstance(item, list):
            parts.append("[" + render(item) + "]")
        elif isinstance(item, str) and " " in item:
            parts.append('"' + item + '"')
        else:
            parts.append(str(item))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Dialects
# ---------------------------------------------------------------------------


@dataclass
class Dialect:
    """A tiny language over blocks: words map to handlers.

    A handler receives ``(dialect, args, env)`` where ``args`` are the
    remaining items after the word and ``env`` is a mutable per-run
    namespace. Handlers may recurse into ``dialect.run(block, env)`` to
    evaluate nested blocks, which is how dialects compose.
    """

    name: str
    words: Dict[str, Handler] = field(default_factory=dict)
    doc: str = ""

    def on(self, word: str, handler: Handler) -> "Dialect":
        """Register (or replace) a word handler. Returns self for chaining."""
        self.words[word] = handler
        return self

    def run(self, block: List[Any], env: Optional[Dict[str, Any]] = None) -> Any:
        """Interpret a block; the value is the last word's result (or None)."""
        env = {} if env is None else env
        # ``parse`` wraps source in one top-level list; unwrap a lone block.
        if len(block) == 1 and isinstance(block[0], list):
            return self.run(block[0], env)
        result: Any = None
        i = 0
        while i < len(block):
            item = block[i]
            if isinstance(item, str) and item in self.words:
                args = block[i + 1 :]
                result = self.words[item](self, list(args), env)
                break  # a word consumes the rest of its block
            i += 1
        return result

    def knows(self, word: str) -> bool:
        return word in self.words


# ---------------------------------------------------------------------------
# Built-in dialect 1: parlex — a tiny pattern-matching dialect
# ---------------------------------------------------------------------------


def make_parlex() -> Dialect:
    """``parlex``: match input text against a block of matchers.

    Words: ``lit "s"`` (literal), ``any`` (one char), ``many <matcher>``
    (greedy repeat), ``seq [ ... ]`` (all in order), ``either [ ... ]``
    (first that matches). Result: matched text or ``None``.
    """

    def _match(d: Dialect, block: List[Any], text: str, pos: int) -> Optional[int]:
        """Match a matcher block at pos; return end position or None."""
        if not block:
            return pos
        word, rest = block[0], block[1:]
        if word == "lit":
            s = str(rest[0])
            return pos + len(s) if text.startswith(s, pos) else None
        if word == "any":
            return pos + 1 if pos < len(text) else None
        if word == "many":
            (sub,) = rest
            p = pos
            while True:
                nxt = _match(d, sub if isinstance(sub, list) else [sub], text, p)
                if nxt is None or nxt == p:
                    break
                p = nxt
            return p
        if word == "seq":
            p = pos
            for sub in rest[0]:
                nxt = _match(d, sub if isinstance(sub, list) else [sub], text, p)
                if nxt is None:
                    return None
                p = nxt
            return p
        if word == "either":
            for sub in rest[0]:
                nxt = _match(d, sub if isinstance(sub, list) else [sub], text, pos)
                if nxt is not None:
                    return nxt
            return None
        raise ValueError(f"parlex: unknown matcher {word!r}")

    def match_word(d: Dialect, args: List[Any], env: Dict[str, Any]) -> Any:
        text = env.get("text", "")
        end = _match(d, args, text, 0)
        return text[:end] if end is not None else None

    return Dialect("parlex", doc="pattern-matching dialect").on("match", match_word)


# ---------------------------------------------------------------------------
# Built-in dialect 2: sigil — a tiny layout/UI dialect
# ---------------------------------------------------------------------------


def make_sigil() -> Dialect:
    """``sigil``: build a widget tree from blocks.

    Words: ``row``/``col`` (containers), ``label "text"``,
    ``button "text"``. Result: a nested dict tree describing the UI.
    """

    def _widget(d: Dialect, block: List[Any]) -> Dict[str, Any]:
        word, rest = block[0], block[1:]
        if word in ("row", "col"):
            kids = [_widget(d, b) for b in rest[0]] if rest else []
            return {"kind": word, "children": kids}
        if word in ("label", "button"):
            return {"kind": word, "text": str(rest[0])}
        raise ValueError(f"sigil: unknown widget {word!r}")

    def build_word(d: Dialect, args: List[Any], env: Dict[str, Any]) -> Any:
        return _widget(d, args)

    return Dialect("sigil", doc="layout dialect").on("build", build_word)


# ---------------------------------------------------------------------------
# Built-in dialect 3: sketch — a tiny drawing dialect
# ---------------------------------------------------------------------------


def make_sketch() -> Dialect:
    """``sketch``: accumulate drawing commands.

    Words: ``pen "color"``, ``box x y w h``, ``circle x y r``.
    Result: a list of command dicts (a display list, not pixels).
    """

    def draw_word(d: Dialect, args: List[Any], env: Dict[str, Any]) -> Any:
        cmds: List[Dict[str, Any]] = []
        i = 0
        while i < len(args):
            word = args[i]
            if word == "pen":
                env["pen"] = str(args[i + 1])
                i += 2
            elif word in ("box", "circle"):
                n = 4 if word == "box" else 3
                cmds.append(
                    {
                        "op": word,
                        "pen": env.get("pen", "black"),
                        "args": [float(a) for a in args[i + 1 : i + 1 + n]],
                    }
                )
                i += 1 + n
            else:
                raise ValueError(f"sketch: unknown command {word!r}")
        return cmds

    return Dialect("sketch", doc="drawing dialect").on("draw", draw_word)


BUILTINS: Dict[str, Callable[[], Dialect]] = {
    "parlex": make_parlex,
    "sigil": make_sigil,
    "sketch": make_sketch,
}
