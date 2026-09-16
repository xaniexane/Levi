"""LEVI Galaxy — the services layer: a deny-closed service directory.

This is the substrate of the LEVI Galaxy ecosystem: third parties publish
skills, tools, and services as *packages*, and every cross-package call
goes through :class:`GalaxyServices` — never by direct import of another
package's module.

Design, in one breath:

- Each installed package registers its verbs on a named port
  ``galaxy.<package-id>`` in a :class:`~levi.revival.arexx.PortRegistry`
  (ARexx-style named ports; see :mod:`levi.revival.arexx`).
- Every :meth:`GalaxyServices.call` verifies a Telescript-style
  capability token *before* invoking anything (see
  :mod:`levi.revival.telescript`): tampered, expired, revoked, or
  wrong-grantee tokens are refused with the original typed exceptions —
  never wrapped into vagueness, never executed.
- Action names are ``galaxy.<id>.<verb>``; capability patterns are
  deny-closed (``galaxy.acme.*`` covers a whole package, ``galaxy.*``
  covers everything — grant narrowly).
- Successful and refused calls are metered through the governor usage
  ledger (:class:`~levi.governor.meter.Meter`) when one is attached.

The package registry persists (owner-only JSON) so installs survive
restarts; entry points are re-resolved and hash-pinned on load. Anything
that fails to verify on load is marked *broken* and never registered.

stdlib-only. No network. No daemons.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from levi.galaxy import trust as galaxy_trust
from levi.galaxy.package import load_manifest
from levi.galaxy.registry import GalaxyRegistry

from levi.revival.arexx import (
    AccessDenied,
    PortError,
    PortRegistry,
    UnknownPort,
    UnknownVerb,
)
from levi.revival.telescript import (
    ActionRefused,
    Capability,
    CapabilityError,
    ExpiredToken,
    InvalidSignature,
    MalformedToken,
    RevocationList,
    RevokedToken,
    WrongGrantee,
    issue,
    permits,
    verify,
)

__all__ = [
    "GalaxyError",
    "ManifestError",
    "InstallError",
    "UnknownPackage",
    "InstalledPackage",
    "GalaxyServices",
    "CAPABILITY_ISSUER",
    "galaxy_home",
    "default_store_dir",
    # re-exported refusal types so callers catch one family
    "PortError",
    "UnknownPort",
    "UnknownVerb",
    "AccessDenied",
    "CapabilityError",
    "MalformedToken",
    "InvalidSignature",
    "ExpiredToken",
    "WrongGrantee",
    "RevokedToken",
    "ActionRefused",
]

CAPABILITY_ISSUER = "levi.galaxy"
"""Issuer string stamped on capabilities minted by the directory."""

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_ENTRYPOINT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*")


# ---------------------------------------------------------------------------
# Errors — galaxy's own; refusal types are re-exported above, never wrapped
# ---------------------------------------------------------------------------


class GalaxyError(Exception):
    """Base class for Galaxy packaging/install failures."""


class ManifestError(GalaxyError):
    """The install record is malformed or missing required fields."""


class InstallError(GalaxyError):
    """The manifest was valid but the package could not be installed."""


class UnknownPackage(GalaxyError):
    """No package is installed under that id."""


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def galaxy_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    """Directory holding Galaxy state. ``home`` is the user's HOME dir."""
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "galaxy"


def default_store_dir(home: "str | os.PathLike[str] | None" = None) -> Path:
    return galaxy_home(home)


# ---------------------------------------------------------------------------
# Installed package record
# ---------------------------------------------------------------------------


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _pin_manifest(manifest: dict) -> str:
    return hashlib.sha256(_canonical(manifest).encode("utf-8")).hexdigest()


@dataclass
class InstalledPackage:
    """One installed Galaxy package and how to reach it."""

    id: str
    name: str = ""
    version: str = ""
    description: str = ""
    author: str = ""
    kind: str = "service"  # skill | tool | service
    entry_points: dict[str, str] = field(
        default_factory=dict
    )  # verb -> "module:function"
    pin: str = ""  # sha256 of the canonical install record
    source: str = ""  # where it was installed from (path/URL/note)
    installed_at: float = 0.0
    broken: Optional[str] = None  # set when entry points failed to resolve

    @property
    def port(self) -> str:
        return f"galaxy.{self.id}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "kind": self.kind,
            "entry_points": dict(self.entry_points),
            "pin": self.pin,
            "source": self.source,
            "installed_at": self.installed_at,
            "broken": self.broken,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "InstalledPackage":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def matches(self, query: str) -> bool:
        q = query.lower()
        hay = " ".join(
            [self.id, self.name, self.description, self.author]
            + list(self.entry_points)
        ).lower()
        return q in hay


# ---------------------------------------------------------------------------
# The directory
# ---------------------------------------------------------------------------


class GalaxyServices:
    """The Galaxy service directory.

    Installs package manifests, registers each package's verbs on a named
    port ``galaxy.<id>``, gates every call behind a capability check, and
    meters calls through the governor ledger.
    """

    def __init__(
        self,
        store_dir: "str | os.PathLike[str] | None" = None,
        *,
        meter: Any = None,
        home: "str | os.PathLike[str] | None" = None,
        clock=time.time,
    ) -> None:
        self._store_dir = (
            Path(store_dir) if store_dir is not None else default_store_dir(home)
        )
        self._store_file = self._store_dir / "packages.json"
        self._home = (
            home  # the "~" home; LEVI home is <home>/.levi (may be None -> Path.home())
        )
        self._clock = clock
        self._registry = PortRegistry()
        self._revocations = RevocationList()
        self._packages: dict[str, InstalledPackage] = {}
        # Meter seam: an explicit Meter wins; otherwise attach the real
        # governor ledger (writes to ~/.levi/governor/usage.jsonl). Pass
        # meter=None only when metering is genuinely unwanted — the default
        # is to meter, because unmetered service calls are invisible spend.
        if meter is None:
            from levi.governor.meter import Meter

            meter = Meter(home=home, clock=clock)
        self._meter = meter
        self._load()

    # -- install / remove -------------------------------------------------
    @staticmethod
    def validate_manifest(manifest: dict) -> dict:
        """Check an install record; return a normalized copy. Raise ManifestError."""
        if not isinstance(manifest, dict):
            raise ManifestError("manifest must be a JSON object")
        pkg_id = manifest.get("id")
        if not isinstance(pkg_id, str) or not _ID_RE.fullmatch(pkg_id):
            raise ManifestError(
                f"manifest 'id' must match {_ID_RE.pattern!r}, got {pkg_id!r}"
            )
        entry_points = manifest.get("entry_points")
        if not isinstance(entry_points, dict) or not entry_points:
            raise ManifestError("manifest needs a non-empty 'entry_points' object")
        for verb, target in entry_points.items():
            if not isinstance(verb, str) or not verb or not verb.strip():
                raise ManifestError(f"invalid verb name: {verb!r}")
            if not isinstance(target, str) or not _ENTRYPOINT_RE.fullmatch(
                target.strip()
            ):
                raise ManifestError(
                    f"entry point for verb {verb!r} must be 'module:function', "
                    f"got {target!r}"
                )
        normalized = {
            "id": pkg_id,
            "name": str(manifest.get("name") or pkg_id),
            "version": str(manifest.get("version") or "0.0.0"),
            "description": str(manifest.get("description") or ""),
            "author": str(manifest.get("author") or ""),
            "kind": str(manifest.get("kind") or "service"),
            "entry_points": {str(v): str(t).strip() for v, t in entry_points.items()},
        }
        if normalized["kind"] not in ("skill", "tool", "service"):
            raise ManifestError(
                f"manifest 'kind' must be skill|tool|service, got {normalized['kind']!r}"
            )
        return normalized

    @staticmethod
    def _resolve_with_dir(
        entry_points: dict[str, str], package_dir: "Path | None"
    ) -> dict[str, Any]:
        """Resolve entry points, with ``package_dir`` importable during resolution.

        The directory is put on ``sys.path`` just long enough to import the
        entry-point modules (all-or-nothing), then removed. Modules already
        imported stay cached in ``sys.modules`` — harmless, since resolution
        is content-addressed by the install's hash pin.
        """
        added_to_path = False
        if package_dir is not None:
            p = os.fspath(package_dir)
            if p not in sys.path:
                sys.path.insert(0, p)
                added_to_path = True
        try:
            return GalaxyServices._resolve_entry_points(entry_points)
        finally:
            if added_to_path:
                try:
                    sys.path.remove(p)
                except ValueError:
                    pass

    @staticmethod
    def _resolve_entry_points(entry_points: dict[str, str]) -> dict[str, Any]:
        """Import every entry point. All-or-nothing: one failure aborts."""
        resolved: dict[str, Any] = {}
        for verb, target in entry_points.items():
            module_name, _, attr = target.partition(":")
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:
                raise InstallError(
                    f"verb {verb!r}: cannot import module {module_name!r}: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
            try:
                fn = getattr(module, attr)
            except AttributeError as exc:
                raise InstallError(
                    f"verb {verb!r}: module {module_name!r} has no attribute {attr!r}"
                ) from exc
            if not callable(fn):
                raise InstallError(f"verb {verb!r}: {target!r} is not callable")
            resolved[verb] = fn
        return resolved

    def install(self, manifest: dict, *, source: str = "") -> InstalledPackage:
        """Install a package from an install record.

        Validates the manifest, resolves every entry point, registers the
        verbs on port ``galaxy.<id>``, hash-pins the record, and persists it.
        Deny-closed: a duplicate id is refused (remove first, then reinstall).
        """
        normalized = self.validate_manifest(manifest)
        return self._register(normalized, package_dir=None, source=source)

    def _register(
        self,
        normalized: dict,
        package_dir: "Path | None",
        *,
        source: str = "",
    ) -> InstalledPackage:
        """Shared registration core: resolve entry points, register the port."""
        pkg_id = normalized["id"]
        if pkg_id in self._packages:
            raise InstallError(
                f"package {pkg_id!r} is already installed; "
                "remove it first, then reinstall"
            )
        # Entry points name importable modules. When the package lives in an
        # install directory (via levi.galaxy.install), put that directory on
        # sys.path just long enough to resolve them — all-or-nothing.
        resolved = self._resolve_with_dir(normalized["entry_points"], package_dir)
        pkg = InstalledPackage(
            **normalized,
            pin=_pin_manifest(normalized),
            source=str(source or ""),
            installed_at=self._clock(),
        )
        self._registry.register_port(pkg.port, resolved)
        self._packages[pkg_id] = pkg
        self._save()
        return pkg

    def register_installed(
        self,
        record: dict,
        *,
        home: "str | os.PathLike[str] | None" = None,
    ) -> InstalledPackage:
        """Register the verbs of a package installed via :mod:`levi.galaxy.install`.

        ``record`` is the install-record dict returned by
        :func:`levi.galaxy.install.install`; ``home`` is the LEVI home
        (``~/.levi`` in production). Integrity is verified BEFORE anything is
        imported — a tampered install raises :class:`TamperError` and nothing
        is registered. Entry points come from the installed ``levi-skill.json``.
        """
        levi_home = (
            Path(home).expanduser() if home is not None else Path.home() / ".levi"
        )
        pkg_id = record.get("id")
        if not galaxy_trust.verify_install(levi_home, record):
            raise galaxy_trust.TamperError(
                f"package {pkg_id!r} failed integrity verification; refusing to register"
            )
        pkg_dir = galaxy_trust.install_dir(levi_home, record)
        manifest = load_manifest(pkg_dir)  # PackageError propagates, deny-closed
        normalized = self.validate_manifest(
            {
                "id": record["id"],
                "name": manifest.name,
                "version": record["version"],
                "description": manifest.description,
                "author": record.get("author", ""),
                "kind": record.get("kind", "service"),
                "entry_points": dict(manifest.entry_points),
            }
        )
        return self._register(normalized, pkg_dir, source=record.get("source", ""))

    def sync_from_registry(
        self, *, home: "str | os.PathLike[str] | None" = None
    ) -> dict[str, list[str]]:
        """Register every installed package missing from this directory.

        The install registry (``levi.galaxy.registry``) is the source of truth
        for *what is installed*; this directory is the runtime view of *what
        is callable*. Sync closes the gap. Per-record deny-closed: one bad
        package is skipped with its reason recorded, never blocking the rest.
        """
        levi_home = (
            Path(home).expanduser() if home is not None else Path.home() / ".levi"
        )
        registry = GalaxyRegistry(levi_home)
        registered: list[str] = []
        skipped: list[str] = []
        for record in registry.list():
            if record.get("id") in self._packages:
                continue
            try:
                self.register_installed(record, home=levi_home)
            except Exception as exc:
                skipped.append(f"{record.get('id')}: {type(exc).__name__}: {exc}")
            else:
                registered.append(record["id"])
        return {"registered": registered, "skipped": skipped}

    def remove(self, pkg_id: str) -> InstalledPackage:
        """Uninstall a package: unregister its port and drop its record."""
        try:
            pkg = self._packages.pop(pkg_id)
        except KeyError:
            raise UnknownPackage(f"no package installed as {pkg_id!r}") from None
        if self._registry.has_port(pkg.port):
            self._registry.unregister_port(pkg.port)
        self._save()
        return pkg

    def info(self, pkg_id: str) -> InstalledPackage:
        try:
            return self._packages[pkg_id]
        except KeyError:
            raise UnknownPackage(f"no package installed as {pkg_id!r}") from None

    # -- directory ----------------------------------------------------------
    def list_services(self) -> dict[str, dict]:
        """The service directory: port -> package info + verb names.

        Broken packages (entry points that failed to resolve on load) are
        listed with ``broken`` set and no verbs registered — they can never
        be called.
        """
        out: dict[str, dict] = {}
        for pkg_id in sorted(self._packages):
            pkg = self._packages[pkg_id]
            verbs = (
                sorted(self._registry.list_ports().get(pkg.port, []))
                if pkg.broken is None
                else []
            )
            out[pkg.port] = {
                "package": pkg.id,
                "name": pkg.name,
                "version": pkg.version,
                "description": pkg.description,
                "author": pkg.author,
                "kind": pkg.kind,
                "verbs": verbs,
                "pin": pkg.pin,
                "broken": pkg.broken,
                "installed_at": pkg.installed_at,
            }
        return out

    def search(self, query: str) -> list[InstalledPackage]:
        """Substring search over installed packages (id, name, description, verbs)."""
        q = (query or "").strip().lower()
        if not q:
            return []
        return [p for p in self._packages.values() if p.matches(q)]

    # -- capabilities -------------------------------------------------------
    def issue_capability(
        self,
        grantee: str,
        actions: list[str],
        ttl_seconds: float = 3600,
    ) -> str:
        """Mint a capability token for a caller (e.g. a skill's executor).

        Action names are ``galaxy.<id>.<verb>``; grant narrowly, e.g.
        ``["galaxy.acme.*"]`` for one package or ``["galaxy.acme.summarize"]``
        for a single verb. Deny-closed: ``actions=[]`` permits nothing.
        """
        return issue(CAPABILITY_ISSUER, grantee, actions, ttl_seconds=ttl_seconds)

    def revoke(self, token_or_nonce: str) -> None:
        """Revoke a capability by full token or raw nonce."""
        self._revocations.revoke(token_or_nonce)

    # -- the call path --------------------------------------------------------
    def _meter_attempt(
        self, action: str, grantee: str, error: Optional[str] = None
    ) -> None:
        """Record one service-call attempt on the governor ledger.

        Metering must never break the call path: a ledger failure is noted
        nowhere and swallowed, because refusing a valid call over a full
        disk would be worse than an unrecorded call.
        """
        if self._meter is None:
            return
        try:
            fingerprint = hashlib.sha256(
                f"{action}\x00{grantee}".encode("utf-8")
            ).hexdigest()[:16]
            self._meter.record(
                provider="galaxy",
                agent_id=grantee,
                tool_name=action,
                prompt_fingerprint=fingerprint,
                error=error,
            )
        except Exception:
            pass

    def call(
        self,
        port: str,
        verb: str,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        *,
        capability: str,
        grantee: Optional[str] = None,
        revocations: Optional[RevocationList] = None,
    ) -> Any:
        """Call a service verb through the directory.

        1. The capability token is verified FIRST — malformed, tampered,
           expired, revoked, or wrong-grantee tokens raise the original
           :mod:`levi.revival.telescript` exceptions, and nothing is invoked.
        2. The ``galaxy.<id>.<verb>`` action must be covered by a granted
           pattern, else :class:`ActionRefused`.
        3. The verb is invoked via the port registry (``UnknownPort`` /
           ``UnknownVerb`` on miss).
        4. The attempt is metered on the governor ledger.

        This is how skill A calls skill B's verb: through this directory,
        never by importing B's module.
        """
        action = f"{port}.{verb}"
        if not isinstance(port, str) or not port.startswith("galaxy."):
            raise UnknownPort(f"not a galaxy service port: {port!r}")
        revs = revocations if revocations is not None else self._revocations
        try:
            cap: Capability = verify(
                capability, expected_grantee=grantee, revocations=revs
            )
        except CapabilityError as exc:
            self._meter_attempt(action, grantee or "?", error=type(exc).__name__)
            raise
        if not permits(cap, action):
            self._meter_attempt(action, cap.grantee, error="ActionRefused")
            raise ActionRefused(
                f"capability for {cap.grantee!r} does not permit {action!r} "
                "(deny-closed: grant the action explicitly)"
            )
        try:
            result = self._registry.send_command(
                port,
                verb,
                args=list(args or []),
                kwargs=dict(kwargs or {}),
                caller=cap.grantee,
            )
        except Exception as exc:
            self._meter_attempt(action, cap.grantee, error=type(exc).__name__)
            raise
        self._meter_attempt(action, cap.grantee)
        return result

    # -- persistence --------------------------------------------------------
    def _save(self) -> None:
        self._store_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "packages": {pid: pkg.to_dict() for pid, pkg in self._packages.items()}
        }
        tmp = self._store_file.with_suffix(".tmp")
        tmp.write_text(_canonical(payload) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._store_file)

    def _install_dir_for(self, pkg_id: str, version: str) -> "Path | None":
        """Filesystem dir of an installed package, if it exists on disk.

        Packages registered through :meth:`register_installed` live under
        ``<levi-home>/galaxy/packages/<id>/<version>/``; resolving their
        entry points on reload needs that dir importable. Packages installed
        purely in-process (``install(manifest_dict)``) have no dir → None.
        """
        try:
            levi_home = (
                Path(self._home).expanduser() / ".levi"
                if self._home is not None
                else Path.home() / ".levi"
            )
            candidate = galaxy_trust.install_dir(
                levi_home, {"id": pkg_id, "version": version}
            )
        except Exception:
            return None
        return candidate if candidate.is_dir() else None

    def _load(self) -> None:
        if not self._store_file.exists():
            return
        try:
            raw = json.loads(self._store_file.read_text(encoding="utf-8"))
            stored = raw.get("packages", {})
            if not isinstance(stored, dict):
                return
        except (json.JSONDecodeError, OSError):
            return  # corrupt store: start empty, never crash the directory
        for pkg_id, record in stored.items():
            if not isinstance(record, dict):
                continue
            manifest = {
                k: record.get(k)
                for k in (
                    "id",
                    "name",
                    "version",
                    "description",
                    "author",
                    "kind",
                    "entry_points",
                )
            }
            pkg = InstalledPackage.from_dict(record)
            # Hash pin check: the record must be exactly what was installed.
            if record.get("pin") != _pin_manifest(manifest):
                pkg.broken = "hash pin mismatch: install record was modified"
                self._packages[pkg_id] = pkg
                continue
            try:
                pkg_dir = self._install_dir_for(pkg_id, pkg.version)
                resolved = self._resolve_with_dir(pkg.entry_points, pkg_dir)
            except GalaxyError as exc:
                pkg.broken = str(exc)
                self._packages[pkg_id] = pkg
                continue
            self._registry.register_port(pkg.port, resolved)
            self._packages[pkg_id] = pkg
