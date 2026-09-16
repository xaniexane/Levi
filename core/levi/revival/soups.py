"""Newton revival: application-independent object stores ("soups").

On the Newton, a "soup" was a persistent object store that belonged to no
application — apps read and wrote soups, but the data outlived any single
app. This module is that idea for LEVI: named, typed JSON object stores
that survive the modules that use them.

Model:

- ``Soup``: one named store. ``put(obj, schema, schema_version)``,
  ``get(obj_id)``, ``query(predicate)``, ``delete(obj_id)``.
- Every object carries its own ``schema`` name and ``schema_version``.
  Versions are stored, never silently coerced: readers ask for objects by
  schema and declare the minimum version they understand.
- Persistence: one JSON file per soup under ``~/.levi/soups/<name>.json``
  (overridable ``base_dir`` for hermetic tests), owner-only file
  permissions (0o600), atomic writes via temp-file + rename.
- Fail-closed on corrupt files: a soup file that does not parse is
  quarantined to ``<name>.corrupt-<timestamp>.json`` and a
  ``SoupCorruptError`` is raised — the corrupt bytes are never silently
  dropped and the store refuses to run on them.
- ``list_soups``: registry of every soup with its schemas and counts.

stdlib-only. No network. Defensive-only.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class SoupError(Exception):
    """Base error for soup operations."""


class SoupCorruptError(SoupError):
    """Raised when a soup file cannot be parsed. Fail-closed."""

    def __init__(
        self, name: str, path: Path, reason: str, quarantined_to: Optional[Path] = None
    ):
        self.soup_name = name
        self.path = Path(path)
        self.reason = reason
        self.quarantined_to = quarantined_to
        super().__init__(
            "soups: soup %r is corrupt (%s); file quarantined at %s"
            % (name, reason, quarantined_to)
        )


def _default_base_dir() -> Path:
    return Path(os.path.expanduser("~")) / ".levi" / "soups"


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("soups: soup name must be a non-empty string")
    if any(c in name for c in "/\\") or name.startswith("."):
        raise ValueError("soups: invalid soup name %r" % name)
    return name.strip()


def _validate_schema(schema: str, schema_version: int) -> Tuple[str, int]:
    if not isinstance(schema, str) or not schema.strip():
        raise ValueError("soups: schema name must be a non-empty string")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise ValueError("soups: schema_version must be an int")
    if schema_version < 1:
        raise ValueError("soups: schema_version must be >= 1")
    return schema.strip(), schema_version


class Soup:
    """A named, typed, application-independent object store."""

    def __init__(self, name: str, base_dir: Optional[Path] = None, create: bool = True):
        self.name = _validate_name(name)
        self.base_dir = Path(base_dir) if base_dir else _default_base_dir()
        self._path = self.base_dir / ("%s.json" % self.name)
        self._objects: Dict[str, Dict[str, Any]] = {}
        self._seq = 0
        if create:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            # Owner-only directory perms, best effort.
            try:
                os.chmod(self.base_dir, 0o700)
            except OSError:
                pass
        self._load()

    # -- persistence --------------------------------------------------------
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self._quarantine("unreadable: %s" % exc)
            raise SoupCorruptError(
                self.name,
                self._path,
                str(exc),
                quarantined_to=self._last_quarantine,
            )
        if not isinstance(raw, dict) or not isinstance(raw.get("objects"), dict):
            reason = "top level is not {objects: {...}}"
            self._quarantine(reason)
            raise SoupCorruptError(
                self.name,
                self._path,
                reason,
                quarantined_to=self._last_quarantine,
            )
        self._objects = raw["objects"]
        self._seq = int(raw.get("seq", 0) or 0)

    def _quarantine(self, reason: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = self._path.with_name("%s.corrupt-%s.json" % (self.name, ts))
        try:
            self._path.replace(dest)
            self._last_quarantine: Optional[Path] = dest
        except OSError:
            self._last_quarantine = None

    def _persist(self) -> None:
        payload = {
            "version": 1,
            "name": self.name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "seq": self._seq,
            "objects": self._objects,
        }
        tmp = self._path.with_suffix(".tmp")
        # Owner-only from the moment of creation: open with mode 0o600.
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        os.replace(str(tmp), str(self._path))
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    # -- object API ----------------------------------------------------------
    def put(self, obj: Dict[str, Any], schema: str, schema_version: int) -> str:
        """Store an object; returns its id. ``obj`` must be a JSON-able dict."""
        if not isinstance(obj, dict):
            raise TypeError("soups: obj must be a dict, got %s" % type(obj).__name__)
        schema, schema_version = _validate_schema(schema, schema_version)
        try:
            json.dumps(obj)
        except (TypeError, ValueError) as exc:
            raise ValueError("soups: obj is not JSON-serializable: %s" % exc)
        self._seq += 1
        obj_id = "%s-%d" % (self.name, self._seq)
        record = {
            "id": obj_id,
            "schema": schema,
            "schema_version": schema_version,
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "data": obj,
        }
        self._objects[obj_id] = record
        self._persist()
        return obj_id

    def get(self, obj_id: str) -> Dict[str, Any]:
        """Return the full record (id, schema, schema_version, stored_at, data)."""
        try:
            return self._objects[obj_id]
        except KeyError:
            raise SoupError("soups: soup %r has no object %r" % (self.name, obj_id))

    def query(
        self, predicate: Callable[[Dict[str, Any]], bool]
    ) -> List[Dict[str, Any]]:
        """Return all records for which ``predicate(record)`` is true.

        The predicate sees the full record, never coerced — it can filter
        on ``record["schema"]`` / ``record["schema_version"]`` itself.
        """
        if not callable(predicate):
            raise TypeError("soups: predicate must be callable")
        return [rec for rec in self._objects.values() if predicate(rec)]

    def query_schema(self, schema: str, min_version: int = 1) -> List[Dict[str, Any]]:
        """Convenience: objects of ``schema`` with ``schema_version >= min_version``."""
        schema, min_version = _validate_schema(schema, min_version)
        return [
            rec
            for rec in self._objects.values()
            if rec.get("schema") == schema
            and rec.get("schema_version", 0) >= min_version
        ]

    def compatible(self, obj_id: str, schema: str, min_version: int) -> bool:
        """True if the object carries ``schema`` at ``schema_version >= min_version``."""
        rec = self.get(obj_id)
        return (
            rec.get("schema") == schema
            and int(rec.get("schema_version", 0)) >= min_version
        )

    def delete(self, obj_id: str) -> Dict[str, Any]:
        """Delete an object; returns the removed record. Raises if missing."""
        try:
            rec = self._objects.pop(obj_id)
        except KeyError:
            raise SoupError("soups: soup %r has no object %r" % (self.name, obj_id))
        self._persist()
        return rec

    def count(self) -> int:
        return len(self._objects)

    def schemas(self) -> Dict[str, List[int]]:
        """Schema names present in this soup, each with sorted versions seen."""
        out: Dict[str, set] = {}
        for rec in self._objects.values():
            out.setdefault(str(rec.get("schema")), set()).add(
                int(rec.get("schema_version", 0))
            )
        return {k: sorted(v) for k, v in out.items()}

    def path(self) -> Path:
        return self._path


# --------------------------------------------------------------------------
# Registry: all soups in a base dir
# --------------------------------------------------------------------------


def list_soups(base_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """List every soup in the base dir with its schemas and object counts.

    Corrupt soups are listed with ``"corrupt": true`` instead of raising —
    the registry inspects, ``Soup(name)`` fails closed.
    """
    base = Path(base_dir) if base_dir else _default_base_dir()
    out: List[Dict[str, Any]] = []
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*.json")):
        if ".corrupt-" in path.name:
            continue
        name = path.stem
        try:
            soup = Soup(name, base_dir=base, create=False)
            out.append(
                {
                    "name": name,
                    "path": str(path),
                    "corrupt": False,
                    "objects": soup.count(),
                    "schemas": soup.schemas(),
                }
            )
        except SoupCorruptError as exc:
            out.append(
                {
                    "name": name,
                    "path": str(path),
                    "corrupt": True,
                    "error": exc.reason,
                }
            )
        except SoupError as exc:
            out.append(
                {"name": name, "path": str(path), "corrupt": True, "error": str(exc)}
            )
    return out


__all__ = [
    "Soup",
    "SoupError",
    "SoupCorruptError",
    "list_soups",
]
