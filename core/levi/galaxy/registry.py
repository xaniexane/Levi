"""Galaxy package registry: durable record of installed packages.

Storage: JSONL at ``<home>/galaxy/registry.jsonl`` (one install record per
line). Packages themselves live under ``<home>/galaxy/packages/``.

Design notes:
- Every mutation rewrites the whole file via write-tmp + atomic rename, so
  a crash can never leave a half-written registry.
- Corrupted lines are quarantined (moved to ``registry.jsonl.quarantine``)
  instead of failing the whole read — one bad line must not take down the
  registry.
- ``search()`` only looks at INSTALLED packages (records present in the
  registry), across ``id``, ``description`` and ``capabilities``.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Union

__all__ = ["GalaxyRegistry", "RegistryError"]

PathLike = Union[str, os.PathLike]


class RegistryError(RuntimeError):
    """Raised for registry-level failures (unwritable dir, bad record shape)."""


def _galaxy_dir(home: PathLike) -> Path:
    return Path(home).expanduser() / "galaxy"


class GalaxyRegistry:
    """Durable JSONL registry of installed Galaxy packages."""

    def __init__(self, home: PathLike) -> None:
        self.home = Path(home).expanduser()
        self.root = _galaxy_dir(self.home)
        self.path = self.root / "registry.jsonl"
        self.quarantine_path = self.root / "registry.jsonl.quarantine"

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _read_raw_lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return self.path.read_text(encoding="utf-8").splitlines()

    def _load(self) -> tuple[list[dict[str, Any]], list[str]]:
        """Return (valid records, corrupted lines found this read).

        Corrupted lines are quarantined AND removed from the registry file
        (atomic rewrite), so each bad line is quarantined exactly once and a
        later read never sees it again.
        """
        records: list[dict[str, Any]] = []
        corrupted: list[str] = []
        for line in self._read_raw_lines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                corrupted.append(line)
                continue
            if not isinstance(obj, dict) or "id" not in obj:
                corrupted.append(line)
                continue
            records.append(obj)
        if corrupted:
            self._quarantine(corrupted)
            self._write_all(records)  # drop the bad lines, atomically
        return records, corrupted

    def _quarantine(self, bad_lines: list[str]) -> None:
        """Append corrupted lines to the quarantine file and drop them."""
        self._ensure()
        with self.quarantine_path.open("a", encoding="utf-8") as fh:
            for line in bad_lines:
                fh.write(line + "\n")

    def _write_all(self, records: list[dict[str, Any]]) -> None:
        """Atomic full rewrite: write tmp + fsync + rename."""
        self._ensure()
        fd, tmp_name = tempfile.mkstemp(
            dir=str(self.root), prefix="registry.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                for rec in records:
                    fh.write(json.dumps(rec, sort_keys=True) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    @staticmethod
    def _validate_record(record: dict[str, Any]) -> None:
        if not isinstance(record, dict):
            raise RegistryError("install record must be a dict")
        for field in ("id", "version", "kind", "author", "source",
                      "root_sha256", "installed_at", "granted"):
            if field not in record:
                raise RegistryError(f"install record missing field: {field!r}")
        if not isinstance(record["id"], str) or not record["id"]:
            raise RegistryError("install record 'id' must be a non-empty string")

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def add(self, record: dict[str, Any]) -> None:
        """Append an install record (replaces any record with the same id)."""
        self._validate_record(record)
        records, _ = self._load()
        records = [r for r in records if r.get("id") != record["id"]]
        records.append(record)
        self._write_all(records)

    def remove(self, package_id: str) -> bool:
        """Remove the record for ``package_id``. Returns True if one existed."""
        records, _ = self._load()
        kept = [r for r in records if r.get("id") != package_id]
        if len(kept) == len(records):
            return False
        self._write_all(kept)
        return True

    def get(self, package_id: str) -> dict[str, Any] | None:
        """Return the install record for ``package_id``, or None."""
        records, _ = self._load()
        for rec in reversed(records):  # last write wins
            if rec.get("id") == package_id:
                return rec
        return None

    def list(self) -> list[dict[str, Any]]:
        """All install records, in installation order."""
        records, _ = self._load()
        return records

    def search(self, query: str) -> list[dict[str, Any]]:
        """Case-insensitive substring search over id/description/capabilities.

        Only installed packages (registry records) are searched.
        """
        q = (query or "").strip().lower()
        if not q:
            return []
        hits: list[dict[str, Any]] = []
        for rec in self._load()[0]:
            haystacks: list[str] = [str(rec.get("id", ""))]
            desc = rec.get("description")
            if isinstance(desc, str):
                haystacks.append(desc)
            caps = rec.get("capabilities")
            if isinstance(caps, (list, tuple)):
                haystacks.extend(str(c) for c in caps)
            elif isinstance(caps, str):
                haystacks.append(caps)
            if any(q in h.lower() for h in haystacks):
                hits.append(rec)
        return hits

    def quarantined(self) -> list[str]:
        """Raw corrupted lines moved out of the registry so far."""
        if not self.quarantine_path.exists():
            return []
        return [
            line for line in self.quarantine_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
