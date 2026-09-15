"""
LEVI life pack — export / import.

A life pack is a versioned JSON bundle that carries LEVI's portable state
(identity, settings, durable memory, skill manifest) between homes /
machines. It is the close-to-the-DNA fix for "no life pack export/import":
an offline, user-controlled snapshot with a Plan → Preview → Permission
discipline.

Format (version 1)::

    {
        "format": "levi-lifepack",
        "version": 1,
        "exported_at": "<utc iso>",
        "levi_version": "...",
        "sections": {
            "identity": {...},          # UserProfile dict
            "settings": {"<file>": {...}},  # known root JSON config files
            "memory": [ {...}, ... ],   # durable MemoryEntry dicts
            "skills": {"manifest": [ {...}, ... ]},
        },
    }

Deliberately *not* in the pack: secrets/credentials (filtered defensively
on import), playbook bodies (manifest only — they travel with the code),
ephemeral memory (working), scoped/device state (device, project), and
anything under other data dirs (agent workspaces, factories, stories).

All public functions take an explicit ``home`` path so callers (and tests)
never have to touch the real ``~/.levi``.
"""
from __future__ import annotations

import argparse
import json
import re
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
PACK_VERSION = 1

#: Memory types considered durable enough to travel in a life pack.
DURABLE_MEMORY_TYPES = frozenset(
    {
        MemoryType.SEMANTIC,      # facts
        MemoryType.PREFERENCE,    # preferences
        MemoryType.PROCEDURAL,    # learned workflows / routines
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


class LifepackError(RuntimeError):
    """Raised for malformed packs, refusals, and unsafe imports."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def looks_secret(name: str) -> bool:
    """True when a key name looks like credential material.

    Separators are stripped so ``LEVIL_API_KEY``, ``oauth-token`` and
    ``apiKey``-style names all match. The list is intentionally broad:
    when in doubt, skip.
    """
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
        },
    }


# ── Validation ─────────────────────────────────────────────────────


def validate_pack(pack: Dict[str, Any]) -> None:
    if not isinstance(pack, dict):
        raise LifepackError("life pack must be a JSON object")
    if pack.get("format") != FORMAT:
        raise LifepackError(
            f"not a life pack: format={pack.get('format')!r} (expected {FORMAT!r})"
        )
    version = pack.get("version")
    if version != PACK_VERSION:
        raise LifepackError(
            f"unsupported life-pack version {version!r} (this LEVI speaks version {PACK_VERSION})"
        )
    sections = pack.get("sections")
    if not isinstance(sections, dict):
        raise LifepackError("life pack has no 'sections' object")
    for name in ("identity", "settings", "memory", "skills"):
        if name not in sections:
            raise LifepackError(f"life pack is missing section {name!r}")


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
    secret_skipped = [e for e in new + [incoming_entries[e] for e in changed]
                      if looks_secret(e.get("content", "") or "")]
    lines.append(
        f"memory: +{len(new)} new entries, {len(changed)} changed"
        + (f", {len(secret_skipped)} look secret-like (will be skipped)" if secret_skipped else "")
    )

    # skills (manifest is informational: code ships the skills)
    manifest = sections["skills"].get("manifest", [])
    local = _export_skills()["manifest"]
    local_ids = {s["id"] for s in local}
    pack_ids = {s["id"] for s in manifest}
    missing_locally = pack_ids - local_ids
    lines.append(
        f"skills: pack lists {len(manifest)} skills; {len(local)} registered here"
        + (f"; {len(missing_locally)} in pack are unknown here (informational only)" if missing_locally else "")
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
    tmp.replace(path)


def _import_identity(incoming: Dict[str, Any], home: Path) -> Dict[str, Any]:
    store = ProfileStore(path=home / "profile.json")
    current = store.load().to_dict()
    profile = UserProfile.from_dict(incoming)
    new = profile.to_dict()
    diffs = [k for k in new if k not in ("last_active",) and current.get(k) != new.get(k)]
    if not diffs:
        return {"changed": False, "fields": []}
    store.save(profile)  # atomic temp+rename inside ProfileStore.save
    return {"changed": True, "fields": diffs}


def _import_settings(incoming: Dict[str, Any], home: Path) -> Dict[str, Any]:
    written: List[str] = []
    skipped: List[str] = []
    for fname, payload in incoming.items():
        if not isinstance(payload, dict):
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
        print(f"Wrote life pack → {out}")
        print(
            f"  identity: {'present' if secs['identity'] else 'empty'} | "
            f"settings: {len(secs['settings'])} file(s) | "
            f"memory: {len(secs['memory'])} entries | "
            f"skills: {len(secs['skills']['manifest'])} in manifest"
        )
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
        print(f"  identity: {'updated ' + str(ident['fields']) if ident['changed'] else 'unchanged'}")
        print(f"  settings: {sett['files'] or 'unchanged'}")
        if sett["secrets_skipped"]:
            print(f"  settings secrets skipped: {sett['secrets_skipped']}")
        print(
            f"  memory: +{mem['added']} added, {mem['changed_entries']} changed"
            + (f", {len(mem['secrets_skipped'])} secret-like skipped" if mem["secrets_skipped"] else "")
        )
        sk = summary["skills"]
        print(f"  skills: {sk['pack_count']} in pack, {sk['local_count']} registered (manifest only — no writes)")
        return 0

    print("usage: levi lifepack {export|import} <file> [--preview] [--yes]", file=sys.stderr)
    return 2


__all__ = [
    "FORMAT",
    "PACK_VERSION",
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
