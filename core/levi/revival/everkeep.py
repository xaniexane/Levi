"""everkeep — total persistence through a journaled command stream.

Studied from: revival-50-more-20260916-0009/report-part2.md (Section 33).

The load-bearing idea: *every* mutation is a journaled command, so the
whole state can be rebuilt by replaying the journal — there is no
explicit "save" because persistence is not an event, it is the
substrate. Undo and redo are unlimited because the journal remembers
how to run every command backwards.

LEVI's take: ``EverKeep`` wraps a plain ``dict`` state. Mutations go
through ``Command`` objects (``do``/``undo`` pair plus a JSON-friendly
payload). Each executed command is appended to an append-only JSONL
journal — on disk if you give it a path, in memory if you don't — so a
fresh ``EverKeep`` over the same journal rehydrates to the exact same
state. No save button, no save method: if it happened, it's kept.

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

ORIGIN = "levi-revival/everkeep"


class Command:
    """One journaled mutation: how to do it, undo it, and record it."""

    name: str = "command"

    def do(self, state: Dict[str, Any]) -> None:  # pragma: no cover - override
        raise NotImplementedError

    def undo(self, state: Dict[str, Any]) -> None:  # pragma: no cover - override
        raise NotImplementedError

    def record(self) -> Dict[str, Any]:
        """JSON-friendly payload so the journal can replay this command."""
        return {"name": self.name}

    def inverse_record(self) -> Optional[Dict[str, Any]]:
        """Journal payload that undoes this command by *doing* its inverse.

        Journaling undo/redo as forward records keeps the journal
        append-only and replayable — a restart replays the exact same
        history the live session saw.
        """
        return None  # override where the command is reversible


class SetCommand(Command):
    """Set ``state[key] = value``, remembering the old value for undo."""

    name = "set"

    def __init__(self, key: str, value: Any) -> None:
        self.key = key
        self.value = value
        self._had: bool = False
        self._old: Any = None

    def do(self, state: Dict[str, Any]) -> None:
        self._had = self.key in state
        self._old = state.get(self.key)
        state[self.key] = self.value

    def undo(self, state: Dict[str, Any]) -> None:
        if self._had:
            state[self.key] = self._old
        else:
            state.pop(self.key, None)

    def record(self) -> Dict[str, Any]:
        return {"name": self.name, "key": self.key, "value": self.value}

    def inverse_record(self) -> Optional[Dict[str, Any]]:
        if self._had:
            return {"name": "set", "key": self.key, "value": self._old}
        return {"name": "delete", "key": self.key}

    @classmethod
    def from_record(cls, payload: Dict[str, Any]) -> "SetCommand":
        return cls(payload["key"], payload["value"])


class DeleteCommand(Command):
    """Delete ``state[key]``, remembering the old value for undo."""

    name = "delete"

    def __init__(self, key: str) -> None:
        self.key = key
        self._had: bool = False
        self._old: Any = None

    def do(self, state: Dict[str, Any]) -> None:
        self._had = self.key in state
        self._old = state.pop(self.key, None)

    def undo(self, state: Dict[str, Any]) -> None:
        if self._had:
            state[self.key] = self._old

    def record(self) -> Dict[str, Any]:
        return {"name": self.name, "key": self.key}

    def inverse_record(self) -> Optional[Dict[str, Any]]:
        if self._had:
            return {"name": "set", "key": self.key, "value": self._old}
        return None  # deleting a missing key changes nothing

    @classmethod
    def from_record(cls, payload: Dict[str, Any]) -> "DeleteCommand":
        return cls(payload["key"])


_COMMAND_TYPES: Dict[str, Any] = {
    SetCommand.name: SetCommand,
    DeleteCommand.name: DeleteCommand,
}


class EverKeep:
    """A dict that can never lose work: journaled, undoable, rehydratable."""

    def __init__(self, journal_path: Optional[str] = None) -> None:
        self.state: Dict[str, Any] = {}
        self.journal_path = journal_path
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._mem_journal: List[Dict[str, Any]] = []
        if journal_path and os.path.exists(journal_path):
            self._rehydrate()

    # -- journal -------------------------------------------------------
    def _append_journal(self, payload: Dict[str, Any]) -> None:
        self._mem_journal.append(payload)
        if self.journal_path:
            with open(self.journal_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload) + "\n")

    def _rehydrate(self) -> None:
        """Total persistence: rebuild state by replaying the journal."""
        self.state = {}
        self._undo_stack = []
        self._redo_stack = []
        with open(self.journal_path, encoding="utf-8") as fh:  # type: ignore[arg-type]
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                cmd = self._replay(payload)
                self._mem_journal.append(payload)
                self._undo_stack.append(cmd)

    def _replay(self, payload: Dict[str, Any]) -> Command:
        cmd_type = _COMMAND_TYPES.get(payload.get("name", ""))
        if cmd_type is None:
            raise ValueError(f"unknown journaled command: {payload.get('name')!r}")
        cmd = cmd_type.from_record(payload)
        cmd.do(self.state)
        return cmd

    # -- mutation ------------------------------------------------------
    def execute(self, cmd: Command) -> None:
        """Run a command, journal it, clear the redo stack."""
        cmd.do(self.state)
        self._append_journal(cmd.record())
        self._undo_stack.append(cmd)
        self._redo_stack.clear()

    def set(self, key: str, value: Any) -> None:
        self.execute(SetCommand(key, value))

    def delete(self, key: str) -> None:
        self.execute(DeleteCommand(key))

    # -- undo / redo ---------------------------------------------------
    # Undo and redo are journaled as forward records (the inverse of the
    # command, or the command again), so replay always matches live state.
    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo(self.state)
        inverse = cmd.inverse_record()
        if inverse is not None:
            self._append_journal(inverse)
        self._redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.do(self.state)
        self._append_journal(cmd.record())
        self._undo_stack.append(cmd)
        return True

    def depth(self) -> int:
        """How many undoable commands are on the stack."""
        return len(self._undo_stack)
