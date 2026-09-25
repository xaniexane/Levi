"""LEVI Galaxy — namespaced identity, collision detection, resolution policy.

A package's namespaced id is "<author>.<name>", e.g. "com.acme.cleaner".
Both segments are lowercase and must match ^[a-z0-9_.-]+$; the author must be
reverse-DNS (contain a dot) or a registered handle.

Because reverse-DNS authors contain dots themselves, parsing is ambiguous in
general ("a.b.c" could split several ways). This module uses the documented
convention: split on the LAST dot, so the name is the trailing segment and
everything before it is the author.

Deny-closed resolution: installing a package whose namespaced id is already
claimed by a DIFFERENT author is always refused (identity theft wins over
convenience). From the SAME author, a strictly higher semver version upgrades;
equal or lower versions are refused without an explicit override.

stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass

from levi.galaxy.package import SEGMENT_RE, PackageError, parse_version

# Policy names accepted by resolve(). Only "strict" is implemented for now;
# it is the deny-closed default. Additional policies may be added by sibling
# builders, but strict must remain the default.
POLICIES = ("strict",)


class NamespaceError(Exception):
    """Raised for malformed namespaced ids or unparseable names."""


@dataclass(frozen=True)
class RegistryEntry:
    """One installed package as seen by the Galaxy registry."""

    namespaced_id: str
    author: str
    version: str


@dataclass(frozen=True)
class Collision:
    """A detected identity collision between a candidate and the registry."""

    kind: str  # "author_mismatch" | "version_conflict"
    namespaced_id: str
    existing_author: str
    candidate_author: str
    existing_version: str
    candidate_version: str

    def describe(self) -> str:
        if self.kind == "author_mismatch":
            return (
                f"namespaced id {self.namespaced_id!r} is already claimed by "
                f"author {self.existing_author!r}; candidate claims "
                f"{self.candidate_author!r}"
            )
        return (
            f"package {self.namespaced_id!r} already registered at version "
            f"{self.existing_version!r}; candidate is {self.candidate_version!r}"
        )


@dataclass(frozen=True)
class Resolution:
    """Outcome of the install/upgrade resolution policy."""

    allowed: bool
    action: str  # "install" | "upgrade" | "refuse" | "reinstall"
    reason: str


def _check_author_shape(author: str, registered_handles=frozenset()) -> None:
    if not isinstance(author, str) or not author:
        raise NamespaceError("author must be a non-empty string")
    if not SEGMENT_RE.match(author):
        raise NamespaceError(
            f"author {author!r} has invalid characters "
            "(allowed: lowercase letters, digits, '.', '-', '_')"
        )
    if "." in author:
        if author.startswith(".") or author.endswith(".") or ".." in author:
            raise NamespaceError(f"author {author!r} is not well-formed reverse-DNS")
    elif author not in registered_handles:
        raise NamespaceError(
            f"author {author!r} is neither reverse-DNS (no dot) nor a registered handle"
        )


def to_namespaced(author: str, name: str, registered_handles=frozenset()) -> str:
    """Build a namespaced id "<author>.<name>", validating both halves."""
    _check_author_shape(author, registered_handles)
    if not isinstance(name, str) or not name:
        raise NamespaceError("name must be a non-empty string")
    if not SEGMENT_RE.match(name):
        raise NamespaceError(
            f"name {name!r} has invalid characters "
            "(allowed: lowercase letters, digits, '.', '-', '_')"
        )
    return f"{author}.{name}"


def parse_namespaced(namespaced_id: str) -> tuple[str, str]:
    """Split a namespaced id into (author, name) on the LAST dot.

    Raises NamespaceError if the id is malformed. Note: because authors are
    themselves dotted, an id with more than one dot is only unambiguous under
    this last-dot convention — see module docstring.
    """
    if not isinstance(namespaced_id, str) or not namespaced_id:
        raise NamespaceError("namespaced id must be a non-empty string")
    if not SEGMENT_RE.match(namespaced_id):
        raise NamespaceError(
            f"namespaced id {namespaced_id!r} has invalid characters "
            "(allowed: lowercase letters, digits, '.', '-', '_')"
        )
    if "." not in namespaced_id:
        raise NamespaceError(
            f"namespaced id {namespaced_id!r} must be '<author>.<name>'"
        )
    author, name = namespaced_id.rsplit(".", 1)
    if not author or not name:
        raise NamespaceError(
            f"namespaced id {namespaced_id!r} has an empty author or name"
        )
    return author, name


def _entries(registry_ids) -> list[RegistryEntry]:
    """Normalize the registry argument to a list of RegistryEntry."""
    if isinstance(registry_ids, dict):
        out = []
        for nid, rec in registry_ids.items():
            if isinstance(rec, RegistryEntry):
                out.append(rec)
            elif isinstance(rec, dict):
                out.append(
                    RegistryEntry(
                        namespaced_id=nid,
                        author=rec.get("author", ""),
                        version=rec.get("version", ""),
                    )
                )
            else:  # assume a (author, version) tuple
                author, version = rec
                out.append(
                    RegistryEntry(namespaced_id=nid, author=author, version=version)
                )
        return out
    return list(registry_ids)


def check_collision(
    registry_ids,
    namespaced_id: str,
    *,
    candidate_author: str | None = None,
    candidate_version: str | None = None,
) -> Collision | None:
    """Detect a collision between a candidate package and the registry.

    `registry_ids` is a dict {namespaced_id: RegistryEntry | dict | (author,
    version)} or an iterable of RegistryEntry.

    The candidate author defaults to the author parsed out of `namespaced_id`
    itself; pass `candidate_author` explicitly when the candidate's manifest
    author may differ from the id it claims (the impersonation case). The
    candidate version likewise defaults to None, in which case version
    differences are not checked (they need the candidate's manifest version).

    Case 1 (author_mismatch): the id is already claimed in the registry by a
    different author — e.g. candidate manifest says author "evil.com" but the
    id "com.acme.cleaner" is registered to "com.acme". Always suspicious.
    Case 2 (version_conflict): same author, same id, but the registered
    version differs from the candidate's — an upgrade/downgrade/reinstall
    decision, handed to resolve().
    """
    if candidate_author is None:
        candidate_author, _ = parse_namespaced(namespaced_id)
    entries = _entries(registry_ids)
    for entry in entries:
        if entry.namespaced_id != namespaced_id:
            continue
        if entry.author != candidate_author:
            return Collision(
                kind="author_mismatch",
                namespaced_id=namespaced_id,
                existing_author=entry.author,
                candidate_author=candidate_author,
                existing_version=entry.version,
                candidate_version=candidate_version or "",
            )
        if candidate_version is not None and entry.version != candidate_version:
            return Collision(
                kind="version_conflict",
                namespaced_id=namespaced_id,
                existing_author=entry.author,
                candidate_author=candidate_author,
                existing_version=entry.version,
                candidate_version=candidate_version,
            )
        return None
    return None


def _compare_versions(existing: str, candidate: str) -> int:
    """Compare two validated versions: -1 / 0 / +1 (existing vs candidate)."""
    try:
        e_nums, e_pre = parse_version(existing)
    except PackageError as exc:
        raise NamespaceError(f"existing registry version is invalid: {exc}") from exc
    try:
        c_nums, c_pre = parse_version(candidate)
    except PackageError as exc:
        raise NamespaceError(f"candidate version is invalid: {exc}") from exc
    if e_nums != c_nums:
        return -1 if e_nums < c_nums else 1
    # Numeric parts equal: a release beats any pre-release; pre-releases
    # compare lexicographically by identifier.
    if e_pre == c_pre:
        return 0
    if not e_pre:
        return 1  # existing is the release, candidate is pre-release: no upgrade
    if not c_pre:
        return -1  # candidate is the release: upgrade
    return -1 if e_pre < c_pre else 1


def resolve(
    existing: RegistryEntry | None,
    candidate: RegistryEntry,
    *,
    policy: str = "strict",
) -> Resolution:
    """Decide install/upgrade for `candidate` against an existing registry entry.

    Deny-closed default ("strict"):
      - no existing entry            -> install allowed
      - different author on same id  -> REFUSED (identity claim conflict)
      - same author, higher semver   -> upgrade allowed
      - same author, equal version   -> refused ("already installed")
      - same author, lower semver    -> refused ("downgrade denied")
    """
    if policy not in POLICIES:
        raise NamespaceError(
            f"unknown resolution policy {policy!r}; known: {', '.join(POLICIES)}"
        )
    if existing is None:
        return Resolution(
            allowed=True,
            action="install",
            reason=f"{candidate.namespaced_id} is not registered; fresh install",
        )
    if existing.namespaced_id != candidate.namespaced_id:
        return Resolution(
            allowed=False,
            action="refuse",
            reason=(
                f"existing entry {existing.namespaced_id!r} does not match "
                f"candidate {candidate.namespaced_id!r}"
            ),
        )
    if existing.author != candidate.author:
        return Resolution(
            allowed=False,
            action="refuse",
            reason=(
                f"namespaced id {candidate.namespaced_id!r} is claimed by "
                f"author {existing.author!r}; candidate author "
                f"{candidate.author!r} refused"
            ),
        )
    cmp = _compare_versions(existing.version, candidate.version)
    if cmp < 0:
        return Resolution(
            allowed=True,
            action="upgrade",
            reason=(
                f"candidate {candidate.version} is newer than "
                f"registered {existing.version}"
            ),
        )
    if cmp == 0:
        return Resolution(
            allowed=False,
            action="refuse",
            reason=(
                f"{candidate.namespaced_id} version {candidate.version} "
                "is already installed"
            ),
        )
    return Resolution(
        allowed=False,
        action="refuse",
        reason=(
            f"candidate {candidate.version} is older than registered "
            f"{existing.version}; downgrade denied"
        ),
    )
