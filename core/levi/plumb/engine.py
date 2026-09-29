"""The dispatch engine: match a message against the keeper's rules.

Semantics, adapted from Pike's winnowing:
- Rules are tried in file order; the FIRST rule whose every condition
  holds wins (law 5).
- The rule's FIRST ``match`` pattern winnows the data: among all matches
  of the pattern in the data, the engine picks the longest match that
  touches the click offset (if the message carries one), else the
  leftmost-longest match. Every further ``match`` pattern must match
  that same winnowed span, and its captures merge into the result.
- ``require: file-exists <template>`` renders the template with the
  captures and checks ``os.path.isfile``. A failed predicate fails the
  rule — silently, moving on to the next rule.
- The action template renders with ``$0``..``$9`` (numbered groups of
  the winnowing match) and ``{name}`` (named groups of any pattern).
- No rule matches => ``None``. Deny-closed, always (law 1).

The engine never executes: it returns a :class:`PlumbResult` naming a
port. :class:`PortRegistry` maps port names to callables the keeper
registered; dispatching to an unregistered port raises
:class:`PlumbError` instead of guessing (law 4).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .rules import Rule


class PlumbError(RuntimeError):
    """Dispatch refused: unregistered port, or a bad rule at runtime."""


@dataclass(frozen=True)
class PlumbResult:
    """The decision the engine reached. Data, not execution."""

    rule: str
    port: str
    action: str
    data: str  # the winnowed span the rule fired on
    captures: dict[str, str]  # {"0": ..., "1": ..., "name": ...}

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"{self.rule}: plumb to {self.port}: {self.action}"


def _winnow(pattern: str, data: str, click: int | None) -> re.Match | None:
    """Pick the winning match span for the first pattern.

    With a click offset: the longest match touching the offset (ties go
    to the earliest start). Without: leftmost-longest — the earliest
    start, longest span at that start. This is the honest stdlib
    approximation of Pike's "longest leftmost match touching the
    cursor".
    """
    matches = list(re.finditer(pattern, data))
    if not matches:
        return None
    if click is not None:
        touching = [m for m in matches if m.start() <= click < m.end()]
        if not touching:
            return None
        touching.sort(key=lambda m: (-(m.end() - m.start()), m.start()))
        return touching[0]
    matches.sort(key=lambda m: (m.start(), -(m.end() - m.start())))
    return matches[0]


def _render(template: str, match: re.Match, named: dict[str, str]) -> str:
    """Render ``$N`` and ``{name}`` substitutions."""
    out = template
    groups = (match.group(0),) + match.groups()
    # Longest-first ($9..$0) so "$10" never eats "$1".
    for i in range(min(10, len(groups)) - 1, -1, -1):
        out = out.replace(f"${i}", groups[i] if groups[i] is not None else "")
    for key, value in named.items():
        out = out.replace("{" + key + "}", value)
    return out


def _check_requires(rule: Rule, named: dict[str, str]) -> bool:
    for req in rule.requires:
        kind, _, template = req.partition(" ")
        rendered = template
        for key, value in named.items():
            rendered = rendered.replace("{" + key + "}", value)
        if kind == "file-exists":
            if not os.path.isfile(rendered):
                return False
        else:  # pragma: no cover - parser rejects these; belt and suspenders
            raise PlumbError(f"rule {rule.name!r}: unknown require {kind!r}")
    return True


def plumb(
    message: dict[str, Any],
    rules: list[Rule],
    click: int | None = None,
) -> PlumbResult | None:
    """Dispatch ``message`` against ``rules``.

    ``message`` needs ``"data"`` (str); ``"type"`` is optional and only
    constrains rules that declare one. ``click`` is an optional offset
    into ``data`` (the cursor/selection point).

    Returns the first winning :class:`PlumbResult`, or ``None`` when
    nothing matches.
    """
    data = message.get("data", "")
    mtype = message.get("type")
    if not isinstance(data, str):
        raise PlumbError("message 'data' must be a string")

    for rule in rules:
        if rule.type is not None and rule.type != mtype:
            continue
        first = _winnow(rule.patterns[0], data, click)
        if first is None:
            continue
        span = first.group(0)
        named: dict[str, str] = {
            k: v for k, v in first.groupdict().items() if v is not None
        }
        ok = True
        for pat in rule.patterns[1:]:
            m = re.search(pat, span)
            if m is None or m.group(0) != span:
                ok = False
                break
            for k, v in m.groupdict().items():
                if v is not None and k not in named:
                    named[k] = v
        if not ok:
            continue
        if not _check_requires(rule, named):
            continue
        captures: dict[str, str] = {
            str(i): (g if g is not None else "")
            for i, g in enumerate((first.group(0),) + first.groups())
        }
        captures.update(named)
        action = _render(rule.action, first, named)
        return PlumbResult(
            rule=rule.name, port=rule.port, action=action,
            data=span, captures=captures,
        )
    return None


class PortRegistry:
    """Explicit port table. Empty by default; the keeper registers
    handlers. Dispatching to an unknown port raises instead of guessing."""

    def __init__(self) -> None:
        self._ports: dict[str, Callable[[PlumbResult], Any]] = {}

    def register(self, name: str, handler: Callable[[PlumbResult], Any]) -> None:
        if not name or not callable(handler):
            raise PlumbError("port name and callable handler required")
        self._ports[name] = handler

    def dispatch(self, result: PlumbResult) -> Any:
        try:
            handler = self._ports[result.port]
        except KeyError:
            raise PlumbError(
                f"port {result.port!r} is not registered — refusing to "
                f"dispatch (rule {result.rule!r})"
            ) from None
        return handler(result)

    def ports(self) -> tuple[str, ...]:
        return tuple(self._ports)
