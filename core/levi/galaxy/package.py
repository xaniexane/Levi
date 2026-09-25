"""LEVI Galaxy — package manifest loading and strict validation.

Manifest contract (levi-skill.json):
    {"name": str, "version": str (semver-ish), "kind": "skill"|"tool"|"service",
     "description": str,
     "author": str (reverse-DNS or registered handle),
     "entry_points": {"verb": "module:function" or relative script path},
     "capabilities": [action-pattern strings],
     "permissions": {"network": bool, "fs": [rel paths], "subprocess": bool},
     "min_levi_version": str}

Deny-closed: a malformed manifest, a missing required field, a bad version,
an unknown kind, or an invalid entry_point raises PackageError with a precise
reason. `validate_manifest` returns the same complaints as a list (empty ==
valid) so callers can batch-report; `load_manifest` raises on the first
problem instead.

stdlib-only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_FILENAME = "levi-skill.json"

VALID_KINDS = ("skill", "tool", "service")

REQUIRED_FIELDS = (
    "name",
    "version",
    "kind",
    "description",
    "author",
    "entry_points",
    "capabilities",
    "permissions",
    "min_levi_version",
)

PERMISSION_FIELDS = ("network", "fs", "subprocess")

# A namespaced segment (both halves of "<author>.<name>") and the manifest
# name itself: lowercase, digits, dots, dashes, underscores.
SEGMENT_RE = re.compile(r"^[a-z0-9_.-]+$")

# Semver-ish: 1, 2 or 3 numeric components, optional pre-release / build.
# "1.0" and "2" are accepted as lenient shorthands for "1.0.0" / "2.0.0";
# anything less structured ("latest", "v1", "1.0.0.0") is refused.
VERSION_RE = re.compile(
    r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){0,2}"
    r"(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$"
)

# module:function targets, e.g. "levi_skills.acme.clean:run"
MODULE_FUNC_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")

# Verb keys in entry_points, e.g. "clean", "analyze-text".
VERB_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

# Action-pattern strings in capabilities, e.g. "finance.quote.*"
CAPABILITY_RE = re.compile(r"^[A-Za-z0-9_.*:-]+$")


class PackageError(Exception):
    """Raised for any malformed or invalid package manifest."""


@dataclass(frozen=True)
class Manifest:
    """A validated package manifest."""

    name: str
    version: str
    kind: str
    description: str
    author: str
    entry_points: dict
    capabilities: tuple
    permissions: dict
    min_levi_version: str
    source_dir: Path = field(compare=False)

    @property
    def namespaced_id(self) -> str:
        # Kept in sync with levi.galaxy.namespace.to_namespaced().
        return f"{self.author}.{self.name}"

    def entry_path(self, verb: str) -> Path:
        """Resolve an entry_point target to an absolute path inside source_dir.

        Raises PackageError for unknown verbs and KeyError-behaving lookups;
        returns only module:function targets as the literal target string's
        module half — callers that need a filesystem path for a module target
        should resolve it themselves via import machinery.
        """
        target = self.entry_points[verb]
        if ":" in target:
            raise PackageError(
                f"entry_point {verb!r} is a module target {target!r}; "
                "no filesystem path exists for it"
            )
        return self.source_dir / target


def parse_version(version: str) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """Parse a validated version into ((major, minor, patch), (prerelease...)).

    Raises PackageError if the version is not semver-ish. Missing numeric
    components are zero-filled so "1.0" compares equal to "1.0.0".
    """
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise PackageError(f"bad version {version!r}: must be semver-ish")
    core = version.split("+", 1)[0]
    if "-" in core:
        core, pre = core.split("-", 1)
        prerelease = tuple(pre.split("."))
    else:
        prerelease = ()
    nums = tuple(int(p) for p in core.split("."))
    nums = nums + (0,) * (3 - len(nums))
    return nums, prerelease


def _err(errors: list, message: str) -> None:
    errors.append(message)


def _check_author(author, errors: list, registered_handles=frozenset()) -> None:
    if not isinstance(author, str) or not author:
        _err(errors, "author must be a non-empty string")
        return
    if not SEGMENT_RE.match(author):
        _err(
            errors,
            f"author {author!r} has invalid characters "
            "(allowed: lowercase letters, digits, '.', '-', '_')",
        )
        return
    if "." in author:
        bad = [seg for seg in author.split(".") if not re.match(r"^[a-z0-9_-]+$", seg)]
        if bad:
            _err(errors, f"author {author!r} has invalid reverse-DNS segments: {bad}")
        if author.startswith(".") or author.endswith(".") or ".." in author:
            _err(errors, f"author {author!r} is not well-formed reverse-DNS")
    elif author not in registered_handles:
        _err(
            errors,
            f"author {author!r} is neither reverse-DNS (no dot) "
            "nor a registered handle",
        )


def _check_entry_points(data, errors: list, source_dir: Path | None) -> None:
    eps = data.get("entry_points")
    if not isinstance(eps, dict):
        _err(errors, "entry_points must be an object mapping verb -> target")
        return
    if not eps:
        _err(errors, "entry_points must define at least one verb")
    for verb, target in eps.items():
        if not isinstance(verb, str) or not VERB_RE.match(verb):
            _err(errors, f"entry_points has invalid verb {verb!r}")
        if not isinstance(target, str) or not target:
            _err(errors, f"entry_points[{verb!r}] must be a non-empty string")
            continue
        if ":" in target:
            if not MODULE_FUNC_RE.match(target):
                _err(
                    errors,
                    f"entry_points[{verb!r}] target {target!r} is not "
                    "valid 'module:function' form",
                )
        else:
            # Relative script path: must stay inside the package directory.
            p = Path(target)
            if p.is_absolute() or ".." in p.parts or target.startswith("~"):
                _err(
                    errors,
                    f"entry_points[{verb!r}] script path {target!r} must be "
                    "a relative path inside the package directory",
                )
            elif source_dir is not None and not (source_dir / target).is_file():
                _err(
                    errors,
                    f"entry_points[{verb!r}] script {target!r} does not exist "
                    f"in {source_dir}",
                )


def _check_capabilities(data, errors: list) -> None:
    caps = data.get("capabilities")
    if not isinstance(caps, list):
        _err(errors, "capabilities must be a list of action-pattern strings")
        return
    for cap in caps:
        if not isinstance(cap, str) or not cap:
            _err(errors, f"capabilities contains invalid entry {cap!r}")
        elif not CAPABILITY_RE.match(cap):
            _err(errors, f"capabilities entry {cap!r} has invalid characters")


def _check_permissions(data, errors: list) -> None:
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        _err(errors, "permissions must be an object")
        return
    for key in perms:
        if key not in PERMISSION_FIELDS:
            _err(errors, f"permissions has unknown key {key!r}")
    for key in PERMISSION_FIELDS:
        if key not in perms:
            _err(errors, f"permissions is missing required key {key!r}")
    net = perms.get("network")
    if "network" in perms and not isinstance(net, bool):
        _err(errors, "permissions.network must be a boolean")
    sub = perms.get("subprocess")
    if "subprocess" in perms and not isinstance(sub, bool):
        _err(errors, "permissions.subprocess must be a boolean")
    fs = perms.get("fs")
    if "fs" in perms:
        if not isinstance(fs, list) or any(not isinstance(p, str) for p in fs):
            _err(errors, "permissions.fs must be a list of relative paths")
        else:
            for p in fs:
                path = Path(p)
                if path.is_absolute() or ".." in path.parts or p.startswith("~"):
                    _err(
                        errors,
                        f"permissions.fs entry {p!r} must be a relative path "
                        "inside the package directory",
                    )


def validate_manifest(data, registered_handles=frozenset()) -> list:
    """Return a list of error strings describing why `data` is invalid.

    Empty list means valid. `data` should be the parsed JSON object.
    `registered_handles` is the set of known non-reverse-DNS author handles;
    a dot-less author not in this set is refused.
    """
    errors: list = []
    if not isinstance(data, dict):
        return ["manifest must be a JSON object"]
    for field_name in REQUIRED_FIELDS:
        if field_name not in data:
            _err(errors, f"missing required field {field_name!r}")
    unknown = [k for k in data if k not in REQUIRED_FIELDS]
    for key in unknown:
        _err(errors, f"unknown field {key!r}")

    name = data.get("name")
    if "name" in data:
        if not isinstance(name, str) or not name:
            _err(errors, "name must be a non-empty string")
        elif not SEGMENT_RE.match(name):
            _err(
                errors,
                f"name {name!r} has invalid characters "
                "(allowed: lowercase letters, digits, '.', '-', '_')",
            )

    if "version" in data:
        try:
            parse_version(data["version"])
        except PackageError as exc:
            _err(errors, str(exc))

    if "kind" in data and data["kind"] not in VALID_KINDS:
        _err(
            errors,
            f"kind {data['kind']!r} is unknown; must be one of "
            f"{', '.join(VALID_KINDS)}",
        )

    if "description" in data:
        desc = data["description"]
        if not isinstance(desc, str) or not desc.strip():
            _err(errors, "description must be a non-empty string")

    if "author" in data:
        _check_author(data["author"], errors, registered_handles)

    if "entry_points" in data:
        _check_entry_points(data, errors, source_dir=None)

    if "capabilities" in data:
        _check_capabilities(data, errors)

    if "permissions" in data:
        _check_permissions(data, errors)

    if "min_levi_version" in data:
        try:
            parse_version(data["min_levi_version"])
        except PackageError as exc:
            _err(errors, f"min_levi_version: {exc}")

    return errors


def load_manifest(directory, registered_handles=frozenset()) -> Manifest:
    """Load and strictly validate levi-skill.json from `directory`.

    Raises PackageError with a precise reason on any problem: missing or
    unreadable file, invalid JSON, schema violations, or entry-point script
    paths that do not exist on disk.
    """
    source_dir = Path(directory)
    manifest_path = source_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise PackageError(
            f"manifest not found: {manifest_path} does not exist or is not a file"
        )
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PackageError(f"cannot read manifest {manifest_path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PackageError(
            f"manifest {manifest_path} is not valid JSON: {exc}"
        ) from exc

    errors = validate_manifest(data, registered_handles)
    # Script-path entry points must exist on disk (deny-closed); this check
    # needs the directory, which validate_manifest() does not have.
    if isinstance(data, dict) and "entry_points" in data:
        _check_entry_points(data, errors, source_dir)

    if errors:
        detail = "; ".join(errors)
        raise PackageError(f"invalid manifest {manifest_path}: {detail}")

    return Manifest(
        name=data["name"],
        version=data["version"],
        kind=data["kind"],
        description=data["description"],
        author=data["author"],
        entry_points=dict(data["entry_points"]),
        capabilities=tuple(data["capabilities"]),
        permissions=dict(data["permissions"]),
        min_levi_version=data["min_levi_version"],
        source_dir=source_dir,
    )
