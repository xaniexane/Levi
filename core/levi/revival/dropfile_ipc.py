"""dropfile_ipc — file-based IPC as a capability contract.

Studied from: dead-networks-20260916/report.md (BBS door "drop files"
protocol).

The load-bearing idea: when the host hands control to an external
program, it first writes a small, fully documented text file
describing the live session — who is connected, on what kind of
terminal, how much time remains. ANY program, in ANY language, can
read that file and take over the terminal coherently. The file IS the
contract; no shared memory, no sockets, no version coupling.

LEVI's take: ``DropSession`` is a plain dataclass; ``write_dropfile``
serializes it to a strict line-oriented format and ``read_dropfile``
parses it back, validating every field. Round-trip safe and
self-describing. This is an original, from-scratch implementation
for LEVI.

Honest limits: the format carries session metadata only — never
secrets (passwords are explicitly refused at write time). Timestamps
are Unix epoch ints to avoid locale issues.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

ORIGIN = "levi-revival/dropfile-ipc"

FORMAT_ID = "LEVIDROP"  # first line of every drop file
FORMAT_VERSION = 1

_FIELDS = (
    "user_name",
    "user_handle",
    "terminal_kind",
    "rows",
    "cols",
    "time_limit_s",
    "time_used_s",
    "started_epoch",
    "node",
    "capabilities",
)


@dataclass(frozen=True)
class DropSession:
    """Session facts a chain program needs to take over coherently."""

    user_name: str
    user_handle: str
    terminal_kind: str = "ansi"  # "ansi" | "dumb" | "raw"
    rows: int = 24
    cols: int = 80
    time_limit_s: int = 1800
    time_used_s: int = 0
    started_epoch: int = 0
    node: int = 1
    capabilities: str = ""  # comma-separated capability tokens

    @property
    def time_left_s(self) -> int:
        return max(0, self.time_limit_s - self.time_used_s)


def _check(session: DropSession) -> None:
    if "\n" in session.user_name or "\n" in session.user_handle:
        raise ValueError("name/handle must be single-line")
    lowered = (session.user_name + session.user_handle).lower()
    if "password" in lowered:
        raise ValueError("drop files must never carry secrets")
    if session.terminal_kind not in ("ansi", "dumb", "raw"):
        raise ValueError(f"unknown terminal_kind {session.terminal_kind!r}")
    if session.rows <= 0 or session.cols <= 0:
        raise ValueError("rows/cols must be positive")
    if session.time_limit_s < 0 or session.time_used_s < 0:
        raise ValueError("time fields must be non-negative")


def write_dropfile(session: DropSession, path: str | Path) -> Path:
    """Serialize a session to a drop file; returns the path written."""
    _check(session)
    values = [
        session.user_name,
        session.user_handle,
        session.terminal_kind,
        str(session.rows),
        str(session.cols),
        str(session.time_limit_s),
        str(session.time_used_s),
        str(session.started_epoch),
        str(session.node),
        session.capabilities,
    ]
    lines = [FORMAT_ID, f"version={FORMAT_VERSION}"]
    lines.extend(f"{name}={value}" for name, value in zip(_FIELDS, values, strict=True))
    target = Path(path)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def read_dropfile(path: str | Path) -> DropSession:
    """Parse and validate a drop file back into a DropSession."""
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != FORMAT_ID:
        raise ValueError("not a LEVI drop file (bad format id)")
    if lines[1].strip() != f"version={FORMAT_VERSION}":
        raise ValueError("unsupported drop-file version")
    parsed: dict = {}
    for line in lines[2:]:
        if "=" not in line:
            raise ValueError(f"malformed drop-file line: {line!r}")
        key, _, value = line.partition("=")
        parsed[key.strip()] = value
    missing = [f for f in _FIELDS if f not in parsed]
    if missing:
        raise ValueError(f"drop file missing fields: {missing}")
    try:
        session = DropSession(
            user_name=parsed["user_name"],
            user_handle=parsed["user_handle"],
            terminal_kind=parsed["terminal_kind"],
            rows=int(parsed["rows"]),
            cols=int(parsed["cols"]),
            time_limit_s=int(parsed["time_limit_s"]),
            time_used_s=int(parsed["time_used_s"]),
            started_epoch=int(parsed["started_epoch"]),
            node=int(parsed["node"]),
            capabilities=parsed["capabilities"],
        )
    except ValueError as exc:
        raise ValueError(f"drop file has invalid numeric field: {exc}") from exc
    _check(session)
    return session


def summarize(session: DropSession) -> List[str]:
    """One-line-per-fact human summary of the session."""
    return [
        f"user: {session.user_name} ({session.user_handle}) on node {session.node}",
        f"terminal: {session.terminal_kind} {session.cols}x{session.rows}",
        f"time left: {session.time_left_s}s of {session.time_limit_s}s",
        f"capabilities: {session.capabilities or '(none)'}",
    ]


def demo(tmp_path: Optional[Path] = None) -> dict:
    """Write a drop file, read it back, and summarize it."""
    from tempfile import TemporaryDirectory

    session = DropSession(
        user_name="chauncey",
        user_handle="levi",
        terminal_kind="ansi",
        time_limit_s=3600,
        time_used_s=120,
        capabilities="doors,chat",
    )
    with TemporaryDirectory() as td:
        path = Path(tmp_path or td) / "session.drop"
        write_dropfile(session, path)
        back = read_dropfile(path)
    return {
        "round_trip_equal": back == session,
        "summary": summarize(back),
    }
