"""Grounded blocks microworld — words that bottom out in real operations.

Studied from: revival-50-more-20260916-0009/report-part1.md (sec 22);
ai-si-software-internals-20260916-0005/report.md (sec 1.1) — MERGED.

The mechanism under study: a tiny closed world (a table, colored blocks,
stacking) plus a small command grammar whose every word bottoms out in
executable world operations. No word floats: "move", "pick", "put",
"stack", "list", "red", "onto" each map through a lexicon to concrete
state transitions on the world. Grounding is total and checkable — the
system answers "what did you do" from an explicit, inspectable history
of its own acts, not from a story it reconstructs.

This is an original, from-scratch implementation for LEVI. Blocks are
named (A..H) and colored; the world tracks support relations, clearness,
and what the hand holds. The grammar is LEVI's own (imperative commands
like "move red onto blue", "pick up the green", "put A on the table",
"stack B on C", "list", "clear hand", "what did you do", "describe").
Parsing is deterministic; unknowns raise honest errors naming the word
the system failed to ground.

Public surface:
- ``Microworld``: the world; ``reset()``, ``parse(text) -> Command``,
  ``execute(command) -> str``, ``ask(text)`` (command or question),
  ``history()`` / ``explain_last(n)`` (the "what did you do" answer).
- ``parse`` / ``GroundError`` for embedding.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ORIGIN = "levi-revival/microworld"

TABLE = "table"


@dataclass
class Block:
    name: str
    color: str


class GroundError(ValueError):
    """A word in the command could not be grounded in the world."""


@dataclass
class Act:
    """One executed act: a grounded operation with its plain telling."""

    op: str
    args: Tuple[str, ...]
    telling: str


@dataclass
class Command:
    op: str
    args: Tuple[str, ...] = ()
    question: Optional[str] = None


class Microworld:
    """A tiny blocks world with grounded commands and an honest act log."""

    COLORS = ("red", "blue", "green", "yellow")

    def __init__(self) -> None:
        self.blocks: Dict[str, Block] = {}
        self._on: Dict[str, str] = {}  # block -> supporter (block name or TABLE)
        self._holding: Optional[str] = None
        self.acts: List[Act] = []
        self.reset()

    # ------------------------------------------------------------------
    # world setup
    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.blocks = {}
        colors = ["red", "blue", "green", "yellow", "red", "blue", "green", "yellow"]
        for i, name in enumerate("ABCDEFGH"):
            self.blocks[name] = Block(name, colors[i])
        self._on = {name: TABLE for name in self.blocks}
        self._holding = None
        self.acts = []

    # ------------------------------------------------------------------
    # world queries (everything words ground into)
    # ------------------------------------------------------------------
    def support(self, block: str) -> str:
        return self._on[block]

    def top_of(self, block: str) -> Optional[str]:
        for b, sup in self._on.items():
            if sup == block and b != self._holding:
                return b
        return None

    def clear(self, block: str) -> bool:
        return self.top_of(block) is None and self._holding != block

    def clear_table_spot(self) -> bool:
        return True  # the table always has room in this world

    def holding(self) -> Optional[str]:
        return self._holding

    def describe_block(self, name: str) -> str:
        b = self.blocks[name]
        sup = "in hand" if self._holding == name else f"on {self._on[name]}"
        top = self.top_of(name)
        under = f", holding up {top}" if top else ""
        return f"{name} ({b.color}) {sup}{under}"

    # ------------------------------------------------------------------
    # executable world operations — the grounding floor
    # ------------------------------------------------------------------
    def _record(self, op: str, args: Tuple[str, ...], telling: str) -> None:
        self.acts.append(Act(op, args, telling))

    def op_pick(self, name: str) -> str:
        self._need_block(name)
        if self._holding is not None:
            raise GroundError(f"hand already holds {self._holding}; put it down first")
        if not self.clear(name):
            raise GroundError(f"{name} is not clear — something sits on it")
        self._on.pop(name, None)
        self._holding = name
        telling = f"picked up {name} ({self.blocks[name].color})"
        self._record("pick", (name,), telling)
        return telling

    def op_put(self, name: str, target: str) -> str:
        """Put held block ``name`` onto ``target`` (block name or TABLE)."""
        if self._holding != name:
            raise GroundError(f"not holding {name}; cannot put it down")
        if target != TABLE:
            self._need_block(target)
            if not self.clear(target):
                raise GroundError(f"{target} is not clear — cannot stack onto it")
            if target == name:
                raise GroundError("a block cannot rest on itself")
        self._holding = None
        self._on[name] = target
        dest = "the table" if target == TABLE else target
        telling = f"put {name} ({self.blocks[name].color}) on {dest}"
        self._record("put", (name, target), telling)
        return telling

    def op_move(self, name: str, target: str) -> str:
        """Move block ``name`` onto ``target`` (block or table), atomically."""
        self._need_block(name)
        if self._holding == name:
            return self.op_put(name, target)
        previous = self._on.get(name, TABLE)
        self.op_pick(name)
        try:
            return self.op_move(name, target)  # now held; second call puts
        except GroundError:
            # pick succeeded, put failed: restore it exactly where it was
            self._holding = None
            self._on[name] = previous
            self._record(
                "restore",
                (name, previous),
                f"set {name} back on {previous} after a failed move",
            )
            raise

    def op_stack(self, name: str, target: str) -> str:
        if target == TABLE:
            raise GroundError(
                "stack needs a block, not the table — say 'put on the table'"
            )
        telling = self.op_move(name, target)
        return telling

    def _need_block(self, name: str) -> Block:
        try:
            return self.blocks[name]
        except KeyError:
            raise GroundError(f"no block named {name!r} in this world") from None

    # ------------------------------------------------------------------
    # grammar — words bottom out here
    # ------------------------------------------------------------------
    def resolve(self, word: str) -> str:
        """Ground a referring word to a block name or TABLE."""
        w = word.strip().lower()
        if w in ("table", "the table"):
            return TABLE
        for name, b in self.blocks.items():
            if w == name.lower() or w == b.color:
                return name
        # "the red block" style
        m = re.fullmatch(r"(?:the\s+)?([a-z]+)(?:\s+block)?", w)
        if m:
            for name, b in self.blocks.items():
                if m.group(1) in (name.lower(), b.color):
                    return name
        raise GroundError(f"cannot ground {word!r} to anything in this world")

    def parse(self, text: str) -> Command:
        t = text.strip().lower()
        t = re.sub(r"\s+", " ", t)

        if t in (
            "what did you do",
            "what did you do?",
            "what have you done",
            "tell me what you did",
        ):
            return Command(op="what", question="acts")
        if t in (
            "describe",
            "describe the world",
            "what does the world look like",
            "list",
            "list blocks",
            "show blocks",
        ):
            return Command(op="describe")

        m = re.fullmatch(r"move\s+(\S+(?:\s+\S+)?)\s+onto\s+(.+)", t)
        if m:
            return Command("move", (self.resolve(m.group(1)), self.resolve(m.group(2))))
        m = re.fullmatch(r"stack\s+(\S+(?:\s+\S+)?)\s+on\s+(.+)", t)
        if m:
            return Command(
                "stack", (self.resolve(m.group(1)), self.resolve(m.group(2)))
            )
        m = re.fullmatch(r"pick\s+up\s+(.+)", t)
        if m:
            return Command("pick", (self.resolve(m.group(1)),))
        m = re.fullmatch(r"(?:put|place)\s+(\S+(?:\s+\S+)?)\s+(?:on|onto)\s+(.+)", t)
        if m:
            return Command("put", (self.resolve(m.group(1)), self.resolve(m.group(2))))
        m = re.fullmatch(r"clear\s+(?:the\s+)?hand", t)
        if m:
            return Command("clearhand", ())
        if t in ("reset", "start over"):
            return Command("reset", ())
        # unknown: find the offending word honestly
        words = t.split()
        raise GroundError(f"cannot ground command {text!r} (words: {words})")

    # ------------------------------------------------------------------
    # execution + the "what did you do" answer
    # ------------------------------------------------------------------
    def execute(self, cmd: Command) -> str:
        if cmd.op == "what":
            return self.explain_acts()
        if cmd.op == "describe":
            return self.describe()
        if cmd.op == "reset":
            self.reset()
            return "world reset; all blocks back on the table"
        if cmd.op == "clearhand":
            if self._holding is None:
                return "hand already empty"
            name = self._holding
            return self.op_put(name, TABLE)
        if cmd.op == "pick":
            return self.op_pick(cmd.args[0])
        if cmd.op == "put":
            return self.op_put(cmd.args[0], cmd.args[1])
        if cmd.op == "move":
            return self.op_move(cmd.args[0], cmd.args[1])
        if cmd.op == "stack":
            return self.op_stack(cmd.args[0], cmd.args[1])
        raise GroundError(f"unknown op {cmd.op!r}")

    def ask(self, text: str) -> str:
        """One door: commands and the history question alike."""
        return self.execute(self.parse(text))

    def history(self) -> List[Act]:
        return list(self.acts)

    def explain_acts(self, n: Optional[int] = None) -> str:
        acts = self.acts if n is None else self.acts[-n:]
        if not acts:
            return "I have done nothing yet — the world is as you left it."
        lines = [f"{i + 1}. {a.telling}" for i, a in enumerate(acts)]
        return "Here is what I did, act by act:\n" + "\n".join(lines)

    def explain_last(self, n: int = 1) -> str:
        return self.explain_acts(n)

    def describe(self) -> str:
        lines = [self.describe_block(n) for n in sorted(self.blocks)]
        if self._holding:
            lines.append(f"hand holds {self._holding}")
        else:
            lines.append("hand empty")
        return "\n".join(lines)
