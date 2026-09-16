"""Shared paths and atomic-write helpers for the cybrus package (private).

State root: ``~/.levi/cybrus/`` — ``LEVI_HOME`` env override honored, exactly
the convention used across the LEVI tree (see ``levi/methods/_persist.py``).

Rules shared by every cybrus store:
- The cybrus directory is created owner-only (0o700), and chmod'ed to 0o700
  even when it already exists (fail closed on permissions).
- Every file write is atomic (unique temp file in the same directory +
  ``os.replace``) and owner-only (0o600) from creation.
- Corrupt JSON is never silently absorbed: the bad file is quarantined to
  ``<name>.corrupt-<unix-ts>.json`` and a :class:`CorruptStoreError` raised.
- Read-modify-write sequences that must be single-winner across processes
  (approval consume, token rotate, registry appends) run under
  :func:`store_lock`, an advisory fcntl exclusive lock on a sidecar
  ``<store>.lock`` file.
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None  # type: ignore[assignment]


class CorruptStoreError(Exception):
    """Persisted cybrus JSON could not be parsed. The bad file was quarantined
    beside the original as ``<name>.corrupt-<unix-ts>.json`` for forensics."""


def cybrus_dir() -> Path:
    """Resolve ``<home>/.levi/cybrus/``: ``$LEVI_HOME`` when set (hermetic
    tests), else ``~/.levi``. Creates the directory owner-only."""
    raw = os.environ.get("LEVI_HOME", "").strip()
    root = Path(raw).expanduser() if raw else Path.home()
    d = root / ".levi" / "cybrus"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)  # fail closed even if the dir pre-existed with looser perms
    return d


def store_path(name: str) -> Path:
    """Path for a cybrus JSON store. Refuses path-traversal names."""
    if not name or not isinstance(name, str):
        raise ValueError("store name must be a non-empty string")
    if "/" in name or "\\" in name or name.startswith(".") or ".." in name:
        raise ValueError(f"refusing unsafe store name: {name!r}")
    return cybrus_dir() / f"{name}.json"


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    """Write ``data`` to ``path`` atomically with owner-only permissions.

    The temp file is opened with ``mode`` from creation (no window with
    default permissions), then renamed over the target. The temp name is
    unique per process+write so two concurrent writers to the same store
    cannot interleave through a shared ``.tmp`` file; ``fchmod`` re-asserts
    ``mode`` in case a stale temp file was reused.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.parent / f"{path.name}.tmp.{os.getpid()}.{secrets.token_hex(4)}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    os.replace(tmp, path)


# --- advisory file locking -------------------------------------------------
# Serializes read-modify-write sequences on a store across cooperating
# processes (two CLI invocations racing on the same ledger). On POSIX this is
# fcntl.flock on a sidecar ``<store>.lock`` file; elsewhere it degrades to a
# per-path threading lock (same-process threads only). It is ADVISORY: a
# non-cooperating process (or a root attacker rewriting files directly) is
# not stopped by it — see docs/CYBRUS.md residual risks.

_fallback_locks: dict[str, threading.Lock] = {}
_fallback_guard = threading.Lock()


@contextlib.contextmanager
def store_lock(path: Path):
    """Hold an exclusive advisory lock for the store at ``path``.

    Usage: wrap the whole load → mutate → save sequence so concurrent
    processes cannot interleave (approval double-consume, token double-
    rotate, grant/apikey/identity/vault entry loss). Never nest: acquire
    once per public operation; internal helpers assume the caller holds it.
    """
    path = Path(path)
    if fcntl is not None:
        lock_path = path.parent / (path.name + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "w") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    else:  # pragma: no cover - non-POSIX fallback
        with _fallback_guard:
            key = str(path)
            lock = _fallback_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                _fallback_locks[key] = lock
        with lock:
            yield


def load_json_store(path: Path):
    """Load a JSON store. Returns ``None`` when the file does not exist.

    On corrupt JSON the file is quarantined to ``<stem>.corrupt-<ts>.json``
    and :class:`CorruptStoreError` is raised — data is never silently dropped.
    """
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        stamp = int(time.time())
        quarantine = path.parent / f"{path.stem}.corrupt-{stamp}.json"
        try:
            path.replace(quarantine)
        except OSError:
            pass
        raise CorruptStoreError(
            f"cybrus store {path.name} is corrupt (quarantined to "
            f"{quarantine.name}): {exc}"
        ) from exc


def save_json_store(path: Path, payload) -> None:
    """Persist ``payload`` as JSON atomically, owner-only."""
    raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    atomic_write_bytes(path, raw, 0o600)
