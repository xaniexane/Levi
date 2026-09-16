"""hunt — the perpetual hunt as procedure + state.

LEVI never stops hunting forgotten knowledge. This module is the procedure,
the state, and the handoff format — not the research itself. When a scheduled
hunt fires, the assistant performs the web research (deep_research), writes
the report to ``research_notes/``, and records the wave here:

- findings are validated as ``levi.archive.record.ArchiveRecord`` and queued
  for Archive ingest under ``~/.levi/perpetual/pending/``
- buildable findings (load-bearing / useful-pattern) are queued for building
  under the standing auto-approval in ``build_queue.jsonl``

Hunts never repeat ground: every completed wave's exclusion list is embedded
below, and ``plan_next_hunt()`` refuses to plan a theme whose ground is
covered unless every theme is covered (then it plans a deeper vein and says
so explicitly).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.archive.record import ArchiveRecord

HUNT_INTERVAL_DAYS = 7

# --------------------------------------------------------------------------
# Covered ground — exclusion lists from completed research waves.
# A future hunt must not re-cover these; plan_next_hunt() enforces it.
# --------------------------------------------------------------------------

WAVE1_DEAD_SOFTWARE = frozenset({
    "HyperCard", "Plan 9", "Smalltalk", "BeOS", "BFS", "WinFS", "Telescript",
    "ARexx", "AppleScript", "OpenDoc", "Lotus Agenda", "Memex",
    "Project Xanadu", "NLS", "Augment", "NoteCards", "Hearsay-II", "Soar",
    "ACT-R", "Subsumption architecture", "Viable System Model",
    "Conversation Theory", "Lisp Machines", "Oberon", "PLATO", "Erlang",
    "OTP", "NewtonScript", "Newton soups", "Canon Cat", "Lotus Improv",
    "Self", "ZigZag", "Apple Data Detectors",
})

WAVE2_DEAD_SOFTWARE_II = frozenset({
    "Inferno", "AmigaOS", "OS/2 Workplace Shell", "SOM", "NeXTSTEP",
    "QNX Neutrino", "AtheOS", "Syllable", "Amoeba", "Interlisp-D", "Eiffel",
    "Rebol", "Cedar", "Mesa", "Croquet", "Open Croquet", "Ecco Pro", "MORE",
    "InfoSelect", "Borland Sidekick", "Minitel", "GEnie", "The WELL",
    "CompuServe CB Simulator", "The Palace", "SHRDLU", "Eurisko", "KEE",
    "MRS", "ART", "Cyc", "Hyper-G", "HyperWave", "Microcosm", "Intermedia",
    "Pad++", "Jazz", "BumpTop", "Archy", "NeWS", "GOAP",
    "The Sims smart terrain", "Facade", "EROS", "Coyotos", "KeyKOS",
    "CAP computer", "MUMPS", "Pick", "MultiValue", "CODASYL", "GemStone",
    "MojoNation", "Groove Networks", "NIST RCS", "Lotus Notes replication",
    "Banyan VINES", "The Coordinator",
})

WAVE3_FORGOTTEN_METHODS = frozenset({
    "Method of Loci", "Llull", "Ars Magna", "Bruno memory wheels", "Pinakes",
    "Tironian Notes", "Commonplace Books", "Locke's Index", "Florilegia",
    "Paciolian triple-book", "Edge-notched cards", "McBee cards",
    "Optical-coincidence cards", "Peek-a-Boo cards", "Uniterm",
    "Colon Classification", "Ranganathan", "Mundaneum", "UDC", "Kardex",
    "Tickler File", "Ivy Lee", "Franklin moral ledger",
    "Analysis of Competing Hypotheses", "ACH", "Repertory Grid",
    "Morphological Analysis", "Zwicky Box", "TRIZ", "de Bono", "Water Logic",
    "Viable System Model", "Cybersyn", "Deming", "Trivium", "Quadrivium",
    "Ratio Studiorum", "Monitorial instruction", "Pecia system",
    "Nautical Almanac duplex verification", "Los Alamos T-5", "Therbligs",
    "Pneumatic dispatch", "Telegraph codebooks", "Q-Codes", "Prosigns",
    "Prowords", "Chappe semaphore", "Quipu", "Kriegsspiel",
    "RAND political-military gaming",
})


@dataclass(frozen=True)
class HuntTheme:
    id: str
    name: str
    brief: str
    exclusions: frozenset = frozenset()
    covered: bool = False  # True when a wave already covered this ground


HUNT_THEMES: List[HuntTheme] = [
    HuntTheme(
        id="dead-software-i",
        name="Dead software, wave 1",
        brief="Retired/ahead-of-their-time software systems (1980s-2000s).",
        exclusions=WAVE1_DEAD_SOFTWARE,
        covered=True,
    ),
    HuntTheme(
        id="dead-software-ii",
        name="Dead software, wave 2",
        brief="50 more retired/preserved/underused systems, OSes to game AI.",
        exclusions=WAVE2_DEAD_SOFTWARE_II,
        covered=True,
    ),
    HuntTheme(
        id="forgotten-methods",
        name="Forgotten methods",
        brief="40 forgotten human/organizational methods: memory arts, "
              "pre-digital retrieval, dead productivity systems, analytical "
              "techniques, management cybernetics, labor automation.",
        exclusions=WAVE3_FORGOTTEN_METHODS,
        covered=True,
    ),
    HuntTheme(
        id="dead-protocols",
        name="Dead protocols",
        brief="Forgotten communication and network protocols and signaling "
              "systems not covered in wave 3 (beyond Q-codes, telegraph "
              "codebooks, prowords): dead wire protocols, signaling codes, "
              "pre-internet networking rituals, lost radio procedure.",
        exclusions=frozenset({"Q-Codes", "Prosigns", "Prowords",
                              "Telegraph codebooks", "Chappe semaphore"}),
    ),
    HuntTheme(
        id="lost-interfaces",
        name="Lost interfaces",
        brief="Dead human-computer interface paradigms not covered in waves "
              "1-2 (beyond HyperCard, Canon Cat, BumpTop, Archy, NeWS): "
              "forgotten input devices, dead interaction models, abandoned "
              "UI metaphors and their mechanisms.",
        exclusions=frozenset({"HyperCard", "Canon Cat", "BumpTop", "Archy",
                              "NeWS", "OS/2 Workplace Shell"}),
    ),
    HuntTheme(
        id="abandoned-hardware",
        name="Abandoned hardware",
        brief="Dead machines, consoles, handhelds, and peripherals and the "
              "tricks their constraints forced: forgotten architectures, "
              "dead storage media workflows, lost embedded cleverness.",
    ),
    HuntTheme(
        id="forgotten-languages",
        name="Forgotten languages",
        brief="Dead programming languages, specification languages, "
              "shorthand systems, and constructed working languages not "
              "covered before (beyond Tironian notes, Interlisp-D, Rebol, "
              "Eiffel, SHRDLU): their ideas worth reviving.",
        exclusions=frozenset({"Tironian Notes", "Interlisp-D", "Rebol",
                              "Eiffel", "SHRDLU"}),
    ),
    HuntTheme(
        id="pre-digital-computation",
        name="Pre-digital computation",
        brief="Mechanical computing, human-computer pipelines, and analog "
              "methods beyond wave 3's T-5 and Nautical Almanac: desk-machine "
              "workflows, planimeters, nomography, analog programming.",
        exclusions=frozenset({"Los Alamos T-5",
                              "Nautical Almanac duplex verification"}),
    ),
    HuntTheme(
        id="dead-networks",
        name="Dead networks",
        brief="Dead online services, BBS cultures, and pre-web networks not "
              "covered in wave 2 (beyond Minitel, GEnie, The WELL, CB "
              "Simulator, The Palace): their social and technical mechanisms.",
        exclusions=frozenset({"Minitel", "GEnie", "The WELL",
                              "CompuServe CB Simulator", "The Palace"}),
    ),
    HuntTheme(
        id="lost-crafts",
        name="Lost crafts",
        brief="Pre-industrial knowledge systems and craft techniques beyond "
              "wave 3's quipu and pecia: guild knowledge transfer, dead "
              "measurement systems, forgotten making-methods with mechanisms "
              "worth reviving.",
        exclusions=frozenset({"Quipu", "Pecia system"}),
    ),
    HuntTheme(
        id="dead-genres-games",
        name="Dead genres: games",
        brief="Dead game genres and forgotten mechanics (parser interactive "
              "fiction, hotseat pass-and-play, dead multiplayer rituals), "
              "killed gaming platforms (Stadia and friends), and predatory "
              "monetization trades (loot boxes, pay-to-win, battle passes, "
              "vanishing subscription libraries) — always as honest playful "
              "ADDITIONS (local games, fair mechanics, player-owned "
              "progress, never predatory monetization), never rebuilds.",
    ),
]

THEMES_BY_ID = {t.id: t for t in HUNT_THEMES}


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

def perpetual_home(home: "str | os.PathLike[str] | None" = None) -> Path:
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    return base / ".levi" / "perpetual"


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def _write_private(path: Path, data: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


@dataclass
class HuntWave:
    id: str                 # e.g. "wave-004"
    theme_id: str
    planned_at: str         # ISO
    completed_at: Optional[str] = None
    research_slug: str = ""
    findings_count: int = 0
    status: str = "planned"  # planned | in-progress | completed
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "theme_id": self.theme_id,
            "planned_at": self.planned_at, "completed_at": self.completed_at,
            "research_slug": self.research_slug,
            "findings_count": self.findings_count,
            "status": self.status, "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HuntWave":
        if data.get("status") not in ("planned", "in-progress", "completed"):
            raise ValueError("bad wave status: %r" % data.get("status"))
        if data.get("theme_id") not in THEMES_BY_ID:
            raise ValueError("unknown theme: %r" % data.get("theme_id"))
        return cls(
            id=str(data["id"]), theme_id=str(data["theme_id"]),
            planned_at=str(data.get("planned_at", "")),
            completed_at=data.get("completed_at"),
            research_slug=str(data.get("research_slug", "")),
            findings_count=int(data.get("findings_count", 0)),
            status=str(data["status"]), notes=str(data.get("notes", "")),
        )


@dataclass
class HuntState:
    waves: List[HuntWave] = field(default_factory=list)
    next_due: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"waves": [w.to_dict() for w in self.waves],
                "next_due": self.next_due}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HuntState":
        if not isinstance(data, dict):
            raise ValueError("hunt state must be a mapping")
        return cls(
            waves=[HuntWave.from_dict(w) for w in data.get("waves", [])],
            next_due=str(data.get("next_due", "")),
        )


def _state_path(home) -> Path:
    return perpetual_home(home) / "hunt_state.json"


def load_state(home: "str | os.PathLike[str] | None" = None) -> HuntState:
    path = _state_path(home)
    try:
        return HuntState.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return HuntState()
    except (OSError, ValueError) as exc:
        raise ValueError("corrupt hunt state at %s: %s" % (path, exc)) from exc


def save_state(state: HuntState,
               home: "str | os.PathLike[str] | None" = None) -> None:
    _ensure_dir(perpetual_home(home))
    _write_private(_state_path(home), json.dumps(state.to_dict(), indent=2))


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class HuntPlan:
    wave_id: str
    theme: HuntTheme
    deeper_vein: bool        # True when all themes covered: re-hunt deeper
    exclusions: frozenset
    due: str
    instructions: str

    def describe(self) -> str:
        lines = [
            "HUNT PLAN %s" % self.wave_id,
            "Theme: %s" % self.theme.name,
            "Due: %s" % self.due,
        ]
        if self.deeper_vein:
            lines.append("NOTE: all themes covered before — hunt a DEEPER vein "
                         "of this theme; do not repeat covered ground.")
        lines.append("")
        lines.append("EXCLUSIONS (never re-cover these):")
        for name in sorted(self.exclusions):
            lines.append("  - %s" % name)
        lines.append("")
        lines.append(self.instructions)
        return "\n".join(lines)


def _next_wave_id(state: HuntState) -> str:
    taken = {w.id for w in state.waves}
    n = len(state.waves) + 1
    while "wave-%03d" % n in taken:
        n += 1
    return "wave-%03d" % n


def plan_next_hunt(state: HuntState,
                   now: Optional[datetime] = None) -> HuntPlan:
    """Plan the next hunt wave. Never repeats covered ground."""
    now = now or datetime.now(timezone.utc)
    covered_themes = {w.theme_id for w in state.waves
                      if w.status == "completed"}
    in_flight = [w for w in state.waves if w.status in ("planned", "in-progress")]
    if in_flight:
        # Don't stack plans: finish the open wave first.
        w = in_flight[0]
        theme = THEMES_BY_ID[w.theme_id]
        return HuntPlan(
            wave_id=w.id, theme=theme, deeper_vein=False,
            exclusions=theme.exclusions,
            due=state.next_due or now.isoformat(),
            instructions=_instructions(theme, w.id, False),
        )
    deeper_vein = False
    theme = next((t for t in HUNT_THEMES
                  if not t.covered and t.id not in covered_themes), None)
    if theme is None:
        # Everything covered: re-hunt the oldest theme, deeper.
        deeper_vein = True
        completed = [w for w in state.waves if w.status == "completed"]
        oldest = min(completed, key=lambda w: w.completed_at or "")
        theme = THEMES_BY_ID[oldest.theme_id]
    wave_id = _next_wave_id(state)
    due = (now + timedelta(days=HUNT_INTERVAL_DAYS)).isoformat()
    return HuntPlan(
        wave_id=wave_id, theme=theme, deeper_vein=deeper_vein,
        exclusions=theme.exclusions, due=due,
        instructions=_instructions(theme, wave_id, deeper_vein),
    )


#: Deep-web pass for hunts: public-but-unindexed sources (Wayback, Common
#: Crawl, sitemaps, feeds, arXiv, open portals). Polite, robots.txt-honoring,
#: public-only — see core/levi/research/deepweb.py for the hard boundaries.
DEEPWEB_SURVEY_CMD = (
    'python3 -m levi.research.deepweb survey "<topic>" '
    "[--domain <seed-domain>] [--save]"
)


def _instructions(theme: HuntTheme, wave_id: str, deeper_vein: bool) -> str:
    vein = ("This theme was hunted before — go DEEPER: a narrower sub-vein, "
            "primary sources, mechanisms the first pass missed. "
            if deeper_vein else "")
    return (
        "%sResearch brief for %s:\n"
        "Find 30-50 retired, discontinued, or ahead-of-their-time systems, "
        "methods, or techniques in this theme: %s\n"
        "For each: what/when, the concrete ahead-of-its-time mechanism, the "
        "real reason it died, a revival recipe paired with modern capability, "
        "one concrete local-first personal-AI application, and two source "
        "links. Label each LOAD-BEARING / USEFUL PATTERN / INSPIRATIONAL and "
        "flag romanticized history honestly.\n"
        "Write the report to research_notes/<slug>/report.md, then record the "
        "wave with: python3 -m levi.perpetual hunt-record %s findings.jsonl\n"
        "where findings.jsonl holds one ArchiveRecord JSON object per line.\n"
        "Deep-web pass (public sources only, robots.txt-honoring): %s\n"
        "%s"
        % (vein, wave_id, theme.brief, wave_id, DEEPWEB_SURVEY_CMD,
           HARD_ROUTE_LAW)
    )


HANDOFF_FORMAT = """\
# Hunt handoff format (for the scheduled worker)

1. `python3 -m levi.perpetual hunt-plan` → shows the next wave + exclusions.
2. Perform the research (deep_research subagent): 30-50 entries, each with
   what/when, mechanism, cause of death, revival recipe, LEVI application,
   two sources, value rating, skepticism flags.
3. Write `research_notes/<slug>/report.md`.
4. Convert entries to ArchiveRecord JSON (one per line) in `findings.jsonl`:
   required fields: id (arch-<tag>-...), title, kind
   (software|method|technique), summary, mechanism, decline, revival_recipe,
   levi_application; sources (http URLs); rating; status; provenance
   {found_date, research_slug}.
5. `python3 -m levi.perpetual hunt-record <wave-id> findings.jsonl`
   → validates every record (deny-closed), queues them for Archive ingest,
   queues buildable items under the standing auto-approval.
6. Build the load-bearing findings into LEVI (standing pre-approval).
   HARD-ROUTE LAW: where a find carries a cost (paid API, licensed
   software, proprietary dependency), never recommend paying — plan a
   clean-room recreation: analyze the pattern, rebuild stdlib-only,
   local-first.
7. Report back: wave id, findings count, build SHAs.
"""

# --------------------------------------------------------------------------
# Hard-route law
# --------------------------------------------------------------------------

HARD_ROUTE_LAW = (
    "HARD-ROUTE LAW: where a hunt find carries a cost — a paid API, licensed "
    "software, a proprietary dependency, a subscription — the hunt must never "
    "recommend paying. Instead it plans a clean-room recreation: analyze the "
    "pattern, then rebuild it from scratch, stdlib-only, local-first. Where "
    "there's a cost, take the hard route."
)

#: Lowercase substrings suggesting a revival recipe leans on something
#: paid/proprietary. Heuristic, not proof — flags for human review.
COST_SIGNALS = (
    "paid api", "api key", "api-key", "subscription", "saas",
    "licens",  # license, licensed, licensing
    "proprietary", "per-seat", "per seat", "paywall",
    "monthly fee", "annual fee", "purchase", "commercial",
)


def hard_route_review(records: List[ArchiveRecord]) -> List[Dict[str, Any]]:
    """Flag findings whose revival recipe mentions cost-bearing dependencies.

    Returns ``[{"record_id", "title", "signals"}]``. A flagged finding is not
    refused — the flag means its build plan must be a clean-room recreation
    (analyze the pattern, rebuild stdlib-only, local-first), never a purchase.
    """
    flagged: List[Dict[str, Any]] = []
    for rec in records:
        hay = ("%s\n%s" % (rec.revival_recipe, rec.levi_application)).lower()
        signals = sorted({sig for sig in COST_SIGNALS if sig in hay})
        if signals:
            flagged.append({"record_id": rec.id, "title": rec.title,
                            "signals": signals})
    return flagged


# --------------------------------------------------------------------------
# Recording
# --------------------------------------------------------------------------

_BUILDABLE_RATINGS = ("load-bearing", "useful-pattern")


def _pending_dir(home) -> Path:
    return _ensure_dir(perpetual_home(home) / "pending")


def _build_queue_path(home) -> Path:
    return perpetual_home(home) / "build_queue.jsonl"


def queue_for_archive(records: List[ArchiveRecord], wave_id: str,
                      home: "str | os.PathLike[str] | None" = None) -> Path:
    """Write validated records to the Archive ingest queue.

    The Archive's own ingest consumes these files; until it does, they are
    the durable pending record. Records are validated ArchiveRecords —
    anything malformed was already refused by the constructor.
    """
    path = _pending_dir(home) / ("%s.jsonl" % wave_id)
    lines = [json.dumps(r.to_dict(), ensure_ascii=False) for r in records]
    _write_private(path, "\n".join(lines) + "\n" if lines else "")
    return path


def queue_for_build(records: List[ArchiveRecord], wave_id: str,
                    home: "str | os.PathLike[str] | None" = None,
                    now: Optional[datetime] = None) -> int:
    """Queue buildable findings under the standing auto-approval.

    Only load-bearing and useful-pattern findings are queued; inspirational
    ones stay in the Archive as inspiration, not build orders.
    """
    now = now or datetime.now(timezone.utc)
    _ensure_dir(perpetual_home(home))
    path = _build_queue_path(home)
    queued = 0
    flagged_ids = {f["record_id"] for f in hard_route_review(records)}
    with open(path, "a", encoding="utf-8") as fh:
        for rec in records:
            if rec.rating not in _BUILDABLE_RATINGS:
                continue
            item = {
                "wave_id": wave_id,
                "record_id": rec.id,
                "title": rec.title,
                "kind": rec.kind,
                "rating": rec.rating,
                "queued_at": now.isoformat(),
                "status": "queued",
                "hard_route": rec.id in flagged_ids,
            }
            if rec.id in flagged_ids:
                item["hard_route_note"] = (
                    "clean-room recreation required: analyze the pattern, "
                    "rebuild stdlib-only, local-first; never pay.")
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            queued += 1
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return queued


def read_build_queue(
        home: "str | os.PathLike[str] | None" = None) -> List[Dict[str, Any]]:
    path = _build_queue_path(home)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def pending_waves(home: "str | os.PathLike[str] | None" = None) -> List[str]:
    d = perpetual_home(home) / "pending"
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.jsonl"))


def record_hunt(state: HuntState, wave_id: str, records: List[ArchiveRecord],
                research_slug: str,
                home: "str | os.PathLike[str] | None" = None,
                now: Optional[datetime] = None) -> Dict[str, Any]:
    """Record a completed hunt wave. Deny-closed on every input.

    - every record must already be a validated ArchiveRecord
    - the wave must exist and not already be completed
    - nothing is half-recorded: state is saved only after queues are written
    """
    now = now or datetime.now(timezone.utc)
    if not research_slug or not research_slug.strip():
        raise ValueError("research_slug is required")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", research_slug):
        raise ValueError("bad research_slug: %r" % research_slug)
    wave = next((w for w in state.waves if w.id == wave_id), None)
    if wave is None:
        # The plan was produced but state was never saved (e.g. fresh home):
        # create the wave from the plan rather than refusing honest work.
        theme_id = next(
            (t.id for t in HUNT_THEMES if not t.covered), HUNT_THEMES[0].id)
        wave = HuntWave(id=wave_id, theme_id=theme_id,
                        planned_at=now.isoformat(), status="planned")
        state.waves.append(wave)
    if wave.status == "completed":
        raise ValueError("wave %s is already completed" % wave_id)
    if not records:
        raise ValueError("refusing to record an empty hunt")
    seen = set()
    for rec in records:
        if not isinstance(rec, ArchiveRecord):
            raise ValueError("findings must be ArchiveRecord instances")
        if rec.id in seen:
            raise ValueError("duplicate record id in findings: %s" % rec.id)
        seen.add(rec.id)

    pending_path = queue_for_archive(records, wave_id, home)
    build_queued = queue_for_build(records, wave_id, home, now)
    hard_route_flagged = hard_route_review(records)

    wave.status = "completed"
    wave.completed_at = now.isoformat()
    wave.research_slug = research_slug
    wave.findings_count = len(records)
    state.next_due = (now + timedelta(days=HUNT_INTERVAL_DAYS)).isoformat()
    save_state(state, home)
    return {
        "wave_id": wave_id,
        "findings": len(records),
        "pending_file": str(pending_path),
        "build_queued": build_queued,
        "hard_route_flagged": hard_route_flagged,
        "next_due": state.next_due,
    }
