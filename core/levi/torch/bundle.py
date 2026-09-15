"""Pass the torch — mentor bundles for a new LEVI instance.

``levi torch create <file>`` packages what this instance has learned
into a versioned JSON bundle:

  * lifepack export (identity + settings + durable memory) — REUSES
    ``levi.lifepack``; never forked, never reimplemented here.
  * curriculum digest (topics + lesson count + provenance, plus the
    lessons themselves).
  * journal highlights — "what I've learned": top corroborated
    growth learnings.
  * current model card — from the lab's ``MODEL_CARDS`` when present.
  * founder's note — a template Chauncey can sign (blank until he does).

``levi torch read <file>`` ingests a bundle as seed on a NEW instance:
lifepack import (preview → confirm discipline), curriculum lessons via
the curriculum loader (or a torch-planted seed file the study quiz can
read), learnings as provisional ``taught-by: torch`` seed facts, and
the founder's note displayed.

Bundles are plain JSON (``format: "levi-torch"``, versioned) — meant
to be handed to a fresh machine, a new install, or the next LEVI.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

FORMAT = "levi-torch"
TORCH_VERSION = 1

FOUNDERS_NOTE_PLACEHOLDER = (
    "Founder's note — sign this bundle for the next LEVI.\n"
    "Write what this instance learned that mattered, what to watch out\n"
    "for, and what kind of LEVI you want the next one to become.\n"
    "(Use `levi torch sign <file> --by <name> --note <text>` to sign.)"
)

HIGHLIGHT_LIMIT = 10


class TorchError(RuntimeError):
    """Malformed bundle, failed validation, or unsafe ingest."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_home(home: Optional[Path]) -> Path:
    return Path(home).expanduser() if home else Path.home() / ".levi"


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


def _curriculum_lessons() -> List[Dict[str, Any]]:
    from levi.growth import study as _study

    return _study.get_lessons()


def _curriculum_digest() -> Dict[str, Any]:
    lessons = _curriculum_lessons()
    topics: List[str] = []
    provenance: Dict[str, int] = {}
    for lesson in lessons:
        topic = str(lesson.get("topic", "")).strip()
        if topic and topic not in topics:
            topics.append(topic)
        taught_by = str(lesson.get("taught_by", "")).strip() or "unknown"
        provenance[taught_by] = provenance.get(taught_by, 0) + 1
    return {
        "lesson_count": len(lessons),
        "topics": sorted(topics),
        "provenance": provenance,
        "lessons": lessons,
    }


def _journal_highlights(
    home: Path, limit: int = HIGHLIGHT_LIMIT
) -> List[Dict[str, Any]]:
    """Top corroborated growth learnings — 'what I've learned'."""
    from levi.memory.store import MemoryStore

    store = MemoryStore(data_dir=home / "memory")
    entries = [e for e in store.list(limit=5000) if "growth" in e.tags]

    def _score(e: Any) -> tuple:
        md = e.metadata or {}
        return (int(md.get("corroborated_count", 0) or 0), float(e.importance or 0.0))

    entries.sort(key=_score, reverse=True)
    out = []
    for e in entries[:limit]:
        kinds = [
            t for t in e.tags if t in ("fact", "preference", "procedural", "correction")
        ]
        out.append(
            {
                "content": e.content,
                "kinds": kinds,
                "corroborated_count": int(
                    (e.metadata or {}).get("corroborated_count", 0) or 0
                ),
                "confidence": float(
                    (e.metadata or {}).get("confidence", e.importance) or 0.0
                ),
                "created_at": e.created_at,
            }
        )
    return out


def _model_card() -> Optional[Dict[str, Any]]:
    """Current model card from the lab registry, or None with a reason."""
    try:
        from levi.lab import MODEL_CARDS
        from levi.agent.local_model import DEFAULT_MODEL_KEY
    except Exception:  # noqa: BLE001 — lab/agent must never break torch
        return None
    card = MODEL_CARDS.get(DEFAULT_MODEL_KEY)
    if not isinstance(card, dict):
        return None
    return {"current": DEFAULT_MODEL_KEY, "cards": dict(MODEL_CARDS)}


def create_bundle(home: Optional[Path] = None) -> Dict[str, Any]:
    """Build the mentor bundle dict for ``home``."""
    from levi import __version__ as LEVI_VERSION
    from levi.lifepack.pack import export_pack

    home = _resolve_home(home)
    return {
        "format": FORMAT,
        "version": TORCH_VERSION,
        "created_at": _utc_now(),
        "levi_version": LEVI_VERSION,
        "sections": {
            "lifepack": export_pack(home),
            "curriculum": _curriculum_digest(),
            "journal_highlights": _journal_highlights(home),
            "model_card": _model_card(),
            "founders_note": {
                "note": FOUNDERS_NOTE_PLACEHOLDER,
                "signed_by": "",
                "signed_at": "",
            },
        },
    }


def write_bundle(path: Path, bundle: Dict[str, Any]) -> Path:
    path = Path(path).expanduser()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return path


# ---------------------------------------------------------------------------
# read / validate
# ---------------------------------------------------------------------------


def read_bundle(path: Path) -> Dict[str, Any]:
    try:
        raw = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TorchError("cannot read bundle %s: %s" % (path, exc)) from exc
    return validate_bundle(raw)


def validate_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(bundle, dict):
        raise TorchError("bundle is not a JSON object")
    if bundle.get("format") != FORMAT:
        raise TorchError("not a torch bundle (format=%r)" % (bundle.get("format"),))
    if int(bundle.get("version", 0)) != TORCH_VERSION:
        raise TorchError(
            "unsupported torch version %r (this LEVI reads %d)"
            % (bundle.get("version"), TORCH_VERSION)
        )
    sections = bundle.get("sections")
    if not isinstance(sections, dict):
        raise TorchError("bundle has no sections")
    for required in ("lifepack", "curriculum", "journal_highlights", "founders_note"):
        if required not in sections:
            raise TorchError("bundle missing section %r" % required)
    return bundle


def preview_read(bundle: Dict[str, Any]) -> List[str]:
    """Plan step: human-readable summary of what ingest would do."""
    sections = bundle["sections"]
    cur = sections["curriculum"]
    highlights = sections["journal_highlights"]
    note = sections.get("founders_note") or {}
    lines = [
        "torch bundle (levi-torch v%d, created %s, levi %s)"
        % (bundle["version"], bundle.get("created_at"), bundle.get("levi_version")),
        "  lifepack: identity+settings+memory sections from the source instance",
        "  curriculum: %d lesson(s), %d topic(s), provenance %s"
        % (
            cur.get("lesson_count", 0),
            len(cur.get("topics", [])),
            cur.get("provenance", {}),
        ),
        "  journal highlights: %d learning(s) as provisional torch seed facts"
        % (len(highlights) if isinstance(highlights, list) else 0),
        "  model card: %s"
        % ((sections.get("model_card") or {}).get("current", "none shipped")),
    ]
    if note.get("signed_by"):
        lines.append(
            "  founder's note: signed by %s at %s"
            % (note["signed_by"], note.get("signed_at"))
        )
    else:
        lines.append(
            "  founder's note: UNSIGNED (template — sign with `levi torch sign`)"
        )
    lines.append("  secrets: never shipped in bundles (lifepack strips them on export)")
    return lines


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9]+")


def _ingest_torch_lessons(lessons: List[Dict[str, Any]], store: Any) -> Dict[str, Any]:
    """Load bundle lessons as torch-taught seed entries.

    Mirrors the pattern in ``levi.growth.curriculum.loader.load_curriculum``
    (consolidate → stamp identity/provenance) but marks the teachings as
    ``taught-by: torch`` rather than the founders'. Consolidation dedups
    against anything the lifepack import already brought over.
    """
    from levi.growth.consolidate import consolidate
    from levi.growth.reflect import Learning

    valid = [
        it
        for it in lessons
        if isinstance(it, dict)
        and str(it.get("text", "")).strip()
        and str(it.get("topic", "")).strip()
    ]
    learnings = [
        Learning(
            kind=str(it.get("kind", "fact") or "fact"),
            content=str(it["text"]),
            confidence=0.95,
            provenance={
                "source": "torch",
                "taught_by": "torch",
                "note": "seeded from a mentor bundle",
            },
        )
        for it in valid
    ]
    report = consolidate(learnings, cycle_id="torch-%s" % _utc_now()[:10], store=store)
    stamped = 0
    entries = store.list(limit=5000)
    for lesson in valid:
        match = next(
            (
                e
                for e in entries
                if e.content == str(lesson["text"]) and "growth" in e.tags
            ),
            None,
        )
        if match is None:
            continue
        md = dict(match.metadata or {})
        provenance = md.get("provenance")
        if not isinstance(provenance, dict):
            provenance = {}
        provenance.update({"source": "torch", "taught_by": "torch"})
        md.update(
            {
                "provenance": provenance,
                "lesson_id": str(lesson.get("id") or ""),
                "topic": str(lesson.get("topic")),
                "taught_by": "torch",
                "seed": True,
                "status": "seeded",
            }
        )
        tags = list(match.tags)
        for tag in ("curriculum", "torch-seed"):
            if tag not in tags:
                tags.append(tag)
        store.update(match.id, tags=tags, metadata=md)
        stamped += 1
    return {
        "total": len(valid),
        "accepted": report["accepted"],
        "corroborated": report["corroborated"],
        "stamped": stamped,
    }


def _plant_seed_file(lessons: List[Dict[str, Any]]) -> str:
    """Last-resort lesson store when the curriculum module is absent."""
    from levi.growth import journal as _journal

    seed_path = _journal.growth_dir() / "curriculum_seed.json"
    seed_path.write_text(
        json.dumps({"lessons": lessons}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return "torch seed file (%s)" % seed_path


def _content_overlap(a: str, b: str) -> float:
    """Jaccard word overlap — dedup for torch seed facts."""
    wa = set(_WORD_RE.findall(a.lower()))
    wb = set(_WORD_RE.findall(b.lower()))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def ingest_bundle(
    bundle: Dict[str, Any],
    home: Optional[Path] = None,
    *,
    confirm: bool = False,
) -> Dict[str, Any]:
    """Ingest a validated bundle as seed into ``home``.

    Discipline: Plan → Preview → Permission → Execute. Raises
    ``TorchError`` unless ``confirm=True`` (the CLI maps this to ``--yes``
    after printing the preview).
    """
    if not confirm:
        raise TorchError(
            "refusing to ingest without confirmation: preview first "
            "(`levi torch read <file>`), then re-run with --yes"
        )
    bundle = validate_bundle(bundle)
    home = _resolve_home(home)
    home.mkdir(parents=True, exist_ok=True)
    sections = bundle["sections"]
    summary: Dict[str, Any] = {"home": str(home)}

    # 1. lifepack — identity, settings, durable memory (reuses the real thing)
    from levi.lifepack.pack import import_pack

    lifepack_section = sections["lifepack"]
    summary["lifepack"] = import_pack(lifepack_section, home=home, confirm=True)

    # 2. curriculum — founders' seed loader first, then the bundle's own
    #    lessons as torch-taught seeds (deduped against the lifepack).
    from levi.memory.store import MemoryStore

    store = MemoryStore(data_dir=home / "memory")
    lessons = sections["curriculum"].get("lessons") or []
    curriculum_steps: List[str] = []
    try:
        from levi.growth.curriculum import load_curriculum as _load_curriculum

        seed_report = _load_curriculum(store)
        curriculum_steps.append(
            "curriculum.load_curriculum: %d accepted, %d corroborated"
            % (seed_report.get("accepted", 0), seed_report.get("corroborated", 0))
        )
    except Exception:  # noqa: BLE001 — module not built yet; keep going
        pass
    try:
        torch_report = _ingest_torch_lessons(lessons, store)
        curriculum_steps.append(
            "torch lessons: %d total, %d accepted, %d corroborated, %d stamped"
            % (
                torch_report["total"],
                torch_report["accepted"],
                torch_report["corroborated"],
                torch_report["stamped"],
            )
        )
    except Exception as exc:  # noqa: BLE001 — last resort: plant the seed file
        curriculum_steps.append(
            "%s (in-memory ingest failed: %s)"
            % (_plant_seed_file(lessons), type(exc).__name__)
        )
    summary["curriculum"] = {"lessons": len(lessons), "steps": curriculum_steps}

    # 3. journal highlights — learnings enter as provisional seed facts with
    #    taught-by: torch provenance. The lifepack import above usually
    #    already brought the same entries over; in that case we STAMP them
    #    (no duplicates) rather than adding copies.
    from levi.memory.types import MemoryType

    added = 0
    stamped = 0
    for h in sections["journal_highlights"]:
        content = str(h.get("content", "")).strip()
        if not content:
            continue
        dup = next(
            (
                e
                for e in store.list(limit=5000)
                if _content_overlap(content, e.content) >= 0.8
            ),
            None,
        )
        if dup is None:
            store.add(
                MemoryType.SEMANTIC,
                content,
                importance=float(h.get("confidence") or 0.5),
                source="torch",
                tags=["growth", "levi-learned", "fact", "torch-seed"],
                metadata={
                    "status": "provisional",
                    "provenance": {
                        "source": "torch",
                        "taught_by": "torch",
                        "note": "journal highlight from a mentor bundle",
                    },
                    "corroborated_count": int(h.get("corroborated_count", 0) or 0),
                    "kinds": list(h.get("kinds") or []),
                    "torch_created_at": bundle.get("created_at"),
                    "torch_levi_version": bundle.get("levi_version"),
                },
            )
            added += 1
            continue
        md = dict(dup.metadata or {})
        prov = md.get("provenance")
        if not isinstance(prov, dict):
            prov = {}
        prov.update({"source": "torch", "taught_by": "torch"})
        md["provenance"] = prov
        md["status"] = "provisional"
        md["corroborated_count"] = max(
            int(md.get("corroborated_count", 0) or 0),
            int(h.get("corroborated_count", 0) or 0),
        )
        tags = list(dup.tags)
        if "torch-seed" not in tags:
            tags.append("torch-seed")
        store.update(dup.id, tags=tags, metadata=md)
        stamped += 1
    summary["torch_seed_facts"] = {"added": added, "stamped_from_lifepack": stamped}

    # 4. founder's note — displayed, and journaled as the bundle's arrival.
    note = sections.get("founders_note") or {}
    summary["founders_note"] = {
        "signed_by": note.get("signed_by") or "",
        "signed_at": note.get("signed_at") or "",
    }
    try:
        from levi.growth import journal as _journal

        _journal.append_entry(
            {
                "kind": "torch-read",
                "created_at": bundle.get("created_at"),
                "levi_version": bundle.get("levi_version"),
                "lessons": len(lessons),
                "seed_facts_added": added,
                "founder_signed_by": note.get("signed_by") or "",
            }
        )
    except Exception:  # noqa: BLE001 — journal must never break ingest
        pass
    return summary


def sign_bundle(path: Path, *, by: str, note: str = "") -> Dict[str, Any]:
    """Chauncey signs the founder's note in place."""
    bundle = read_bundle(path)
    entry = bundle["sections"]["founders_note"]
    entry["note"] = note.strip() or entry.get("note") or FOUNDERS_NOTE_PLACEHOLDER
    entry["signed_by"] = by.strip()
    entry["signed_at"] = _utc_now()
    write_bundle(path, bundle)
    return entry


# ---------------------------------------------------------------------------
# CLI entry (wired by cli/main.py; kept here so it is testable)
# ---------------------------------------------------------------------------


def format_founders_note(note: Dict[str, Any]) -> str:
    signed_by = (note.get("signed_by") or "").strip()
    header = (
        "— signed by %s at %s —" % (signed_by, note.get("signed_at") or "?")
        if signed_by
        else "— unsigned founder's note (sign with `levi torch sign <file> --by <name>`) —"
    )
    return "%s\n%s" % (header, (note.get("note") or "").strip())


def cmd_torch(args: argparse.Namespace, home: Optional[Path] = None) -> int:
    """``levi torch <create|read|sign> [path]`` — pass the torch."""
    action = getattr(args, "torch_action", "create") or "create"
    path_arg = (getattr(args, "path", "") or "").strip()

    if action == "create":
        out = path_arg or "levi-torch-%s.json" % datetime.now(timezone.utc).strftime(
            "%Y%m%d"
        )
        bundle = create_bundle(home)
        write_bundle(out, bundle)
        cur = bundle["sections"]["curriculum"]
        print("torch bundle created: %s" % out)
        print("  format: levi-torch v%d" % bundle["version"])
        print(
            "  curriculum: %d lesson(s), %d topic(s)"
            % (cur["lesson_count"], len(cur["topics"]))
        )
        print("  highlights: %d" % len(bundle["sections"]["journal_highlights"]))
        print(
            "  model card: %s"
            % ((bundle["sections"]["model_card"] or {}).get("current", "none"))
        )
        print("  founder's note: unsigned — sign it before handing over:")
        print('    levi torch sign %s --by "Chauncey"' % out)
        return 0

    if action == "read":
        if not path_arg:
            print("usage: levi torch read <bundle-file> [--yes]")
            return 2
        bundle = read_bundle(path_arg)
        for line in preview_read(bundle):
            print(line)
        if not getattr(args, "yes", False):
            print("\nThis is the preview. Re-run with --yes to ingest as seed.")
            return 0
        summary = ingest_bundle(bundle, home, confirm=True)
        print("\ningested into %s" % summary["home"])
        print("  curriculum: %d lesson(s)" % summary["curriculum"]["lessons"])
        for step in summary["curriculum"]["steps"]:
            print("    - %s" % step)
        sf = summary["torch_seed_facts"]
        print(
            "  torch seed facts: %d added fresh, %d stamped (from lifepack)"
            % (sf["added"], sf["stamped_from_lifepack"])
        )
        print()
        print(format_founders_note(bundle["sections"].get("founders_note") or {}))
        return 0

    if action == "sign":
        if not path_arg:
            print("usage: levi torch sign <bundle-file> --by <name> [--note <text>]")
            return 2
        by = (getattr(args, "sign_by", "") or "").strip()
        if not by:
            print("sign needs --by <name>")
            return 2
        entry = sign_bundle(path_arg, by=by, note=getattr(args, "sign_note", "") or "")
        print("founder's note signed by %s" % entry["signed_by"])
        return 0

    print("unknown torch action: %r (use create|read|sign)" % action)
    return 2
