"""LEVI customizations — the handoff: how work changes hands between sessions.

A handoff names the shape of a session boundary: how much context the
receiver gets (``verbosity``), which moments force a checkpoint
(``checkpoint_points``), how the checkpoint is written
(``receipt_format``), and whether the receiver must acknowledge before
acting (``require_ack``).

This is his standing rule made concrete: a crew report must not land
nine identical times, and a session must never pick up half-remembered.
The handoff style decides the density; the writer still writes the
words.

Storage is local-first: ``~/.levi/customizations/handoff.json``.
Everything is deny-closed: unknown verbosity levels, checkpoint points,
receipt formats, and unparseable handoffs are refused with a named
error, never coerced.

Usage::

    from levi.customizations import handoff

    h = handoff.build_handoff("night-crew", verbosity="terse",
                              checkpoint_points=["gate", "blocked"],
                              require_ack=True)
    handoff.set_active(h)              # writes handoff.json
    active = handoff.read_active()     # Handoff | None

Run it: ``python -m levi.customizations.handoff show``
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

__all__ = [
    "HandoffError",
    "Handoff",
    "VERBOSITY",
    "CHECKPOINT_POINTS",
    "RECEIPT_FORMATS",
    "DEFAULT_ROOT",
    "build_handoff",
    "set_active",
    "read_active",
    "deactivate",
]


class HandoffError(ValueError):
    """Raised when a handoff fails validation or the store misbehaves."""


#: Verbosity levels: terse (outcomes only), standard (outcomes + open
#: threads), full (outcomes + threads + receipts).
VERBOSITY = ("terse", "standard", "full")

#: Moments that force a checkpoint record.
CHECKPOINT_POINTS = ("phase-complete", "gate", "blocked", "run-end")

#: Receipt formats: lines (human-readable) or ledger (machine-readable).
RECEIPT_FORMATS = ("lines", "ledger")

#: Where the handoff record lives unless a caller says otherwise.
DEFAULT_ROOT = Path.home() / ".levi" / "customizations"

_ACTIVE_FILE = "handoff.json"


@dataclass(frozen=True)
class Handoff:
    """One named handoff style for session boundaries."""

    name: str
    verbosity: str = "standard"
    checkpoint_points: Tuple[str, ...] = ("gate", "blocked")
    receipt_format: str = "lines"
    require_ack: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "verbosity": self.verbosity,
            "checkpoint_points": list(self.checkpoint_points),
            "receipt_format": self.receipt_format,
            "require_ack": self.require_ack,
        }

    @staticmethod
    def from_dict(data: dict) -> "Handoff":
        return build_handoff(
            data.get("name"),
            verbosity=data.get("verbosity", "standard"),
            checkpoint_points=data.get("checkpoint_points", ("gate", "blocked")),
            receipt_format=data.get("receipt_format", "lines"),
            require_ack=data.get("require_ack", False),
        )


def _slug(name: object) -> str:
    if not isinstance(name, str) or not name.strip():
        raise HandoffError(f"handoff name must be a non-empty string, got {name!r}")
    if not name.replace("-", "").replace("_", "").isalnum():
        raise HandoffError(f"handoff name must be [a-z0-9_-], got {name!r}")
    return name


def build_handoff(
    name: object,
    verbosity: object = "standard",
    checkpoint_points: Optional[List[str]] = None,
    receipt_format: object = "lines",
    require_ack: object = False,
) -> Handoff:
    """Validate everything and build an immutable Handoff."""
    clean_name = _slug(name)

    if verbosity not in VERBOSITY:
        raise HandoffError(f"verbosity must be one of {VERBOSITY}, got {verbosity!r}")

    points = checkpoint_points if checkpoint_points is not None else ["gate", "blocked"]
    if not isinstance(points, (list, tuple)) or not points:
        raise HandoffError(
            f"checkpoint_points must be a non-empty list, got {points!r}"
        )
    clean_points = []
    for point in points:
        if point not in CHECKPOINT_POINTS:
            raise HandoffError(
                f"checkpoint point must be one of {CHECKPOINT_POINTS}, got {point!r}"
            )
        clean_points.append(point)
    if len(set(clean_points)) != len(clean_points):
        raise HandoffError("checkpoint_points has duplicates")

    if receipt_format not in RECEIPT_FORMATS:
        raise HandoffError(
            f"receipt_format must be one of {RECEIPT_FORMATS}, got {receipt_format!r}"
        )

    if not isinstance(require_ack, bool):
        raise HandoffError(f"require_ack must be a bool, got {require_ack!r}")

    return Handoff(
        name=clean_name,
        verbosity=verbosity,
        checkpoint_points=tuple(clean_points),
        receipt_format=receipt_format,
        require_ack=require_ack,
    )


def _root(path: Optional[Path]) -> Path:
    root = Path(path) if path is not None else DEFAULT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def set_active(handoff: Handoff, root: Optional[Path] = None) -> Path:
    """Write the handoff as the active one. Returns the file path."""
    if not isinstance(handoff, Handoff):
        raise HandoffError(
            f"set_active expects a Handoff, got {type(handoff).__name__}"
        )
    target = _root(root) / _ACTIVE_FILE
    tmp = target.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(handoff.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    tmp.replace(target)
    return target


def read_active(root: Optional[Path] = None) -> Optional[Handoff]:
    """Read the active handoff; None when none is set. Corrupt = error, not None."""
    target = _root(root) / _ACTIVE_FILE
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HandoffError(f"handoff store is corrupt: {exc}") from exc
    if not isinstance(data, dict):
        raise HandoffError("active handoff must be a JSON object")
    return Handoff.from_dict(data)


def deactivate(root: Optional[Path] = None) -> bool:
    """Remove the active handoff. Returns True if one was set."""
    target = _root(root) / _ACTIVE_FILE
    if not target.exists():
        return False
    target.unlink()
    return True


def render_receipt(handoff: Handoff, entries: List[str]) -> str:
    """Render a checkpoint receipt in the handoff's receipt format.

    ``entries`` are the receipt lines (outcome, open threads, blockers —
    the writer supplies the words; the format only shapes them). Pure:
    no I/O, no store access.
    """
    if not isinstance(handoff, Handoff):
        raise HandoffError(
            f"render_receipt expects a Handoff, got {type(handoff).__name__}"
        )
    if not isinstance(entries, list) or any(not isinstance(e, str) for e in entries):
        raise HandoffError("entries must be a list of strings")
    if handoff.receipt_format == "ledger":
        return json.dumps(
            {"handoff": handoff.name, "receipt": entries},
            indent=2,
            sort_keys=True,
        )
    # "lines": human-readable, verbosity shapes the header
    header = {
        "terse": "handoff (terse)",
        "standard": "handoff (standard)",
        "full": "handoff (full)",
    }[handoff.verbosity]
    return "\n".join([header, "-" * len(header), *entries])


def _cli(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="levi.customizations.handoff",
        description="Handoff styles for LEVI session boundaries.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="print the active handoff")
    sub.add_parser("deactivate", help="clear the active handoff")
    act = sub.add_parser("activate", help="activate a handoff built from flags")
    act.add_argument("name")
    act.add_argument("--verbosity", default="standard", choices=VERBOSITY)
    act.add_argument(
        "--checkpoint",
        action="append",
        default=[],
        choices=CHECKPOINT_POINTS,
        help="a checkpoint point (repeatable)",
    )
    act.add_argument("--receipt-format", default="lines", choices=RECEIPT_FORMATS)
    act.add_argument(
        "--require-ack", action="store_true", help="receiver must acknowledge"
    )
    rcpt = sub.add_parser("receipt", help="render a sample receipt (stdin lines)")
    rcpt.add_argument("--format", default="lines", choices=RECEIPT_FORMATS)
    rcpt.add_argument("--verbosity", default="standard", choices=VERBOSITY)
    args = ap.parse_args(argv)

    if args.cmd == "show":
        active = read_active()
        if active is None:
            print("no active handoff")
            return 1
        print(json.dumps(active.to_dict(), indent=2, sort_keys=True))
        return 0
    if args.cmd == "deactivate":
        print("deactivated" if deactivate() else "no active handoff")
        return 0
    if args.cmd == "receipt":
        import sys

        entries = [line.rstrip("\n") for line in sys.stdin]
        sample = build_handoff(
            "cli-preview",
            verbosity=args.verbosity,
            receipt_format=args.format,
        )
        print(render_receipt(sample, entries))
        return 0
    try:
        handoff = build_handoff(
            args.name,
            verbosity=args.verbosity,
            checkpoint_points=args.checkpoint or ["gate", "blocked"],
            receipt_format=args.receipt_format,
            require_ack=args.require_ack,
        )
    except HandoffError as exc:
        ap.error(str(exc))
    path = set_active(handoff)
    print(f"activated {handoff.name} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
