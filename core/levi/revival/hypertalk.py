"""English-sentence scripting over inspectable containers.

Studied from: languages-hunt-20260915, report.md [S2, LOAD-BEARING].

Inspired by the *shape* of HyperTalk: scripts written as plain English
sentences (``put ... into ...``, ``go to card 2``) that operate on a
stack of cards, each card holding named fields — and every container is
inspectable, so a non-programmer learns by opening things. This is an
original, from-scratch implementation for LEVI — no HyperTalk code is used.

A :class:`Stack` holds ordered :class:`Card`s; cards hold :class:`Field`s
with text and properties. :class:`Script` objects run handler bodies like
``on mouseUp ... end mouseUp``; the special variable ``it`` carries the
result of the last ``get`` or ``ask``, matching the English-sentence feel.

Honest limits: the grammar is a small line-based subset, not a full
parser; ``ask`` answers come from a scripted answer queue (no real user
input); expressions support quoted strings, field references, ``it``,
numbers and ``&`` concatenation only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/hypertalk"


class ScriptError(Exception):
    """Base class for script failures."""


class NoSuchCard(ScriptError):
    """The stack has no card matching the reference."""


class NoSuchField(ScriptError):
    """The card has no field of that name."""


class NoSuchHandler(ScriptError):
    """No handler answers that message."""


@dataclass
class Field:
    """A named text container with inspectable properties."""

    name: str
    text: str = ""
    props: Dict[str, str] = field(default_factory=dict)

    def inspect(self) -> Dict[str, object]:
        """Return everything a user could learn by opening this field."""
        return {"name": self.name, "text": self.text, "props": dict(self.props)}


@dataclass
class Card:
    """One inspectable container in the stack."""

    name: str
    fields: Dict[str, Field] = field(default_factory=dict)
    scripts: Dict[str, List[str]] = field(default_factory=dict)  # handler -> body lines

    def add_field(self, name: str, text: str = "") -> Field:
        fld = Field(name=name, text=text)
        self.fields[name.lower()] = fld
        return fld

    def get_field(self, name: str) -> Field:
        try:
            return self.fields[name.lower()]
        except KeyError:
            raise NoSuchField(f"card {self.name!r} has no field {name!r}") from None

    def inspect(self) -> Dict[str, object]:
        """Return everything a user could learn by opening this card."""
        return {
            "name": self.name,
            "fields": {n: f.inspect() for n, f in self.fields.items()},
            "handlers": list(self.scripts),
        }


class Stack:
    """An ordered stack of cards with a current-card pointer."""

    def __init__(self, name: str = "untitled") -> None:
        self.name = name
        self.cards: List[Card] = []
        self.current: int = 0
        self.answers: List[str] = []  # scripted replies for `ask`
        self.answer_log: List[str] = []  # everything `answer` showed
        self.it: str = ""  # the special "it" variable

    # -- structure ----------------------------------------------------------
    def add_card(self, name: str) -> Card:
        card = Card(name=name)
        self.cards.append(card)
        return card

    def card(self) -> Card:
        if not self.cards:
            raise NoSuchCard("stack has no cards")
        return self.cards[self.current]

    def go_to(self, ref: str) -> Card:
        ref = ref.strip().lower()
        if ref.startswith("next"):
            self.current = (self.current + 1) % len(self.cards)
        elif ref.startswith("prev"):
            self.current = (self.current - 1) % len(self.cards)
        elif ref.startswith("card "):
            target = ref[5:].strip()
            if target.isdigit():
                idx = int(target) - 1
                if not 0 <= idx < len(self.cards):
                    raise NoSuchCard(f"no card {target}")
                self.current = idx
            else:
                for i, c in enumerate(self.cards):
                    if c.name.lower() == target:
                        self.current = i
                        break
                else:
                    raise NoSuchCard(f"no card named {target!r}")
        else:
            raise ScriptError(f"cannot go to {ref!r}")
        return self.card()

    def inspect(self) -> Dict[str, object]:
        """The whole stack, openable: every card, every field."""
        return {
            "name": self.name,
            "current": self.current + 1,
            "cards": [c.inspect() for c in self.cards],
        }


# ---------------------------------------------------------------------------
# Expression evaluation
# ---------------------------------------------------------------------------


def _split_concat(expr: str) -> List[str]:
    parts, depth, cur = [], 0, ""
    for ch in expr:
        if ch == '"':
            depth = 1 - depth
        if ch == "&" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def evaluate_expr(stack: Stack, expr: str) -> str:
    """Evaluate a small expression: quoted strings, numbers, ``it``, field
    references (``field "name"`` / ``fld "name"``), joined with ``&``."""
    result = ""
    for part in _split_concat(expr):
        part = part.strip()
        low = part.lower()
        if part.startswith('"') and part.endswith('"') and len(part) >= 2:
            result += part[1:-1]
        elif low == "it":
            result += stack.it
        elif low == "empty":
            result += ""
        elif low.startswith("field ") or low.startswith("fld "):
            name = part.split(None, 1)[1].strip().strip('"')
            result += stack.card().get_field(name).text
        else:
            result += part  # bare number or word, taken literally
    return result


def _condition_true(stack: Stack, cond: str) -> bool:
    cond = cond.strip()
    low = cond.lower()
    for op in (" is not ", " is ", " contains ", "="):
        if op in low:
            left, right = low.split(op, 1)
            lval = evaluate_expr(stack, left.strip())
            rval = evaluate_expr(stack, right.strip())
            if op == " is not ":
                return lval != rval
            if op == " contains ":
                return rval.strip('"') in lval
            return lval == rval
    return bool(evaluate_expr(stack, cond))


# ---------------------------------------------------------------------------
# Script runner
# ---------------------------------------------------------------------------


def _parse_put_target(text: str) -> Tuple[str, str]:
    """Parse ``field "name"`` or ``it`` from the tail of a put command."""
    low = text.strip().lower()
    if low == "it":
        return ("it", "")
    for prefix in ("field ", "fld "):
        if low.startswith(prefix):
            return ("field", text.strip()[len(prefix) :].strip().strip('"'))
    raise ScriptError(f"cannot put into {text!r}")


def run_script(stack: Stack, lines: List[str]) -> None:
    """Run script lines against ``stack``'s current card.

    Supports: ``put <expr> into <field|it>``, ``get field "x"``,
    ``add <expr> to field "x"``, ``go to card N|next card|prev card``,
    ``answer <expr>``, ``ask <expr> [with <expr>]``, ``set the <prop> of
    field "x" to <expr>``, ``if <cond> then ... end if``, ``--`` comments.
    """
    i = 0
    while i < len(lines):
        raw = lines[i].strip()
        i += 1
        if not raw or raw.startswith("--"):
            continue
        low = raw.lower()

        if low.startswith("put "):
            expr, _, target = raw[4:].rpartition(" into ")
            if not target:
                raise ScriptError(f"put needs 'into': {raw!r}")
            kind, name = _parse_put_target(target)
            value = evaluate_expr(stack, expr)
            if kind == "it":
                stack.it = value
            else:
                stack.card().get_field(name).text = value

        elif low.startswith("add "):
            expr, _, target = raw[4:].rpartition(" to ")
            if not target:
                raise ScriptError(f"add needs 'to': {raw!r}")
            kind, name = _parse_put_target(target)
            value = evaluate_expr(stack, expr)
            if kind == "it":
                stack.it += value
            else:
                stack.card().get_field(name).text += value

        elif low.startswith("get "):
            rest = raw[4:].strip()
            for prefix in ("field ", "fld "):
                if rest.lower().startswith(prefix):
                    name = rest[len(prefix) :].strip().strip('"')
                    stack.it = stack.card().get_field(name).text
                    break
            else:
                raise ScriptError(f"get needs a field: {raw!r}")

        elif low.startswith("go to ") or low.startswith("go "):
            ref = raw.split(None, 2)[-1] if low.startswith("go to ") else raw[3:]
            stack.go_to(ref)

        elif low.startswith("answer "):
            stack.answer_log.append(evaluate_expr(stack, raw[7:]))

        elif low.startswith("ask "):
            rest = raw[4:]
            prompt, _, default = rest.partition(" with ")
            stack.answer_log.append("ask: " + evaluate_expr(stack, prompt))
            if stack.answers:
                stack.it = stack.answers.pop(0)
            else:
                stack.it = evaluate_expr(stack, default) if default else ""

        elif low.startswith("set the "):
            # set the <prop> of field "x" to <expr>
            body = raw[8:]
            prop, _, rest = body.partition(" of ")
            target, _, expr = rest.partition(" to ")
            kind, name = _parse_put_target(target)
            if kind != "field":
                raise ScriptError(f"set the needs a field: {raw!r}")
            stack.card().get_field(name).props[prop.strip().lower()] = evaluate_expr(
                stack, expr
            )

        elif low.startswith("if ") and low.endswith(" then"):
            cond = raw[3:-5]
            body: List[str] = []
            depth = 1
            while i < len(lines):
                nxt = lines[i].strip()
                i += 1
                if nxt.lower().startswith("if ") and nxt.lower().endswith(" then"):
                    depth += 1
                elif nxt.lower() == "end if":
                    depth -= 1
                    if depth == 0:
                        break
                body.append(nxt)
            if depth:
                raise ScriptError("if without end if")
            if _condition_true(stack, cond):
                run_script(stack, body)

        else:
            raise ScriptError(f"do not understand: {raw!r}")


def send(stack: Stack, handler: str, card: Optional[Card] = None) -> None:
    """Send a message (e.g. ``"mouseUp"``) to a card's handler.

    Handlers are declared with ``on <name> ... end <name>`` via
    :func:`install_handler`. Unhandled messages raise :class:`NoSuchHandler`
    instead of failing silently.
    """
    target = card or stack.card()
    key = handler.lower()
    if key not in target.scripts:
        raise NoSuchHandler(f"card {target.name!r} has no handler for {handler!r}")
    run_script(stack, target.scripts[key])


def install_handler(card: Card, source: str) -> str:
    """Install an ``on <name> ... end <name>`` handler on ``card``.

    Returns the handler name.
    """
    lines = [ln.strip() for ln in source.strip().splitlines() if ln.strip()]
    if not lines or not lines[0].lower().startswith("on "):
        raise ScriptError("handler must start with 'on <name>'")
    name = lines[0][3:].strip().lower()
    if not lines[-1].lower() == f"end {name}":
        raise ScriptError(f"handler {name!r} missing 'end {name}'")
    card.scripts[name] = lines[1:-1]
    return name
