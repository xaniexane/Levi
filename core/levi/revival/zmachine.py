"""A tiny VM for text adventures: story files decoupled from hardware.

Studied from: dead-game-genres-2026-09-16/report.md [Entries — The Z-Machine]
(Tiny VM opcodes for text adventures; story files (Z-code) decoupled from
hardware; write-once-run-anywhere portability as the product).

This is an original, from-scratch implementation for LEVI — a small
stack-based virtual machine in the *spirit* of the classic text-adventure
VMs, written fresh rather than cloned. A "story file" is a program: a list
of instructions plus a string table, assembled by ``StoryBuilder`` into a
portable ``StoryFile`` (JSON-serializable dict). ``Zvm`` executes it. The
story never touches hardware directly — all I/O goes through two abstract
ports the host provides: ``output`` (a callable receiving text) and
``input_fn`` (a callable returning one line). Write once, run anywhere the
host implements those two ports.

Instruction set (each instruction is a ``(op, arg)`` tuple):

- Stack: ``PUSH n``, ``POP``, ``DUP``, ``ADD``, ``SUB``, ``MUL``, ``DIV``,
  ``MOD``, ``NEG`` (all integer arithmetic; DIV/MOD by zero traps).
- Memory: ``LOAD name``, ``STORE name`` (named variables, ints or strings).
- Strings: ``PRINT`` (pop + emit), ``SAY n`` (emit string-table entry n),
  ``INPUT`` (read a line via the input port, push it).
- Control: ``JMP n``, ``JZ n``, ``JNZ n`` (jump to instruction index n;
  JZ/JNZ pop the test value), ``HALT``.
- Calls: ``CALL n`` (call instruction index n, pushing a return frame),
  ``RET`` (pop the top of stack into the caller's frame, resume after call).

``StoryBuilder`` gives the author labels and a string table so stories are
written with names, not raw indices.

Public surface:
- ``Zvm(story, output=print, input_fn=input)``: ``run()`` -> final variable
  map; ``steps`` counts executed instructions.
- ``StoryBuilder``: ``say(text)``, ``emit(op, arg=None)``, ``label(name)``,
  ``build()`` -> ``StoryFile``.
- ``StoryFile``: ``to_dict()`` / ``from_dict()`` for portability.
- ``ZvmError`` for traps (bad jumps, stack underflow, div-by-zero, ...).

Honest limits: this is a teaching-scale VM — integer + string values only,
no objects, no save/restore of full machine state. Step counting bounds
runaway stories via ``max_steps``. Input/output are host-provided; the VM
itself never touches stdin/stdout unless the host wires it that way.

stdlib-only. No network. Deterministic given the same input lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple


ORIGIN = "levi-revival/zmachine"

Instruction = Tuple[str, Any]


class ZvmError(RuntimeError):
    """A VM trap: bad jump, stack underflow, div-by-zero, unknown opcode..."""


@dataclass
class StoryFile:
    """A portable story: instructions + string table, JSON-serializable."""

    instructions: List[Instruction]
    strings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": "levi-story/1",
            "instructions": [[op, arg] for op, arg in self.instructions],
            "strings": list(self.strings),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryFile":
        if data.get("format") != "levi-story/1":
            raise ZvmError(f"unsupported story format: {data.get('format')!r}")
        instructions = [(op, arg) for op, arg in data["instructions"]]
        return cls(instructions=instructions, strings=list(data["strings"]))


class StoryBuilder:
    """Assemble a story with labels and a string table."""

    def __init__(self) -> None:
        self._instructions: List[Instruction] = []
        self._strings: List[str] = []
        self._labels: Dict[str, int] = {}

    def say(self, text: str) -> "StoryBuilder":
        """Emit string-table entry for ``text`` at this point."""
        idx = len(self._strings)
        self._strings.append(text)
        self._instructions.append(("SAY", idx))
        return self

    def emit(self, op: str, arg: Any = None) -> "StoryBuilder":
        """Emit a raw instruction; ``arg`` may be a label name for jumps/calls."""
        self._instructions.append((op.upper(), arg))
        return self

    def label(self, name: str) -> "StoryBuilder":
        """Mark the next instruction's address with ``name``."""
        if name in self._labels:
            raise ZvmError(f"duplicate label {name!r}")
        self._labels[name] = len(self._instructions)
        return self

    def build(self) -> StoryFile:
        """Resolve labels and produce the portable StoryFile."""
        resolved: List[Instruction] = []
        for op, arg in self._instructions:
            if op in ("JMP", "JZ", "JNZ", "CALL") and isinstance(arg, str):
                if arg not in self._labels:
                    raise ZvmError(f"undefined label {arg!r}")
                arg = self._labels[arg]
            resolved.append((op, arg))
        return StoryFile(instructions=resolved, strings=list(self._strings))


@dataclass
class Zvm:
    """The tiny text-adventure VM. I/O flows through host-provided ports."""

    story: StoryFile
    output: Callable[[str], None] = print
    input_fn: Callable[[], str] = input
    max_steps: int = 100_000

    _stack: List[Any] = field(default_factory=list, init=False)
    _vars: Dict[str, Any] = field(default_factory=dict, init=False)
    _call_stack: List[int] = field(default_factory=list, init=False)
    steps: int = field(default=0, init=False)

    def run(self) -> Dict[str, Any]:
        """Execute until HALT; return the final variable map."""
        code = self.story.instructions
        pc = 0
        while True:
            if not 0 <= pc < len(code):
                raise ZvmError(f"pc {pc} out of bounds")
            if self.steps >= self.max_steps:
                raise ZvmError(f"step budget exhausted at pc {pc}")
            op, arg = code[pc]
            self.steps += 1
            pc = self._execute(op, arg, pc, code)
            if pc == -1:  # HALT
                return dict(self._vars)

    # -- execution -----------------------------------------------------
    def _pop(self) -> Any:
        if not self._stack:
            raise ZvmError("stack underflow")
        return self._stack.pop()

    def _execute(self, op: str, arg: Any, pc: int, code: List[Instruction]) -> int:
        if op == "PUSH":
            self._stack.append(arg)
        elif op == "POP":
            self._pop()
        elif op == "DUP":
            v = self._pop()
            self._stack.extend([v, v])
        elif op in ("ADD", "SUB", "MUL", "DIV", "MOD"):
            b, a = self._pop(), self._pop()
            if not isinstance(a, int) or not isinstance(b, int):
                raise ZvmError(f"{op} needs integers")
            if op == "ADD":
                self._stack.append(a + b)
            elif op == "SUB":
                self._stack.append(a - b)
            elif op == "MUL":
                self._stack.append(a * b)
            elif op == "DIV":
                if b == 0:
                    raise ZvmError("division by zero")
                self._stack.append(a // b)
            else:
                if b == 0:
                    raise ZvmError("modulo by zero")
                self._stack.append(a % b)
        elif op == "NEG":
            v = self._pop()
            if not isinstance(v, int):
                raise ZvmError("NEG needs an integer")
            self._stack.append(-v)
        elif op == "LOAD":
            self._stack.append(self._vars.get(arg, 0))
        elif op == "STORE":
            self._vars[arg] = self._pop()
        elif op == "PRINT":
            self.output(str(self._pop()))
        elif op == "SAY":
            try:
                self.output(self.story.strings[arg])
            except (IndexError, TypeError) as exc:
                raise ZvmError(f"bad string index {arg!r}") from exc
        elif op == "INPUT":
            self._stack.append(self.input_fn())
        elif op == "JMP":
            return self._checked_jump(arg, len(code))
        elif op == "JZ":
            return self._checked_jump(arg, len(code)) if self._pop() == 0 else pc + 1
        elif op == "JNZ":
            return self._checked_jump(arg, len(code)) if self._pop() != 0 else pc + 1
        elif op == "CALL":
            target = self._checked_jump(arg, len(code))
            self._call_stack.append(pc + 1)
            return target
        elif op == "RET":
            if not self._call_stack:
                raise ZvmError("RET with no caller")
            return self._call_stack.pop()
        elif op == "HALT":
            return -1
        else:
            raise ZvmError(f"unknown opcode {op!r}")
        return pc + 1

    @staticmethod
    def _checked_jump(target: Any, code_len: int) -> int:
        if not isinstance(target, int) or not 0 <= target < code_len:
            raise ZvmError(f"bad jump target {target!r}")
        return target
