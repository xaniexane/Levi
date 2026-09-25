"""LEVI's sandbox cell — untrusted skill code runs here, and only here.

Studied from: systems-internals survey (Inferno Dis VM, type-safe
bytecode half). LEVI already has the 9P-namespace half as
``revival.inferno``; this module is the *other* half and does not
duplicate it.

The mechanism, functionally: a tiny original stack-based bytecode VM.
Programs are assembled from a plain-text assembly (one instruction per
line, ``LABEL:`` markers, ``#`` comments). The instruction set is
small and closed: PUSH/ADD/SUB/MUL/DIV/LOAD/STORE/JMP/JZ/CALL/RET/
PRINT/HALT. There are no host syscalls — a program can touch the
stack, its own locals, and the output buffer, nothing else. Every run
is bounded: exceed ``max_steps`` and the VM halts the program with a
``RunawayError`` instead of hanging the host. Division by zero,
unknown labels, and stack underflow are hard errors, reported honestly.

Honesty: this is a sandbox for *untrusted arithmetic/logic* skill
snippets, not a general compute platform. The boundary is the
instruction set itself — there is simply no opcode that reaches the
host.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

ORIGIN = "levi-revival/vmcell"


class VMError(Exception):
    """Base failure for the sandbox cell."""


class RunawayError(VMError):
    """Raised when a program exceeds its step bound."""


class AssemblyError(VMError):
    """Raised for malformed assembly text."""


# Opcodes. The closed set — nothing here can reach the host.
_OPS = {
    "PUSH",
    "ADD",
    "SUB",
    "MUL",
    "DIV",
    "LOAD",
    "STORE",
    "JMP",
    "JZ",
    "CALL",
    "RET",
    "PRINT",
    "HALT",
    "DUP",
    "POP",
}


def assemble(source: str) -> List[Tuple[str, object]]:
    """Assemble text assembly into (opcode, operand) instructions."""
    labels: Dict[str, int] = {}
    raw: List[Tuple[str, object, int]] = []  # (op, operand, line)
    for lineno, line in enumerate(source.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        while ":" in line:
            label, _, rest = line.partition(":")
            label = label.strip()
            if not label.replace("_", "").isalnum() or label[0].isdigit():
                raise AssemblyError(f"line {lineno}: bad label {label!r}")
            if label in labels:
                raise AssemblyError(f"line {lineno}: duplicate label {label!r}")
            labels[label] = len(raw)
            line = rest.strip()
            if not line:
                break
        else:
            pass
        if not line:
            continue
        parts = line.split(None, 1)
        op = parts[0].upper()
        if op not in _OPS:
            raise AssemblyError(f"line {lineno}: unknown opcode {op!r}")
        operand: object = None
        if len(parts) > 1:
            operand = parts[1].strip()
            if op == "PUSH":
                try:
                    operand = int(operand)
                except ValueError:
                    raise AssemblyError(
                        f"line {lineno}: PUSH needs an integer"
                    ) from None
        raw.append((op, operand, lineno))

    program: List[Tuple[str, object]] = []
    for op, operand, lineno in raw:
        if op in ("JMP", "JZ", "CALL") and isinstance(operand, str):
            if operand not in labels:
                raise AssemblyError(f"line {lineno}: unknown label {operand!r}")
            operand = labels[operand]
        program.append((op, operand))
    return program


class Cell:
    """One sandboxed execution cell."""

    def __init__(self, max_steps: int = 10_000):
        self.max_steps = max_steps

    def run(self, program: List[Tuple[str, object]]) -> List[int]:
        """Execute a program; returns everything it PRINTed."""
        stack: List[int] = []
        call_stack: List[int] = []
        local_vars: Dict[str, int] = {}
        out: List[int] = []
        pc = 0
        steps = 0

        def pop() -> int:
            if not stack:
                raise VMError("stack underflow")
            return stack.pop()

        while True:
            if steps >= self.max_steps:
                raise RunawayError(f"program exceeded {self.max_steps} steps — halted")
            steps += 1
            if not (0 <= pc < len(program)):
                raise VMError(f"pc out of bounds: {pc}")
            op, operand = program[pc]
            pc += 1

            if op == "PUSH":
                stack.append(int(operand))  # type: ignore[arg-type]
            elif op == "ADD":
                b, a = pop(), pop()
                stack.append(a + b)
            elif op == "SUB":
                b, a = pop(), pop()
                stack.append(a - b)
            elif op == "MUL":
                b, a = pop(), pop()
                stack.append(a * b)
            elif op == "DIV":
                b, a = pop(), pop()
                if b == 0:
                    raise VMError("division by zero")
                stack.append(a // b)
            elif op == "DUP":
                if not stack:
                    raise VMError("stack underflow")
                stack.append(stack[-1])
            elif op == "POP":
                pop()
            elif op == "LOAD":
                name = str(operand)
                if name not in local_vars:
                    raise VMError(f"unbound variable {name!r}")
                stack.append(local_vars[name])
            elif op == "STORE":
                local_vars[str(operand)] = pop()
            elif op == "JMP":
                pc = int(operand)  # type: ignore[arg-type]
            elif op == "JZ":
                target = int(operand)  # type: ignore[arg-type]
                if pop() == 0:
                    pc = target
            elif op == "CALL":
                call_stack.append(pc)
                pc = int(operand)  # type: ignore[arg-type]
            elif op == "RET":
                if not call_stack:
                    raise VMError("RET with empty call stack")
                pc = call_stack.pop()
            elif op == "PRINT":
                out.append(pop())
            elif op == "HALT":
                return out
            else:  # pragma: no cover - assembler guards this
                raise VMError(f"bad opcode {op!r}")
