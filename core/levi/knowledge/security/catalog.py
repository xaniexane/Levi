"""Validated loader for the offline security knowledge catalog.

The catalog lives next to this module as ``catalog.json`` and is the
offline security-knowledge index: 81 defensive domains distilled from the
Awesome-Hacking meta-list's category names. Every entry is defensive
blue-team content (detection/analysis/hardening); entries flagged
``attack_relevant`` additionally carry an ``attack_profile`` that
describes *what the attack looks like* so defenders can recognize it —
knowledge of attacks, never instructions.

This loader validates the file structurally and raises :class:`CatalogError`
with an actionable message instead of letting malformed data through or
crashing with a raw ``json``/``KeyError`` traceback. It never rewrites
``catalog.json`` — prose stays exactly as curated.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

CATALOG_PATH = Path(__file__).resolve().parent / "catalog.json"
REFERENCE_PREFIX = "Hack-with-Github/Awesome-Hacking -> "
_ID_RE = re.compile(r"^[a-z0-9-]+$")

PathLike = Union[str, Path]


class CatalogError(Exception):
    """Raised when catalog.json is missing, unparsable, or fails schema validation."""


@dataclass(frozen=True)
class SecurityDomain:
    """One validated catalog entry."""

    id: str
    name: str
    defensive_summary: str
    detection_notes: str
    hardening_notes: str
    key_concepts: tuple = field(default_factory=tuple)
    reference: str = ""
    attack_relevant: bool = False
    attack_profile: str = ""


@dataclass
class SecurityCatalog:
    """The validated catalog: 81 defensive security domains."""

    domains: List[SecurityDomain] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.domains)

    def __iter__(self) -> Iterator[SecurityDomain]:
        return iter(self.domains)

    def ids(self) -> List[str]:
        """All domain ids, in catalog order."""
        return [d.id for d in self.domains]

    def get(self, domain_id: str) -> Optional[SecurityDomain]:
        """Return the domain with ``domain_id``, or None."""
        for d in self.domains:
            if d.id == domain_id:
                return d
        return None

    def attack_relevant(self) -> List[SecurityDomain]:
        """Domains flagged as attack-relevant (carry an attack_profile)."""
        return [d for d in self.domains if d.attack_relevant]


def _fail(index: int, entry_id: Optional[str], message: str) -> CatalogError:
    where = f"entry #{index}"
    if entry_id:
        where += f" (id={entry_id!r})"
    return CatalogError(f"security catalog invalid: {where}: {message}")


def _require_str(
    raw: Dict[str, Any], key: str, index: int, entry_id: Optional[str]
) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _fail(index, entry_id, f"{key!r} must be a non-empty string")
    return value


def _validate_entry(raw: Any, index: int) -> SecurityDomain:
    if not isinstance(raw, dict):
        raise _fail(index, None, f"entry must be an object, got {type(raw).__name__}")
    entry_id = raw.get("id")
    if not isinstance(entry_id, str) or not entry_id:
        raise _fail(index, None, "'id' must be a non-empty string")
    if not _ID_RE.match(entry_id):
        raise _fail(
            index,
            entry_id,
            "'id' must be kebab-case ([a-z0-9-]), e.g. 'web-application-security'",
        )

    name = _require_str(raw, "name", index, entry_id)
    defensive_summary = _require_str(raw, "defensive_summary", index, entry_id)
    if len(defensive_summary) < 100:
        raise _fail(
            index,
            entry_id,
            f"'defensive_summary' too short ({len(defensive_summary)} chars, "
            "minimum 100)",
        )
    detection_notes = _require_str(raw, "detection_notes", index, entry_id)
    hardening_notes = _require_str(raw, "hardening_notes", index, entry_id)

    concepts = raw.get("key_concepts")
    if not isinstance(concepts, list) or not all(
        isinstance(c, str) and c.strip() for c in concepts
    ):
        raise _fail(
            index, entry_id, "'key_concepts' must be a list of non-empty strings"
        )
    if not 3 <= len(concepts) <= 8:
        raise _fail(
            index,
            entry_id,
            f"'key_concepts' must hold 3-8 concepts, got {len(concepts)}",
        )

    reference = _require_str(raw, "reference", index, entry_id)
    if not reference.startswith(REFERENCE_PREFIX):
        raise _fail(
            index,
            entry_id,
            f"'reference' must start with {REFERENCE_PREFIX!r}",
        )

    attack_relevant = raw.get("attack_relevant")
    if type(attack_relevant) is not bool:
        raise _fail(
            index,
            entry_id,
            f"'attack_relevant' must be a boolean, got {attack_relevant!r}",
        )

    profile = raw.get("attack_profile", "")
    if attack_relevant:
        if not isinstance(profile, str) or len(profile.strip()) < 200:
            got = len(profile.strip()) if isinstance(profile, str) else "non-string"
            raise _fail(
                index,
                entry_id,
                f"attack_relevant entry must carry 'attack_profile' of at "
                f"least 200 chars (got {got})",
            )
        attack_profile = profile
    else:
        if isinstance(profile, str) and profile.strip():
            raise _fail(
                index,
                entry_id,
                "defense-only entry must not carry a non-empty 'attack_profile'",
            )
        attack_profile = ""

    return SecurityDomain(
        id=entry_id,
        name=name,
        defensive_summary=defensive_summary,
        detection_notes=detection_notes,
        hardening_notes=hardening_notes,
        key_concepts=tuple(concepts),
        reference=reference,
        attack_relevant=attack_relevant,
        attack_profile=attack_profile,
    )


def load_catalog(path: Optional[PathLike] = None) -> SecurityCatalog:
    """Load and validate the security knowledge catalog.

    Raises :class:`CatalogError` when the file is missing, is not valid
    JSON, or fails schema validation (missing keys, wrong types, bad ids,
    duplicate ids, attack-profile inconsistencies). Never returns a
    partially-validated catalog.
    """
    catalog_path = Path(path) if path is not None else CATALOG_PATH
    try:
        text = catalog_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CatalogError(
            f"security catalog not found at {catalog_path}; "
            "expected catalog.json next to the loader"
        ) from exc
    except OSError as exc:
        raise CatalogError(
            f"cannot read security catalog at {catalog_path}: {exc}"
        ) from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CatalogError(
            f"security catalog at {catalog_path} is not valid JSON: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise CatalogError(
            "security catalog invalid: top level must be an object "
            f"with an 'entries' list, got {type(raw).__name__}"
        )
    entries = raw.get("entries")
    if not isinstance(entries, list) or not entries:
        raise CatalogError(
            "security catalog invalid: 'entries' must be a non-empty list"
        )

    domains: List[SecurityDomain] = []
    seen: Dict[str, int] = {}
    for index, entry in enumerate(entries):
        domain = _validate_entry(entry, index)
        if domain.id in seen:
            raise CatalogError(
                f"security catalog invalid: duplicate id {domain.id!r} "
                f"(entries #{seen[domain.id]} and #{index})"
            )
        seen[domain.id] = index
        domains.append(domain)
    return SecurityCatalog(domains=domains)
