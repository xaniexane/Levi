# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Forgehand grafts — the signed, sandboxed graft API.

A graft is a small package of capability Forgehand bolts onto the
Forge. Every graft carries a manifest: name, version, declared
capabilities, entry point. The manifest is bound to an HMAC-SHA256
signature over its canonical JSON — tamper with one byte of the
manifest and the signature no longer verifies, so a graft whose
declared permissions were edited after signing can never install.

The registry admits a graft only when BOTH the signature verifies
AND the sandbox policy passes: capability declarations must come
from the known set, `net` requires explicit user consent, and
`fs.write` requires a declared filesystem scope. A registry that
installs an unsigned or over-privileged graft is a broken one.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from levi.dynasty.dna import AgentError

__all__ = [
    "GraftError",
    "CAPABILITIES",
    "create",
    "canonical_json",
    "sign",
    "verify",
    "policy_check",
    "GraftRegistry",
]


class GraftError(AgentError):
    """A graft manifest was malformed, tampered, unsigned, or
    over-privileged — it never reached the sandbox."""


#: The only capabilities a graft may declare.
CAPABILITIES = frozenset({"fs.read", "fs.write", "net", "clock", "shell.exec"})

#: Graft versions are dotted integers (1.2.3, 1, 2.0 …).
_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+)*$")


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GraftError(f"graft manifest field {field!r} must be a non-empty string")
    return value.strip()


def create(
    name: str,
    version: str,
    permissions: Iterable[str],
    entry: str,
    *,
    net_consent: bool = False,
    fs_scope: Iterable[str] = (),
) -> Dict[str, Any]:
    """Build a graft manifest. Raises :class:`GraftError` on malformed
    fields: empty name/entry, non-version strings, unknown
    capabilities, non-boolean consent, non-string scopes."""
    name = _require_str(name, "name")
    version = _require_str(version, "version")
    if not _VERSION_RE.match(version):
        raise GraftError(f"graft version must be dotted integers, got {version!r}")
    entry = _require_str(entry, "entry")
    if not isinstance(net_consent, bool):
        raise GraftError("net_consent must be a bool")
    scope = tuple(fs_scope) if fs_scope is not None else ()
    for s in scope:
        if not isinstance(s, str) or not s.strip():
            raise GraftError("fs_scope entries must be non-empty strings")

    caps: List[str] = []
    for cap in permissions if permissions is not None else []:
        if not isinstance(cap, str) or cap not in CAPABILITIES:
            raise GraftError(
                f"unknown capability {cap!r} — allowed: {sorted(CAPABILITIES)}"
            )
        if cap not in caps:
            caps.append(cap)

    return {
        "kind": "levi-graft",
        "name": name,
        "version": version,
        "permissions": caps,
        "entry": entry,
        "net_consent": net_consent,
        "fs_scope": [s.strip() for s in scope],
    }


def canonical_json(manifest: Dict[str, Any]) -> bytes:
    """Canonical encoding of a manifest: sorted keys, compact
    separators, UTF-8. The signature binds to this exact byte string."""
    if not isinstance(manifest, dict):
        raise GraftError("manifest must be a dict")
    return json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def _as_key_bytes(key: Any) -> bytes:
    if isinstance(key, bytes):
        raw = key
    elif isinstance(key, str):
        raw = key.encode("utf-8")
    else:
        raise GraftError(f"signing key must be bytes or str, got {type(key).__name__}")
    if not raw:
        raise GraftError("signing key must not be empty")
    return raw


def sign(manifest: Dict[str, Any], key: Any) -> str:
    """HMAC-SHA256 of the manifest's canonical JSON. Returns the
    hex digest — the signature."""
    raw = _as_key_bytes(key)
    return hmac.new(raw, canonical_json(manifest), hashlib.sha256).hexdigest()


def verify(manifest: Dict[str, Any], signature: Any, key: Any) -> bool:
    """True only when ``signature`` is the manifest's signature under
    ``key``. Never raises on a mismatch — a tampered manifest simply
    fails. Raises :class:`GraftError` on malformed inputs."""
    if not isinstance(signature, str) or not signature:
        raise GraftError("signature must be a non-empty string")
    expected = sign(manifest, key)
    return hmac.compare_digest(expected, signature)


def policy_check(manifest: Dict[str, Any]) -> List[str]:
    """Sandbox policy audit of a manifest.

    Returns a list of violation strings — empty means the manifest is
    policy-clean. Checks: manifest shape, unknown capabilities, `net`
    without explicit user consent (`net_consent`), and `fs.write`
    without a declared filesystem scope (`fs_scope`).
    """
    violations: List[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be a dict"]
    if manifest.get("kind") != "levi-graft":
        violations.append("manifest kind must be 'levi-graft'")
    perms = manifest.get("permissions", [])
    if not isinstance(perms, list):
        return violations + ["permissions must be a list"]
    declared = {p for p in perms if isinstance(p, str)}
    for p in perms:
        if p not in CAPABILITIES:
            violations.append(f"undeclared capability: {p!r}")
    if "net" in declared and manifest.get("net_consent") is not True:
        violations.append("capability 'net' requires explicit user consent")
    if "fs.write" in declared:
        scope = manifest.get("fs_scope", [])
        if not isinstance(scope, list) or not any(
            isinstance(s, str) and s.strip() for s in scope
        ):
            violations.append("capability 'fs.write' requires a declared fs_scope")
    return violations


def _version_tuple(version: str) -> Tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))


class GraftRegistry:
    """The installed-graft registry.

    install() is the only door in: it verifies the signature AND runs
    the sandbox policy before admitting a manifest. Reinstalling the
    same version is idempotent; a newer version replaces; a downgrade
    is refused (fail-closed).
    """

    def __init__(self) -> None:
        self._grafts: Dict[str, Dict[str, Any]] = {}

    def install(
        self, manifest: Dict[str, Any], signature: str, key: Any
    ) -> Dict[str, Any]:
        """Admit a graft. Raises :class:`GraftError` when the signature
        is bad, the policy fails, or the version is a downgrade."""
        if not verify(manifest, signature, key):
            raise GraftError(
                "signature mismatch — manifest was tampered with or signed "
                "under a different key; graft refused"
            )
        violations = policy_check(manifest)
        if violations:
            raise GraftError(f"sandbox policy violations: {violations}")
        name = manifest["name"]
        version = manifest["version"]
        installed = self._grafts.get(name)
        if installed is not None:
            old_v, new_v = installed["version"], version
            if new_v == old_v:
                return dict(installed)  # idempotent reinstall
            if _VERSION_RE.match(old_v) and _VERSION_RE.match(new_v):
                if _version_tuple(new_v) < _version_tuple(old_v):
                    raise GraftError(
                        f"downgrade refused: {name} {old_v} installed, {new_v} offered"
                    )
        stored = dict(manifest)
        self._grafts[name] = stored
        return dict(stored)

    def list_grafts(self) -> List[Dict[str, Any]]:
        """All installed manifests, as copies — the registry's state
        cannot be mutated through these."""
        return [dict(m) for m in self._grafts.values()]

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """The installed manifest for ``name``, or None."""
        found = self._grafts.get(name)
        return dict(found) if found is not None else None

    def uninstall(self, name: str) -> None:
        """Remove a graft. Raises :class:`GraftError` if not installed."""
        if name not in self._grafts:
            raise GraftError(f"no such graft installed: {name!r}")
        del self._grafts[name]
