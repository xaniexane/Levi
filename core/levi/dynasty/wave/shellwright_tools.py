# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Shellwright tooling — session snapshots, command policy, hooks.

Companion to :mod:`levi.dynasty.wave.shellwright`: Shellwright owns
the Shell, and these are its instruments.

- :class:`SessionSnapshotter` freezes a session's metadata + transcript
  to JSON under ``<home>/dynasty/shell/snapshots/<id>.json`` and
  brings it back. Missing or corrupt snapshots raise a typed
  :class:`SnapshotError`.
- :class:`PolicyProfile` gates command argv through an allowlist +
  denylist, deny always winning. Refusals raise a typed
  :class:`PolicyRefusal` that names the rule that refused.
- :class:`HookRegistry` registers named automation hooks as argv
  templates with ``{arg}`` placeholders; ``invoke`` validates the
  required args and renders the argv.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import string
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Sequence

from levi.dynasty.dna import AgentError

__all__ = [
    "SnapshotError",
    "PolicyRefusal",
    "HookError",
    "SessionSnapshotter",
    "PolicyProfile",
    "strict_profile",
    "standard_profile",
    "open_profile",
    "HookRegistry",
]


class SnapshotError(AgentError):
    """A session snapshot is missing, unreadable, or malformed."""


class PolicyRefusal(AgentError):
    """A command policy refused the argv. Names the rule."""


class HookError(AgentError):
    """An automation hook is unknown, misregistered, or misinvoked."""


def _resolve_home(home: Optional[Path]) -> Path:
    if home is not None:
        return Path(home)
    env = os.environ.get("LEVI_HOME")
    if env:
        return Path(env)
    raise AgentError("no home: pass home= or set LEVI_HOME")


# -- snapshots ------------------------------------------------------

_SNAPSHOT_VERSION = 1
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_SAFE_ID_FULL = re.compile(r"[A-Za-z0-9_.-]+")


def _snapshot_id(session_name: str) -> str:
    """Deterministic, filesystem-safe id for a session name.

    Names that are already safe round-trip unchanged; anything else is
    sanitized and suffixed with a short hash of the original, so ids
    stay unique and no name can escape the snapshots directory.
    """
    safe = _SAFE_ID_RE.sub("_", session_name)
    if safe and safe == session_name and safe not in (".", ".."):
        return safe
    digest = hashlib.sha1(session_name.encode("utf-8")).hexdigest()[:8]
    base = safe.strip("._") or "session"
    return f"{base}__{digest}"


class SessionSnapshotter:
    """Snapshot/restore session metadata + transcripts on disk."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self._home = _resolve_home(home)
        self._dir = self._home / "dynasty" / "shell" / "snapshots"

    @property
    def snapshots_dir(self) -> Path:
        return self._dir

    def snapshot(
        self,
        session_name: str,
        record: Dict[str, Any],
        transcript: Sequence[Any],
    ) -> Dict[str, Any]:
        """Freeze ``record`` + ``transcript`` to ``<id>.json``.

        Returns the stored snapshot body (a copy). Atomic write:
        tmp file + rename, so a crashed write never leaves a torn
        snapshot behind.
        """
        if not isinstance(session_name, str) or not session_name.strip():
            raise AgentError("session name must be a non-empty string")
        if not isinstance(record, dict):
            raise AgentError("snapshot record must be a dict")
        if not isinstance(transcript, (list, tuple)):
            raise AgentError("snapshot transcript must be a list")
        snap_id = _snapshot_id(session_name)
        body = {
            "version": _SNAPSHOT_VERSION,
            "id": snap_id,
            "session_name": session_name,
            "record": dict(record),
            "transcript": list(transcript),
        }
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._dir / f"{snap_id}.json"
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(body, indent=2), encoding="utf-8")
        os.replace(tmp, target)
        return dict(body)

    def restore(self, snap_id: str) -> Dict[str, Any]:
        """Return the snapshot body for ``snap_id``.

        Raises :class:`SnapshotError` if the file is missing, is not
        valid JSON, or fails the snapshot schema.
        """
        if (
            not isinstance(snap_id, str)
            or not snap_id
            or not _SAFE_ID_FULL.fullmatch(snap_id)
        ):
            raise SnapshotError(f"bad snapshot id: {snap_id!r}")
        path = self._dir / f"{snap_id}.json"
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            raise SnapshotError(f"snapshot not found: {snap_id!r}") from None
        try:
            body = json.loads(raw)
        except ValueError as exc:
            raise SnapshotError(f"snapshot {snap_id!r} is corrupt: {exc}") from None
        if (
            not isinstance(body, dict)
            or body.get("version") != _SNAPSHOT_VERSION
            or body.get("id") != snap_id
            or not isinstance(body.get("session_name"), str)
            or not isinstance(body.get("record"), dict)
            or not isinstance(body.get("transcript"), list)
        ):
            raise SnapshotError(f"snapshot {snap_id!r} is corrupt: schema mismatch")
        return dict(body)

    def list_snapshots(self) -> List[Dict[str, str]]:
        """``[{"id", "session_name"}]`` sorted by id.

        Unreadable or corrupt files are skipped — listing stays robust
        when one snapshot went bad.
        """
        found: List[Dict[str, str]] = []
        if not self._dir.is_dir():
            return found
        for path in sorted(self._dir.glob("*.json")):
            try:
                body = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (
                isinstance(body, dict)
                and isinstance(body.get("id"), str)
                and isinstance(body.get("session_name"), str)
            ):
                found.append({"id": body["id"], "session_name": body["session_name"]})
        return sorted(found, key=lambda e: e["id"])


# -- command policy -------------------------------------------------


class PolicyProfile:
    """Allowlist + denylist gate over command argv.

    ``allowlist=None`` means "anything not denied"; a non-None
    allowlist permits only its members. ``denylist`` always wins over
    the allowlist. Matching is on the program basename, so
    ``/bin/rm`` is the same rule as ``rm``.
    """

    def __init__(
        self,
        name: str,
        allowlist: Optional[Sequence[str]] = None,
        denylist: Optional[Sequence[str]] = None,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise AgentError("policy name must be a non-empty string")
        self.name = name.strip()
        self.allowlist: Optional[FrozenSet[str]] = (
            frozenset(allowlist) if allowlist is not None else None
        )
        self.denylist: FrozenSet[str] = (
            frozenset(denylist) if denylist is not None else frozenset()
        )

    def check(self, argv: Sequence[str]) -> List[str]:
        """Vet ``argv``. Returns the argv as a list on success.

        Raises :class:`PolicyRefusal` naming the rule on refusal, and
        :class:`AgentError` on malformed argv.
        """
        if not isinstance(argv, (list, tuple)) or not argv:
            raise AgentError("policy check needs a non-empty argv list")
        if any(not isinstance(a, str) or not a for a in argv):
            raise AgentError("policy check needs argv of non-empty strings")
        prog = os.path.basename(argv[0])
        if prog in self.denylist:
            raise PolicyRefusal(f"policy {self.name!r}: denylist rule refuses {prog!r}")
        if self.allowlist is not None and prog not in self.allowlist:
            raise PolicyRefusal(
                f"policy {self.name!r}: allowlist rule does not permit {prog!r}"
            )
        return list(argv)


def strict_profile() -> PolicyProfile:
    """Tiny allowlist only: read-only inspection commands."""
    return PolicyProfile(
        "strict",
        allowlist={
            "echo",
            "true",
            "false",
            "pwd",
            "ls",
            "cat",
            "whoami",
            "date",
            "uname",
            "printf",
            "head",
            "tail",
            "wc",
        },
    )


def standard_profile() -> PolicyProfile:
    """Everything except a hard deny-list of destructive/network tools."""
    return PolicyProfile(
        "standard",
        denylist={
            "rm",
            "dd",
            "mkfs",
            "mkfs.ext4",
            "shutdown",
            "reboot",
            "poweroff",
            "halt",
            "curl",
            "wget",
            "ssh",
            "scp",
            "sftp",
            "nc",
            "ncat",
        },
    )


def open_profile() -> PolicyProfile:
    """Denylist only: the irreducible minimum of destructive commands."""
    return PolicyProfile(
        "open",
        denylist={"rm", "dd", "mkfs"},
    )


# -- automation hooks -------------------------------------------------

_FORMATTER = string.Formatter()


class HookRegistry:
    """Named automation hooks: argv templates with ``{arg}`` slots.

    ``register("deploy", ["rsync", "{src}", "{dst}"])`` then
    ``invoke("deploy", {"src": "a", "dst": "b"})`` renders the argv.
    All ``{placeholders}`` in the template are required; missing ones
    raise :class:`HookError`. Extra args are ignored. ``{{``/``}}``
    escapes survive rendering.
    """

    def __init__(self) -> None:
        self._hooks: Dict[str, List[str]] = {}

    def register(self, name: str, argv_template: Sequence[str]) -> List[str]:
        """Register a hook. Duplicates and malformed templates are
        refused with :class:`HookError`."""
        if not isinstance(name, str) or not name.strip():
            raise HookError("hook name must be a non-empty string")
        if (
            not isinstance(argv_template, (list, tuple))
            or not argv_template
            or any(not isinstance(t, str) or not t for t in argv_template)
        ):
            raise HookError(
                f"hook {name!r}: template must be a non-empty list of strings"
            )
        name = name.strip()
        if name in self._hooks:
            raise HookError(f"hook {name!r} already registered")
        self._hooks[name] = list(argv_template)
        return list(argv_template)

    def _required_args(self, template: Sequence[str]) -> List[str]:
        required: List[str] = []
        for token in template:
            for _, field, _, _ in _FORMATTER.parse(token):
                if field is not None and field not in required:
                    # Root field only: "{x}" — dotted/indexed fields
                    # ("{x.y}", "{x[0]}") are not supported.
                    root = field.split(".")[0].split("[")[0]
                    if root and root not in required:
                        required.append(root)
        return required

    def invoke(self, name: str, args: Optional[Dict[str, Any]] = None) -> List[str]:
        """Render the hook's argv from ``args``.

        Raises :class:`HookError` on unknown hooks or missing required
        args (naming them); :class:`AgentError` on malformed args.
        """
        if not isinstance(name, str) or not name.strip():
            raise HookError("hook name must be a non-empty string")
        template = self._hooks.get(name.strip())
        if template is None:
            raise HookError(f"unknown hook: {name!r}")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise AgentError("hook args must be a dict")
        required = self._required_args(template)
        missing = [r for r in required if r not in args]
        if missing:
            raise HookError(
                f"hook {name!r}: missing required args: {', '.join(missing)}"
            )
        try:
            return [token.format_map(args) for token in template]
        except (KeyError, ValueError) as exc:
            raise HookError(f"hook {name!r}: template render failed: {exc}") from exc

    def list_hooks(self) -> List[str]:
        """Registered hook names, sorted."""
        return sorted(self._hooks)
