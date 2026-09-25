"""Buffer engine: open / edit / save with bounded op-based undo/redo.

Line-oriented, deterministic, offline. The daemon owns buffers; the UI
only renders them. Large files (> LARGE_FILE_LINES) still edit fine —
only highlighting is windowed (see highlight.py), never the buffer.
"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass

MAX_UNDO = 200
LARGE_FILE_LINES = 20_000
MAX_OPEN_BYTES = 50 * 1024 * 1024


class BufferError(Exception):
    """Raised for out-of-range edits, undecodable files, oversized files."""


@dataclass(frozen=True)
class Position:
    line: int
    col: int


@dataclass(frozen=True)
class _Op:
    """One undoable edit. kind: insert | delete | replace(set_text)."""

    kind: str
    start: Position
    end: Position
    text: str  # text inserted by the op
    removed: str  # text removed by the op


def _insert_end(start: Position, text: str) -> Position:
    """Where the cursor lands after inserting text at start."""
    if "\n" not in text:
        return Position(start.line, start.col + len(text))
    tail = text.split("\n")[-1]
    return Position(start.line + text.count("\n"), len(tail))


class Buffer:
    """A single editable file buffer."""

    def __init__(
        self,
        text: str = "",
        path: str | None = None,
        encoding: str = "utf-8",
        newline: str = "\n",
    ) -> None:
        self.path = path
        self.encoding = encoding
        self.newline = newline
        self._lines = text.split("\n")
        self._dirty = False
        self._undo: deque[_Op] = deque(maxlen=MAX_UNDO)
        self._redo: deque[_Op] = deque(maxlen=MAX_UNDO)

    # ------------------------------------------------------------------ open
    @classmethod
    def open(cls, path: str, encoding: str = "utf-8") -> "Buffer":
        """Open a file. Detects CRLF vs LF; refuses binary/oversize files."""
        size = os.path.getsize(path)
        if size > MAX_OPEN_BYTES:
            raise BufferError(f"file too large to open: {path} ({size} bytes)")
        with open(path, "rb") as fh:
            raw = fh.read()
        if b"\x00" in raw[:8192]:
            raise BufferError(f"refusing to open binary file: {path}")
        newline = "\r\n" if b"\r\n" in raw else "\n"
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError as exc:
            raise BufferError(f"cannot decode {path} as {encoding}") from exc
        buf = cls(
            text.replace("\r\n", "\n"), path=path, encoding=encoding, newline=newline
        )
        buf._dirty = False
        return buf

    # ------------------------------------------------------------------ read
    @property
    def line_count(self) -> int:
        return len(self._lines)

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def is_large(self) -> bool:
        """Large-file mode: highlighting windows, editing stays full."""
        return len(self._lines) > LARGE_FILE_LINES

    def line(self, n: int) -> str:
        self._check_line(n)
        return self._lines[n]

    def lines(self, start: int = 0, end: int | None = None) -> list[str]:
        """Windowed read — the large-file path for renderers."""
        end = len(self._lines) if end is None else end
        if start < 0 or end > len(self._lines) or start > end:
            raise BufferError(f"bad line window [{start}:{end}]")
        return self._lines[start:end]

    def get_text(self) -> str:
        return "\n".join(self._lines)

    def _check_line(self, n: int) -> None:
        if not 0 <= n < len(self._lines):
            raise BufferError(f"line {n} out of range (0..{len(self._lines) - 1})")

    def _check_pos(self, pos: Position) -> None:
        self._check_line(pos.line)
        if not 0 <= pos.col <= len(self._lines[pos.line]):
            raise BufferError(f"col {pos.col} out of range on line {pos.line}")

    # ------------------------------------------------------------------ edit
    def insert(self, line: int, col: int, text: str) -> Position:
        """Insert text at (line, col). Returns the new cursor position."""
        start = Position(line, col)
        self._check_pos(start)
        if not text:
            return start
        end = _insert_end(start, text)
        self._apply_insert(start, text)
        self._push(_Op("insert", start, end, text, ""))
        return end

    def delete(
        self, start_line: int, start_col: int, end_line: int, end_col: int
    ) -> str:
        """Delete [start, end). Returns the removed text."""
        start = Position(start_line, start_col)
        end = Position(end_line, end_col)
        self._check_pos(start)
        self._check_pos(end)
        if (end.line, end.col) < (start.line, start.col):
            raise BufferError("delete end before start")
        removed = self._apply_delete(start, end)
        self._push(_Op("delete", start, end, "", removed))
        return removed

    def replace_range(
        self,
        start_line: int,
        start_col: int,
        end_line: int,
        end_col: int,
        text: str,
    ) -> None:
        """Delete [start, end) and insert text — one undo step."""
        start = Position(start_line, start_col)
        end = Position(end_line, end_col)
        self._check_pos(start)
        self._check_pos(end)
        removed = self._apply_delete(start, end)
        new_end = _insert_end(start, text)
        self._apply_insert(start, text)
        self._push(_Op("replace", start, new_end, text, removed))

    def set_text(self, text: str) -> None:
        """Replace the whole buffer — one undo step (replace-all path)."""
        old = self.get_text()
        if old == text:
            return
        self._lines = text.split("\n")
        self._push(
            _Op(
                "replace",
                Position(0, 0),
                _insert_end(Position(0, 0), text),
                text,
                old,
            )
        )
        self._dirty = True

    # ------------------------------------------------------------- undo/redo
    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> bool:
        op = self._undo.pop() if self._undo else None
        if op is None:
            return False
        self._apply_inverse(op)
        self._redo.append(op)
        self._dirty = True
        return True

    def redo(self) -> bool:
        op = self._redo.pop() if self._redo else None
        if op is None:
            return False
        self._apply_forward(op)
        self._undo.append(op)
        self._dirty = True
        return True

    # ------------------------------------------------------------------ save
    def save(self, path: str | None = None) -> str:
        """Atomic save (temp file + os.replace). Never half-writes."""
        target = path or self.path
        if target is None:
            raise BufferError("no path: save() needs an explicit path")
        directory = os.path.dirname(os.path.abspath(target))
        os.makedirs(directory, exist_ok=True)
        tmp = target + ".hicomb-tmp"
        with open(tmp, "w", encoding=self.encoding, newline="") as fh:
            fh.write(self.newline.join(self._lines))
        os.replace(tmp, target)
        self.path = target
        self._dirty = False
        return target

    # -------------------------------------------------------------- internals
    def _push(self, op: _Op) -> None:
        self._undo.append(op)
        self._redo.clear()
        self._dirty = True

    def _apply_insert(self, start: Position, text: str) -> None:
        cur = self._lines[start.line]
        before, after = cur[: start.col], cur[start.col :]
        parts = text.split("\n")
        if len(parts) == 1:
            self._lines[start.line] = before + text + after
        else:
            self._lines[start.line] = before + parts[0]
            tail = [parts[-1] + after]
            self._lines[start.line + 1 : start.line + 1] = parts[1:-1] + tail

    def _apply_delete(self, start: Position, end: Position) -> str:
        if start.line == end.line:
            cur = self._lines[start.line]
            removed = cur[start.col : end.col]
            self._lines[start.line] = cur[: start.col] + cur[end.col :]
            return removed
        parts = [self._lines[start.line][start.col :]]
        parts.extend(self._lines[start.line + 1 : end.line])
        parts.append(self._lines[end.line][: end.col])
        removed = "\n".join(parts)
        self._lines[start.line] = (
            self._lines[start.line][: start.col] + self._lines[end.line][end.col :]
        )
        del self._lines[start.line + 1 : end.line + 1]
        return removed

    def _apply_forward(self, op: _Op) -> None:
        if op.kind == "insert":
            self._apply_insert(op.start, op.text)
        elif op.kind == "delete":
            self._apply_delete(op.start, op.end)
        else:  # replace
            self._apply_delete(op.start, _insert_end(op.start, op.removed))
            self._apply_insert(op.start, op.text)

    def _apply_inverse(self, op: _Op) -> None:
        if op.kind == "insert":
            self._apply_delete(op.start, op.end)
        elif op.kind == "delete":
            self._apply_insert(op.start, op.removed)
        else:  # replace
            self._apply_delete(op.start, op.end)
            self._apply_insert(op.start, op.removed)
