"""LEVI warehouses — not a tool belt.

A tool belt is a small flat list you carry; a warehouse is a vast
categorized depot with inventory, indexing, and retrieval. This module is
a *presentation/organization layer* over the existing modules — it
rewrites nothing, it reorganizes how capabilities are browsed.

Every warehouse:

- has a name, a summary, and one or more *shelves* (manifest modules),
- reports a real ``inventory_count`` (actual registered items, counted,
  never estimated),
- can be browsed, inventoried (with honest ``limit``/``offset``
  pagination — no silent truncation), and pulled from (read-only lookup
  of one item's full detail plus how to invoke it — never executed).

Stable API (the CLI worker wires to exactly this — keep names stable):

- :func:`list_warehouses` -> list of {name, summary, inventory_count}
- :func:`browse_warehouse` -> {name, summary, shelves, inventory_count, notes}
- :func:`warehouse_inventory` -> {warehouse, total, offset, limit,
  truncated, items: [{id, kind, summary}]}
- :func:`pull_from_shelf` -> one item's full detail + invocation
- :data:`CLI_COMMANDS` -> module name to CLI reachability

Unknown warehouse/item names raise ``ValueError`` naming what *is*
available — honest errors, never guesses.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from levi.interop.manifest import DECLARATIONS

__all__ = [
    "WAREHOUSES",
    "CLI_COMMANDS",
    "list_warehouses",
    "browse_warehouse",
    "warehouse_inventory",
    "pull_from_shelf",
]


# ---------------------------------------------------------------------------
# Static maps
# ---------------------------------------------------------------------------

#: module name -> how to reach it from the CLI. A list entry starting with
#: "python -m" is a module-level CLI (not a `levi` subparser). Empty list =
#: no CLI surface (import the module).
CLI_COMMANDS: Dict[str, List[str]] = {
    "bloodstream": ["turn"],
    "lifepack": ["lifepack"],
    "growth": ["growth"],
    "daemon": ["daemon"],
    "galaxy": ["python -m levi.galaxy"],
    "perpetual": ["python -m levi.perpetual"],
    "finance": ["finance"],
    "organs": ["echo", "mandella"],
    "memory-store": ["remember", "recall"],
    "knowledge": ["courses", "news", "security"],
    "academy": ["academy"],
    "bounty": ["bounty"],
    "agent-assistant": ["ask"],
    "bot-services": ["services"],
    "factory": ["factory"],
    "archive": ["python -m levi.archive"],
    "cyber-skills": [],
    "methods": [],
    "revival": [],
    "memory-retrieval": [],
    "rag": [],
    "oath": [],
    "serve": ["serve", "python -m levi.serve"],
}


#: Reachability for the operator + additions waves. Every package with a
#: ``__main__`` is honestly reachable as ``python -m levi.<pkg>``; packages
#: without one are import-only until the unified CLI wires them.
CLI_COMMANDS.update(
    {
        # -- operator wave ------------------------------------------------
        "signals": ["python -m levi.signals"],
        "creed": [],
        "promises": ["python -m levi.promises"],
        "decisions": ["python -m levi.decisions"],
        "interruptions": ["python -m levi.interruptions"],
        "snapshots": ["python -m levi.snapshots"],
        "drift": ["python -m levi.drift"],
        "teachback": ["python -m levi.teachback"],
        "energy": ["python -m levi.energy"],
        "friction": ["python -m levi.friction"],
        "sweeps": ["python -m levi.sweeps"],
        "premortem": ["python -m levi.premortem"],
        # -- deep-web research --------------------------------------------
        "research": [],
        # -- games (perpetual-hunt games wave) ------------------------------
        "games": ["python -m levi.games"],
        # -- copper (perpetual-hunt wave-004: scored choreography) ---------------
        "copper": ["python -m levi.copper"],
        # -- verify (perpetual-hunt wave-006: pre-digital proof rituals) ------
        "verify": ["python -m levi.verify"],
        # -- analog (perpetual-hunt wave-006: analog computing revived) ------
        "analog": ["python -m levi.analog"],
        # -- telegraph (perpetual-hunt wave-001: dead protocols revived) ---
        "telegraph": ["python -m levi.telegraph"],
        # -- craft (perpetual-hunt wave-014: lost crafts revived) ---------
        "craft": ["python -m levi.craft"],
        # -- digest (perpetual-hunt wave-008: dead networks — LISTSERV) --
        "digest": ["python -m levi.digest"],
        # -- pdi (perpetual-hunt wave-008: dead networks — NAPLPS remix) --
        "pdi": ["python -m levi.pdi"],
        # -- boards (perpetual-hunt wave-008: dead networks — BBS areas) --
        "boards": ["python -m levi.boards"],
        # -- doors (perpetual-hunt wave-008: dead networks — door games) --
        "doors": ["python -m levi.doors"],
        # -- shelf (perpetual-hunt daily 2026-09-16: fallen platforms --------
        # Reader share-with-note + Digg bury, revived as a local curation desk
        "shelf": ["python -m levi.shelf"],
        # -- reveal (perpetual-hunt daily 2026-09-16b: retired software ------
        # WordPerfect Reveal Codes, clean-room revived: the honest second
        # screen on a document — structure codes + invisible characters.
        "reveal": ["python -m levi.reveal"],
        # -- circles (perpetual-hunt daily 2026-09-16 evening: Path's cap) --
        "circles": ["python -m levi.circles"],
        # -- feedlab (perpetual-hunt daily 2026-09-16: giant-patterns inversion)
        "feedlab": ["python -m levi.feedlab rank --demo"],
        # -- additions wave -----------------------------------------------
        "ephemera": ["python -m levi.ephemera"],
        "feedreader": ["python -m levi.feedreader"],
        "packs": ["python -m levi.packs"],
        # -- shareware (perpetual-hunt daily 2026-09-16: the honest
        # markets — Apogee's episode model remixed as local trial grants)
        "shareware": ["python -m levi.shareware"],
        "commitments": ["python -m levi.commitments"],
        "recap": ["python -m levi.recap"],
        "classifieds": ["python -m levi.classifieds"],
        "dials": ["python -m levi.dials"],
        "bridging": ["python -m levi.bridging"],
        "communities": ["python -m levi.communities"],
        "threads": ["python -m levi.threads"],
        "charters": ["python -m levi.charters"],
        "capproto": ["python -m levi.capproto"],
        "mailtriage": ["python -m levi.mailtriage"],
        "vaults": ["python -m levi.vaults"],
        "canvas": ["python -m levi.canvas"],
        "discover": ["python -m levi.discover"],
        "presence": ["python -m levi.presence"],
        "honestsearch": ["python -m levi.honestsearch"],
        # -- quickdial (perpetual-hunt evening-20260916-software: Opera ----
        # Speed Dial + gestures, LEVI-native workflow slots)
        "quickdial": ["python -m levi.quickdial"],
        "recommender": ["python -m levi.recommender"],
        # -- liberation (perpetual-hunt daily 2026-09-15: roach-motel inversion)
        "liberation": ["python -m levi.liberation"],
        # -- sentinel (source-sync `the-pack`: defensive blue-team host tooling)
        "sentinel": ["sentinel"],
    }
)


def _pkg_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _first_doc_line(path: Path) -> str:
    """First line of a module's docstring (parsed, never imported)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        doc = ast.get_docstring(tree) or ""
    except (OSError, SyntaxError):
        doc = ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return path.stem.replace("_", " ")


def _module_files(package: str) -> Iterator[Tuple[str, Path]]:
    """(module_name, path) for every real module file in a package dir.

    Skips ``__init__``, ``__main__`` and private helpers — those are
    plumbing, not inventory.
    """
    root = _pkg_root() / package
    if not root.is_dir():
        return
    for path in sorted(root.glob("[a-z]*.py")):
        if path.stem in ("__init__", "__main__"):
            continue
        yield path.stem, path


def _playbook_title(path: Path) -> str:
    """First markdown heading of a playbook file."""
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#"):
                    return line.lstrip("#").strip()
                if line:
                    return line[:90]
    except OSError:
        pass
    return path.stem.replace("-", " ")


def _playbook_id(path: Path) -> str:
    base = _pkg_root() / "skill" / "playbooks"
    try:
        rel = path.relative_to(base).with_suffix("")
    except ValueError:
        rel = Path(path.stem)
    return "playbook." + ".".join(rel.parts)


# ---------------------------------------------------------------------------
# Warehouse definitions
# ---------------------------------------------------------------------------
#
# strategy selects the inventory counter:
#   "techniques"   — one item per module file under core/levi/methods/
#   "revivals"     — one item per module file under core/levi/revival/
#   "playbooks"    — one item per *.md under core/levi/skill/playbooks/
#   "records"      — one item per ArchiveRecord in ~/.levi/archive (live)
#   "services"     — galaxy installs/services + daemon automations (live)
#   "capabilities" — one item per manifest `provides` entry on the shelves
#   "empty"        — no stock yet (honest zero + note)
#
WAREHOUSES: Dict[str, Dict[str, Any]] = {
    "methods": {
        "title": "Methods Warehouse",
        "summary": (
            "40 forgotten human techniques reborn as original LEVI works: "
            "pre-digital memory, retrieval, and organizing systems — loci, "
            "ACH, colon classification, morphological boxes — stdlib-only, "
            "local-first, defensive throughout."
        ),
        "shelves": ["methods"],
        "strategy": "techniques",
        "pull_hint": "from levi.methods import <technique>  (e.g. loci, ach, colon)",
    },
    "revivals": {
        "title": "Revivals Warehouse",
        "summary": (
            "Retired software systems and dead protocols re-implemented from "
            "scratch as LEVI's own code — telescript's capability tokens, "
            "plan9's namespaces, Arexx ports, blackboards, plus the telegraph "
            "office (FidoNet store-and-forward, Telex answerback, AppleTalk "
            "chooser) and the analog workbench (patch-panel ODE solving, "
            "printable nomographs, terminal Fourier playground) and the guild "
            "quarter (hallmark struck provenance, indenture ladder, museum of "
            "dead measures) — never copied, always remixed into something "
            "unreplicable."
        ),
        "shelves": ["revival", "telegraph", "analog", "craft"],
        "strategy": "revivals",
        "pull_hint": "from levi.revival import <system>  (e.g. telescript, plan9, arexx); python -m levi.telegraph <send|poll|inbox|...>; python -m levi.analog <run|parts|nomo|fourier>; python -m levi.craft <hallmark|guild|measures>",
    },
    "skills": {
        "title": "Skills & Playbooks Warehouse",
        "summary": (
            "823 original defensive blue-team playbooks (detection, analysis, "
            "hardening — never attack how-tos), data-driven registered with "
            "risk tags. The agent's warehouse shelf."
        ),
        "shelves": ["cyber-skills"],
        "strategy": "playbooks",
        "pull_hint": "SkillRegistry().get('<playbook-id>') — loaded via agent skill_load",
    },
    "archive": {
        "title": "Archive Knowledge Warehouse",
        "summary": (
            "The Smithsonian records: curated finds from the perpetual hunt — "
            "dead software, forgotten methods, tech-giant patterns — plus the "
            "dated courses/news/security corpora. Dated, queryable, citable."
        ),
        "shelves": ["archive", "knowledge", "academy", "bounty", "research"],
        "strategy": "records",
        "pull_hint": "ArchiveStore().get('<record-id>') or: python -m levi.archive search <q>",
    },
    "services": {
        "title": "Services Warehouse",
        "summary": (
            "Live services: galaxy-installed packages and their port→verb "
            "service directory, daemon automations and supervision, the "
            "perpetual hunt/pulse engine, and the bot service registry."
        ),
        "shelves": ["galaxy", "daemon", "perpetual", "bot-services", "serve"],
        "strategy": "services",
        "pull_hint": "python -m levi.galaxy services  ·  levi daemon  ·  python -m levi.perpetual pulse",
    },
    "games": {
        "title": "Games Warehouse",
        "summary": (
            "Fair-play additions: honest local games with fair mechanics and "
            "player-owned progress — dead genres, forgotten mechanics, and "
            "killed gaming platforms, remixed as additions (never predatory "
            "rebuilds)."
        ),
        "shelves": ["games"],
        "strategy": "capabilities",
        "pull_hint": (
            "python -m levi.games charter  ·  python -m levi.games play "
            "codebreak|tictactoe|nim  ·  python -m levi.games cipher"
        ),
        "note": (
            "Stocked by the perpetual hunt games wave (2026-09-16). Every "
            "game passes the Fair Play Charter (charter.py): no paid "
            "randomness, no streak punishment, no FOMO timers, free hints, "
            "offline-first, portable player-owned saves — plus wave-006 "
            "rules: no kill switch (Stadia lesson), no synthetic scarcity "
            "(battle-pass lesson), odds are public with an empirical audit "
            "hook (loot-box lesson). New: bagatelle (pins-in-a-board, "
            "prove-the-odds mode) and mancala (parametric game grammar with "
            "variant generator)."
        ),
    },
    "memory": {
        "title": "Memory & Growth Warehouse",
        "summary": (
            "The substrate everything reads and writes through: the memory "
            "store, hybrid/BM25 retrieval, cited RAG answers, the assistant "
            "prompt layer, and baby Levi's harvest→reflect→consolidate→journal "
            "growth loop."
        ),
        "shelves": [
            "memory-store",
            "memory-retrieval",
            "rag",
            "agent-assistant",
            "growth",
        ],
        "strategy": "capabilities",
        "pull_hint": "MemoryStore()  ·  levi remember / levi recall  ·  levi growth",
    },
    "finance": {
        "title": "Finance Warehouse",
        "summary": (
            "SI-powered paper-trading intelligence: quotes, indicators, "
            "advisory signals, and the simulated paper broker. Paper-only — "
            "live trading is structurally unwired and stays that way until "
            "Chauncey provides keys and asks."
        ),
        "shelves": ["finance"],
        "strategy": "capabilities",
        "pull_hint": "levi finance quote|indicators|signal|portfolio",
    },
    "factory": {
        "title": "Factory Warehouse",
        "summary": (
            "The production line that fills the warehouses: hunt (intake) → "
            "archive (processing) → manufacture (the never-stops build "
            "engine) → warehouse stocking → galaxy (distribution). "
            "Constructive software cascades, risk-ceiling bounded."
        ),
        "shelves": ["factory"],
        "strategy": "capabilities",
        "pull_hint": "levi factory  ·  SoftwareFactory().create(name, idea)",
    },
    "organism": {
        "title": "Organism Core Warehouse",
        "summary": (
            "The organism itself: the bloodstream turn pipeline and event bus, "
            "the four branching organs (echoverse / mandella / REIM / RIEM), "
            "life-pack export/import (LEVI duplicating itself), and the oath "
            "identity/trust substrate."
        ),
        "shelves": ["bloodstream", "organs", "lifepack", "oath"],
        "strategy": "capabilities",
        "pull_hint": "levi turn <text>  ·  levi lifepack  ·  from levi.bloodstream import run_turn",
    },
    "forge": {
        "title": "Forge Warehouse",
        "summary": (
            "LEVI's own code home: local git hosting that works with stock "
            "git clients, repo browser, issues, pull requests, local-first CI "
            "with no minute metering, and one-command full export of "
            "everything — the additions GitHub refuses."
        ),
        "shelves": ["forge"],
        "strategy": "capabilities",
        "pull_hint": "levi forge  ·  python -m levi.forge",
    },
    "operations": {
        "title": "Operations Warehouse",
        "summary": (
            "LEVI's operating layer: the graded signal plane (SILENT / NUDGE "
            "/ CARD / ESCALATE with cooldown instincts, focus mute, "
            "active-hours gate), the frozen creed of laws and tone masks, and "
            "the ledgers and rituals of a reliable operator — promises, "
            "decisions, interruptions, snapshots, drift, teach-back, energy, "
            "friction, sweeps, pre-mortems."
        ),
        "shelves": [
            "signals",
            "creed",
            "promises",
            "decisions",
            "interruptions",
            "snapshots",
            "drift",
            "teachback",
            "energy",
            "friction",
            "sweeps",
            "premortem",
            "copper",
            "verify",
        ],
        "strategy": "capabilities",
        "pull_hint": "python -m levi.signals  ·  python -m levi.promises  ·  from levi.creed import laws",
    },
    "commons": {
        "title": "Commons Warehouse",
        "summary": (
            "Portable social fabric — additions the giants refuse: "
            "communities you can leave any platform with, bridging-ranked "
            "discussion trees, disagreement-bridging without a central "
            "moderator, trust-graph classifieds with no ad layer, portable "
            "governance charters, guilt-free commitment devices, yearly "
            "recaps computed on-device, a sovereign feed reader, and a "
            "feed-ranking transparency lab that discloses exactly how "
            "engagement-bait scoring would rank your own posts, and a "
            "liberation ledger that prices your exit from data-hostage "
            "services."
        ),
        "shelves": [
            "communities",
            "threads",
            "bridging",
            "classifieds",
            "charters",
            "commitments",
            "recap",
            "feedreader",
            "feedlab",
            "liberation",
        ],
        "strategy": "capabilities",
        "pull_hint": "python -m levi.communities  ·  python -m levi.threads  ·  python -m levi.feedreader",
    },
    "craft": {
        "title": "Craft Warehouse",
        "summary": (
            "Sovereign instruments, local-first: true-delete ephemeral "
            "channels, scoped knowledge packs you own, attention dials for "
            "user-owned feed ranking, the capability-gated service protocol, "
            "mail triage over a local store, per-project vaults with explicit "
            "retention, a versioned workbench canvas, ritualized discovery "
            "over your own corpus, LAN presence rooms with no account and no "
            "server, clean-room link-graph search, and goal-directed "
            "recommendations with no engagement mining, and an honest trial "
            "engine that sells premium packs the shareware way: a real free "
            "slice, local receipts, no data harvest."
        ),
        "shelves": [
            "ephemera",
            "packs",
            "shareware",
            "dials",
            "capproto",
            "mailtriage",
            "vaults",
            "canvas",
            "discover",
            "presence",
            "honestsearch",
            "recommender",
        ],
        "strategy": "capabilities",
        "pull_hint": "python -m levi.ephemera  ·  python -m levi.vaults  ·  python -m levi.honestsearch",
    },
}


# ---------------------------------------------------------------------------
# Inventory counting (real counts, never estimates)
# ---------------------------------------------------------------------------


def _count_techniques() -> Tuple[int, List[Dict[str, str]]]:
    items = [
        {
            "id": f"methods.{name}",
            "kind": "technique",
            "summary": _first_doc_line(path),
        }
        for name, path in _module_files("methods")
    ]
    return len(items), items


def _count_revivals(shelves: List[str]) -> Tuple[int, List[Dict[str, str]]]:
    items: List[Dict[str, str]] = []
    for shelf in shelves:
        if shelf == "revival":
            items.extend(
                {
                    "id": f"revival.{name}",
                    "kind": "revival",
                    "summary": _first_doc_line(path),
                }
                for name, path in _module_files("revival")
            )
        else:
            # companion shelves (e.g. telegraph): manifest capabilities
            decl = DECLARATIONS.get(shelf, {})
            items.extend(
                {
                    "id": cap,
                    "kind": "capability",
                    "summary": cap.replace(".", " ").replace("-", " "),
                }
                for cap in decl.get("provides", [])
            )
    return len(items), items


def _count_playbooks() -> Tuple[int, List[Dict[str, str]]]:
    base = _pkg_root() / "skill" / "playbooks"
    paths = sorted(base.rglob("*.md")) if base.is_dir() else []
    items = [
        {
            "id": _playbook_id(p),
            "kind": "playbook",
            "summary": _playbook_title(p),
        }
        for p in paths
    ]
    return len(items), items


def _count_records() -> Tuple[int, List[Dict[str, str]]]:
    try:
        from levi.archive.store import ArchiveStore

        store = ArchiveStore()  # resolves ~/.levi/archive at call time
        items = [
            {
                "id": rec.id,
                "kind": "record",
                "summary": f"{rec.title} — {rec.summary[:80]}".strip(" —"),
            }
            for rec in store.all()
        ]
        return len(items), items
    except Exception:  # noqa: BLE001 — unreadable home is 0 records, honestly
        return 0, []


def _count_services() -> Tuple[int, List[Dict[str, str]]]:
    items: List[Dict[str, str]] = []
    try:  # galaxy installs (live runtime state)
        from levi.galaxy.service import GalaxyServices

        services = GalaxyServices()
        for pkg in services._registry.list():  # install records, oldest first
            items.append(
                {
                    "id": f"galaxy.{pkg.get('id', 'unknown')}",
                    "kind": "galaxy-package",
                    "summary": str(pkg.get("description") or pkg.get("id", ""))[:90],
                }
            )
    except Exception:  # noqa: BLE001
        pass
    try:  # daemon automations (live runtime state)
        from levi.daemon.automation import AutomationRegistry

        auto_dir = Path.home() / ".levi" / "bloodstream" / "automations"
        reg = AutomationRegistry(data_dir=auto_dir)
        for auto in getattr(reg, "list", lambda: [])() or []:
            name = getattr(auto, "name", None) or getattr(auto, "id", "automation")
            items.append(
                {
                    "id": f"daemon.{name}",
                    "kind": "automation",
                    "summary": str(getattr(auto, "description", "") or name)[:90],
                }
            )
    except Exception:  # noqa: BLE001
        pass
    return len(items), items


def _count_capabilities(shelves: List[str]) -> Tuple[int, List[Dict[str, str]]]:
    items = []
    for module in shelves:
        decl = DECLARATIONS.get(module)
        if not decl:
            continue
        for cap in decl.get("provides", []):
            items.append(
                {
                    "id": cap,
                    "kind": "capability",
                    "summary": cap.replace(".", " ").replace("-", " "),
                }
            )
    return len(items), items


def _inventory_for(name: str) -> Tuple[int, List[Dict[str, str]]]:
    """Real (count, items) for a warehouse — every strategy counts actual
    registered items, never estimates."""
    strategy = WAREHOUSES[name]["strategy"]
    shelves = WAREHOUSES[name]["shelves"]
    if strategy == "techniques":
        return _count_techniques()
    if strategy == "revivals":
        return _count_revivals(shelves)
    if strategy == "playbooks":
        return _count_playbooks()
    if strategy == "records":
        return _count_records()
    if strategy == "services":
        return _count_services()
    if strategy == "capabilities":
        return _count_capabilities(shelves)
    if strategy == "empty":
        return 0, []
    raise ValueError(f"unknown inventory strategy {strategy!r}")  # pragma: no cover


def _check_warehouse(name: str) -> str:
    if not isinstance(name, str) or name not in WAREHOUSES:
        raise ValueError(
            f"unknown warehouse {name!r}; available: " + ", ".join(sorted(WAREHOUSES))
        )
    return name


# ---------------------------------------------------------------------------
# Stable API
# ---------------------------------------------------------------------------


def list_warehouses() -> List[Dict[str, Any]]:
    """Every warehouse: name, title, summary, and its real inventory_count."""
    out = []
    for name in sorted(WAREHOUSES):
        wh = WAREHOUSES[name]
        count, _ = _inventory_for(name)
        out.append(
            {
                "name": name,
                "title": wh["title"],
                "summary": wh["summary"],
                "inventory_count": count,
            }
        )
    return out


def browse_warehouse(name: str) -> Dict[str, Any]:
    """One warehouse: its shelves (manifest modules) with one-line summaries,
    CLI reachability, and the real inventory count."""
    _check_warehouse(name)
    wh = WAREHOUSES[name]
    shelves = []
    for module in wh["shelves"]:
        decl = DECLARATIONS.get(module, {})
        shelves.append(
            {
                "module": module,
                "summary": _module_summary(module),
                "provides": list(decl.get("provides", [])),
                "requires": list(decl.get("requires", [])),
                "cli": CLI_COMMANDS.get(module, []),
            }
        )
    count, _ = _inventory_for(name)
    result: Dict[str, Any] = {
        "name": name,
        "title": wh["title"],
        "summary": wh["summary"],
        "shelves": shelves,
        "inventory_count": count,
        "pull_hint": wh.get("pull_hint", ""),
    }
    if wh.get("note"):
        result["note"] = wh["note"]
    return result


def warehouse_inventory(
    name: str, limit: Optional[int] = 50, offset: int = 0
) -> Dict[str, Any]:
    """Every item on a warehouse's shelves: id, kind, summary.

    Pagination is honest: ``total`` is the real count, ``truncated`` says
    whether the returned page is partial, and ``limit=None`` returns all.
    """
    _check_warehouse(name)
    total, items = _inventory_for(name)
    if offset < 0:
        raise ValueError(f"offset must be >= 0, got {offset}")
    page = items[offset:] if limit is None else items[offset : offset + limit]
    return {
        "warehouse": name,
        "total": total,
        "offset": offset,
        "limit": limit,
        "truncated": (offset + len(page)) < total,
        "items": page,
    }


def pull_from_shelf(warehouse: str, item_id: str) -> Dict[str, Any]:
    """Read-only lookup of one item: full detail + how to invoke it.

    Never executes — it inspects (parses docstrings, reads playbook
    frontmatter, reflects records). Unknown item -> ValueError naming
    what's available.
    """
    _check_warehouse(warehouse)
    strategy = WAREHOUSES[warehouse]["strategy"]

    if strategy == "techniques":
        return _pull_technique(item_id)
    if strategy == "revivals":
        if item_id.startswith("revival."):
            return _pull_revival(item_id)
        return _pull_capability(warehouse, item_id)
    if strategy == "playbooks":
        return _pull_playbook(item_id)
    if strategy == "records":
        return _pull_record(item_id)
    if strategy == "services":
        return _pull_service(item_id)
    if strategy == "capabilities":
        return _pull_capability(warehouse, item_id)
    raise ValueError(
        f"warehouse {warehouse!r} has no stock to pull from yet: "
        + (WAREHOUSES[warehouse].get("note") or "empty")
    )


# ---------------------------------------------------------------------------
# pull details
# ---------------------------------------------------------------------------


def _module_summary(module: str) -> str:
    summaries = {
        "methods": "40 forgotten human techniques, stdlib-only",
        "revival": "20 retired systems reborn as original LEVI works",
        "galaxy": "ecosystem packaging, registry, install, live services",
        "lifepack": "portable LEVI state — export/import/validate",
        "bloodstream": "the one-turn pipeline + event bus",
        "daemon": "control plane — automations, heartbeat, kernel",
        "perpetual": "the never-stops engine — hunt, pulse, supervision",
        "archive": "the Smithsonian records (dated queryable corpus)",
        "cyber-skills": "823 original defensive blue-team playbooks",
        "factory": "the production line — constructive software cascades",
        "finance": "AI paper-trading intelligence (paper-only)",
        "memory-store": "the substrate: write/read/list memory",
        "memory-retrieval": "hybrid + BM25 retrieval over memory",
        "rag": "cited answers over the substrate",
        "agent-assistant": "prompts + user-context loading",
        "growth": "baby Levi's learning loop (harvest→journal)",
        "knowledge": "dated corpora: courses, news, security",
        "academy": "courses → concepts → spaced repetition",
        "bounty": "defensive recon findings",
        "organs": "echoverse / mandella / REIM / RIEM",
        "oath": "identity / trust substrate",
        "bot-services": "service registry incl. research-brief",
    }
    return summaries.get(module, module)


def _public_members(path: Path) -> List[str]:
    """Public classes/functions of a module (parsed, never imported)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                names.append(node.name)
    return names


def _pull_technique(item_id: str) -> Dict[str, Any]:
    if not item_id.startswith("methods."):
        raise ValueError(
            f"unknown item {item_id!r} in warehouse 'methods'; "
            "item ids look like 'methods.loci'"
        )
    name = item_id[len("methods.") :]
    path = _pkg_root() / "methods" / f"{name}.py"
    if not path.is_file():
        raise ValueError(
            f"unknown technique {item_id!r}; see warehouse_inventory('methods')"
        )
    return {
        "warehouse": "methods",
        "id": item_id,
        "kind": "technique",
        "summary": _first_doc_line(path),
        "invoke": f"from levi.methods.{name} import ...",
        "detail": {
            "module": f"levi.methods.{name}",
            "path": str(path),
            "public_members": _public_members(path),
        },
    }


def _pull_revival(item_id: str) -> Dict[str, Any]:
    if not item_id.startswith("revival."):
        raise ValueError(
            f"unknown item {item_id!r} in warehouse 'revivals'; "
            "item ids look like 'revival.telescript'"
        )
    name = item_id[len("revival.") :]
    path = _pkg_root() / "revival" / f"{name}.py"
    if not path.is_file():
        raise ValueError(
            f"unknown revival {item_id!r}; see warehouse_inventory('revivals')"
        )
    return {
        "warehouse": "revivals",
        "id": item_id,
        "kind": "revival",
        "summary": _first_doc_line(path),
        "invoke": f"from levi.revival.{name} import ...",
        "detail": {
            "module": f"levi.revival.{name}",
            "path": str(path),
            "public_members": _public_members(path),
        },
    }


def _pull_playbook(item_id: str) -> Dict[str, Any]:
    if not item_id.startswith("playbook."):
        raise ValueError(
            f"unknown item {item_id!r} in warehouse 'skills'; "
            "item ids look like 'playbook.cyber.<name>'"
        )
    base = _pkg_root() / "skill" / "playbooks"
    rel = Path(*item_id[len("playbook.") :].split(".")).with_suffix(".md")
    path = base / rel
    if not path.is_file():
        raise ValueError(
            f"unknown playbook {item_id!r}; see warehouse_inventory('skills')"
        )
    return {
        "warehouse": "skills",
        "id": item_id,
        "kind": "playbook",
        "summary": _playbook_title(path),
        "invoke": f"SkillRegistry().get({item_id!r}) — loaded via agent skill_load",
        "detail": {
            "path": str(path),
            "title": _playbook_title(path),
            "category": "cybersecurity (defensive blue-team)",
        },
    }


def _pull_record(item_id: str) -> Dict[str, Any]:
    try:
        from levi.archive.store import ArchiveStore

        rec = ArchiveStore().get(item_id)
    except Exception:  # noqa: BLE001
        rec = None
    if rec is None:
        raise ValueError(
            f"unknown archive record {item_id!r}; see warehouse_inventory('archive')"
        )
    return {
        "warehouse": "archive",
        "id": rec.id,
        "kind": "record",
        "summary": f"{rec.title} — {rec.summary}",
        "invoke": f"ArchiveStore().get({rec.id!r})",
        "detail": {
            "title": rec.title,
            "era": rec.era,
            "kind": rec.kind,
            "mechanism": rec.mechanism,
            "decline": rec.decline,
            "revival_recipe": rec.revival_recipe,
            "levi_application": rec.levi_application,
            "rating": rec.rating,
            "status": rec.status,
        },
    }


def _pull_service(item_id: str) -> Dict[str, Any]:
    total, items = _count_services()
    for item in items:
        if item["id"] == item_id:
            invoke = (
                f"python -m levi.galaxy info {item_id[len('galaxy.') :]}"
                if item["kind"] == "galaxy-package"
                else "levi daemon"
            )
            return {
                "warehouse": "services",
                "id": item_id,
                "kind": item["kind"],
                "summary": item["summary"],
                "invoke": invoke,
                "detail": item,
            }
    raise ValueError(
        f"unknown service {item_id!r} (checked {total} live services); "
        "see warehouse_inventory('services')"
    )


def _pull_capability(warehouse: str, item_id: str) -> Dict[str, Any]:
    shelves = WAREHOUSES[warehouse]["shelves"]
    for module in shelves:
        decl = DECLARATIONS.get(module, {})
        if item_id in decl.get("provides", []):
            return {
                "warehouse": warehouse,
                "id": item_id,
                "kind": "capability",
                "summary": item_id.replace(".", " ").replace("-", " "),
                "invoke": _capability_invoke(module, item_id),
                "detail": {
                    "module": module,
                    "requires": list(decl.get("requires", [])),
                    "cli": CLI_COMMANDS.get(module, []),
                },
            }
    raise ValueError(
        f"unknown capability {item_id!r} in warehouse {warehouse!r}; "
        "see warehouse_inventory(%r)" % warehouse
    )


def _capability_invoke(module: str, capability: str) -> str:
    cli = CLI_COMMANDS.get(module, [])
    if cli:
        return "levi " + cli[0] if not cli[0].startswith("python") else cli[0]
    return f"import levi.{module.replace('-', '_')}"
