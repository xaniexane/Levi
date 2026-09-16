"""Vault: an isolated scoped memory store with an explicit retention policy.

Each vault lives in its own directory (``<home>/<name>/``) with:

- ``entries.jsonl`` — one JSON object per line (MemoryEntry dicts).
- ``policy.json``   — the retention policy, human-readable and editable::

    {"ttl_by_type": {"working": 86400, "episodic": 2592000},
     "max_entries": 500,
     "note": "TTLs in seconds; 0 or missing = keep forever"}

Retention is ENFORCED, not advisory: every mutating or reading access
runs :meth:`Vault.purge` first — entries older than their class TTL are
dropped, then if the vault is over ``max_entries`` the lowest-importance
oldest entries are dropped. Purged entries are reported (counts), never
silently kept.

ISOLATION: a :class:`Vault` only ever reads its own directory. There is
no cross-vault query path — :class:`Vaults` hands you one Vault at a
time, and each Vault's ``entries.jsonl`` is the entire universe it can
see. The isolation test asserts a secret stored in vault A is invisible
to every query against vault B.

Entry shape reuses :mod:`levi.memory.types` (portable with the flat
store); the vault adds scoping + retention, which the flat store lacks.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.memory.types import MemoryEntry, MemoryType, new_entry

__all__ = ["VaultError", "Vault", "Vaults", "default_home", "VALID_NAME_RE"]

VALID_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


class VaultError(Exception):
    """Vault operation failed (bad name, bad policy, unknown vault...)."""


def default_home() -> Path:
    """Resolve ~/.levi/vaults at CALL time (hermetic: HOME/LEVI_HOME respected)."""
    override = os.environ.get("LEVI_HOME")
    base = Path(override) if override else Path(os.path.expanduser("~/.levi"))
    return base / "vaults"


def _check_name(name: str) -> str:
    if not isinstance(name, str) or not VALID_NAME_RE.fullmatch(name):
        raise VaultError(
            f"invalid vault name {name!r}: use 1-64 chars of [A-Za-z0-9_-], "
            "starting alnum (this keeps vault dirs safe and portable)"
        )
    return name


def _parse_ts(value: Any) -> Optional[float]:
    if not value:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(value)).timestamp()
    except (ValueError, TypeError):
        return None


class Vault:
    """One isolated scoped store."""

    def __init__(self, name: str, home: Optional[Path] = None):
        self.name = _check_name(name)
        self.home = Path(home) if home else default_home()
        self.dir = self.home / self.name
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.dir, 0o700)
        except OSError:
            pass
        self._entries_path = self.dir / "entries.jsonl"
        self._policy_path = self.dir / "policy.json"
        self._entries: Dict[str, MemoryEntry] = {}
        self.policy: Dict[str, Any] = self._load_policy()
        self._load_entries()

    # -- policy ----------------------------------------------------------
    def _load_policy(self) -> Dict[str, Any]:
        default = {
            "ttl_by_type": {},
            "max_entries": 1000,
            "note": "TTLs in seconds per memory type; 0/missing = keep forever",
        }
        if not self._policy_path.exists():
            self._policy_path.write_text(
                json.dumps(default, indent=2), encoding="utf-8"
            )
            return dict(default)
        try:
            raw = json.loads(self._policy_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise VaultError(
                f"vault {self.name!r}: policy.json unreadable ({exc})"
            ) from exc
        if not isinstance(raw, dict):
            raise VaultError(f"vault {self.name!r}: policy.json must be an object")
        merged = dict(default)
        merged.update(raw)
        return merged

    def set_policy(
        self,
        ttl_by_type: Optional[Dict[str, float]] = None,
        max_entries: Optional[int] = None,
    ) -> Dict[str, Any]:
        if ttl_by_type is not None:
            if not isinstance(ttl_by_type, dict):
                raise VaultError("set_policy: ttl_by_type must be a dict")
            known = {t.value for t in MemoryType}
            for k, v in ttl_by_type.items():
                if k not in known:
                    raise VaultError(
                        f"set_policy: unknown memory type {k!r} (known: {sorted(known)})"
                    )
                if not isinstance(v, (int, float)) or v < 0:
                    raise VaultError(f"set_policy: TTL for {k!r} must be >= 0")
            self.policy["ttl_by_type"] = {k: float(v) for k, v in ttl_by_type.items()}
        if max_entries is not None:
            if not isinstance(max_entries, int) or max_entries < 1:
                raise VaultError("set_policy: max_entries must be a positive int")
            self.policy["max_entries"] = max_entries
        self._policy_path.write_text(
            json.dumps(self.policy, indent=2), encoding="utf-8"
        )
        self.purge()  # new policy applies immediately
        return self.policy

    # -- entries ---------------------------------------------------------
    def _load_entries(self) -> None:
        if not self._entries_path.exists():
            return
        with open(self._entries_path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = MemoryEntry.from_dict(json.loads(line))
                except (ValueError, TypeError) as exc:
                    print(
                        f"vault {self.name}: skipping corrupt entry line {lineno} ({exc})"
                    )
                    continue
                self._entries[entry.id] = entry

    def _persist(self) -> None:
        tmp = self._entries_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            for e in self._entries.values():
                fh.write(json.dumps(e.to_dict(), separators=(",", ":")) + "\n")
        tmp.replace(self._entries_path)

    def purge(self, now: Optional[float] = None) -> Dict[str, int]:
        """Enforce the retention policy. Returns counts {expired, over_cap}."""
        now = time.time() if now is None else now
        ttl_by_type = self.policy.get("ttl_by_type", {})
        expired = []
        for eid, e in self._entries.items():
            ttl = ttl_by_type.get(e.memory_type.value, 0)
            if ttl and ttl > 0:
                created = _parse_ts(e.created_at)
                if created is not None and created + ttl <= now:
                    expired.append(eid)
        for eid in expired:
            del self._entries[eid]
        max_entries = int(self.policy.get("max_entries", 1000) or 1000)
        over_cap = 0
        if len(self._entries) > max_entries:
            ranked = sorted(
                self._entries.values(),
                key=lambda e: (e.importance, _parse_ts(e.updated_at) or 0),
            )
            for e in ranked[: len(self._entries) - max_entries]:
                del self._entries[e.id]
                over_cap += 1
        if expired or over_cap:
            self._persist()
        return {"expired": len(expired), "over_cap": over_cap}

    def add(
        self,
        memory_type: MemoryType,
        content: str,
        importance: float = 0.5,
        source: str = "user",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        self.purge()  # make room under max_entries before adding
        entry = new_entry(
            memory_type=memory_type,
            content=content,
            importance=max(0.0, min(1.0, float(importance))),
            source=source,
            tags=tags or [],
            project_id=self.name,
            metadata=metadata,
        )
        self._entries[entry.id] = entry
        self._persist()
        return entry

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        self.purge()
        return self._entries.get(entry_id)

    def list(
        self, memory_type: Optional[MemoryType] = None, limit: int = 50
    ) -> List[MemoryEntry]:
        self.purge()
        results = list(self._entries.values())
        if memory_type:
            results = [e for e in results if e.memory_type == memory_type]
        results.sort(key=lambda e: (e.importance, e.updated_at), reverse=True)
        return results[:limit]

    def search(self, query: str, limit: int = 20) -> List[MemoryEntry]:
        """Keyword search scoped to THIS vault only. Never sees other vaults."""
        self.purge()
        q = query.lower().strip()
        if not q:
            return []
        scored = []
        for e in self._entries.values():
            text = (e.content + " " + " ".join(e.tags)).lower()
            if q in text:
                scored.append((e.importance, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def delete(self, entry_id: str) -> bool:
        self.purge()
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._persist()
            return True
        return False

    def stats(self) -> Dict[str, Any]:
        self.purge()
        counts: Dict[str, int] = {}
        for e in self._entries.values():
            counts[e.memory_type.value] = counts.get(e.memory_type.value, 0) + 1
        return {
            "vault": self.name,
            "total": len(self._entries),
            "by_type": counts,
            "policy": self.policy,
        }


class Vaults:
    """Manager: create/delete/list vaults. Hands out one isolated Vault at a time."""

    def __init__(self, home: Optional[Path] = None):
        self.home = Path(home) if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.home, 0o700)
        except OSError:
            pass

    def create(self, name: str) -> Vault:
        _check_name(name)
        if (self.home / name).exists():
            raise VaultError(f"vault {name!r} already exists")
        return Vault(name, home=self.home)

    def get(self, name: str) -> Vault:
        _check_name(name)
        if not (self.home / name).is_dir():
            raise VaultError(f"unknown vault {name!r}")
        return Vault(name, home=self.home)

    def delete(self, name: str) -> bool:
        _check_name(name)
        target = self.home / name
        if not target.is_dir():
            return False
        import shutil

        shutil.rmtree(target)
        return True

    def list(self) -> List[str]:
        if not self.home.is_dir():
            return []
        return sorted(
            p.name
            for p in self.home.iterdir()
            if p.is_dir() and VALID_NAME_RE.fullmatch(p.name)
        )
