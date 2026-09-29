"""Contained artifact writer. The emulator's ONLY file I/O path.

Every byte an exercise synthesizes lands inside one sandbox directory.
Absolute paths, ``..`` escapes, and drive specs are rejected before any
write. This is the mechanical teeth of the non-destructive invariant:
even a malicious scenario description cannot make the runner touch
anything outside the sandbox.
"""

from __future__ import annotations

from pathlib import Path


class SandboxEscape(Exception):
    """Raised when a write target escapes the sandbox root."""


class Sandbox:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._artifacts: list[Path] = []

    @property
    def root(self) -> Path:
        return self._root

    @property
    def artifacts(self) -> tuple[Path, ...]:
        return tuple(self._artifacts)

    def write(self, relpath: str, content: str) -> Path:
        """Write text to a path relative to the sandbox root.

        Raises SandboxEscape for absolute paths, parent escapes, and
        anything resolving outside the root. Creates parent dirs.
        """
        candidate = Path(relpath)
        if candidate.is_absolute():
            raise SandboxEscape(f"absolute path rejected: {relpath!r}")
        # Resolve against the root WITHOUT touching the filesystem for the
        # leaf (parents are created after the containment check).
        resolved = (self._root / candidate).resolve()
        if resolved != self._root and self._root not in resolved.parents:
            raise SandboxEscape(f"escape rejected: {relpath!r}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        self._artifacts.append(resolved)
        return resolved
