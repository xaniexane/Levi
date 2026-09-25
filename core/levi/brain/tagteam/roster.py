"""Teacher roster for the tag-team loop.

Protocol seats (Chauncey's nine), in canonical order:

    kai9000, qwen, deepseek, mistral, kimi, grok, claude, gemini, rex

Integration note: the curator seat (``levi.brain.train.teacher_intake``,
sibling-owned — read-only here) currently accepts
``muse, gemini, chatgpt, claude, grok, qwen, deepseek, mistral, kimi``.
That roster has no ``kai9000`` seat yet and carries ``chatgpt``, which is
not a protocol seat. This module bridges the gap WITHOUT touching the
sibling's file:

- ``rex`` aliases to ``muse`` ("muse is Rex's own seat", per intake docs).
- The other seven protocol seats map 1:1.
- ``kai9000`` drops are held in a staging directory and reported in the
  round ledger as ``staged_pending_roster``. The moment the intake roster
  gains the seat, staging drains automatically — no code change here.

Drop validation is also the structural enforcement of the standing law:
any weight file (``.pt``/``.bin``/``.safetensors``/``.ckpt``) in a teacher
drop is REJECTED. Teachers supply text, never weights; only LEVI's
trainer (``continue.py``) writes weights.
"""

from __future__ import annotations

from pathlib import Path

try:  # package import (tests, library use)
    from levi.brain.train.teacher_intake import TEACHERS as INTAKE_TEACHERS
except ImportError:  # run from inside the tagteam/ directory
    from teacher_intake import TEACHERS as INTAKE_TEACHERS  # type: ignore[no-redef]

# The nine protocol seats, canonical rotation order.
TEAM = (
    "kai9000",
    "qwen",
    "deepseek",
    "mistral",
    "kimi",
    "grok",
    "claude",
    "gemini",
    "rex",
)

# Protocol seat -> intake-accepted name. Seats absent from the intake
# roster (currently: kai9000) have no alias and go to staging.
INTAKE_ALIAS = {
    "rex": "muse",
}

# File suffixes that may never arrive in a teacher drop. A teacher
# shipping weights would be a standing-law violation, so the loop
# refuses the whole drop loudly instead of quietly skipping the file.
WEIGHT_SUFFIXES = (".pt", ".bin", ".safetensors", ".ckpt")


class UnknownSeat(Exception):
    """A drop names a teacher outside the nine protocol seats."""


class DropRejected(Exception):
    """A teacher drop failed validation (weight files or bad shape)."""


def intake_name(seat: str) -> str | None:
    """Map a protocol seat to the name the curator intake accepts.

    Returns None when the intake roster has no such seat yet — the
    caller stages those drops instead of sending them to intake.
    """
    seat = seat.strip().lower()
    if seat not in TEAM:
        raise UnknownSeat(f"not a protocol seat: {seat!r}")
    aliased = INTAKE_ALIAS.get(seat, seat)
    return aliased if aliased in INTAKE_TEACHERS else None


def iter_drop_files(drops_dir: Path) -> list[Path]:
    """JSONL files in a drops dir, deterministic order. Rejects weights."""
    drops_dir = Path(drops_dir)
    if not drops_dir.is_dir():
        raise DropRejected(f"drops dir missing: {drops_dir}")
    bad = sorted(
        p.name
        for p in drops_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in WEIGHT_SUFFIXES
    )
    if bad:
        raise DropRejected(
            "weight files in teacher drop (only LEVI's trainer writes "
            f"weights): {', '.join(bad)}"
        )
    return sorted(
        p for p in drops_dir.glob("*.jsonl") if p.is_file()
    )


def split_staged(
    records: list[dict], staged: dict[str, list[dict]] | None = None
) -> tuple[list[dict], dict[str, list[dict]]]:
    """Split raw drop records into intake-ready vs staged-by-seat.

    ``records`` are raw JSONL dicts with a ``"teacher"`` field. Returns
    (ready, staged) where ``ready`` lines had their teacher rewritten to
    the intake-accepted name and ``staged`` maps unknown-roster seats to
    their held lines. Unknown protocol seats raise; non-protocol seats
    raise UnknownSeat — never silently dropped.
    """
    staged = staged if staged is not None else {}
    ready: list[dict] = []
    for rec in records:
        seat = str(rec.get("teacher", "")).strip().lower()
        name = intake_name(seat)  # raises UnknownSeat for non-protocol seats
        if name is None:
            staged.setdefault(seat, []).append(rec)
        else:
            rec = dict(rec)
            rec["teacher"] = name
            ready.append(rec)
    return ready, staged
