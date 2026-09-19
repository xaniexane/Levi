"""Text that is also the interface: commands embedded in ordinary prose.

Studied from: interfaces-hunt-20260915/report.md [2. The Oberon System]

The studied shape: text input and command input are one thing.
Commands of the form ``M.P`` (module dot procedure) may occur in
*any* text; middle-clicking one executes it, with selection or
arguments where relevant. Tools are not separate programs — they are
just texts that contain commands.

LEVI-native re-expression: an actionable-text engine. A **ToolRegistry**
names tools (``module.procedure``); any document text can embed
``Module.Procedure`` tokens, optionally with ``(args)``, and the
**activator** finds the token under (or nearest to) a cursor position
and dispatches it against the registry. Selection context can be
passed as an implicit argument.

Operations:

* ``ToolRegistry.register("Module.Procedure", fn)`` — name a tool;
  ``fn`` receives ``(selection, *args)``
* ``scan(text)`` — list every actionable token with its span
* ``activate(text, pos, selection="")`` — run the token at/nearest
  ``pos``; returns the tool's result
* ``run(name, selection="", *args)`` — dispatch by name directly

Honest limits: only tokens matching the ``Module.Procedure`` shape
that are *registered* fire — unknown tokens are inert text, and
activation returns ``None`` for them. Tools are plain Python
callables trusted by whoever registers them; this module provides
no sandboxing of its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

ORIGIN = "levi-revival/actionable-text"

# Module.Procedure optionally followed by (arg, arg, ...).
_TOKEN = re.compile(
    r"(?P<module>[A-Za-z_][\w]*)\.(?P<proc>[A-Za-z_][\w]*)"
    r"(?:\((?P<args>[^()]*)\))?"
)

# Split args on commas, honoring single/double quotes.
_ARG_SPLIT = re.compile(r"""(?:[^,'"]|'[^']*'|"[^"]*")+""")


@dataclass
class Command:
    module: str
    proc: str
    args: Tuple[str, ...]
    span: Tuple[int, int]

    @property
    def name(self) -> str:
        return f"{self.module}.{self.proc}"

    def __str__(self) -> str:  # noqa: D105
        a = f"({', '.join(self.args)})" if self.args else ""
        return f"{self.name}{a}"


def _parse_args(raw: Optional[str]) -> Tuple[str, ...]:
    if raw is None or not raw.strip():
        return ()
    out: List[str] = []
    for piece in _ARG_SPLIT.findall(raw):
        piece = piece.strip()
        if len(piece) >= 2 and piece[0] == piece[-1] and piece[0] in ("'", '"'):
            piece = piece[1:-1]
        out.append(piece)
    return tuple(out)


def scan(text: str) -> List[Command]:
    """Find every actionable ``Module.Procedure`` token in ``text``."""
    cmds: List[Command] = []
    for m in _TOKEN.finditer(text):
        cmds.append(
            Command(
                module=m.group("module"),
                proc=m.group("proc"),
                args=_parse_args(m.group("args")),
                span=(m.start(), m.end()),
            )
        )
    return cmds


class ToolRegistry:
    """Named tools a text's commands can activate."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        if "." not in name:
            raise ValueError("tool name must look like 'Module.Procedure'")
        self._tools[name] = fn

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> List[str]:
        return sorted(self._tools)

    def run(self, name: str, selection: str = "", *args: str) -> Any:
        fn = self._tools.get(name)
        if fn is None:
            return None
        return fn(selection, *args)


def token_at(cmds: List[Command], pos: int) -> Optional[Command]:
    """The command whose span contains ``pos`` (or the nearest one,
    ties broken by earliest start)."""
    inside = [c for c in cmds if c.span[0] <= pos <= c.span[1]]
    if inside:
        return min(inside, key=lambda c: c.span[0])
    if not cmds:
        return None
    return min(cmds, key=lambda c: min(abs(c.span[0] - pos), abs(c.span[1] - pos)))


def activate(text: str, pos: int, registry: ToolRegistry, selection: str = "") -> Any:
    """Middle-click semantics: run the command at/nearest ``pos``.

    Returns the tool's result, or ``None`` when there is no token at
    all or the token names an unregistered tool.
    """
    cmds = scan(text)
    cmd = token_at(cmds, pos)
    if cmd is None:
        return None
    return registry.run(cmd.name, selection, *cmd.args)
