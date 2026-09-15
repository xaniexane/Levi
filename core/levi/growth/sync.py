"""Learning sync — the distribution half of LEVI's collective learning.

The harvest half (this package: harvest → redact → reflect → consolidate)
turns consented sessions into technique-only procedural learnings in the
local memory store. This module ships those learnings to OTHER LEVI
instances as versioned learning packs:

    harvest → pack (publisher) → cloud transport → ingest (receiver)

Batched and versioned — never real-time.

Privacy line (binding):

* Only TECHNIQUE travels. Personal facts, preferences, verbatim session
  text, and anything user-identifiable are HARD EXCLUDED — once at
  consolidation (the ``shareable`` mark) and again at pack build
  (re-verification). Either gate alone is sufficient; both run.
* Packs carry aggregate counts only: ``corroborated_sources`` (int) and
  ``source_types`` (``{"cloud": n, "local": n}``). No user ids, no key
  names, no session ids, no raw provenance leaves the machine.
* Ingested learnings are marked ``shareable=False``: the collective
  never re-packs what it received, so corroboration cannot echo-chamber.
* Contributing is opt-in. Cloud-distilled learnings pack by default
  (consent was given at key creation and the content was redacted
  before reflection). The owner's own local learnings pack only with
  ``LEVI_GROWTH_CONTRIBUTE=1``.
* Receiving is on with opt-out: ``LEVI_GROWTH_RECEIVE=0`` disables
  ingest.

Integrity: packs are canonical-JSON SHA-256 hashed; the manifest pins
the hash. Ingest rejects tampered packs and any version that is not
newer than the newest installed pack.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

from levi.growth.consolidate import (
    _jaccard,
    _words,
    contribute_enabled,
    shareable_learning,
)
from levi.growth.redact import redact_text

try:
    from levi.memory.store import MemoryStore
    from levi.memory.types import MemoryType
except Exception:  # pragma: no cover — memory package is stdlib-only too
    MemoryStore = None  # type: ignore
    MemoryType = None  # type: ignore


PACK_FORMAT = "levi-learning-pack/1"
MANIFEST_FORMAT = "levi-learning-manifest/1"
PACK_PREFIX = "learning-pack-"


class PackError(Exception):
    """The pack is tampered, stale, malformed, or policy-blocked."""


# ---------------------------------------------------------------------------
# Policy switches
# ---------------------------------------------------------------------------
# contribute_enabled() / shareable_learning() live in
# levi.growth.consolidate (single source of truth); re-exported here
# for the publisher-side API.

__all__ = [
    "PackError",
    "contribute_enabled",
    "receive_enabled",
    "shareable_learning",
    "build_pack",
    "collect_shareable",
    "fetch_latest_pack",
    "identifier_risk",
    "ingest_pack",
    "ingest_pack_file",
    "installed_packs",
    "latest_pack_payload",
    "packs_dir",
    "sync_from_server",
    "verify_pack",
]


def receive_enabled() -> bool:
    """Receiving is on with opt-out: ``LEVI_GROWTH_RECEIVE=0`` disables."""
    return os.environ.get("LEVI_GROWTH_RECEIVE", "1").strip().lower() not in (
        "0", "false", "no",
    )


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def packs_dir() -> Path:
    """``~/.levi/cloud/learning_packs`` (``LEVI_CLOUD_DIR`` override)."""
    override = os.environ.get("LEVI_CLOUD_DIR", "").strip()
    base = Path(override).expanduser() if override else Path.home() / ".levi" / "cloud"
    p = base / "learning_packs"
    p.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass
    return p


def manifest_path() -> Path:
    return packs_dir() / "manifest.json"


def installed_registry_path() -> Path:
    """Where this instance records which packs it has ingested."""
    from levi.growth.journal import growth_dir

    return growth_dir() / "installed_packs.json"


# ---------------------------------------------------------------------------
# Pack building (publisher side)
# ---------------------------------------------------------------------------

# Content templates from reflection that embed another user's speech —
# never packable, even if a marking bug let them through.
_FORBIDDEN_TEMPLATES = (
    "user corrected",
    "user preference expressed",
    "user asked levi to remember",
    "from past conversation",
    "[email redacted]",
    "[phone redacted]",
    "[secret redacted]",
    "[id redacted]",
    "[digits redacted]",
)


def identifier_risk(content: str) -> bool:
    """True if ``content`` looks like it carries identifiers or PII-shaped
    text, or echoes a reflection template that embeds user speech."""
    if not content:
        return True
    if redact_text(content) != content:
        return True  # redact patterns fired → something scrub-worthy inside
    low = content.lower()
    return any(marker in low for marker in _FORBIDDEN_TEMPLATES)


def collect_shareable(
    store: Any = None,
    *,
    min_corroboration: int = 0,
) -> tuple[list[Any], list[dict[str, Any]]]:
    """Return ``(shareable, excluded)`` growth entries.

    ``excluded`` carries ``{id, reason}`` for auditability — the pack
    builder can say exactly why something stayed home.
    """
    if MemoryStore is None:
        return [], []
    store = store or MemoryStore()
    shareable: list[Any] = []
    excluded: list[dict[str, Any]] = []
    for entry in store.list(limit=10000):
        if "growth" not in (entry.tags or []):
            continue
        md = entry.metadata or {}
        if "procedural" not in (entry.tags or []):
            excluded.append({"id": entry.id, "reason": "not-technique-kind"})
            continue
        if not md.get("shareable"):
            excluded.append({"id": entry.id, "reason": "not-marked-shareable"})
            continue
        if identifier_risk(entry.content or ""):
            excluded.append({"id": entry.id, "reason": "identifier-risk"})
            continue
        if int(md.get("corroborated_count", 0)) < min_corroboration:
            excluded.append({"id": entry.id, "reason": "below-min-corroboration"})
            continue
        shareable.append(entry)
    return shareable, excluded


def _source_type(entry: Any) -> str:
    md = entry.metadata or {}
    prov = md.get("provenance") or {}
    if str(prov.get("mode", "")) == "rules:cloud-distill":
        return "cloud"
    return "local"


def _canonical(pack: dict[str, Any]) -> bytes:
    return json.dumps(
        pack, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def pack_sha256(pack: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(pack)).hexdigest()


def _next_version() -> int:
    best = 0
    for path in packs_dir().glob(PACK_PREFIX + "*.json"):
        try:
            best = max(best, int(path.stem[len(PACK_PREFIX):]))
        except ValueError:
            continue
    return best + 1


def build_pack(
    store: Any = None,
    *,
    min_corroboration: int = 0,
) -> dict[str, Any]:
    """Aggregate shareable learnings into a versioned pack + manifest.

    Dedupes with the same Jaccard rule as consolidation; each pack
    entry aggregates corroboration as counts only — never identities.
    Returns ``{"version", "path", "manifest", "entries", "excluded"}``.
    """
    from levi.growth import journal as _journal

    shareable, excluded = collect_shareable(
        store, min_corroboration=min_corroboration
    )

    # cluster near-duplicates, aggregate counts (never identities)
    clusters: list[dict[str, Any]] = []
    for entry in shareable:
        words = _words(entry.content or "")
        placed = False
        for cluster in clusters:
            if _jaccard(words, cluster["words"]) >= 0.5:
                md = entry.metadata or {}
                prov = md.get("provenance") or {}
                cluster["sources"] += 1 + int(md.get("corroborated_count", 0))
                st = _source_type(entry)
                cluster["source_types"][st] = cluster["source_types"].get(st, 0) + 1
                cluster["confidence"] = max(
                    cluster["confidence"], float(md.get("confidence", 0.5))
                )
                learned_from = str(prov.get("learned_from", "") or "")
                if learned_from and learned_from not in cluster["learned_from"]:
                    cluster["learned_from"].append(learned_from)
                placed = True
                break
        if not placed:
            md = entry.metadata or {}
            prov = md.get("provenance") or {}
            learned_from = str(prov.get("learned_from", "") or "")
            clusters.append(
                {
                    "words": words,
                    "content": (entry.content or "").strip(),
                    "confidence": float(md.get("confidence", 0.5)),
                    "sources": 1 + int(md.get("corroborated_count", 0)),
                    "source_types": {_source_type(entry): 1},
                    "learned_from": [learned_from] if learned_from else [],
                }
            )

    version = _next_version()
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entries = [
        {
            "kind": "procedural",
            "content": c["content"],
            "confidence": round(c["confidence"], 3),
            "corroborated_sources": c["sources"],
            "source_types": dict(sorted(c["source_types"].items())),
            "learned_from": sorted(c["learned_from"]),
        }
        for c in clusters
    ]
    pack = {
        "format": PACK_FORMAT,
        "version": version,
        "created_at": created,
        "entry_count": len(entries),
        "entries": entries,
    }
    digest = pack_sha256(pack)
    path = packs_dir() / f"{PACK_PREFIX}{version}.json"
    path.write_text(
        json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest = {
        "format": MANIFEST_FORMAT,
        "version": version,
        "sha256": digest,
        "entry_count": len(entries),
        "created_at": created,
    }
    manifest_path().write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    try:
        _journal.append_entry(
            {
                "kind": "pack-build",
                "pack_version": version,
                "entries": len(entries),
                "excluded": len(excluded),
                "sha256": digest[:16],
            }
        )
    except Exception:
        pass
    return {
        "version": version,
        "path": str(path),
        "manifest": manifest,
        "entries": len(entries),
        "excluded": excluded,
    }


def latest_pack_payload() -> dict[str, Any]:
    """What the cloud endpoint serves: manifest + pack, or nulls."""
    mpath = manifest_path()
    if not mpath.exists():
        return {"manifest": None, "pack": None}
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    ppath = packs_dir() / f"{PACK_PREFIX}{manifest['version']}.json"
    pack = json.loads(ppath.read_text(encoding="utf-8"))
    return {"manifest": manifest, "pack": pack}


# ---------------------------------------------------------------------------
# Verification + ingest (receiver side)
# ---------------------------------------------------------------------------


def verify_pack(pack: dict[str, Any], manifest: dict[str, Any] | None = None) -> str:
    """Validate structure, format, and (when a manifest is given) hash.

    Returns the canonical sha256. Raises :class:`PackError`.
    """
    if not isinstance(pack, dict):
        raise PackError("pack is not a JSON object")
    if pack.get("format") != PACK_FORMAT:
        raise PackError("unknown pack format: %r" % (pack.get("format"),))
    version = pack.get("version")
    if not isinstance(version, int) or version < 1:
        raise PackError("pack has no valid version")
    entries = pack.get("entries")
    if not isinstance(entries, list):
        raise PackError("pack entries are not a list")
    for i, e in enumerate(entries):
        if not isinstance(e, dict) or e.get("kind") != "procedural":
            raise PackError(f"pack entry {i} is not a technique entry")
        content = e.get("content", "")
        if not isinstance(content, str) or len(content.strip()) < 12:
            raise PackError(f"pack entry {i} has no usable content")
        if identifier_risk(content):
            raise PackError(f"pack entry {i} failed the identifier scan")
    digest = pack_sha256(pack)
    if manifest is not None:
        if manifest.get("format") != MANIFEST_FORMAT:
            raise PackError("unknown manifest format")
        if manifest.get("version") != version:
            raise PackError("manifest version does not match pack version")
        if manifest.get("sha256") != digest:
            raise PackError("pack hash does not match manifest — tampered pack")
    return digest


def installed_packs() -> list[dict[str, Any]]:
    """Packs this instance has ingested, newest first."""
    path = installed_registry_path()
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(records, list):
        return []
    return sorted(records, key=lambda r: int(r.get("version", 0)), reverse=True)


def _record_installed(version: int, sha256: str, entry_count: int) -> None:
    path = installed_registry_path()
    records = [r for r in installed_packs() if int(r.get("version", 0)) != version]
    records.append(
        {
            "version": version,
            "sha256": sha256,
            "entry_count": entry_count,
            "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def ingest_pack(
    pack: dict[str, Any],
    *,
    manifest: dict[str, Any] | None = None,
    store: Any = None,
) -> dict[str, Any]:
    """Verify and merge a pack into local learnings.

    New entries are tagged ``collective`` with provenance
    ``learned_from: collective`` + pack version — never user identity.
    Near-duplicates of existing learnings corroborate instead of
    duplicating. Ingested entries are ``shareable=False``: the
    collective never re-packs what it received.
    """
    if not receive_enabled():
        raise PackError("receiving is disabled (LEVI_GROWTH_RECEIVE=0)")
    if MemoryStore is None:
        raise PackError("memory store unavailable")
    digest = verify_pack(pack, manifest)
    version = int(pack["version"])
    installed = installed_packs()
    newest = int(installed[0]["version"]) if installed else 0
    if version <= newest:
        raise PackError(
            f"pack version {version} is not newer than installed {newest}"
        )
    store = store or MemoryStore()
    growth_entries = [e for e in store.list(limit=10000) if "growth" in (e.tags or [])]

    accepted = 0
    corroborated = 0
    for e in pack["entries"]:
        content = (e.get("content") or "").strip()
        words = _words(content)
        best = None
        best_score = 0.0
        for existing in growth_entries:
            score = _jaccard(words, _words(existing.content or ""))
            if score > best_score:
                best_score = score
                best = existing
        if best is not None and best_score >= 0.5:
            md = dict(best.metadata or {})
            md["corroborated_count"] = int(md.get("corroborated_count", 0)) + 1
            md["collective_corroborated"] = True
            store.update(best.id, metadata=md)
            corroborated += 1
            continue
        entry = store.add(
            memory_type=MemoryType("procedural"),
            content=content,
            importance=round(max(0.05, min(1.0, float(e.get("confidence", 0.5)))), 3),
            source="growth",
            tags=["growth", "levi-learned", "procedural", "collective"],
            metadata={
                "confidence": round(float(e.get("confidence", 0.5)), 3),
                "provenance": {
                    "learned_from": "collective",
                    "pack_version": version,
                    "pack_sha256": digest[:16],
                    "collective_sources": int(e.get("corroborated_sources", 1)),
                    "collective_source_types": e.get("source_types", {}),
                },
                "status": "provisional",
                "corroborated_count": 0,
                "shareable": False,
            },
        )
        growth_entries.append(entry)
        accepted += 1

    _record_installed(version, digest, len(pack["entries"]))
    try:
        from levi.growth import journal as _journal

        _journal.append_entry(
            {
                "kind": "pack-ingest",
                "pack_version": version,
                "accepted": accepted,
                "corroborated": corroborated,
                "sha256": digest[:16],
            }
        )
    except Exception:
        pass
    return {
        "version": version,
        "sha256": digest,
        "accepted": accepted,
        "corroborated": corroborated,
    }


def ingest_pack_file(
    path: str | Path,
    *,
    manifest: dict[str, Any] | None = None,
    store: Any = None,
) -> dict[str, Any]:
    """Ingest a pack from a file (the offline fallback)."""
    raw = Path(path).read_text(encoding="utf-8")
    try:
        pack = json.loads(raw)
    except ValueError as exc:
        raise PackError(f"pack file is not valid JSON: {exc}") from exc
    if manifest is None:
        # A manifest sitting next to the pack is verified when present.
        sibling = Path(path).with_name("manifest.json")
        if sibling.exists():
            try:
                manifest = json.loads(sibling.read_text(encoding="utf-8"))
            except ValueError:
                manifest = None
    return ingest_pack(pack, manifest=manifest, store=store)


# ---------------------------------------------------------------------------
# Cloud transport
# ---------------------------------------------------------------------------


def fetch_latest_pack(
    server: str, api_key: str, *, timeout: int = 30
) -> dict[str, Any]:
    """GET /v1/learning/packs/latest → {"manifest", "pack"}."""
    url = server.rstrip("/") + "/v1/learning/packs/latest"
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + api_key}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
    except Exception as exc:
        raise PackError(f"could not reach learning server: {exc}") from exc
    if status != 200:
        raise PackError(f"server returned HTTP {status}")
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise PackError(f"server returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PackError("server returned a malformed payload")
    return payload


def sync_from_server(
    server: str,
    api_key: str,
    *,
    store: Any = None,
) -> dict[str, Any]:
    """Pull the latest pack from the cloud and ingest it."""
    payload = fetch_latest_pack(server, api_key)
    manifest = payload.get("manifest")
    pack = payload.get("pack")
    if not manifest or not pack:
        return {"status": "no-packs", "version": None}
    report = ingest_pack(pack, manifest=manifest, store=store)
    report["status"] = "ingested"
    return report
