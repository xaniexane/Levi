"""Checksum plugin — honest stdlib file-integrity as a connector plugin.

Where ``netcheck`` probes the network and ``units`` answers desk math,
``checksum`` answers the provenance question: "is this the file I think
it is?" Pure stdlib hashing, no network, no API, no fabrication.

Operations (all read-only; no confirmation gate can ever trigger):
* ``hash`` — hash a file (params: ``path``, ``algorithm`` =
  ``sha256`` | ``sha512`` | ``sha1``, ``allowed_roots`` optional);
* ``verify`` — compare a file against an expected digest with a
  timing-safe comparison (params: ``path``, ``expected``,
  ``algorithm``, ``allowed_roots`` optional).

Honesty rules, deny-closed:
* path must be absolute, must resolve to a regular file under an allowed
  root (default: the user's home directory); symlinks are resolved then
  re-checked — nothing outside the roots is ever read;
* directories, missing files, and unreadable files are refused, never
  half-hashed;
* unknown algorithm → ``invalid_params`` — never guess which one was meant;
* ``expected`` must be a hex string of the algorithm's exact digest
  length, else refused;
* verification uses :func:`hmac.compare_digest` — match is a real
  constant-time comparison, not a formatted guess.

``checksum`` is the reference digester (FIPS 180-4 algorithms), never
LEVI identity. Credentialless by design: ``credential()`` returns the
``"public"`` sentinel so the registry's credential gate never fires for
reads.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.plugins.registry import (
    Capability,
    Connector,
    InvalidParams,
    Operation,
    Transport,
    register_connector,
)

_REFERENCE = "fips-180-4"

_ALGORITHMS = {
    "sha256": (hashlib.sha256, 64),
    "sha512": (hashlib.sha512, 128),
    "sha1": (hashlib.sha1, 40),
}

_CHUNK = 1024 * 1024


# ---------------------------------------------------------------------------
# Deny-closed helpers
# ---------------------------------------------------------------------------


def _allowed_roots(allowed_roots: Optional[Any]) -> List[str]:
    if allowed_roots is None:
        return [os.path.realpath(str(Path.home()))]
    if not isinstance(allowed_roots, (list, tuple)) or not allowed_roots:
        raise InvalidParams(
            "checksum: 'allowed_roots' must be a non-empty list of paths."
        )
    resolved = []
    for root in allowed_roots:
        if not isinstance(root, str) or not root.strip():
            raise InvalidParams(
                "checksum: 'allowed_roots' must hold non-empty strings."
            )
        resolved.append(os.path.realpath(root.strip()))
    return resolved


def _resolve_file(path: Any, allowed_roots: Optional[Any]) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise InvalidParams("checksum: 'path' must be a non-empty string.")
    if not os.path.isabs(path.strip()):
        raise InvalidParams(
            f"checksum: path {path!r} must be absolute — relative paths are refused."
        )
    roots = _allowed_roots(allowed_roots)
    real = os.path.realpath(path.strip())
    if not any(real == root or real.startswith(root + os.sep) for root in roots):
        raise InvalidParams(
            f"checksum: path {real!r} is outside the allowed roots — refused."
        )
    candidate = Path(real)
    if not candidate.is_file():
        raise InvalidParams(f"checksum: path {real!r} is not a regular file — refused.")
    return candidate


def _algorithm(name: Any) -> str:
    if not isinstance(name, str):
        raise InvalidParams(
            f"checksum: 'algorithm' must be one of {sorted(_ALGORITHMS)}."
        )
    algo = name.strip().lower()
    if algo not in _ALGORITHMS:
        raise InvalidParams(
            f"checksum: unknown algorithm {name!r} — "
            f"want one of {sorted(_ALGORITHMS)}, never guessed."
        )
    return algo


def _digest_of(target: Path, algo: str) -> Tuple[str, int]:
    constructor, _length = _ALGORITHMS[algo]
    hasher = constructor()
    total = 0
    try:
        with target.open("rb") as fh:
            while True:
                chunk = fh.read(_CHUNK)
                if not chunk:
                    break
                hasher.update(chunk)
                total += len(chunk)
    except OSError as exc:
        raise InvalidParams(f"checksum: cannot read {target}: {exc}.") from exc
    return hasher.hexdigest(), total


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def hash_file(
    path: str,
    algorithm: str = "sha256",
    allowed_roots: Optional[Any] = None,
) -> Dict[str, Any]:
    """Hash a file: deny-closed path and algorithm."""
    algo = _algorithm(algorithm)
    target = _resolve_file(path, allowed_roots)
    digest, size = _digest_of(target, algo)
    return {
        "path": str(target),
        "algorithm": algo,
        "digest": digest,
        "bytes": size,
    }


def verify_file(
    path: str,
    expected: str,
    algorithm: str = "sha256",
    allowed_roots: Optional[Any] = None,
) -> Dict[str, Any]:
    """Compare a file against an expected digest, timing-safe."""
    algo = _algorithm(algorithm)
    if not isinstance(expected, str):
        raise InvalidParams("checksum: 'expected' must be a hex string.")
    _constructor, length = _ALGORITHMS[algo]
    want = expected.strip().lower()
    if len(want) != length or any(c not in "0123456789abcdef" for c in want):
        raise InvalidParams(
            f"checksum: 'expected' must be {length} hex chars for {algo} — refused."
        )
    target = _resolve_file(path, allowed_roots)
    actual, size = _digest_of(target, algo)
    return {
        "path": str(target),
        "algorithm": algo,
        "expected": want,
        "actual": actual,
        "match": bool(hmac.compare_digest(actual, want)),
        "bytes": size,
    }


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


class ChecksumConnector(Connector):
    """The stdlib file-integrity connector plugin."""

    id = "checksum"
    reference = _REFERENCE
    credential_env_var = "LEVI_CHECKSUM_TOKEN"  # never set: credentialless by design
    display_name = "Checksum"
    description = (
        "Honest stdlib file hashing and digest verification (sha256 / "
        "sha512 / sha1) — deny-closed paths, credentialless."
    )
    capabilities = (
        Capability("read.checksum.hash", "Hash a file with a FIPS 180-4 digest"),
        Capability(
            "read.checksum.verify",
            "Timing-safe digest verification of a file",
        ),
    )
    operations = (
        Operation(
            "hash",
            "Hash a file (params: path, algorithm, allowed_roots — optional)",
            params=("path", "algorithm", "allowed_roots"),
        ),
        Operation(
            "verify",
            "Verify a file against a digest (params: path, expected, "
            "algorithm, allowed_roots — optional)",
            params=("path", "expected", "algorithm", "allowed_roots"),
        ),
    )
    references = (_REFERENCE,)

    def credential(self) -> Optional[str]:
        return super().credential() or "public"

    def perform(
        self,
        operation: str,
        params: Dict[str, Any],
        token: Optional[str],
        transport: Transport | None,
    ) -> Any:
        if operation == "hash":
            return hash_file(
                params.get("path"),
                params.get("algorithm", "sha256"),
                params.get("allowed_roots"),
            )
        if operation == "verify":
            return verify_file(
                params.get("path"),
                params.get("expected"),
                params.get("algorithm", "sha256"),
                params.get("allowed_roots"),
            )
        raise InvalidParams(f"unknown operation {operation!r}.")


register_connector(ChecksumConnector)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "plugins-checksum",
            provides=("plugins.checksum.hash", "plugins.checksum.verify"),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
