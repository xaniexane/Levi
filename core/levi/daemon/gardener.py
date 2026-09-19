"""Gardener — compost daemon for stale runtime state.

LEVI's runtime accumulates cruft: expired cache entries, oversized logs,
abandoned tmp files. The gardener prunes them on a schedule and writes a
compost receipt for everything it touched, so the Archive can see exactly
what was reclaimed (REIM doctrine: compost honestly, never silently).

Hard boundaries — the gardener NEVER touches:
  * memory stores (``~/.levi/memory/``)
  * the brain / corpus (``~/.levi/brain/``)
  * the oath trust store, vaults, or anything outside its configured
    cache/log roots

It only operates inside its configured ``cache_dir`` and ``log_dir``
(defaults under ``~/.levi``). Cache entries are JSON files shaped
``{"value": ..., "expires_at": "<iso>"}``; entries whose ``expires_at``
is in the past are pruned. Log files larger than ``max_log_bytes`` are
rotated (timestamped generation, ``generations`` kept).

There is no daemonize here — the long-run entry is
``python3 -m levi.daemon.gardener`` inside the perpetual supervisor
(one_for_one child), or a plain ``tick()`` call from cron.

Stdlib only, local-first.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CACHE_DIR = Path.home() / ".levi" / "cache"
DEFAULT_LOG_DIR = Path.home() / ".levi" / "logs"
DEFAULT_STATE_DIR = Path.home() / ".levi" / "gardener"
DEFAULT_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MiB
DEFAULT_GENERATIONS = 3

#: Directories the gardener will never enter, even if configured to.
FORBIDDEN = ("memory", "brain", "vault", "oath", "secrets")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _forbidden(path: Path) -> bool:
    return any(part in FORBIDDEN for part in path.parts)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@dataclass
class GardenerReport:
    """Outcome of one gardener tick."""

    at: str = ""
    pruned: List[str] = field(default_factory=list)
    rotated: List[str] = field(default_factory=list)
    bytes_reclaimed: int = 0
    skipped_forbidden: int = 0
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Gardener:
    """Prunes expired cache entries and rotates oversized logs."""

    def __init__(
        self,
        home: Optional[Path] = None,
        cache_dir: Optional[Path] = None,
        log_dir: Optional[Path] = None,
        max_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
        generations: int = DEFAULT_GENERATIONS,
    ) -> None:
        self.home = Path(home) if home is not None else Path.home()
        base = self.home / ".levi"
        self.cache_dir = Path(cache_dir) if cache_dir else base / "cache"
        self.log_dir = Path(log_dir) if log_dir else base / "logs"
        self.state_dir = base / "gardener"
        self.max_log_bytes = max(1, int(max_log_bytes))
        self.generations = max(1, int(generations))

    # -- pruning ----------------------------------------------------------

    def _prune_cache(self, report: GardenerReport, now: datetime) -> None:
        if not self.cache_dir.is_dir():
            return
        for path in sorted(self.cache_dir.glob("*.json")):
            if _forbidden(path):
                report.skipped_forbidden += 1
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                report.errors.append(f"unreadable cache entry {path.name}: {exc}")
                continue
            if not isinstance(raw, dict):
                continue
            expires = _parse_ts(raw.get("expires_at"))
            if expires is None or expires >= now:
                continue  # fresh, or no expiry — not ours to judge
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            if not report.dry_run:
                try:
                    path.unlink()
                except OSError as exc:
                    report.errors.append(f"cannot prune {path.name}: {exc}")
                    continue
            report.pruned.append(path.name)
            report.bytes_reclaimed += size

    # -- rotation ----------------------------------------------------------

    def _rotate_logs(self, report: GardenerReport, now: datetime) -> None:
        if not self.log_dir.is_dir():
            return
        stamp = now.strftime("%Y%m%dT%H%M%S")
        for path in sorted(self.log_dir.glob("*.log")):
            if _forbidden(path):
                report.skipped_forbidden += 1
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size <= self.max_log_bytes:
                continue
            gen_name = f"{path.name}.{stamp}.1"
            gen_path = path.with_name(gen_name)
            if not report.dry_run:
                try:
                    shutil.move(str(path), str(gen_path))
                    path.touch()
                except OSError as exc:
                    report.errors.append(f"cannot rotate {path.name}: {exc}")
                    continue
                # Trim old generations beyond the keep count.
                older = sorted(
                    self.log_dir.glob(f"{path.name}.*"),
                    key=lambda p: p.name,
                )
                for stale in older[: max(0, len(older) - self.generations)]:
                    try:
                        reclaimed = stale.stat().st_size
                        stale.unlink()
                        report.bytes_reclaimed += reclaimed
                    except OSError:
                        pass
            report.rotated.append(path.name)
            report.bytes_reclaimed += size

    # -- tick --------------------------------------------------------------

    def tick(self, dry_run: bool = False) -> GardenerReport:
        """One compost pass. Never raises — failures land in the report."""
        now = _utcnow()
        report = GardenerReport(at=now.isoformat(), dry_run=dry_run)
        for step in (self._prune_cache, self._rotate_logs):
            try:
                step(report, now)
            except Exception as exc:  # noqa: BLE001 — report, never crash
                report.errors.append(f"{step.__name__} failed: {exc}")
        self._save_report(report)
        return report

    def _save_report(self, report: GardenerReport) -> None:
        try:
            _atomic_write(
                self.state_dir / "last_report.json",
                json.dumps(report.to_dict(), indent=2),
            )
            receipt = self.state_dir / "compost_receipts.jsonl"
            receipt.parent.mkdir(parents=True, exist_ok=True)
            with open(receipt, "a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "at": report.at,
                            "pruned": report.pruned,
                            "rotated": report.rotated,
                            "bytes_reclaimed": report.bytes_reclaimed,
                            "dry_run": report.dry_run,
                        }
                    )
                    + "\n"
                )
        except OSError:
            pass

    def check(self) -> tuple:
        """Lightweight coherence check for the supervisor (never raises)."""
        try:
            if _forbidden(self.cache_dir) or _forbidden(self.log_dir):
                return False, "gardener roots overlap a forbidden directory"
            state = self.state_dir / "last_report.json"
            if state.exists():
                raw = json.loads(state.read_text(encoding="utf-8"))
                pruned = len(raw.get("pruned", []))
                rotated = len(raw.get("rotated", []))
                return True, (
                    f"last tick pruned {pruned} cache entrie(s), "
                    f"rotated {rotated} log(s)"
                )
            return True, "gardener ready (no tick yet)"
        except Exception as exc:  # noqa: BLE001
            return False, f"gardener check failed: {exc}"


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m levi.daemon.gardener")
    ap.add_argument("--dry-run", action="store_true", help="Report, change nothing.")
    args = ap.parse_args(argv)
    report = Gardener().tick(dry_run=args.dry_run)
    print(
        "gardener tick: pruned=%d rotated=%d reclaimed=%d bytes%s"
        % (
            len(report.pruned),
            len(report.rotated),
            report.bytes_reclaimed,
            " (dry run)" if report.dry_run else "",
        )
    )
    for name in report.pruned:
        print(f"  pruned:   {name}")
    for name in report.rotated:
        print(f"  rotated:  {name}")
    for err in report.errors:
        print(f"  error:    {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
