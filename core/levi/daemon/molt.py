"""Molt — the generation-shedder daemon.

Snapshots, digests, and exports accumulate as numbered generations:
``slate.gen-1.md``, ``slate.gen-2.md``, … The gardener prunes cache and
logs, but generations are *records* — and LEVI never deletes records.
The molt sheds old generations the way a snake sheds skin: the newest
``keep`` generations stay in place, older ones are *relocated* (never
deleted) into a dated directory under ``stored/``, and every move gets a
receipt.

A generation file is shaped ``<name>.gen-<N><ext>`` — ``N`` a positive
integer, ``<ext>`` anything (or nothing). Families are grouped by
``<name><ext>``; ordering is numeric (gen-10 sorts after gen-9), never
lexicographic.

Hard laws:
  * NEVER-DELETE — this module contains no unlink, rmtree, or remove.
    A generation that cannot be relocated stays where it is and is
    receipted as ``skipped`` with the reason.
  * Dated provenance — every relocated file lands under
    ``<stored>/molt/<YYYY-MM-DD>/`` with its original name intact.
  * Evidence — every action (kept, relocated, skipped) is appended to
    ``~/.levi/molt/molt_receipts.jsonl``.

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.molt --root <dir>`` inside the perpetual
supervisor (one_for_one child), or a plain ``tick()`` call from cron.

Stdlib only, local-first.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_STATE_DIR = Path.home() / ".levi" / "molt"
DEFAULT_STORED_DIR = Path.home() / ".levi" / "stored"
RECEIPTS_NAME = "molt_receipts.jsonl"

_GEN_RE = re.compile(r"^(?P<name>.+)\.gen-(?P<num>[0-9]+)(?P<ext>\..+)?$")

MAX_FAMILIES = 1024
MAX_GENERATIONS = 4096


class MoltError(Exception):
    """A named refusal: bad root, bad keep, or an unreadable directory."""


@dataclass
class MoltReceipt:
    """One shed action, receipted."""

    at: str  # UTC ISO-8601 timestamp
    action: str  # kept | relocated | skipped
    src: str
    dst: str  # "" when action == kept
    family: str
    generation: int
    reason: str


@dataclass
class MoltReport:
    """Outcome of one molt pass. Never raises — failures land here."""

    root: str
    kept: int = 0
    relocated: int = 0
    skipped: int = 0
    families: int = 0
    notes: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"molt {self.root}: {self.families} families, "
            f"{self.kept} kept, {self.relocated} relocated, "
            f"{self.skipped} skipped"
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_generation(path: Path) -> Optional[Tuple[str, int]]:
    """Return (family, generation) for a generation file, else None."""
    match = _GEN_RE.match(path.name)
    if not match:
        return None
    num = int(match.group("num"))
    if num < 1:
        return None
    ext = match.group("ext") or ""
    family = match.group("name") + ext
    return family, num


def _resolve_root(root: Any) -> Path:
    if not isinstance(root, (str, Path)):
        raise MoltError(f"molt root must be a path, got {type(root).__name__}")
    resolved = Path(root).expanduser()
    if not resolved.is_dir():
        raise MoltError(f"molt root is not a directory: {resolved}")
    return resolved


def _resolve_keep(keep: Any) -> int:
    if isinstance(keep, bool) or not isinstance(keep, int):
        raise MoltError(f"molt keep must be an int >= 1, got {type(keep).__name__}")
    if keep < 1:
        raise MoltError(f"molt keep must be >= 1, got {keep!r}")
    return keep


def _ensure_dirs(state_dir: Path, stored_dir: Path) -> None:
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stored_dir.mkdir(mode=0o700, parents=True, exist_ok=True)


def _append_receipt(state_dir: Path, receipt: MoltReceipt) -> None:
    target = state_dir / RECEIPTS_NAME
    fd, tmp = tempfile.mkstemp(
        dir=str(state_dir), prefix=".molt-receipts-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if target.exists():
                handle.write(target.read_text(encoding="utf-8"))
            handle.write(json.dumps(asdict(receipt), sort_keys=True) + "\n")
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def scan(root: Path | str, keep: int = 3) -> Dict[str, List[Tuple[Path, int]]]:
    """Group generation files into families, newest generation first.

    Returns {family: [(path, generation), ...]} sorted by generation
    descending. Files that are not generation files are ignored, never
    touched.
    """
    resolved = _resolve_root(root)
    keep = _resolve_keep(keep)
    families: Dict[str, List[Tuple[Path, int]]] = {}
    try:
        entries = sorted(resolved.iterdir())
    except OSError as exc:
        raise MoltError(f"cannot list molt root {resolved}: {exc}") from exc
    for entry in entries:
        if not entry.is_file():
            continue
        parsed = _parse_generation(entry)
        if parsed is None:
            continue
        family, num = parsed
        families.setdefault(family, []).append((entry, num))
    if len(families) > MAX_FAMILIES:
        raise MoltError(
            f"{len(families)} families exceed the {MAX_FAMILIES} bound — "
            "refusing rather than half-shedding"
        )
    for members in families.values():
        if len(members) > MAX_GENERATIONS:
            raise MoltError(
                f"family exceeds the {MAX_GENERATIONS} generation bound — "
                "refusing rather than half-shedding"
            )
        members.sort(key=lambda item: item[1], reverse=True)
    return families


def tick(
    root: Path | str,
    keep: int = 3,
    dry_run: bool = False,
    state_dir: Path = DEFAULT_STATE_DIR,
    stored_dir: Path = DEFAULT_STORED_DIR,
) -> MoltReport:
    """One molt pass. Never raises — per-item failures land in the report."""
    resolved = _resolve_root(root)
    keep = _resolve_keep(keep)
    report = MoltReport(root=str(resolved))

    try:
        _ensure_dirs(state_dir, stored_dir)
    except OSError as exc:
        report.notes.append(f"state dirs unavailable: {exc}")
        return report

    try:
        families = scan(resolved, keep=keep)
    except MoltError as exc:
        report.notes.append(f"scan refused: {exc}")
        return report

    today = _utcnow().strftime("%Y-%m-%d")
    for family, members in sorted(families.items()):
        report.families += 1
        for path, num in members[:keep]:
            report.kept += 1
            try:
                _append_receipt(
                    state_dir,
                    MoltReceipt(
                        at=_utcnow().isoformat(),
                        action="kept",
                        src=str(path),
                        dst="",
                        family=family,
                        generation=num,
                        reason=f"within newest {keep}",
                    ),
                )
            except OSError as exc:  # receipting must never shed
                report.notes.append(f"receipt failed for kept {path.name}: {exc}")
        for path, num in members[keep:]:
            dest_dir = stored_dir / "molt" / today
            dest = dest_dir / path.name
            reason = f"generation {num} older than newest {keep}"
            if dry_run:
                report.relocated += 1
                report.notes.append(f"dry-run: would relocate {path.name}")
                continue
            try:
                dest_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
                if dest.exists():
                    report.skipped += 1
                    report.notes.append(
                        f"destination already holds {path.name} — leaving in place"
                    )
                    _append_receipt(
                        state_dir,
                        MoltReceipt(
                            at=_utcnow().isoformat(),
                            action="skipped",
                            src=str(path),
                            dst=str(dest),
                            family=family,
                            generation=num,
                            reason="destination collision; never overwrites",
                        ),
                    )
                    continue
                shutil.move(str(path), str(dest))
                report.relocated += 1
                _append_receipt(
                    state_dir,
                    MoltReceipt(
                        at=_utcnow().isoformat(),
                        action="relocated",
                        src=str(path),
                        dst=str(dest),
                        family=family,
                        generation=num,
                        reason=reason,
                    ),
                )
            except OSError as exc:
                report.skipped += 1
                report.notes.append(f"relocation failed for {path.name}: {exc}")
                try:
                    _append_receipt(
                        state_dir,
                        MoltReceipt(
                            at=_utcnow().isoformat(),
                            action="skipped",
                            src=str(path),
                            dst=str(dest),
                            family=family,
                            generation=num,
                            reason=f"move failed: {exc}",
                        ),
                    )
                except OSError:
                    pass
    return report


def _cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="levi.daemon.molt",
        description="Shed old snapshot generations into stored/ (never deletes).",
    )
    parser.add_argument("--root", required=True, help="directory holding generations")
    parser.add_argument(
        "--keep", type=int, default=3, help="newest generations kept in place"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="report, relocate nothing"
    )
    args = parser.parse_args(argv)
    try:
        report = tick(args.root, keep=args.keep, dry_run=args.dry_run)
    except MoltError as exc:
        print(f"refused: {exc}")
        return 2
    print(report.summary())
    for note in report.notes:
        print(f"  - {note}")
    return 0


def main(argv: List[str] | None = None) -> int:
    import sys

    return _cli(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
