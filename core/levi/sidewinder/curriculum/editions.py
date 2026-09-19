"""Edition packs — manifest-driven curriculum bundles, stdlib only.

An edition is a named, manifest-driven curriculum pack for a career field
or audience: a selector (filter over domains/tracks/levels, plus explicit
ids), track emphasis, and optional edition-specific entries. Manifests live
in ``edition_packs/*.json`` (see ``edition_packs/README.md`` + ``_template.json``);
Chauncey authors new career-field packs declaratively — no code changes.

A pack's view = selector matches over the corpus, plus the edition's own
entries as an overlay, plus the prerequisite closure beneath — so every
learning path inside the pack is self-contained.

First pack shipped: ``first-responder``.

Pack law (inherits the crisis doctrine): professional help FIRST, always —
improvisation is last resort when no help or equipment is coming. Every
crisis entry in every pack carries an explicit call-for-help-first stop
condition plus do-not-attempt conditions. Standard first-aid/wilderness
knowledge only — no DIY surgery, ever.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.sidewinder import DOMAINS, LEVELS, LEVEL_ORDER, TRACKS
from levi.sidewinder.curriculum.corpus import Corpus, normalize_title
from levi.sidewinder.curriculum.schema import validate_entry
from levi.sidewinder.curriculum.scope import scoped_corpus, scoped_ids

MODULE_DIR = Path(__file__).resolve().parent
MANIFESTS_DIR = MODULE_DIR / "edition_packs"

_ID_RE = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_ENTRY_ID_RE = re.compile(r"\Asw-[a-z0-9]+(?:-[a-z0-9]+)*-\d{3}\Z")

MANIFEST_KEYS = (
    "id",
    "name",
    "blurb",
    "selector",
    "track_emphasis",
    "entries",
    "entries_file",
)
SELECTOR_KEYS = ("domains", "tracks", "levels", "ids")


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def validate_manifest(manifest: Any) -> List[str]:
    """Structural manifest validation; empty list means valid."""
    errors: List[str] = []
    if not isinstance(manifest, dict):
        return ["manifest is not a JSON object"]
    unknown = [k for k in manifest if k not in MANIFEST_KEYS]
    if unknown:
        errors.append(f"unknown manifest key(s): {', '.join(sorted(unknown))}")
    mid = manifest.get("id")
    if not isinstance(mid, str) or not _ID_RE.match(mid):
        errors.append(f"bad id {mid!r} (want lowercase slug, e.g. 'first-responder')")
    for key in ("name", "blurb"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            errors.append(f"{key} must be a non-empty string")
    selector = manifest.get("selector")
    if not isinstance(selector, dict):
        errors.append("selector must be an object with domains/tracks/levels/ids")
    else:
        unknown_sel = [k for k in selector if k not in SELECTOR_KEYS]
        if unknown_sel:
            errors.append(f"unknown selector key(s): {', '.join(sorted(unknown_sel))}")
        for key in SELECTOR_KEYS:
            if key in selector and not _is_str_list(selector[key]):
                errors.append(f"selector.{key} must be a list of strings")
        if isinstance(selector.get("domains"), list):
            bad = [d for d in selector["domains"] if d not in DOMAINS]
            if bad:
                errors.append(f"selector.domains has unknown domain(s): {', '.join(bad)}")
        if isinstance(selector.get("tracks"), list):
            bad = [t for t in selector["tracks"] if t not in TRACKS]
            if bad:
                errors.append(f"selector.tracks has unknown track(s): {', '.join(bad)}")
        if isinstance(selector.get("levels"), list):
            bad = [lv for lv in selector["levels"] if lv not in LEVELS]
            if bad:
                errors.append(f"selector.levels has unknown level(s): {', '.join(bad)}")
        if isinstance(selector.get("ids"), list):
            bad = [i for i in selector["ids"] if not _ENTRY_ID_RE.match(i)]
            if bad:
                errors.append(f"selector.ids has malformed entr-id(s): {', '.join(bad)}")
        if not any(selector.get(k) for k in SELECTOR_KEYS):
            errors.append("selector is empty — a pack must select at least one domain/track/level/id")
    emphasis = manifest.get("track_emphasis", [])
    if not _is_str_list(emphasis):
        errors.append("track_emphasis must be a list of strings")
    else:
        bad = [t for t in emphasis if t not in TRACKS]
        if bad:
            errors.append(f"track_emphasis has unknown track(s): {', '.join(bad)}")
    if "entries" in manifest and not isinstance(manifest["entries"], list):
        errors.append("entries must be a list of entry objects")
    if "entries_file" in manifest and manifest["entries_file"] is not None and not isinstance(
        manifest["entries_file"], str
    ):
        errors.append("entries_file must be a string path or null")
    return errors


def _load_pack_entries(manifest: Dict[str, Any], manifest_path: Path) -> List[Dict[str, Any]]:
    """Edition-specific entries: inline ``entries`` + ``entries_file`` JSONL."""
    entries: List[Dict[str, Any]] = []
    for raw in manifest.get("entries") or []:
        if isinstance(raw, dict):
            entries.append(dict(raw))
    entries_file = manifest.get("entries_file")
    if entries_file:
        path = (manifest_path.parent / entries_file).resolve()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            entries.append(json.loads(line))
    return entries


def validate_pack_entries(
    manifest: Dict[str, Any], corpus: Corpus
) -> List[str]:
    """Validate a pack's own entries: schema, id/title uniqueness vs the
    corpus, and prerequisite resolution within corpus + pack."""
    errors: List[str] = []
    pack = manifest.get("_entries", [])
    seen_ids: set = set()
    for entry in pack:
        if not isinstance(entry, dict):
            errors.append(f"pack {manifest['id']}: entry is not a JSON object")
            continue
        for err in validate_entry(entry):
            errors.append(f"pack {manifest['id']}: {entry.get('id', '?')}: {err}")
        eid = entry.get("id")
        if isinstance(eid, str):
            if eid in seen_ids:
                errors.append(f"pack {manifest['id']}: duplicate pack entry id {eid}")
            seen_ids.add(eid)
            if corpus.has_id(eid):
                errors.append(f"pack {manifest['id']}: entry id {eid} collides with the corpus")
        title = entry.get("title")
        if isinstance(title, str) and corpus.has_title(title):
            errors.append(f"pack {manifest['id']}: entry title {title!r} collides with the corpus")
    # Prerequisite resolution within corpus + pack.
    pool_ids = {e["id"] for e in corpus.entries} | seen_ids
    for entry in pack:
        if not isinstance(entry, dict):
            continue
        for pre in entry.get("prerequisites", []) or []:
            if pre not in pool_ids:
                errors.append(
                    f"pack {manifest['id']}: {entry.get('id', '?')} -> dangling prerequisite {pre}"
                )
    return errors


def load_manifests(
    path: Optional[Path] = None, corpus: Optional[Corpus] = None
) -> Dict[str, Dict[str, Any]]:
    """Load and validate every ``edition_packs/*.json`` manifest (``_``-prefixed
    files are skipped: template, not a pack). Raises ValueError listing all
    problems. When ``corpus`` is given, pack entries are cross-validated."""
    path = path or MANIFESTS_DIR
    problems: List[str] = []
    manifests: Dict[str, Dict[str, Any]] = {}
    files = sorted(path.glob("*.json")) if path.is_dir() else []
    for mpath in files:
        if mpath.name.startswith("_"):
            continue
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{mpath.name}: unreadable manifest: {exc}")
            continue
        for err in validate_manifest(manifest):
            problems.append(f"{mpath.name}: {err}")
        manifest["_source"] = mpath.name
        try:
            manifest["_entries"] = _load_pack_entries(manifest, mpath)
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{mpath.name}: cannot load pack entries: {exc}")
            manifest["_entries"] = []
        mid = manifest.get("id")
        if isinstance(mid, str):
            if mid in manifests:
                problems.append(f"{mpath.name}: duplicate pack id {mid!r}")
            if mid != mpath.stem:
                problems.append(
                    f"{mpath.name}: pack id {mid!r} should match the file name {mpath.stem!r}"
                )
            manifests[mid] = manifest
    if corpus is not None:
        for manifest in manifests.values():
            problems.extend(validate_pack_entries(manifest, corpus))
    if problems:
        raise ValueError("edition manifest problems:\n  " + "\n  ".join(problems))
    return manifests


def list_editions(manifests: Dict[str, Dict[str, Any]]) -> List[str]:
    return sorted(manifests)


def edition_ids(corpus: Corpus, manifest: Dict[str, Any]) -> set:
    """Entry ids in the pack: selector matches + pack entries + prereq closure."""
    selector = manifest.get("selector", {})
    pack = manifest.get("_entries", [])
    return scoped_ids(
        corpus,
        extra=pack,
        domains=selector.get("domains", ()),
        tracks=selector.get("tracks", ()),
        levels=selector.get("levels", ()),
        ids=selector.get("ids", ()),
    )


def edition_corpus(corpus: Corpus, manifest: Dict[str, Any]) -> Corpus:
    """The pack as a filtered Corpus view (search/get/progressions work)."""
    selector = manifest.get("selector", {})
    pack = manifest.get("_entries", [])
    return scoped_corpus(
        corpus,
        extra=pack,
        domains=selector.get("domains", ()),
        tracks=selector.get("tracks", ()),
        levels=selector.get("levels", ()),
        ids=selector.get("ids", ()),
    )


def format_edition(corpus: Corpus, manifest: Dict[str, Any]) -> str:
    """Terse pack overview for ``levi course --edition <id>``."""
    view = edition_corpus(corpus, manifest)
    emphasis = manifest.get("track_emphasis", []) or []

    def sort_key(entry):
        rank = 0
        for i, track in enumerate(emphasis):
            if track in entry["tracks"]:
                rank = i
                break
        else:
            rank = len(emphasis)
        return (LEVEL_ORDER[entry["level"]], rank, entry["title"])

    entries = sorted(view.entries, key=sort_key)
    tracks = sorted({t for e in entries for t in e["tracks"]})
    domains = sorted({e["domain"] for e in entries})
    pack_n = len(manifest.get("_entries", []))
    lines = [
        f"{str(manifest['name']).upper()} EDITION — {manifest['blurb']}",
        f"{len(entries)} entries across {len(domains)} domains ({', '.join(domains)})"
        + (f", {pack_n} pack-specific" if pack_n else ""),
        "tracks: " + ", ".join(tracks)
        + (f" (emphasis: {', '.join(emphasis)})" if emphasis else ""),
        "",
    ]
    last_level = None
    for entry in entries:
        if entry["level"] != last_level:
            last_level = entry["level"]
            lines.append(f"  [{last_level.upper()}]")
        lines.append(f"    {entry['id']}  {entry['title']}")
    lines.append("")
    lines.append(
        "Edition law: professional help FIRST, always — improvisation is last "
        "resort when no help or equipment is coming. Every crisis entry "
        "carries explicit stop conditions."
    )
    return "\n".join(lines)
