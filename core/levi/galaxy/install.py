"""Galaxy package installation: deny-closed, least-privilege.

Pipeline (every step fails closed with a precise error):
  a. materialize the source (local dir, .tar.gz/.zip, or git URL) to a temp dir
  b. load + validate the manifest via :mod:`levi.galaxy.package`
  c. namespace check via :mod:`levi.galaxy.namespace`
     (``to_namespaced`` / ``check_collision`` / ``resolve``)
  d. permission policy: requested permissions must be a subset of the policy's
     allowed set — the default policy denies network + subprocess
  e. hash the package tree (SHA-256 over sorted relative paths + contents)
  f. derive least-privilege capability actions and validate them through
     :mod:`levi.revival.telescript` (``issue`` / ``permits`` / ``guarded_call``)
  g. copy into ``<home>/galaxy/packages/<id>/<version>/`` and record it

Install record contract (shared with sibling builders)::

    {"id": "<author>.<name>", "version": str, "kind": str, "author": str,
     "source": str, "root_sha256": str, "installed_at": str (iso),
     "granted": {"network": bool, "fs": [paths], "subprocess": bool}}

``description`` and ``capabilities`` are stored as extra fields so the
registry's ``search()`` can find packages by them.

Capability tokens are NOT persisted: telescript tokens are session-scoped by
default (per-process HMAC secret), so the live token for a package is issued
at run time via :func:`issue_capability`, never stored on disk.

stdlib-only.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

from levi.galaxy.namespace import (
    RegistryEntry,
    check_collision,
    resolve,
    to_namespaced,
)
from levi.galaxy.package import Manifest, PackageError, load_manifest
from levi.galaxy.registry import GalaxyRegistry
from levi.revival import telescript

__all__ = [
    "DEFAULT_POLICY",
    "GalaxyInstallError",
    "SourceError",
    "PermissionDenied",
    "CollisionRefused",
    "InstallError",
    "hash_tree",
    "capability_actions",
    "issue_capability",
    "guarded_package_call",
    "install",
]

PathLike = Union[str, os.PathLike]

# Default install policy: deny-closed. Network and subprocess are refused
# unless the caller explicitly allows them; no fs paths are allowed.
DEFAULT_POLICY: dict[str, Any] = {
    "network": False,
    "fs": [],
    "subprocess": False,
}

_CAPABILITY_ISSUER = "levi-galaxy"
_DEFAULT_TOKEN_TTL = 24 * 3600  # capability tokens live one day by default


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GalaxyInstallError(Exception):
    """Base class for install-pipeline failures."""


class SourceError(GalaxyInstallError):
    """The install source could not be materialized."""


class PermissionDenied(GalaxyInstallError):
    """Requested permissions exceed the install policy. Refused."""


class CollisionRefused(GalaxyInstallError):
    """Namespace collision / resolution policy refused the install."""


class InstallError(GalaxyInstallError):
    """Any other install-pipeline failure (hashing, copy, record)."""


# ---------------------------------------------------------------------------
# (e) package-tree hashing
# ---------------------------------------------------------------------------


def hash_tree(root: PathLike) -> str:
    """SHA-256 over sorted relative paths + file contents.

    Deterministic: ``relpath + NUL + sha256(content) + NUL`` for every file,
    sorted by POSIX relative path, finalized with the file count. Symlinks
    are refused outright (deny-closed: no ambiguous or escaping content).
    """
    root = Path(root)
    if not root.is_dir():
        raise InstallError(f"cannot hash non-directory: {root}")
    digest = hashlib.sha256()
    rels: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise InstallError(
                f"refusing package containing symlink: {rel!r}"
            )
        if path.is_file():
            rels.append(rel)
    for rel in sorted(rels):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\x00")
        file_hash = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\x00")
    digest.update(f"count={len(rels)}".encode("ascii"))
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# (f) least-privilege capability tokens (via telescript)
# ---------------------------------------------------------------------------


def capability_actions(granted: dict[str, Any]) -> list[str]:
    """Map a granted-permissions dict to telescript action patterns.

    Least privilege: only granted dimensions appear, each scoped as tightly
    as the pattern language allows (fs paths get per-path read/write
    wildcards).
    """
    actions: list[str] = []
    if granted.get("network"):
        actions.append("galaxy.net.*")
    if granted.get("subprocess"):
        actions.append("galaxy.subprocess.run")
    for path in granted.get("fs") or []:
        path = str(path).strip().strip("/")
        if not path or path == ".":
            path = "**"  # whole package tree; only reachable if policy allows it
        actions.append(f"galaxy.fs.read:{path}*")
        actions.append(f"galaxy.fs.write:{path}*")
    return actions


def issue_capability(
    package_id: str,
    granted: dict[str, Any],
    *,
    ttl_seconds: float = _DEFAULT_TOKEN_TTL,
) -> str:
    """Issue a telescript capability token for an installed package.

    Grantee is the package's namespaced id; actions are exactly the granted
    set (deny-closed: nothing granted => token permits nothing). Grant-time
    validation in :func:`telescript.issue` refuses malformed patterns.
    """
    return telescript.issue(
        _CAPABILITY_ISSUER,
        package_id,
        capability_actions(granted),
        ttl_seconds=ttl_seconds,
    )


def guarded_package_call(
    token: str,
    action: str,
    fn,
    *args: Any,
    expected_grantee: str | None = None,
    **kwargs: Any,
) -> Any:
    """Run ``fn`` only if ``token`` permits ``action`` (telescript guarded_call)."""
    return telescript.guarded_call(
        token, action, fn, *args, expected_grantee=expected_grantee, **kwargs
    )


# ---------------------------------------------------------------------------
# (a) source materialization
# ---------------------------------------------------------------------------

_GIT_URL_PREFIXES = ("http://", "https://", "git://", "ssh://", "git@")


def _is_git_url(source: str) -> bool:
    s = source.strip()
    return s.startswith(_GIT_URL_PREFIXES) or s.endswith(".git")


def _safe_members_tar(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = tar.getmembers()
    for m in members:
        name = m.name
        # zip-slip / tar-slip protection + no symlinks, deny-closed
        if os.path.isabs(name) or ".." in Path(name).parts:
            raise SourceError(f"archive member escapes package dir: {name!r}")
        if m.issym() or m.islnk():
            raise SourceError(f"archive member is a link (refused): {name!r}")
    return members


def _safe_members_zip(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    for info in infos:
        name = info.filename
        if os.path.isabs(name) or ".." in Path(name).parts:
            raise SourceError(f"archive member escapes package dir: {name!r}")
    return infos


def _materialize(source: PathLike, staging: Path) -> Path:
    """Copy/extract/clone ``source`` into ``staging/src``. Returns the dir."""
    src = os.fspath(source) if not isinstance(source, str) else source
    dest = staging / "src"
    dest.mkdir(parents=True, exist_ok=False)

    if _is_git_url(src):
        git = shutil.which("git")
        if git is None:
            raise SourceError("git URL source requires the 'git' binary")
        proc = subprocess.run(
            [git, "clone", "--depth", "1", src, str(dest)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            raise SourceError(f"git clone failed for {src!r}: {proc.stderr.strip()}")
        return dest

    if os.path.isdir(src):
        try:
            shutil.copytree(src, dest, dirs_exist_ok=True)
        except OSError as exc:
            raise SourceError(f"cannot copy source dir {src!r}: {exc}") from exc
        return dest

    if os.path.isfile(src):
        if tarfile.is_tarfile(src):
            try:
                with tarfile.open(src, "r") as tar:
                    # members are pre-validated by _safe_members_tar (deny-closed:
                    # no absolute paths, no "..", no symlinks), so the data
                    # filter's own checks are redundant; "fully_trusted" just
                    # silences the 3.14 deprecation notice.
                    tar.extractall(
                        dest, members=_safe_members_tar(tar), filter="fully_trusted"
                    )
            except (tarfile.TarError, OSError) as exc:
                raise SourceError(f"cannot extract tarball {src!r}: {exc}") from exc
            return dest
        if zipfile.is_zipfile(src):
            try:
                with zipfile.ZipFile(src, "r") as zf:
                    zf.extractall(dest, members=_safe_members_zip(zf))
            except (zipfile.BadZipFile, OSError) as exc:
                raise SourceError(f"cannot extract zip {src!r}: {exc}") from exc
            return dest
        raise SourceError(
            f"source file {src!r} is not a directory, .tar.gz/.tgz/.tar or .zip"
        )

    raise SourceError(f"source does not exist: {src!r}")


# ---------------------------------------------------------------------------
# (d) permission policy
# ---------------------------------------------------------------------------


def _normalize_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_POLICY)
    if policy:
        for key in ("network", "subprocess"):
            if key in policy:
                merged[key] = bool(policy[key])
        if "fs" in policy:
            fs = policy["fs"]
            if not isinstance(fs, (list, tuple)) or any(
                not isinstance(p, (str, os.PathLike)) for p in fs
            ):
                raise PermissionDenied("policy 'fs' must be a list of paths")
            merged["fs"] = [os.fspath(p) for p in fs]
    return merged


def _path_within(requested: str, allowed: str) -> bool:
    """True if ``requested`` is the same as or under ``allowed``."""
    if allowed in (".", ""):
        return True  # policy explicitly opened the whole tree
    r, a = Path(requested), Path(allowed)
    if r.is_absolute() != a.is_absolute():
        return False
    try:
        r.relative_to(a)
        return True
    except ValueError:
        return False


def _check_policy(manifest: Manifest, policy: dict[str, Any]) -> dict[str, Any]:
    """Refuse unless every requested permission is within the policy.

    Returns the granted-permissions dict (== requested, once the subset
    check passes): least privilege means granting only what was asked for.
    """
    req = manifest.permissions
    pid = manifest.namespaced_id

    if req.get("network") and not policy["network"]:
        raise PermissionDenied(
            f"{pid}: manifest requests network access but the install "
            "policy denies it"
        )
    if req.get("subprocess") and not policy["subprocess"]:
        raise PermissionDenied(
            f"{pid}: manifest requests subprocess access but the install "
            "policy denies it"
        )
    for want in req.get("fs") or []:
        if not any(_path_within(str(want), str(allow)) for allow in policy["fs"]):
            raise PermissionDenied(
                f"{pid}: manifest requests fs access to {want!r} which is "
                "outside the install policy's allowed paths"
            )

    return {
        "network": bool(req.get("network")),
        "fs": sorted({str(p) for p in (req.get("fs") or [])}),
        "subprocess": bool(req.get("subprocess")),
    }


# ---------------------------------------------------------------------------
# install()
# ---------------------------------------------------------------------------


def _registry_entries(registry: GalaxyRegistry) -> dict[str, RegistryEntry]:
    entries: dict[str, RegistryEntry] = {}
    for rec in registry.list():
        try:
            entries[rec["id"]] = RegistryEntry(
                namespaced_id=rec["id"],
                author=rec.get("author", ""),
                version=rec.get("version", ""),
            )
        except Exception:
            continue  # a malformed record never blocks resolution
    return entries


def install(
    source: PathLike,
    *,
    home: PathLike,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Install a Galaxy package. Returns the install record dict.

    ``home`` is the LEVI home (``~/.levi`` in production); the registry lives
    at ``<home>/galaxy/registry.jsonl`` and packages extract under
    ``<home>/galaxy/packages/<id>/<version>/``.

    Raises (deny-closed, precise):
      - :class:`SourceError` — source missing/unreadable/unextractable
      - :class:`PackageError` — manifest invalid (from levi.galaxy.package)
      - :class:`CollisionRefused` — namespace collision or resolution refusal
      - :class:`PermissionDenied` — requested permissions exceed the policy
      - :class:`InstallError` — hashing / copy / record failures
    """
    merged_policy = _normalize_policy(policy)
    home_path = Path(home).expanduser()

    with tempfile.TemporaryDirectory(prefix="galaxy-install-") as tmp:
        staging = Path(tmp)

        # (a) materialize
        src_dir = _materialize(source, staging)

        # (b) manifest — PackageError propagates with the sibling's wording
        manifest = load_manifest(src_dir)

        # (c) namespace: canonical id + collision + resolution policy
        package_id = to_namespaced(manifest.author, manifest.name)
        assert package_id == manifest.namespaced_id  # contract with package.py
        registry = GalaxyRegistry(home_path)
        entries = _registry_entries(registry)
        collision = check_collision(
            entries,
            package_id,
            candidate_author=manifest.author,
            candidate_version=manifest.version,
        )
        if collision is not None and collision.kind == "author_mismatch":
            raise CollisionRefused(collision.describe())
        candidate = RegistryEntry(
            namespaced_id=package_id,
            author=manifest.author,
            version=manifest.version,
        )
        resolution = resolve(entries.get(package_id), candidate)
        if not resolution.allowed:
            raise CollisionRefused(
                f"install refused for {package_id}: {resolution.reason}"
            )
        upgrading = resolution.action == "upgrade"

        # (d) permission policy -> granted (least privilege)
        granted = _check_policy(manifest, merged_policy)

        # (e) hash the materialized tree
        root_sha256 = hash_tree(src_dir)

        # (f) derive + grant-time-validate the capability actions via telescript
        # (the live token is issued at run time with issue_capability(); tokens
        # are session-scoped by default so nothing is persisted here)
        issue_capability(package_id, granted)

        # (g) copy into the packages dir and record
        packages_root = home_path / "galaxy" / "packages"
        package_root = packages_root / package_id
        dest = package_root / manifest.version
        if upgrading and package_root.exists():
            shutil.rmtree(package_root, ignore_errors=False)
        try:
            packages_root.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                raise InstallError(f"destination already exists: {dest}")
            shutil.copytree(src_dir, dest)
        except (OSError, InstallError) as exc:
            if isinstance(exc, InstallError):
                raise
            raise InstallError(f"cannot stage package into {dest}: {exc}") from exc

        try:
            record: dict[str, Any] = {
                "id": package_id,
                "version": manifest.version,
                "kind": manifest.kind,
                "author": manifest.author,
                "source": os.fspath(source) if not isinstance(source, str) else source,
                "root_sha256": root_sha256,
                "installed_at": datetime.now(timezone.utc).isoformat(),
                "granted": granted,
                # extras (superset of the shared contract) for registry search
                "description": manifest.description,
                "capabilities": list(manifest.capabilities),
            }
            registry.add(record)
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)
            raise

    return record


def verify_capability(
    token: str, action: str, expected_grantee: str | None = None
) -> bool:
    """Fail-closed check: does ``token`` permit ``action``? Never raises."""
    try:
        cap = telescript.verify(token, expected_grantee=expected_grantee)
    except telescript.CapabilityError:
        return False
    return telescript.permits(cap, action)
