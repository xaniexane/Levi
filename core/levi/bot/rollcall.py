"""LEVI bot rollcall — who answers, and who went silent.

A roll-call bot for LEVI's own population: hand it a roster of named
``probes`` (name → zero-argument callable returning a truthy/falsy answer)
and it pings each one, catching exceptions, and reports the result as a
briefing card. States:

- ``UP``      — the probe answered truthy
- ``DOWN``    — the probe answered falsy
- ``SILENT``  — the probe raised (name + error class recorded, message kept
  short; never leaks tracebacks)

Deny-closed: malformed rosters (empty names, duplicate names, non-callable
probes) are refused with a named error, never coerced. Same roster, same
probes → same card, every time.

Usage::

    from levi.bot.rollcall import take_rollcall

    card = take_rollcall("Night rollcall", {
        "heartbeat": lambda: True,
        "janitor": lambda: True,
    })
    print(card.text)   # card.up / card.down / card.silent counts

Run it: ``python -m levi.bot.rollcall heartbeat=path.to:func``
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Mapping, Optional, Tuple

from levi.bot.brief import render_brief

__all__ = ["RollcallError", "RollcallResult", "take_rollcall", "probe_status"]

#: A probe is a zero-argument callable; truthy answer = UP.
Probe = Callable[[], object]

_UP = "UP"
_DOWN = "DOWN"
_SILENT = "SILENT"


class RollcallError(ValueError):
    """Raised when the roster fails validation."""


def _validate_roster(roster: Mapping[str, Probe]) -> Dict[str, Probe]:
    if not isinstance(roster, Mapping):
        raise RollcallError("roster must be a mapping of name -> probe")
    clean: Dict[str, Probe] = {}
    for name, probe in roster.items():
        if not isinstance(name, str) or not name.strip():
            raise RollcallError(f"roster name must be a non-empty string, got {name!r}")
        if name in clean:
            raise RollcallError(f"duplicate roster name {name!r}")
        if not callable(probe):
            raise RollcallError(f"probe for {name!r} is not callable")
        clean[name] = probe
    return clean


def probe_status(probe: Probe) -> Tuple[str, Optional[str]]:
    """Ping one probe. Never raises: failures come back as SILENT + a note."""
    try:
        answer = probe()
    except Exception as exc:  # noqa: BLE001 - rollcall must not die on a probe
        note = f"{type(exc).__name__}: {str(exc)[:80]}".rstrip(": ")
        return _SILENT, note or type(exc).__name__
    return (_UP, None) if answer else (_DOWN, None)


@dataclass(frozen=True)
class RollcallResult:
    """The card plus honest counts."""

    text: str
    lines: int
    up: int
    down: int
    silent: int
    dropped: int  # body lines the brief card held back


def take_rollcall(
    title: str,
    roster: Mapping[str, Probe],
    max_lines: int = 24,
) -> RollcallResult:
    """Ping every probe in roster order and render the roll-call card."""
    if not isinstance(title, str) or not title.strip():
        raise RollcallError("title must be a non-empty string")
    if not isinstance(max_lines, int) or max_lines < 8:
        raise RollcallError("max_lines must be an int >= 8")
    clean = _validate_roster(roster)
    if not clean:
        raise RollcallError("roster is empty — nothing to roll")

    lines_up, lines_down, lines_silent = [], [], []
    counts = {_UP: 0, _DOWN: 0, _SILENT: 0}
    for name, probe in clean.items():
        state, note = probe_status(probe)
        counts[state] += 1
        rendered = f"{name}: {state}" + (f" ({note})" if note else "")
        if state == _UP:
            lines_up.append(rendered)
        elif state == _DOWN:
            lines_down.append(rendered)
        else:
            lines_silent.append(rendered)

    sections = [
        (f"Answering ({counts[_UP]})", lines_up or ["— none —"]),
        (f"Down ({counts[_DOWN]})", lines_down or ["— none —"]),
        (f"Silent ({counts[_SILENT]})", lines_silent or ["— none —"]),
    ]
    card = render_brief(title, sections, max_lines=max_lines)
    return RollcallResult(
        text=card.text,
        lines=card.lines,
        up=counts[_UP],
        down=counts[_DOWN],
        silent=counts[_SILENT],
        dropped=card.dropped,
    )


def _resolve_probe(spec: str) -> Probe:
    """Resolve 'module.path:attr' to a callable (imported, never exec'd)."""
    import importlib

    if ":" not in spec:
        raise RollcallError(f"probe spec must be module:attr, got {spec!r}")
    module_name, _, attr = spec.partition(":")
    module = importlib.import_module(module_name.strip())
    probe = getattr(module, attr.strip())
    if not callable(probe):
        raise RollcallError(f"{spec!r} did not resolve to a callable")
    return probe


def _cli(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="levi.bot.rollcall",
        description="Ping a roster of LEVI bots/services and report who answers.",
    )
    ap.add_argument("title", help="card title")
    ap.add_argument(
        "roster",
        nargs="+",
        help="name=module:attr entries; each attr is a zero-arg probe callable",
    )
    ap.add_argument("--max-lines", type=int, default=24)
    args = ap.parse_args(argv)

    roster: Dict[str, Probe] = {}
    for entry in args.roster:
        name, _, spec = entry.partition("=")
        if not name or not spec:
            ap.error(f"roster entry must be name=module:attr, got {entry!r}")
        roster[name] = _resolve_probe(spec)
    result = take_rollcall(args.title, roster, max_lines=args.max_lines)
    print(result.text)
    print(f"[rollcall] up={result.up} down={result.down} silent={result.silent}")
    return 1 if result.down or result.silent else 0


if __name__ == "__main__":
    raise SystemExit(_cli())
