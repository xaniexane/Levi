"""LEVI's zero-mode-switch card workshop: reading a stack *is* authoring it.

Studied from: retired-software-revival-research-20260916-0004/report.md (§1).

The load-bearing mechanism of HyperCard: there is no separate "edit
mode" and "run mode". The same API that renders a card is the API that
rewrites it — you fix a plant's name by typing on the card, not by
re-prompting some builder. LEVI's remix, ``cardstack``, keeps that
discipline: a ``Stack`` of ``Card``s, each card carrying named ``fields``
and ``buttons``, each button carrying a small script in ``kard`` — a tiny
original LEVI script dialect with a handful of verbs (``go``, ``set``,
``ask``, ``say``). The engine runs scripts against the very stack the
reader sees; the author mutates the same objects the reader navigates.

This is an original, from-scratch reimplementation — no recovered code.
Local-first, stdlib only, no network. LEVI's own synthetic intelligence,
never a mask of anyone else's.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Callable, Optional


ORIGIN = "levi-revival/cardstack"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CardstackError(Exception):
    """Base class for cardstack failures."""


class UnknownCard(CardstackError):
    """A script or call named a card that isn't in the stack."""

    def __init__(self, name: str):
        super().__init__(f"no card named {name!r} in this stack")
        self.name = name


class UnknownField(CardstackError):
    """A script named a field the current card doesn't carry."""


class KardSyntaxError(CardstackError):
    """A button script line could not be parsed."""


# ---------------------------------------------------------------------------
# Card / Button / Stack
# ---------------------------------------------------------------------------


@dataclass
class Button:
    """A clickable script holder. The script is ``kard`` source text."""

    name: str
    script: str = ""

    def lines(self) -> list[str]:
        return [
            ln.strip()
            for ln in self.script.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]


@dataclass
class Card:
    """One card: named fields (the data) and buttons (the behavior)."""

    name: str
    fields: dict[str, str] = field(default_factory=dict)
    buttons: dict[str, Button] = field(default_factory=dict)

    # -- read ---------------------------------------------------------------
    def read_field(self, field_name: str) -> str:
        if field_name not in self.fields:
            raise UnknownField(f"card {self.name!r} has no field {field_name!r}")
        return self.fields[field_name]

    # -- author (same object the reader sees; no mode switch) ---------------
    def set_field(self, field_name: str, value: str) -> None:
        self.fields[field_name] = str(value)

    def add_button(self, name: str, script: str = "") -> Button:
        button = Button(name=name, script=script)
        self.buttons[name] = button
        return button

    def render(self) -> str:
        """The card as a reader sees it — and as an author edits it."""
        out = [f"== {self.name} =="]
        for key, value in self.fields.items():
            out.append(f"  [{key}] {value}")
        for name in self.buttons:
            out.append(f"  <{name}>")
        return "\n".join(out)


class Stack:
    """An ordered deck of cards with a current position.

    Navigation, reading, and authoring all go through this one object:
    no separate builder, no separate player.
    """

    def __init__(self, name: str = "untitled"):
        self.name = name
        self.cards: dict[str, Card] = {}
        self.order: list[str] = []
        self._current: Optional[str] = None

    # -- authoring ----------------------------------------------------------
    def add_card(self, name: str) -> Card:
        if name in self.cards:
            raise CardstackError(f"card {name!r} already exists in this stack")
        card = Card(name=name)
        self.cards[name] = card
        self.order.append(name)
        if self._current is None:
            self._current = name
        return card

    def remove_card(self, name: str) -> Card:
        if name not in self.cards:
            raise UnknownCard(name)
        card = self.cards.pop(name)
        self.order.remove(name)
        if self._current == name:
            self._current = self.order[0] if self.order else None
        return card

    # -- reading / navigating -----------------------------------------------
    def card(self, name: str) -> Card:
        if name not in self.cards:
            raise UnknownCard(name)
        return self.cards[name]

    @property
    def current(self) -> Card:
        if self._current is None:
            raise CardstackError("this stack is empty — no current card")
        return self.cards[self._current]

    def go(self, name: str) -> Card:
        """Turn to a card by name. Verbs and humans share this."""
        if name not in self.cards:
            raise UnknownCard(name)
        self._current = name
        return self.cards[name]

    def next(self) -> Card:
        if not self.order:
            raise CardstackError("this stack is empty")
        idx = self.order.index(self._current) if self._current else -1
        self._current = self.order[(idx + 1) % len(self.order)]
        return self.cards[self._current]

    def prev(self) -> Card:
        if not self.order:
            raise CardstackError("this stack is empty")
        idx = self.order.index(self._current) if self._current else 0
        self._current = self.order[(idx - 1) % len(self.order)]
        return self.cards[self._current]

    def find_cards(self, field_name: str, value: str) -> list[Card]:
        """Clerical search across the stack — a small courtesy of the machine."""
        return [
            card for card in self.cards.values() if card.fields.get(field_name) == value
        ]

    def render(self) -> str:
        return self.current.render()


# ---------------------------------------------------------------------------
# kard — the tiny original LEVI script dialect
# ---------------------------------------------------------------------------
#
# One verb per line. Verbs:
#   go "card name"            — turn to a card
#   show card "card name"     — alias of go
#   set field "name" to "v"  — write a field on the current card
#   ask "prompt" into var    — read one line of input into a variable
#   say "text"               — emit a line of output
# Variables are $name inside quoted text.


def _interpolate(text: str, variables: dict[str, str]) -> str:
    for key, value in variables.items():
        text = text.replace(f"${key}", value)
    return text


class KardEngine:
    """Runs kard scripts against a stack. The runner *is* the reader's
    view: scripts mutate the very cards a human is looking at."""

    def __init__(
        self,
        stack: Stack,
        ask: Optional[Callable[[str], str]] = None,
        say: Optional[Callable[[str], None]] = None,
    ):
        self.stack = stack
        self.ask = ask if ask is not None else (lambda prompt: input(prompt + " "))
        self.say = say if say is not None else print

    def run_button(self, button_name: str) -> dict[str, str]:
        """Press a button on the current card. Returns the script's variables."""
        card = self.stack.current
        if button_name not in card.buttons:
            raise CardstackError(f"card {card.name!r} has no button {button_name!r}")
        return self.run_script(card.buttons[button_name].script)

    def run_script(self, source: str) -> dict[str, str]:
        variables: dict[str, str] = {}
        for lineno, raw in enumerate(source.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                self._run_line(line, variables)
            except CardstackError:
                raise
            except Exception as exc:
                raise KardSyntaxError(f"kard line {lineno}: {line!r} — {exc}") from exc
        return variables

    # -- verbs --------------------------------------------------------------
    def _run_line(self, line: str, variables: dict[str, str]) -> None:
        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            raise KardSyntaxError(f"cannot parse {line!r}: {exc}") from exc
        if not tokens:
            return
        verb = tokens[0].lower()
        if verb in ("go",):
            self._verb_go(tokens, variables)
        elif verb == "show":
            self._verb_show(tokens, variables)
        elif verb == "set":
            self._verb_set(tokens, variables)
        elif verb == "ask":
            self._verb_ask(tokens, variables)
        elif verb == "say":
            self._verb_say(tokens, variables)
        else:
            raise KardSyntaxError(f"unknown verb {tokens[0]!r}")

    def _verb_go(self, tokens: list[str], variables: dict[str, str]) -> None:
        if len(tokens) != 2:
            raise KardSyntaxError('usage: go "card name"')
        self.stack.go(_interpolate(tokens[1], variables))

    def _verb_show(self, tokens: list[str], variables: dict[str, str]) -> None:
        # show card "name"
        if len(tokens) != 3 or tokens[1].lower() != "card":
            raise KardSyntaxError('usage: show card "card name"')
        self.stack.go(_interpolate(tokens[2], variables))

    def _verb_set(self, tokens: list[str], variables: dict[str, str]) -> None:
        # set field "name" to "value"
        if (
            len(tokens) != 5
            or tokens[1].lower() != "field"
            or tokens[3].lower() != "to"
        ):
            raise KardSyntaxError('usage: set field "name" to "value"')
        self.stack.current.set_field(
            _interpolate(tokens[2], variables),
            _interpolate(tokens[4], variables),
        )

    def _verb_ask(self, tokens: list[str], variables: dict[str, str]) -> None:
        # ask "prompt" into var
        if len(tokens) != 4 or tokens[2].lower() != "into":
            raise KardSyntaxError('usage: ask "prompt" into variable')
        answer = self.ask(_interpolate(tokens[1], variables))
        variables[tokens[3]] = answer

    def _verb_say(self, tokens: list[str], variables: dict[str, str]) -> None:
        if len(tokens) != 2:
            raise KardSyntaxError('usage: say "text"')
        self.say(_interpolate(tokens[1], variables))


# ---------------------------------------------------------------------------
# A runnable little stack, straight out of the revival recipe
# ---------------------------------------------------------------------------


def demo_plant_stack() -> tuple[Stack, KardEngine, list[str]]:
    """Build the houseplant stack: 3 cards, scripted buttons, no mode switch.

    Returns (stack, engine, spoken_lines) so callers can watch it run.
    """
    said: list[str] = []
    stack = Stack("houseplants")

    home = stack.add_card("home")
    home.set_field("title", "The Greenhouse")
    home.set_field("plants", "3")
    home.add_button(
        "water fern",
        'go "fern"\nset field "last watered" to "today"\nsay "Fern watered. $title stays put."',
    )
    home.add_button(
        "tour",
        'show card "fern"\nshow card "cactus"\nshow card "home"\nsay "Tour complete."',
    )

    fern = stack.add_card("fern")
    fern.set_field("title", "Boston fern")
    fern.set_field("last watered", "3 days ago")
    fern.add_button(
        "rename",
        'ask "New name for the fern?" into name\nset field "title" to "$name"\nsay "Renamed to $name."',
    )

    cactus = stack.add_card("cactus")
    cactus.set_field("title", "Barrel cactus")
    cactus.set_field("last watered", "2 weeks ago")
    cactus.add_button(
        "neglect",
        'set field "last watered" to "still never"\nsay "The cactus approves of your neglect."',
    )

    answers = iter(["Maidenhair"])

    def fake_ask(prompt: str) -> str:
        said.append(f"? {prompt}")
        return next(answers)

    engine = KardEngine(stack, ask=fake_ask, say=said.append)
    return stack, engine, said


__all__ = [
    "CardstackError",
    "UnknownCard",
    "UnknownField",
    "KardSyntaxError",
    "Button",
    "Card",
    "Stack",
    "KardEngine",
    "demo_plant_stack",
]
