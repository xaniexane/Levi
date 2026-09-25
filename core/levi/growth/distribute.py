"""Distribution: growth feeds every subsystem (MEGAZORD AXIS 9).

Consolidated learnings are routed to the subsystems they concern:

(a) a routing-slip entry is written to the memory store, tagged
    ``["growth", "levi-learned", "distribution", <subsystem>...]`` where the
    subsystem tags are inferred from keyword matches against the learning
    content, so any subsystem can query ``tag:<its-name>`` for learnings
    meant for it;
(b) a ``levi.growth.learning`` event is published on the bloodstream bus
    when ``levi.bloodstream.bus`` is importable (defensive: its absence
    just means no live subscribers yet);
(c) every routing decision is recorded in the growth journal.

Binding safety rails (same as the rest of growth):
  * distribution WRITES ONLY growth-tagged memory entries and the journal.
    It never touches tools, policy, identity, the charter, or any
    non-growth entry. Every entry written here carries ``source="growth"``
    and the ``"growth"`` tag — enforced, not just conventional.
  * distribution records are mechanical routing slips
    ("learning X -> subsystems: a, b"). They never claim sentience,
    feelings, consciousness, or identity — functional, never phenomenal.
  * distribution records are internal bookkeeping: ``shareable: False``,
    they never travel in learning packs.

Distribution is idempotent per learning: a ``learning_key`` (sha256 of the
learning content) in the record metadata means re-running never writes a
duplicate routing slip.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Union

from levi.growth import journal as _journal
from levi.growth.reflect import Learning

try:
    from levi.memory.store import MemoryStore
    from levi.memory.types import MemoryType
except Exception:  # pragma: no cover — memory package is stdlib-only too
    MemoryStore = None  # type: ignore
    MemoryType = None  # type: ignore


# ---------------------------------------------------------------------------
# Subsystem keyword map — warehouses, factory organs, and core modules.
# A learning is routed to every subsystem whose keywords match its content.
# ---------------------------------------------------------------------------

_SUBSYSTEM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "agent": ("agent", "chat session", "prompt", "tool call", "delegation", "repl"),
    "archive": (
        "archive",
        "research",
        "corpus",
        "ingest",
        "knowledge base",
        "document",
    ),
    "backup": ("backup", "restore", "rclone", "snapshot"),
    "brain": ("brain", "model weight", "training", "tokeniz", "llm", "transformer"),
    "builder": ("builder", "scaffold"),
    "daemon": ("daemon", "heartbeat", "cron", "schedule", "automation"),
    "demand": ("demand", "opportunity", "demandpulse"),
    "factory": ("factory", "manufacture", "production line"),
    "finance": (
        "finance",
        "market",
        "stock",
        "portfolio",
        "trading",
        "broker",
        "alpaca",
        "signal",
    ),
    "forge": (
        "forge",
        "git",
        "repository",
        "pull request",
        "commit",
        "version control",
    ),
    "galaxy": ("galaxy", "package", "ecosystem", "third-party"),
    "governor": ("governor", "budget", "meter", "rate limit"),
    "growth": ("growth", "journal", "reflect", "baby levi"),
    "king": ("king", "manuscript", "story", "narrative"),
    "lifepack": ("lifepack", "life pack"),
    "mcp": ("mcp",),
    "memory": ("memory", "recall"),
    "methods": (
        "method",
        "franklin",
        "tickler",
        "gtd",
        "habit",
        "productivity",
        "quoting",
    ),
    "oath": ("oath", "gpg", "signature"),
    "perpetual": ("perpetual", "hunt"),
    "persona": ("persona",),
    "revival": (
        "revival",
        "retro",
        "plan9",
        "lisp",
        "hypertext",
        "xanadu",
        "forgotten",
    ),
    "ux": ("ux", "user interface", "theme", "onboarding"),
    "vault": ("vault", "secret", "encrypt", "api key"),
}

_FALLBACK_SUBSYSTEM = "general"


def _keyword_patterns() -> dict[str, list[re.Pattern]]:
    out: dict[str, list[re.Pattern]] = {}
    for subsystem, keywords in _SUBSYSTEM_KEYWORDS.items():
        pats = []
        for kw in keywords:
            # single words match on word boundaries; phrases match as substrings
            if " " in kw:
                pats.append(re.compile(re.escape(kw), re.IGNORECASE))
            else:
                pats.append(re.compile(r"\b%s\b" % re.escape(kw), re.IGNORECASE))
        out[subsystem] = pats
    return out


_PATTERNS = _keyword_patterns()


def infer_subsystems(content: str) -> list[str]:
    """Subsystem names whose keywords match ``content`` (order-stable).

    Returns ``["general"]`` when nothing matches — every learning gets a
    routing home, and the fallback is honest about being a fallback.
    """
    text = content or ""
    matched = [
        name for name, pats in _PATTERNS.items() if any(p.search(text) for p in pats)
    ]
    return matched or [_FALLBACK_SUBSYSTEM]


def _learning_key(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()[:32]


def _normalize(learning: Any) -> Union[dict, None]:
    """Accept a Learning or its to_dict(); return a plain dict or None."""
    if isinstance(learning, Learning):
        d = learning.to_dict()
    elif isinstance(learning, dict):
        d = dict(learning)
    else:
        return None
    kind = str(d.get("kind", "") or "")
    content = str(d.get("content", "") or "").strip()
    if kind not in ("fact", "preference", "procedural", "correction"):
        return None
    if len(content) < 12:
        return None
    try:
        confidence = float(d.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    return {
        "kind": kind,
        "content": content,
        "confidence": max(0.0, min(1.0, confidence)),
        "provenance": d.get("provenance")
        if isinstance(d.get("provenance"), dict)
        else {},
    }


def _publish_bus_event(payload: dict[str, Any]) -> bool:
    """Publish ``levi.growth.learning`` on the bloodstream bus.

    Returns True when a bus accepted the event, False when there is no
    bus (module missing, no ``publish`` callable, or publish raised).
    Never raises: distribution must not break for lack of subscribers.
    """
    try:
        from levi.bloodstream import bus as _blood_bus
    except Exception:
        return False
    try:
        publish = getattr(_blood_bus, "publish", None)
        if not callable(publish):
            return False
        publish("levi.growth.learning", payload)
        return True
    except Exception:
        return False


def _journal_path(home: Any) -> Path:
    if home is not None:
        return Path(home) / "growth" / "journal.jsonl"
    return _journal.journal_path()


def _append_journal(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record.setdefault("id", _journal.new_cycle_id())
    record.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    record.setdefault("kind", "distribution")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _existing_keys(store: Any) -> set[str]:
    """learning_keys already distributed (best-effort; empty on any failure)."""
    try:
        entries = store.list(limit=5000)
    except Exception:
        return set()
    keys = set()
    for e in entries:
        try:
            tags = e.tags or []
            md = e.metadata or {}
        except Exception:
            continue
        if "growth" in tags and "distribution" in tags and md.get("learning_key"):
            keys.add(str(md["learning_key"]))
    return keys


def distribute_learnings(
    learnings: list,
    home: Any = None,
    *,
    store: Any = None,
    cycle_id: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Route consolidated learnings to subsystems (memory + bus + journal).

    ``learnings``: list of :class:`~levi.growth.reflect.Learning` (or their
    ``to_dict()`` form). ``home``: the LEVI home (``~/.levi``); when None it
    is resolved from ``LEVI_HOME`` / ``~/.levi``. ``store``: optional memory
    store (created from ``home`` when None).

    Returns ``{distributed, skipped, duplicates, entries, subsystems,
    bus_published, journal_records}``. Raises ValueError when ``learnings``
    is not a list. Never raises for per-learning failures — those are
    counted in ``skipped``.
    """
    if not isinstance(learnings, list):
        raise ValueError(
            "distribute_learnings: learnings must be a list, got %s"
            % type(learnings).__name__
        )
    report: dict[str, Any] = {
        "distributed": 0,
        "skipped": 0,
        "duplicates": 0,
        "entries": [],
        "subsystems": {},
        "bus_published": 0,
        "journal_records": [],
    }
    if MemoryStore is None:
        report["skipped"] = len(learnings)
        return report

    if home is None:
        raw = os.environ.get("LEVI_HOME")
        home = Path(raw).expanduser() if raw else Path.home() / ".levi"
    home = Path(home)
    if store is None:
        store = MemoryStore(data_dir=home / "memory")
    journal_file = _journal_path(home)

    seen_keys = _existing_keys(store)

    for learning in learnings:
        norm = _normalize(learning)
        if norm is None:
            report["skipped"] += 1
            continue
        key = _learning_key(norm["content"])
        if key in seen_keys:
            report["duplicates"] += 1
            continue
        subsystems = infer_subsystems(norm["content"])
        for s in subsystems:
            report["subsystems"][s] = report["subsystems"].get(s, 0) + 1

        if dry_run:
            report["distributed"] += 1
            continue

        # (a) routing slip in the memory store — growth-tagged, always.
        content = (
            "Growth distribution: learning routed to subsystem(s): %s.\n"
            "Learning [%s · conf %.2f · cycle %s]: %s"
            % (
                ", ".join(subsystems),
                norm["kind"],
                norm["confidence"],
                cycle_id or "n/a",
                norm["content"],
            )
        )
        tags = ["growth", "levi-learned", "distribution"] + subsystems
        try:
            entry = store.add(
                memory_type=MemoryType("semantic"),
                content=content,
                importance=round(norm["confidence"], 3),
                source="growth",
                tags=tags,
                metadata={
                    "learning_key": key,
                    "kind": norm["kind"],
                    "confidence": round(norm["confidence"], 3),
                    "subsystems": subsystems,
                    "provenance": norm["provenance"],
                    "cycle_id": cycle_id,
                    "status": "provisional",
                    # internal bookkeeping — never travels in learning packs
                    "shareable": False,
                },
            )
        except Exception:
            report["skipped"] += 1
            continue
        seen_keys.add(key)

        # (b) bloodstream bus event (best-effort; absence is not an error)
        bus_ok = _publish_bus_event(
            {
                "topic": "levi.growth.learning",
                "cycle_id": cycle_id,
                "kind": norm["kind"],
                "confidence": round(norm["confidence"], 3),
                "subsystems": subsystems,
                "learning_key": key,
                "content": norm["content"][:280],
            }
        )
        if bus_ok:
            report["bus_published"] += 1

        # (c) journal record
        rec = _append_journal(
            journal_file,
            {
                "cycle_id": cycle_id,
                "learning_key": key,
                "kind_norm": norm["kind"],
                "subsystems": subsystems,
                "memory_entry_id": entry.id,
                "bus_published": bus_ok,
            },
        )
        report["journal_records"].append(rec["id"])
        report["distributed"] += 1
        report["entries"].append(entry.id)

    return report
