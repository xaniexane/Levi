"""Universal provider references — plug any external provider into LEVI.

Binding identity rule (Chauncey, 2026-09-15): provider and model names —
KAI-9000, Qwen, LLaMA, Pollinations, anything else — are **references**,
never sources: pointers for comparison or attribution, never LEVI
branding, registers, personas, voices, or claimed origins. LEVI is
sourced from itself.

This module is the ONE universal plug-in point for that rule. Any
subsystem that touches an external provider — MCP client servers, plugin
connectors, model downloads, media adapters — records the provider here
as a reference, and every display path labels it as one. A reference can
never be presented as LEVI identity: :func:`assert_not_levi_identity`
rejects any reference name or id that collides with LEVI's own
registers.

Records live in ``~/.levi/references.json`` (owner-only 0o600), written
atomically. stdlib-only.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_NORM_RE = re.compile(r"[^a-z0-9]+")

#: Allowed reference kinds — every subsystem that plugs a provider in
#: uses one of these, so `levi reference list` shows the whole picture.
KINDS = ("mcp-server", "plugin", "model", "media", "other")


class ReferenceError(Exception):
    """A provider reference was invalid or collided with LEVI identity."""


def _home() -> Path:
    return Path.home()


def _refs_file(home: Optional[Path] = None) -> Path:
    return (Path(home) if home else _home()) / ".levi" / "references.json"


# ---------------------------------------------------------------------------
# LEVI-identity guard
# ---------------------------------------------------------------------------


def _levi_identity_tokens() -> set[str]:
    """Normalized tokens that are LEVI's own identity — off-limits.

    Lazily imports the persona registers so this module never creates an
    import cycle (persona/ must stay dependency-light).
    """
    tokens: set[str] = set()
    try:
        from levi.persona.levi import all_variants

        for v in all_variants():
            tokens.add(_NORM_RE.sub("", v.id.lower()))
            tokens.add(_NORM_RE.sub("", v.name.lower()))
    except Exception:
        pass
    tokens.add("levi")
    return {t for t in tokens if t}


def assert_not_levi_identity(name: str, *, what: str = "reference") -> str:
    """Reject ``name`` when it collides with LEVI's own identity.

    Comparison is case-insensitive and ignores separators, so ``LEVI``,
    ``levi-care`` and ``LeviCare`` all collide with the ``levi_care``
    register. Raises :class:`ReferenceError` on collision; returns the
    stripped name otherwise.
    """
    cleaned = (name or "").strip()
    if not cleaned:
        raise ReferenceError(f"{what} name must not be blank")
    norm = _NORM_RE.sub("", cleaned.lower())
    if norm in _levi_identity_tokens():
        raise ReferenceError(
            f"{what} {cleaned!r} collides with LEVI's own identity — "
            "provider references are never LEVI registers, personas, or "
            "branding. Pick a name that is clearly the external provider."
        )
    return cleaned


def validate_provider_name(provider: str) -> str:
    """Validate an external provider name as a reference label."""
    provider = (provider or "").strip()
    if not provider or len(provider) > 120:
        raise ReferenceError("provider reference name must be 1-120 characters")
    if any(ord(c) < 32 for c in provider):
        raise ReferenceError("provider reference name must not contain control chars")
    return assert_not_levi_identity(provider, what="provider reference")


def _validate_id(ref_id: str) -> str:
    if not isinstance(ref_id, str) or not _ID_RE.match(ref_id):
        raise ReferenceError(
            f"invalid reference id {ref_id!r}: use 1-64 chars of [A-Za-z0-9_-]"
        )
    assert_not_levi_identity(ref_id, what="reference id")
    return ref_id


def slug_for(provider: str) -> str:
    """Default local id for a provider: ``ref-<slug>``."""
    slug = _SLUG_RE.sub("-", provider.strip().lower()).strip("-") or "provider"
    return f"ref-{slug}"[:64]


# ---------------------------------------------------------------------------
# Record type + store
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderReference:
    """One external provider, plugged in as a reference — never a source."""

    id: str
    provider: str  # external name, as the provider calls itself
    kind: str  # one of KINDS
    detail: dict[str, Any] = field(default_factory=dict)
    added_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "kind": self.kind,
            "detail": dict(self.detail),
            "added_at": self.added_at,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ProviderReference":
        return ProviderReference(
            id=str(data.get("id", "")),
            provider=str(data.get("provider", "")),
            kind=str(data.get("kind", "other")),
            detail=dict(data.get("detail") or {}),
            added_at=float(data.get("added_at") or 0.0),
        )


def load_references(home: Optional[Path] = None) -> dict[str, ProviderReference]:
    """Return {id: ProviderReference}; {} when no store exists."""
    path = _refs_file(home)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ReferenceError(f"cannot read references file {path}: {exc}") from exc
    refs: dict[str, ProviderReference] = {}
    items = (data or {}).get("references", {})
    if isinstance(items, dict):
        for rid, raw in items.items():
            if isinstance(raw, dict):
                try:
                    refs[str(rid)] = ProviderReference.from_dict(raw)
                except (ValueError, TypeError):
                    continue
    return refs


def save_references(
    refs: dict[str, ProviderReference], home: Optional[Path] = None
) -> Path:
    """Atomically write references.json owner-only (0o600)."""
    path = _refs_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_suffix(".json.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(
                {"references": {k: v.to_dict() for k, v in refs.items()}},
                fh,
                indent=2,
                sort_keys=True,
            )
            fh.write("\n")
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    os.replace(tmp, path)
    return path


def add_reference(
    provider: str,
    kind: str = "other",
    detail: Optional[dict[str, Any]] = None,
    ref_id: Optional[str] = None,
    home: Optional[Path] = None,
) -> ProviderReference:
    """Plug a provider in as a reference. Returns the stored record.

    ``kind`` must be one of :data:`KINDS`. When ``ref_id`` is omitted it
    is derived as ``ref-<slug>`` from the provider name (deduplicated).
    """
    provider = validate_provider_name(provider)
    kind = (kind or "other").strip().lower()
    if kind not in KINDS:
        raise ReferenceError(f"unknown reference kind {kind!r} (one of {KINDS})")
    refs = load_references(home)
    rid = _validate_id(ref_id) if ref_id else slug_for(provider)
    base, n = rid, 2
    while rid in refs:
        rid = f"{base}-{n}"
        n += 1
    ref = ProviderReference(
        id=rid, provider=provider, kind=kind, detail=dict(detail or {})
    )
    refs[rid] = ref
    save_references(refs, home)
    return ref


def remove_reference(ref_id: str, home: Optional[Path] = None) -> None:
    """Unplug a reference. Raises ReferenceError when unknown."""
    rid = _validate_id(ref_id)
    refs = load_references(home)
    if rid not in refs:
        raise ReferenceError(f"unknown provider reference {rid!r}")
    del refs[rid]
    save_references(refs, home)


def remove_references_where(
    predicate: Any, home: Optional[Path] = None
) -> list[str]:
    """Remove every reference matching ``predicate``; return removed ids."""
    refs = load_references(home)
    doomed = [rid for rid, r in refs.items() if predicate(r)]
    for rid in doomed:
        del refs[rid]
    if doomed:
        save_references(refs, home)
    return doomed


def list_references(home: Optional[Path] = None) -> dict[str, ProviderReference]:
    """Return {id: ProviderReference} for every plugged-in reference."""
    return load_references(home)


def get_reference(ref_id: str, home: Optional[Path] = None) -> Optional[ProviderReference]:
    """Return one reference by id, or None."""
    return load_references(home).get(_validate_id(ref_id))


def describe(ref: ProviderReference) -> str:
    """One human-readable block — always labeled as a reference."""
    detail = ref.detail
    where = (
        detail.get("url")
        or detail.get("target")
        or " ".join(detail.get("command", []) or [])
        or detail.get("note", "")
    )
    lines = [
        f"{ref.id} — reference: {ref.provider}  [{ref.kind}]",
        "  (external provider reference — never a LEVI source or identity)",
    ]
    if where:
        lines.append(f"  via: {where}")
    return "\n".join(lines)
