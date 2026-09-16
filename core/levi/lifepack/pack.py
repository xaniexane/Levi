"""
LEVI life pack — export / import.

A life pack is a versioned JSON bundle that carries LEVI's portable state
between homes / machines. It is the close-to-the-DNA fix for "no life pack
export/import": an offline, user-controlled snapshot with a
Plan → Preview → Permission discipline.

Format (version 2)::

    {
        "format": "levi-lifepack",
        "version": 2,
        "exported_at": "<utc iso>",
        "levi_version": "...",
        "sections": {
            "identity": {...},          # UserProfile dict
            "settings": {"<file>": {...}},  # known root JSON config files
            "memory": [ {...}, ... ],   # durable MemoryEntry dicts
            "skills": {"manifest": [ {...}, ... ]},   # manifest only
            "capabilities": {...},      # capability-atlas snapshot (info)
            "growth": {...},            # developmental snapshot (info)
            "workflows": {...},         # workflow registry names (info)
            "manifest": {...},          # pack provenance: version, machine id
        },
    }

Version 1 packs (the four core sections only) are still accepted on import:
``validate_pack`` speaks versions 1 and 2, and ``import_pack`` treats the
four v2-only sections as informational snapshots that are never written —
so a v1 pack imports exactly as it always did.

Deliberately *not* in the pack: secrets/credentials (filtered defensively
on import), playbook bodies (manifest only — they travel with the code),
ephemeral memory (working), scoped/device state (device, project), and
anything under other data dirs (agent workspaces, factories, stories).

All public functions take an explicit ``home`` path so callers (and tests)
never have to touch the real ``~/.levi``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi import __version__ as LEVI_VERSION
from levi.identity.profile import ProfileStore, UserProfile
from levi.memory.store import MemoryStore
from levi.memory.types import MemoryEntry, MemoryType
from levi.skill.registry import SkillRegistry

FORMAT = "levi-lifepack"
PACK_VERSION = 2

#: Life-pack versions this LEVI can read. Exports always write the newest.
SUPPORTED_VERSIONS = frozenset({1, 2})

#: Memory types considered durable enough to travel in a life pack.
DURABLE_MEMORY_TYPES = frozenset(
    {
        MemoryType.SEMANTIC,  # facts
        MemoryType.PREFERENCE,  # preferences
        MemoryType.PROCEDURAL,  # learned workflows / routines
        MemoryType.RELATIONSHIP,  # people and connections
    }
)

#: Known settings-like root JSON files under a LEVI home.
#: Included when present; absence is tolerated silently.
SETTINGS_FILES = (
    "settings.json",
    "preferences.json",
    "charter.json",
    "control_daemon.json",
    "monotropism.json",
    "nervous_system.json",
    "persona_bond.json",
    "demand_pulse.json",
    "brain_table.json",
    "income_factory.json",
)

#: Case-insensitive substrings that mark a key (or setting file key)
#: as secret material. Such keys are NEVER imported — they are skipped
#: and reported. The list is intentionally broad: when in doubt, skip.
SECRET_KEY_HINTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "pwd",
    "api_key",
    "apikey",
    "client_secret",
    "bearer",
    "auth",
    "credential",
    "private_key",
    "seed_phrase",
    "mnemonic",
)


#: Sections every pack carries (v1 and v2).
CORE_SECTIONS = ("identity", "settings", "memory", "skills")

#: Sections added in v2. All four are informational snapshots: import
#: verifies and reports them but never writes them (capabilities and
#: workflows ship with the code; growth state belongs to the growth loop).
V2_SECTIONS = ("capabilities", "growth", "workflows", "manifest")


class LifepackError(RuntimeError):
    """Raised for malformed packs, refusals, and unsafe imports."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def looks_secret(name: str) -> bool:
    """True when a key name looks like credential material.

    Separators are stripped so ``LEVIL_API_KEY``, ``oauth-token`` and
    ``apiKey``-style names all match. The list is intentionally broad:
    when in doubt, skip. Non-string input is never a secret name.
    """
    if not isinstance(name, str):
        return False
    joined = re.sub(r"[^a-z0-9]", "", name.lower())
    return any(hint.replace("_", "") in joined for hint in SECRET_KEY_HINTS)


def _resolve_home(home: Optional[Path]) -> Path:
    return Path(home).expanduser() if home else Path.home() / ".levi"


# ── Export ─────────────────────────────────────────────────────────


def _export_identity(home: Path) -> Dict[str, Any]:
    return ProfileStore(path=home / "profile.json").load().to_dict()


def _export_settings(home: Path) -> Dict[str, Any]:
    settings: Dict[str, Any] = {}
    for fname in SETTINGS_FILES:
        path = home / fname
        if not path.is_file():
            continue
        try:
            settings[fname] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # Corrupt/unreadable settings file: tolerate absence.
            continue
    return settings


def _export_memory(home: Path) -> List[Dict[str, Any]]:
    store = MemoryStore(data_dir=home / "memory")
    entries: List[Dict[str, Any]] = []
    for mtype in sorted(DURABLE_MEMORY_TYPES, key=lambda t: t.value):
        for entry in store.list(memory_type=mtype, limit=10_000):
            entries.append(entry.to_dict())
    return entries


def _export_skills() -> Dict[str, Any]:
    """Manifest only: ids, names, categories — never playbook bodies."""
    registry = SkillRegistry()
    return {
        "manifest": [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category,
                "version": s.version,
                "risk_level": int(s.risk_level),
            }
            for s in registry.list()
        ]
    }


# ── v2-only sections (informational snapshots; never written on import) ──


def _export_capabilities() -> Dict[str, Any]:
    """Capability-atlas snapshot. Defensive: the atlas may not have landed."""
    try:
        from levi.interop.atlas import export_atlas
    except Exception:
        return {"status": "atlas-not-landed"}
    try:
        return {"status": "ok", "atlas": export_atlas()}
    except Exception as exc:  # never let a broken atlas break export
        return {"status": "atlas-unreadable", "error": str(exc)}


def _export_growth(home: Path) -> Dict[str, Any]:
    """Developmental snapshot, read-only via the public growth journal API.

    This module never writes growth state: growth writes belong to the
    growth loop alone. The journal resolves its directory from
    ``LEVI_GROWTH_DIR`` (the public override) or ``~/.levi/growth``; when an
    explicit home was given and no override exists, the read is scoped to
    ``<home>/growth`` so export stays hermetic and portable. (Resolving the
    journal location may create the empty dir — location bookkeeping only;
    no journal data is ever written here.)
    """
    try:
        from levi.growth import journal
    except Exception:
        return {"status": "growth-not-landed"}
    env_was_set = "LEVI_GROWTH_DIR" in os.environ
    if not env_was_set:
        os.environ["LEVI_GROWTH_DIR"] = str(home / "growth")
    try:
        state = journal.load_state()
        cycles = int(state.get("cycles", 0) or 0)
        # Learnings are consolidated into memory tagged "growth" — count
        # them in the home being exported, same rule as growth.status().
        store = MemoryStore(data_dir=home / "memory")
        learnings = sum(
            1
            for e in store.list(limit=50_000)
            if "growth" in (e.tags or [])
        )
        stage, blurb = journal.developmental_stage(learnings, cycles)
        return {
            "status": "ok",
            "stage": stage,
            "stage_note": blurb,
            "learnings": learnings,
            "cycles": cycles,
            "recent_entries": journal.read_entries(limit=10),
        }
    except Exception as exc:  # never let a broken journal break export
        return {"status": "growth-unreadable", "error": str(exc)}
    finally:
        if not env_was_set:
            os.environ.pop("LEVI_GROWTH_DIR", None)


def _export_workflows() -> Dict[str, Any]:
    """Workflow registry snapshot: names + summaries, never step bodies.

    (Step bodies travel with the code — same principle as the skills
    manifest.) Defensive: the workflows module may not have landed.
    """
    try:
        from levi.workflows import list_workflows
    except Exception:
        return {"status": "workflows-not-landed"}
    try:
        items = list_workflows()
        workflows = [
            {"name": w.get("name"), "summary": w.get("summary")}
            for w in items
            if isinstance(w, dict) and w.get("name")
        ]
        return {"status": "ok", "workflows": sorted(workflows, key=lambda w: w["name"])}
    except Exception as exc:  # never let a broken registry break export
        return {"status": "workflows-unreadable", "error": str(exc)}


def _machine_id() -> str:
    """Stable, non-personal source-machine id: sha256(hostname), 16 hex chars.

    Documented so pack readers know exactly what it is: it cannot be
    reversed to a hostname, a username, or anything else about the machine.
    """
    return hashlib.sha256(socket.gethostname().encode("utf-8")).hexdigest()[:16]


def _export_manifest() -> Dict[str, Any]:
    """Pack provenance: what this pack is and where it came from."""
    return {
        "format": FORMAT,
        "pack_version": PACK_VERSION,
        "levi_version": LEVI_VERSION,
        "exported_at": _utc_now(),
        "source_machine_id": _machine_id(),
        "source_machine_id_note": (
            "sha256(hostname) truncated to 16 hex chars — stable per machine, "
            "non-personal, not reversible to a hostname or user"
        ),
    }


def export_pack(home: Optional[Path] = None) -> Dict[str, Any]:
    """Build a life-pack dict from the given LEVI home (read-only)."""
    home = _resolve_home(home)
    return {
        "format": FORMAT,
        "version": PACK_VERSION,
        "exported_at": _utc_now(),
        "levi_version": LEVI_VERSION,
        "sections": {
            "identity": _export_identity(home),
            "settings": _export_settings(home),
            "memory": _export_memory(home),
            "skills": _export_skills(),
            "capabilities": _export_capabilities(),
            "growth": _export_growth(home),
            "workflows": _export_workflows(),
            "manifest": _export_manifest(),
        },
    }


# ── Validation ─────────────────────────────────────────────────────


def _safe_settings_name(fname: Any) -> bool:
    """A settings key is only acceptable when it names one of the known
    root JSON files — no separators, no traversal, no absolute paths."""
    return (
        isinstance(fname, str)
        and fname in SETTINGS_FILES
        and "/" not in fname
        and "\\" not in fname
        and ".." not in fname
        and not fname.startswith(".")
    )


def validate_pack(pack: Dict[str, Any]) -> None:
    """Accept pack versions 1 and 2.

    v1 carries only the four core sections; v2 adds capabilities, growth,
    workflows, and manifest. Unknown extra sections are tolerated (forward
    compatibility), but the required ones must be present and well-shaped.
    """
    if not isinstance(pack, dict):
        raise LifepackError("life pack must be a JSON object")
    if pack.get("format") != FORMAT:
        raise LifepackError(
            f"not a life pack: format={pack.get('format')!r} (expected {FORMAT!r})"
        )
    version = pack.get("version")
    if version not in SUPPORTED_VERSIONS:
        raise LifepackError(
            f"unsupported life-pack version {version!r} "
            f"(this LEVI speaks versions {sorted(SUPPORTED_VERSIONS)})"
        )
    sections = pack.get("sections")
    if not isinstance(sections, dict):
        raise LifepackError("life pack has no 'sections' object")
    required = CORE_SECTIONS + V2_SECTIONS if version == 2 else CORE_SECTIONS
    for name in required:
        if name not in sections:
            raise LifepackError(f"life pack is missing section {name!r}")
    for name in V2_SECTIONS:
        if name in sections and not isinstance(sections[name], dict):
            raise LifepackError(f"life pack {name!r} section must be an object")
    identity = sections["identity"]
    if not isinstance(identity, dict):
        raise LifepackError("life pack 'identity' section must be an object")
    settings = sections["settings"]
    if not isinstance(settings, dict):
        raise LifepackError("life pack 'settings' section must be an object")
    for fname, payload in settings.items():
        if not _safe_settings_name(fname):
            raise LifepackError(
                f"life pack settings key {fname!r} is not a known settings file "
                f"(expected one of {list(SETTINGS_FILES)})"
            )
        if not isinstance(payload, dict):
            raise LifepackError(
                f"life pack settings file {fname!r} must contain a JSON object"
            )
    memory = sections["memory"]
    if not isinstance(memory, list):
        raise LifepackError("life pack 'memory' section must be a list")
    for i, entry in enumerate(memory):
        if not isinstance(entry, dict):
            raise LifepackError(f"life pack memory entry #{i} must be an object")
        if not isinstance(entry.get("id"), str) or not entry["id"]:
            raise LifepackError(f"life pack memory entry #{i} needs a non-empty string 'id'")
    skills = sections["skills"]
    if not isinstance(skills, dict) or not isinstance(skills.get("manifest"), list):
        raise LifepackError("life pack 'skills' section must be an object with a 'manifest' list")
    for i, item in enumerate(skills["manifest"]):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise LifepackError(f"life pack skill manifest entry #{i} must be an object with a string 'id'")


# ── Preview (read-only diff) ───────────────────────────────────────


def _memory_index(home: Path) -> Dict[str, Dict[str, Any]]:
    store = MemoryStore(data_dir=home / "memory")
    out: Dict[str, Dict[str, Any]] = {}
    for mtype in MemoryType:
        for entry in store.list(memory_type=mtype, limit=10_000):
            out[entry.id] = entry.to_dict()
    return out


def _entry_changed(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
    # updated_at/version are import bookkeeping, not content.
    skip = {"updated_at", "version"}
    keys = (set(old) | set(new)) - skip
    return any(old.get(k) != new.get(k) for k in keys)


def preview_import(pack: Dict[str, Any], home: Optional[Path] = None) -> List[str]:
    """Human-readable diff between a pack and the current home.

    Pure read-only: touches nothing under ``home``.
    """
    validate_pack(pack)
    home = _resolve_home(home)
    lines: List[str] = []
    sections = pack["sections"]

    # identity
    profile = ProfileStore(path=home / "profile.json").load()
    current = profile.to_dict()
    incoming = sections["identity"]
    diffs = [
        f"{k}: {current.get(k)!r} → {incoming.get(k)!r}"
        for k in incoming
        if k not in ("last_active", "created_at") and current.get(k) != incoming.get(k)
    ]
    if not diffs:
        lines.append("identity: no changes")
    else:
        lines.append(f"identity: {len(diffs)} field(s) differ")
        lines.extend(f"  {d}" for d in diffs)

    # settings
    existing_settings = _export_settings(home)
    for fname, payload in sections["settings"].items():
        if fname not in existing_settings:
            lines.append(f"settings: +new file '{fname}'")
        elif existing_settings[fname] != payload:
            lines.append(f"settings: file '{fname}' differs")
    if not sections["settings"]:
        lines.append("settings: no changes (pack carries none)")

    # memory
    current_entries = _memory_index(home)
    incoming_entries = {e["id"]: e for e in sections["memory"]}
    new = [e for eid, e in incoming_entries.items() if eid not in current_entries]
    changed = [
        eid
        for eid, e in incoming_entries.items()
        if eid in current_entries and _entry_changed(current_entries[eid], e)
    ]
    secret_skipped = [
        e
        for e in new + [incoming_entries[e] for e in changed]
        if looks_secret(e.get("content", "") or "")
    ]
    lines.append(
        f"memory: +{len(new)} new entries, {len(changed)} changed"
        + (
            f", {len(secret_skipped)} look secret-like (will be skipped)"
            if secret_skipped
            else ""
        )
    )

    # skills (manifest is informational: code ships the skills)
    manifest = sections["skills"].get("manifest", [])
    local = _export_skills()["manifest"]
    local_ids = {s["id"] for s in local}
    pack_ids = {s["id"] for s in manifest}
    missing_locally = pack_ids - local_ids
    lines.append(
        f"skills: pack lists {len(manifest)} skills; {len(local)} registered here"
        + (
            f"; {len(missing_locally)} in pack are unknown here (informational only)"
            if missing_locally
            else ""
        )
    )

    # v2 informational snapshots (never written on import)
    if "capabilities" in sections:
        caps = sections["capabilities"] or {}
        status = caps.get("status", "?")
        detail = ""
        if status == "ok":
            atlas = caps.get("atlas")
            detail = f" ({len(atlas)} top-level keys)" if isinstance(atlas, dict) else ""
        lines.append(f"capabilities: {status}{detail} (informational — no writes)")
    if "growth" in sections:
        growth = sections["growth"] or {}
        status = growth.get("status", "?")
        if status == "ok":
            lines.append(
                f"growth: stage '{growth.get('stage')}', "
                f"{growth.get('learnings')} learnings over {growth.get('cycles')} cycles, "
                f"{len(growth.get('recent_entries') or [])} recent journal entries "
                "(informational — no writes)"
            )
        else:
            lines.append(f"growth: {status} (informational — no writes)")
    if "workflows" in sections:
        wfs = sections["workflows"] or {}
        status = wfs.get("status", "?")
        names = [w.get("name") for w in (wfs.get("workflows") or []) if isinstance(w, dict)]
        lines.append(
            f"workflows: {status}"
            + (f" — {len(names)} registered: {', '.join(names)}" if names else "")
            + " (informational — no writes)"
        )
    if "manifest" in sections:
        mf = sections["manifest"] or {}
        lines.append(
            f"manifest: pack v{mf.get('pack_version')} from machine "
            f"{mf.get('source_machine_id')} (levi {mf.get('levi_version')})"
        )
    return lines


# ── Import ─────────────────────────────────────────────────────────


def _strip_secrets(settings: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
    """Remove secret-looking keys (recursively) from settings payloads."""
    skipped: List[str] = []

    def scrub(value: Any, trail: str) -> Any:
        if isinstance(value, dict):
            kept = {}
            for k, v in value.items():
                if isinstance(k, str) and looks_secret(k):
                    skipped.append(f"{trail}.{k}" if trail else k)
                    continue
                kept[k] = scrub(v, f"{trail}.{k}" if trail else k)
            return kept
        if isinstance(value, list):
            return [scrub(v, trail) for v in value]
        return value

    return scrub(settings, ""), skipped


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)  # settings may carry personal data — owner-only
    tmp.replace(path)


def _import_identity(incoming: Dict[str, Any], home: Path) -> Dict[str, Any]:
    store = ProfileStore(path=home / "profile.json")
    current = store.load().to_dict()
    profile = UserProfile.from_dict(incoming)
    new = profile.to_dict()
    diffs = [
        k for k in new if k not in ("last_active",) and current.get(k) != new.get(k)
    ]
    if not diffs:
        return {"changed": False, "fields": []}
    store.save(profile)  # atomic temp+rename inside ProfileStore.save
    return {"changed": True, "fields": diffs}


def _import_settings(incoming: Dict[str, Any], home: Path) -> Dict[str, Any]:
    written: List[str] = []
    skipped: List[str] = []
    for fname, payload in incoming.items():
        # Belt-and-braces: import_pack() already runs validate_pack(), but
        # _import_settings must never write an attacker-chosen path on its own.
        if not _safe_settings_name(fname):
            skipped.append(str(fname))
            continue
        if not isinstance(payload, dict):
            skipped.append(fname)
            continue
        clean, file_skipped = _strip_secrets({fname: payload})
        skipped.extend(file_skipped)
        payload = clean[fname]
        path = home / fname
        existing: Any = None
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                existing = None
        if existing != payload:
            _atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))
            written.append(fname)
    return {"changed": bool(written), "files": written, "secrets_skipped": skipped}


def _import_memory(incoming: List[Dict[str, Any]], home: Path) -> Dict[str, Any]:
    store = MemoryStore(data_dir=home / "memory")
    existing = {eid: e.to_dict() for eid, e in store._entries.items()}  # noqa: SLF001
    added, changed, secrets_skipped = 0, 0, []
    dirty = False
    for raw in incoming:
        if not isinstance(raw, dict):
            continue  # malformed entry: skip, don't abort the whole import
        try:
            entry = MemoryEntry.from_dict(dict(raw))
        except Exception:
            continue  # malformed entry: skip, don't abort the whole import
        if looks_secret(entry.content):
            secrets_skipped.append(entry.id)
            continue
        if entry.id not in existing:
            store._entries[entry.id] = entry  # noqa: SLF001
            added += 1
            dirty = True
        elif _entry_changed(existing[entry.id], entry.to_dict()):
            cur = store._entries[entry.id]  # noqa: SLF001
            cur.content = entry.content
            cur.importance = entry.importance
            cur.tags = entry.tags
            cur.metadata = entry.metadata
            cur.source = entry.source
            cur.updated_at = _utc_now()
            cur.version += 1
            changed += 1
            dirty = True
    if dirty:
        store._persist()
    return {
        "changed": dirty,
        "added": added,
        "changed_entries": changed,
        "secrets_skipped": secrets_skipped,
    }


def _import_skills(incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Skills are read-only by design: code ships the skills, the pack only
    records which were present at export time. Import verifies and reports."""
    manifest = incoming.get("manifest", [])
    local_ids = {s["id"] for s in _export_skills()["manifest"]}
    pack_ids = {s["id"] for s in manifest}
    return {
        "changed": False,
        "pack_count": len(manifest),
        "local_count": len(local_ids),
        "unknown_locally": sorted(pack_ids - local_ids),
    }


# ── v2 informational sections: verified and reported, never written ──


def _import_capabilities(incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if incoming is None:
        return {"changed": False, "status": "not-in-pack"}
    return {
        "changed": False,
        "status": incoming.get("status", "unknown"),
        "atlas_top_level_keys": (
            len(incoming["atlas"]) if isinstance(incoming.get("atlas"), dict) else 0
        ),
    }


def _import_growth(incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Growth state belongs to the growth loop — import never writes it.
    The snapshot is reported so the operator can compare developmental
    stage across machines."""
    if incoming is None:
        return {"changed": False, "status": "not-in-pack"}
    return {
        "changed": False,
        "status": incoming.get("status", "unknown"),
        "stage": incoming.get("stage"),
        "learnings": incoming.get("learnings"),
        "cycles": incoming.get("cycles"),
        "recent_entries": len(incoming.get("recent_entries") or []),
    }


def _import_workflows(incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if incoming is None:
        return {"changed": False, "status": "not-in-pack"}
    names = [
        w.get("name")
        for w in (incoming.get("workflows") or [])
        if isinstance(w, dict) and w.get("name")
    ]
    return {"changed": False, "status": incoming.get("status", "unknown"), "names": names}


def _import_manifest(incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if incoming is None:
        return {"changed": False, "status": "not-in-pack"}
    return {
        "changed": False,
        "pack_version": incoming.get("pack_version"),
        "levi_version": incoming.get("levi_version"),
        "exported_at": incoming.get("exported_at"),
        "source_machine_id": incoming.get("source_machine_id"),
    }


def import_pack(
    pack: Dict[str, Any],
    home: Optional[Path] = None,
    *,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Import a life pack into ``home``. Returns a summary of what was written.

    Per-section, idempotent (re-importing the same pack is a no-op), and
    each file write is atomic (temp + rename). Secrets are never imported.

    Raises:
        LifepackError: if ``confirm`` is False (preview first), or the pack
            is malformed.
    """
    if not confirm:
        raise LifepackError(
            "refusing to import without confirmation: run preview_import() first, "
            "then call import_pack(..., confirm=True)"
        )
    validate_pack(pack)
    home = _resolve_home(home)
    home.mkdir(parents=True, exist_ok=True)
    sections = pack["sections"]
    summary = {
        "identity": _import_identity(sections["identity"], home),
        "settings": _import_settings(sections["settings"], home),
        "memory": _import_memory(sections["memory"], home),
        "skills": _import_skills(sections["skills"]),
        # v2-only: informational snapshots — verified, reported, never written.
        "capabilities": _import_capabilities(sections.get("capabilities")),
        "growth": _import_growth(sections.get("growth")),
        "workflows": _import_workflows(sections.get("workflows")),
        "manifest": _import_manifest(sections.get("manifest")),
    }
    return summary


# ── CLI entry point (wired by cli/main.py; kept here so it is testable) ──


def cmd_lifepack(args: argparse.Namespace, home: Optional[Path] = None) -> int:
    """``levi lifepack export <file>`` / ``levi lifepack import <file> [--preview]``."""
    home = _resolve_home(home)
    action = getattr(args, "lifepack_action", None)

    if action == "export":
        pack = export_pack(home)
        out = Path(args.file)
        _atomic_write_text(out, json.dumps(pack, indent=2, ensure_ascii=False))
        secs = pack["sections"]
        growth = secs["growth"]
        wfs = secs["workflows"]
        print(f"Wrote life pack v{pack['version']} → {out}")
        print(
            f"  identity: {'present' if secs['identity'] else 'empty'} | "
            f"settings: {len(secs['settings'])} file(s) | "
            f"memory: {len(secs['memory'])} entries | "
            f"skills: {len(secs['skills']['manifest'])} in manifest"
        )
        print(
            f"  capabilities: {growth and secs['capabilities'].get('status')} | "
            f"growth: {growth.get('status')}"
            + (
                f" (stage '{growth['stage']}', {growth['learnings']} learnings)"
                if growth.get("status") == "ok"
                else ""
            )
            + f" | workflows: {wfs.get('status')}"
            + (
                f" ({len(wfs.get('workflows') or [])} registered)"
                if wfs.get("status") == "ok"
                else ""
            )
        )
        print(f"  manifest: source machine {secs['manifest']['source_machine_id']}")
        return 0

    if action == "import":
        path = Path(args.file)
        try:
            pack = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"cannot read pack {path}: {exc}", file=sys.stderr)
            return 1
        try:
            validate_pack(pack)
        except LifepackError as exc:
            print(f"invalid life pack: {exc}", file=sys.stderr)
            return 1

        if getattr(args, "preview", False):
            for line in preview_import(pack, home):
                print(line)
            print("(preview only — nothing was written)")
            return 0

        if not getattr(args, "yes", False):
            if sys.stdin.isatty():
                answer = input(
                    "Import will overwrite identity/settings/memory in this home. "
                    "Type IMPORT to confirm: "
                ).strip()
                if answer != "IMPORT":
                    print("aborted.", file=sys.stderr)
                    return 1
            else:
                print(
                    "refusing: import needs explicit confirmation "
                    "(pass --yes or run on a TTY)",
                    file=sys.stderr,
                )
                return 1

        try:
            summary = import_pack(pack, home, confirm=True)
        except LifepackError as exc:
            print(f"import failed: {exc}", file=sys.stderr)
            return 1
        ident = summary["identity"]
        sett = summary["settings"]
        mem = summary["memory"]
        print("Import summary:")
        print(
            f"  identity: {'updated ' + str(ident['fields']) if ident['changed'] else 'unchanged'}"
        )
        print(f"  settings: {sett['files'] or 'unchanged'}")
        if sett["secrets_skipped"]:
            print(f"  settings secrets skipped: {sett['secrets_skipped']}")
        print(
            f"  memory: +{mem['added']} added, {mem['changed_entries']} changed"
            + (
                f", {len(mem['secrets_skipped'])} secret-like skipped"
                if mem["secrets_skipped"]
                else ""
            )
        )
        sk = summary["skills"]
        print(
            f"  skills: {sk['pack_count']} in pack, {sk['local_count']} registered (manifest only — no writes)"
        )
        caps = summary["capabilities"]
        gr = summary["growth"]
        wfs = summary["workflows"]
        mf = summary["manifest"]
        print(
            f"  capabilities: {caps['status']} (informational — no writes) | "
            f"growth: {gr['status']}"
            + (
                f" (stage '{gr['stage']}', {gr['learnings']} learnings, {gr['cycles']} cycles)"
                if gr.get("status") == "ok"
                else ""
            )
            + f" (informational — no writes)"
        )
        print(
            f"  workflows: {wfs['status']}"
            + (f" ({', '.join(wfs['names'])})" if wfs.get("names") else "")
            + " (informational — no writes)"
        )
        if mf.get("status") != "not-in-pack":
            print(
                f"  manifest: pack v{mf['pack_version']} from machine "
                f"{mf['source_machine_id']} (levi {mf['levi_version']})"
            )
        return 0

    print(
        "usage: levi lifepack {export|import} <file> [--preview] [--yes]",
        file=sys.stderr,
    )
    return 2


__all__ = [
    "FORMAT",
    "PACK_VERSION",
    "SUPPORTED_VERSIONS",
    "CORE_SECTIONS",
    "V2_SECTIONS",
    "DURABLE_MEMORY_TYPES",
    "SETTINGS_FILES",
    "LifepackError",
    "looks_secret",
    "export_pack",
    "validate_pack",
    "preview_import",
    "import_pack",
    "cmd_lifepack",
]
