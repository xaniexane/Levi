"""Capability manifests — the shared, no-silo-format capability record.

Every workstream declares what it can do in the SAME shape: a list of
capabilities, each exists/planned/retired (the ternary). Any sibling can
read any other workstream's manifest with plain json — no private
protocol, no privileged parser.

Register only what exists: a capability marked "exists" must actually be
built. Everything else stays "planned".
"""

from __future__ import annotations

from levi.legion_collective import conventions as C
from levi.legion_collective.registry import RegistryError, WorkstreamRegistry


def new_manifest(slug: str, capabilities: list[dict] | None = None) -> dict:
    """Build a manifest skeleton for a workstream. Capabilities added by owner."""
    return {
        "schema_version": C.SCHEMA_VERSION,
        "slug": slug,
        "capabilities": list(capabilities or []),
    }


def validate_manifest(data: dict) -> list[str]:
    """Return a list of problems; empty means valid."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["manifest must be a dict"]
    if data.get("schema_version") != C.SCHEMA_VERSION:
        errors.append(f"schema_version must be {C.SCHEMA_VERSION}")
    slug = data.get("slug")
    if not isinstance(slug, str) or not slug.strip():
        errors.append("slug must be a non-empty string")
    caps = data.get("capabilities")
    if not isinstance(caps, list):
        errors.append("capabilities must be a list")
        return errors
    seen: set[str] = set()
    for i, cap in enumerate(caps):
        where = f"capabilities[{i}]"
        if not isinstance(cap, dict):
            errors.append(f"{where} must be a dict")
            continue
        name = cap.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{where}.name must be a non-empty string")
        elif name in seen:
            errors.append(f"{where}.name duplicated: {name!r}")
        else:
            seen.add(name)
        if cap.get("status") not in C.CAP_STATUSES:
            errors.append(f"{where}.status must be one of {C.CAP_STATUSES}")
        detail = cap.get("detail", "")
        if not isinstance(detail, str):
            errors.append(f"{where}.detail must be a string")
        unknown = set(cap) - {"name", "status", "detail"}
        if unknown:
            errors.append(f"{where} unknown fields: {sorted(unknown)}")
    return errors


def attach(registry: WorkstreamRegistry, slug: str, manifest: dict, actor: str) -> dict:
    """Validate a manifest and store it on the workstream's registry entry."""
    errors = validate_manifest(manifest)
    if errors:
        raise RegistryError(f"invalid manifest: {errors}")
    if manifest["slug"] != slug:
        raise RegistryError("manifest slug does not match workstream slug")
    entry = registry.get(slug)
    if entry is None:
        raise RegistryError(f"unknown workstream: {slug}")
    return registry.set_capabilities(slug, manifest["capabilities"], actor)


def readable(slug: str, registry: WorkstreamRegistry) -> dict | None:
    """A sibling-readable manifest: plain dicts, same shape for everyone."""
    entry = registry.get(slug)
    if entry is None:
        return None
    return {
        "schema_version": C.SCHEMA_VERSION,
        "slug": slug,
        "title": entry["title"],
        "status": entry["status"],
        "capabilities": entry["capabilities"],
    }
