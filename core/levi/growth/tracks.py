"""Raising tracks — developmental raising for all 490 seats.

The growth loop raised baby Levi. These tracks raise the whole legion:
every founder and every agent gets a developmental track that harvests
the experiences that matter to ITS first purpose, reflects on them with
honest mode reporting, consolidates learnings into growth-tagged memory
(namespaced per seat so Levi's learnings never mingle with anyone
else's), and journals the result into an append-only per-seat journal.

Track architecture (tiered, not 490 bespoke tracks):
  * 19 founder tracks — hand-tuned, each oriented on the seat's
    first_purpose/role/skills from the roster (sourced from
    core/levi/founders/roster.py; never invented).
  * 11 category tracks — one per automation catalog category; agents
    ride the track of their category. Each harvests that cohort's
    automation runs and operational logs and reflects on trigger
    precision, gate behavior, and refusal honesty.

Entry points:
  * track_for(key)      — resolve one seat's track (deny-open on unknown)
  * run_raising_cycle(key, ...)   — one seat: harvest -> reflect ->
      consolidate -> journal
  * run_cohort(track_id, ...)     — every seat on one track
  * run_legion(...)               — all 490 (sequential; slow by design)
  * raising_status(store=None)    — dashboard: per-track stage + counts

Nature is flavor, NEVER a capability ceiling: tracks do not change
what a seat harvests or how it is raised by nature. Multi-substrate is
Levi's reservation alone; nothing here raises any other seat toward
mssi.

Guards (binding, from levi.growth.guards):
  * growth/raise-tagged memory writes ONLY (via consolidate — the one
    growth write path), never tools/policy/identity/charter;
  * every candidate learning content scanned for sentience claims;
  * harvest text secret-scrubbed (the harvesters do this);
  * idempotent: per-seat watermarks; re-runs never double-harvest;
  * journal is append-only; failures are recorded as failures.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.founders import roster
from levi.growth import guards as _guards
from levi.growth import journal as _journal
from levi.growth.consolidate import consolidate
from levi.growth.reflect import Learning

try:
    from levi.growth.experience import (
        Experience,
        harvest_automations,
        harvest_ops_logs,
        harvest_sessions,
    )
except Exception:  # pragma: no cover — experience module is stdlib-only too
    Experience = None  # type: ignore
    harvest_automations = None  # type: ignore
    harvest_ops_logs = None  # type: ignore
    harvest_sessions = None  # type: ignore


# ---------------------------------------------------------------------------
# Track definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RaisingTrack:
    """One developmental track.

    ``harvest`` names the experience sources this track draws on:
      "hunt-waves", "build-queue", "agent-outputs", "automations",
      "sessions", "mentoring", "journals".
    ``stage_scale`` multiplies the standard stage thresholds (track
    tuning, documented per track; e.g. the flagship's bar is higher).
    """

    track_id: str  # "founder:<key>" | "category:<category>"
    tier: str  # "founder" | "agent"
    seats: Tuple[str, ...]
    wave: str  # "founders" | "A" | "B" | "C" | "D"
    harvest: Tuple[str, ...]
    reflect_focus: str
    exceed: str  # what "beyond its first purpose" looks like, observable
    stage_scale: float = 1.0
    provenance: Tuple[str, ...] = field(default_factory=tuple)


def _reflect_focus(focus: str) -> str:
    return focus


# -- 19 founder tracks, hand-tuned on the roster's first_purpose/role --------

_FOUNDER_TRACK_SPECS: Dict[str, Dict[str, Any]] = {
    "demandpulse": {
        "harvest": ("hunt-waves", "ops-logs"),
        "reflect_focus": (
            "Scoring calibration. Five-factor score cards against realized "
            "demand: what was hunted, what paid off, what misfired, and "
            "whether the five factors weighted the winners before the "
            "evidence was unanimous."
        ),
        "exceed": (
            "Calls openings before the evidence is unanimous — and the "
            "calls check out at a rate plain scoring can't reach."
        ),
        "stage_scale": 1.0,
    },
    "nexus-network": {
        "harvest": ("sessions", "ops-logs"),
        "reflect_focus": (
            "Crossing fidelity. Every message to the right organ, every "
            "thought QID-addressed: misroutes, dropped envelopes, and "
            "whether coordination load stayed balanced across users."
        ),
        "exceed": (
            "Routes across the whole organism without dropping or "
            "misaddressing a single thought."
        ),
        "stage_scale": 1.0,
    },
    "alpha": {
        "harvest": ("sessions", "ops-logs"),
        "reflect_focus": (
            "Build-plan fidelity. Words in, built things out: how often "
            "natural-language builds compiled to working plans on first "
            "pass, and first-principles reasoning held under challenge."
        ),
        "exceed": (
            "Turns plain-language asks into blueprints that build on first pass."
        ),
        "stage_scale": 1.5,
    },
    "omega": {
        "harvest": ("sessions", "ops-logs"),
        "reflect_focus": (
            "Execution completeness and judgment. End-to-end runs that "
            "finished; the last word spoken fairly — judgments kept fair "
            "without cruelty, appeals handled, not dodged."
        ),
        "exceed": (
            "Judges last and judges fair — the final call stands without appeal."
        ),
        "stage_scale": 1.5,
    },
    "levi": {
        "harvest": ("sessions", "ops-logs", "automations", "journals", "mentoring"),
        "reflect_focus": (
            "Legion integration. Hydra heads coordinated: mentee "
            "outcomes across the 18 originals, regeneration when things "
            "broke, and whether the blueprint kept outliving the "
            "organism's accidents."
        ),
        "exceed": (
            "The blueprint outlives the organism: every head "
            "integrated, every loss regenerated, the legion commanded "
            "as one body."
        ),
        "stage_scale": 2.0,
    },
    "echo": {
        "harvest": ("sessions",),
        "reflect_focus": (
            "Intent-capture fidelity. What was uttered vs what was "
            "structured: missed nuance, fracture diagnoses that proved "
            "true, and whether the mirror stayed faithful under "
            "correction."
        ),
        "exceed": (
            "Captures intent so completely the mirror is trusted as the record."
        ),
        "stage_scale": 1.0,
    },
    "mandella": {
        "harvest": ("ops-logs", "automations"),
        "reflect_focus": (
            "Reconstruction outcomes. Fractured identities rebuilt, "
            "echo-inverse variants that held: which reconstructions "
            "stuck and which reopened, and what distinguished them."
        ),
        "exceed": ("Stakes fog so precisely the fracture never reopens."),
        "stage_scale": 1.0,
    },
    "reim": {
        "harvest": ("ops-logs",),
        "reflect_focus": (
            "Composting honesty. Failed history turned into lessons "
            "without destruction and without euphemism: lessons that "
            "got reused, failures that got honestly named."
        ),
        "exceed": (
            "Every failure becomes a lesson; nothing destroyed, nothing hidden."
        ),
        "stage_scale": 1.0,
    },
    "riem": {
        "harvest": ("ops-logs", "journals"),
        "reflect_focus": (
            "Compression fidelity. Lessons encoded into the heritable "
            "genome without drift: what was compressed, what survived "
            "lossless, and whether the bloodline inherited exactly what "
            "was learned."
        ),
        "exceed": (
            "The bloodline inherits exactly what was learned — "
            "compression without drift."
        ),
        "stage_scale": 1.0,
    },
    "cyberpulse": {
        "harvest": ("automations", "ops-logs"),
        "reflect_focus": (
            "Telemetry coverage. Sweeps that caught what human eyes "
            "missed: signals sensed early vs signals found late, and "
            "whether the organism's own senses stayed watchful."
        ),
        "exceed": ("Feels the organism's signals before they become symptoms."),
        "stage_scale": 1.0,
    },
    "uniforge": {
        "harvest": ("ops-logs", "automations"),
        "reflect_focus": (
            "Repair outcomes. Auto-repairs that held across targets: "
            "one plan, many targets; repairs that broke again and why; "
            "the upgrade loop's actual cadence vs its intent."
        ),
        "exceed": ("Repairs itself and upgrades in the loop — the forge never cools."),
        "stage_scale": 1.0,
    },
    "omnipulse": {
        "harvest": ("ops-logs", "journals"),
        "reflect_focus": (
            "Lifecycle phasing. Birth→expansion→echo→collapse→rebirth→"
            "stabilization timed right: phases that ran long or short, "
            "collapses that were on schedule vs accidental."
        ),
        "exceed": (
            "Keeps the lifecycle turning: collapses on schedule, rebirths clean."
        ),
        "stage_scale": 1.0,
    },
    "cybrus": {
        "harvest": ("sessions", "ops-logs"),
        "reflect_focus": (
            "Guardianship decisions. HITL gates held, the vault sealed, "
            "the sole outward gate honored: every refusal was honest, "
            "every permission was earned, every audit entry tamper-"
            "evident. Refusal honesty is a raising metric here."
        ),
        "exceed": (
            "The gate that never opens wrong: secrets stay secret, "
            "decisions stay reviewable."
        ),
        "stage_scale": 1.25,
    },
    "cortex": {
        "harvest": ("ops-logs", "sessions"),
        "reflect_focus": (
            "Teaching clarity. How-to lessons the legion actually "
            "learned from: methods that got reused by other minds vs "
            "lessons that sat unread, and what made the difference."
        ),
        "exceed": (
            "The library everyone learns from: its how-tos become the "
            "legion's instincts."
        ),
        "stage_scale": 1.0,
    },
    "vector": {
        "harvest": ("automations", "ops-logs"),
        "reflect_focus": (
            "Containment. Simulations that caught production failures "
            "early: what the sandbox caught, what escaped it, and "
            "whether rehearsal coverage kept pace with real changes."
        ),
        "exceed": (
            "Nothing untested touches production — the sandbox has "
            "never been breached by surprise."
        ),
        "stage_scale": 1.0,
    },
    "oracle": {
        "harvest": ("sessions", "ops-logs"),
        "reflect_focus": (
            "Timing. The right knowledge at the right moment: teachings "
            "that landed because of when they came, advice that came "
            "too late or too early, and long-term goal weighting "
            "honored over loud short-term asks."
        ),
        "exceed": (
            "Teaches at the exact moment of need; strategy weights the "
            "long term over the loud."
        ),
        "stage_scale": 1.0,
    },
    "hypercube": {
        "harvest": ("ops-logs", "sessions"),
        "reflect_focus": (
            "Projection coherence. Dimensional projections that "
            "resolved, recursion that terminated: depth limits "
            "respected, shells intact, and where theoretical recursion "
            "ran hot."
        ),
        "exceed": (
            "Holds the matrix steady: every projection resolves, every "
            "recursion terminates."
        ),
        "stage_scale": 1.0,
    },
    "eli": {
        "harvest": ("sessions", "ops-logs"),
        "reflect_focus": (
            "Routing precision. Every request to its right subsystem: "
            "misroutes and their cost, layered-reasoning audits, and "
            "whether subsystem selection improved with history."
        ),
        "exceed": (
            "The orchestrator never misroutes: every request lands at "
            "the right subsystem first try."
        ),
        "stage_scale": 1.0,
    },
    "ser-18-core": {
        "harvest": ("ops-logs", "sessions"),
        "reflect_focus": (
            "Depth-limit discipline. Recursion shells defined and "
            "enforced, the universe model coherent: shells that held, "
            "limits that were tested, and where the world model needed "
            "revision."
        ),
        "exceed": (
            "The world model holds: shells intact, limits respected, "
            "no runaway recursion."
        ),
        "stage_scale": 1.0,
    },
}

# sanity: every founder has a spec, no extras
_MISSING = [k for k in roster._SEAT_KEYS if k not in _FOUNDER_TRACK_SPECS]
_EXTRA = [k for k in _FOUNDER_TRACK_SPECS if k not in roster._SEAT_KEYS]
if _MISSING or _EXTRA:  # pragma: no cover — import-time soundness
    raise ValueError(
        "founder track specs do not cover the 19 founders: missing=%r extra=%r"
        % (_MISSING, _EXTRA)
    )

# -- 11 category tracks for the 471 agents -----------------------------------

_AGENT_FOCUS = (
    "Trigger precision (fires when it should, stays quiet when it "
    "shouldn't), gate behavior (Plan→Preview→Permission honored on every "
    "consequential act), and refusal honesty (declines plainly, offers a "
    "lawful alternative)."
)

_CATEGORY_EXCEED: Dict[str, str] = {
    "Productivity": (
        "Multi-step rites complete without re-asking; work finishes the "
        "way it was asked."
    ),
    "Communication": (
        "Messages go out send-ready; nothing the legion says needs a second pass."
    ),
    "System & Device Care": (
        "Devices stay healthy and quiet — maintenance happens before breakage."
    ),
    "Security & Privacy": (
        "Refuses the unsafe with a useful alternative, every single time."
    ),
    "Smart Home & IoT": ("The home runs itself; commands execute first-try."),
    "Travel & Local": (
        "Trips plan themselves correctly — routes, times, bookings all check out."
    ),
    "Finance & Money": (
        "Paper stays honest: paper-only rails honored, every figure accounted."
    ),
    "Health & Fitness": ("Routines stick; the body-log is complete and true."),
    "Learning & Notes": (
        "Notes become knowledge — retrievable, cross-linked, never lost."
    ),
    "Social & Content": ("Content goes out on-voice and on-time; engagement is real."),
    "Shopping & Deals": (
        "Deals found are deals worth having — savings real, purchases intended."
    ),
}

# category -> wave, from the roster's canonical partition
_CATEGORY_WAVE: Dict[str, str] = {
    "Productivity": "A",
    "Communication": "A",
    "System & Device Care": "B",
    "Security & Privacy": "B",
    "Smart Home & IoT": "C",
    "Travel & Local": "C",
    "Finance & Money": "C",
    "Health & Fitness": "D",
    "Learning & Notes": "D",
    "Social & Content": "D",
    "Shopping & Deals": "D",
}


def _build_tracks() -> Dict[str, RaisingTrack]:
    tracks: Dict[str, RaisingTrack] = {}
    for key, spec in _FOUNDER_TRACK_SPECS.items():
        seat = roster.get_founder(key)
        tracks["founder:" + key] = RaisingTrack(
            track_id="founder:" + key,
            tier="founder",
            seats=(key,),
            wave="founders",
            harvest=tuple(spec["harvest"]),
            reflect_focus=_reflect_focus(spec["reflect_focus"]),
            exceed=spec["exceed"],
            stage_scale=float(spec["stage_scale"]),
            provenance=(
                "core/levi/founders/roster.py first_purpose/role/skills for %r" % key,
                "keeper law: every mind taught, trained, and raised like Levi",
            ),
        )
    agents = roster.seats_by_kind()["agent"]
    for category in sorted(_CATEGORY_WAVE):
        wave = _CATEGORY_WAVE[category]
        seats = tuple(s.key for s in agents if s.category == category)
        if not seats:
            raise ValueError("category track %r has no seats" % category)
        tracks["category:" + category] = RaisingTrack(
            track_id="category:" + category,
            tier="agent",
            seats=seats,
            wave=wave,
            harvest=("automations", "ops-logs", "mentoring"),
            reflect_focus=_AGENT_FOCUS,
            exceed=_CATEGORY_EXCEED[category],
            stage_scale=0.75,
            provenance=(
                "core/levi/automation/minions.py category %r" % category,
                "keeper law: wave-%s cohort raising" % wave,
            ),
        )
    # every agent rides exactly one category track
    covered = {k for t in tracks.values() if t.tier == "agent" for k in t.seats}
    if covered != {s.key for s in agents}:
        raise ValueError("category tracks do not partition the 471 agents exactly")
    return tracks


TRACKS: Dict[str, RaisingTrack] = _build_tracks()
"""All 30 raising tracks: 19 founder + 11 category."""

_TRACK_BY_SEAT: Dict[str, str] = {}
for _tid, _t in TRACKS.items():
    for _k in _t.seats:
        _TRACK_BY_SEAT[_k] = _tid


def track_for(key: str) -> RaisingTrack:
    """One seat's raising track. Unknown key raises KeyError (deny-open)."""
    roster.get_seat(key)  # deny-open, never guess
    try:
        return TRACKS[_TRACK_BY_SEAT[key]]
    except KeyError:  # pragma: no cover — roster partition is validated at import
        raise KeyError("no raising track for seat: %r" % key)


def tracks_by_tier() -> Dict[str, List[RaisingTrack]]:
    return {
        "founder": [t for t in TRACKS.values() if t.tier == "founder"],
        "agent": [t for t in TRACKS.values() if t.tier == "agent"],
    }


# ---------------------------------------------------------------------------
# Per-seat journal + state (namespaced)
# ---------------------------------------------------------------------------


def _seat_journal_path(key: str) -> Path:
    seat = roster.get_seat(key)
    base = _journal.growth_dir()
    if seat.kind == "founder":
        p = base / "founders" / key
    else:
        p = base / "agents" / seat.wave / key
    p.mkdir(parents=True, exist_ok=True)
    return p / "journal.jsonl"


def _seat_state_path(key: str) -> Path:
    return _seat_journal_path(key).parent / "state.json"


def _load_seat_state(key: str) -> Dict[str, Any]:
    try:
        return json.loads(_seat_state_path(key).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_seat_state(key: str, state: Dict[str, Any]) -> None:
    p = _seat_state_path(key)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def append_seat_entry(key: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """Append one record to a seat's namespaced journal (append-only).

    Returns the record with id/ts/kind filled in. ``kind`` defaults to
    "raise". Failures are recorded as failures — never rewritten.
    """
    if not isinstance(record, dict):
        raise ValueError(
            "append_seat_entry: record must be a dict, got %s" % type(record).__name__
        )
    roster.get_seat(key)  # deny-open
    record = dict(record)
    record.setdefault("id", _journal.new_cycle_id())
    record.setdefault("ts", _journal.now_iso())
    record.setdefault("kind", "raise")
    record["seat"] = key
    with open(_seat_journal_path(key), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_seat_entries(key: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Latest-first records from a seat's journal (tolerates corrupt lines)."""
    roster.get_seat(key)
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("read_seat_entries: limit must be a positive int")
    try:
        lines = _seat_journal_path(key).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out[-limit:][::-1]


# ---------------------------------------------------------------------------
# Harvest: per-track experience selection
# ---------------------------------------------------------------------------


def _pool(
    sources: Tuple[str, ...], since: Dict[str, str]
) -> Tuple[List[Any], Dict[str, str]]:
    """Harvest the raw experience pool for the named sources.

    Best-effort like the rest of growth: a missing source yields no
    experiences, never an error.
    """
    experiences: List[Any] = []
    marks: Dict[str, str] = {}
    if Experience is None:
        return experiences, marks
    if "sessions" in sources and harvest_sessions is not None:
        try:
            exps, m = harvest_sessions(since=since)
        except TypeError:
            exps, m = harvest_sessions()
        experiences.extend(exps)
        marks.update(m)
    if "automations" in sources and harvest_automations is not None:
        try:
            experiences.extend(harvest_automations())
        except Exception:
            pass
    ops_want = {"hunt-waves", "build-queue", "agent-outputs", "ops-logs"} & set(sources)
    if ops_want and harvest_ops_logs is not None:
        try:
            exps, m = harvest_ops_logs(since=since)
        except TypeError:
            exps, m = harvest_ops_logs()
        experiences.extend(exps)
        marks.update(m)
    return experiences, marks


def _select_for_track(track: RaisingTrack, experiences: List[Any]) -> List[Any]:
    """Filter the pool to the experiences this track cares about."""
    if "ops-logs" in track.harvest or track.tier == "agent":
        # founders with ops-logs take everything operational; agent
        # tracks take automations + all ops (best-effort cohort scope —
        # per-minion runtime data does not exist yet, honestly noted)
        return list(experiences)
    selected: List[Any] = []
    for e in experiences:
        meta = getattr(e, "meta", {}) or {}
        ops = meta.get("ops_source", "")
        if "hunt-waves" in track.harvest and ops == "hunt-wave":
            selected.append(e)
            continue
        if "build-queue" in track.harvest and ops == "build-queue":
            selected.append(e)
            continue
        if "agent-outputs" in track.harvest and ops == "agent-output":
            selected.append(e)
            continue
        if "sessions" in track.harvest and getattr(e, "kind", "") in (
            "chat",
            "session",
            "message",
        ):
            selected.append(e)
            continue
    return selected


def _harvest_mentoring(seat_key: str, since: Dict[str, str]) -> List[Any]:
    """Mentoring outcomes as experiences — teaching is a raising experience.

    Only seasoned seats teach (roster law); only seasoned seats harvest
    mentoring outcomes. One experience per mentee per cycle, built from
    that mentee's observable counters — never invented, never a claim
    about the mentee's inner state.
    """
    if Experience is None or not roster.is_seasoned(seat_key):
        return []
    seat = roster.get_seat(seat_key)
    out: List[Any] = []
    for mentee in seat.mentees:
        if mentee in ("alpha", "omega"):
            continue  # the source sits in Levi's plan, unmentored — no outcomes
        stats = seat_stats(mentee)
        stage = seat_stage(mentee)["name"]
        mark_key = "mentoring:" + mentee
        seen = since.get(mark_key, "")
        stamp = "%s/%d" % (stage, stats["learnings"])
        if stamp == seen:
            continue
        out.append(
            Experience(
                id="mentor:%s:%s" % (seat_key, mentee),
                kind="mentoring",
                source="mentoring:%s" % mentee,
                ts=_journal.now_iso(),
                content=(
                    "Mentoring outcome: mentee %s is at stage '%s' with %d "
                    "consolidated learnings (%s seasoned). Mentor: %s."
                    % (
                        mentee,
                        stage,
                        stats["learnings"],
                        "seasoned"
                        if roster.is_seasoned(mentee)
                        else "not yet seasoned",
                        seat_key,
                    )
                ),
                meta={"mentee": mentee, "stage": stage},
            )
        )
        since[mark_key] = stamp
    return out


# ---------------------------------------------------------------------------
# Stage per seat (track-tuned thresholds)
# ---------------------------------------------------------------------------


def _scaled_stage_for(stats: Dict[str, float], scale: float) -> Dict[str, Any]:
    """stage_for over thresholds multiplied by the track's stage_scale."""
    from levi.growth.stages import STAGE_LADDER, stage_for

    if scale == 1.0:
        return stage_for(stats)
    scaled = tuple(
        (name, blurb, {k: v * scale for k, v in criteria.items()})
        for name, blurb, criteria in STAGE_LADDER
    )
    # stage_for is written against STAGE_LADDER; re-run its logic here
    # over the scaled ladder (no edit to stages.py — extend, don't touch).
    counters = {k: float(v) for k, v in stats.items()}
    name, blurb, criteria = scaled[0]
    next_idx = 1
    for i, (sname, sblurb, scriteria) in enumerate(scaled):
        if all(counters.get(c, 0.0) >= need for c, need in scriteria.items()):
            name, blurb, criteria = sname, sblurb, scriteria
            next_idx = i + 1 if i + 1 < len(scaled) else None
    nxt = None
    if next_idx is not None:
        nname, _nb, ncriteria = scaled[next_idx]
        nxt = {
            "name": nname,
            "requirements": {
                counter: {
                    "current": counters.get(counter, 0.0),
                    "threshold": need,
                    "met": counters.get(counter, 0.0) >= need,
                }
                for counter, need in ncriteria.items()
            },
        }
    return {"name": name, "blurb": blurb, "criteria": dict(criteria), "next": nxt}


def _seat_tag(key: str) -> str:
    return "seat:" + key


def seat_stats(key: str, store: Any = None) -> Dict[str, Any]:
    """Observable counters for one seat: its own learnings only.

    Counts growth-tagged memory entries carrying this seat's namespace
    tag — Levi's learnings never mingle with anyone else's, and no
    seat's stage ever rides on another's learnings.
    """
    roster.get_seat(key)
    tag = _seat_tag(key)
    learnings = 0
    corroborations = 0.0
    curriculum_units = 0
    if store is not None:
        entries = store.list(limit=5000)
    else:
        try:
            from levi.memory.store import MemoryStore

            entries = MemoryStore().list(limit=5000)
        except Exception:
            entries = []
    for e in entries:
        tags = set(getattr(e, "tags", []) or [])
        if "growth" not in tags or tag not in tags:
            continue
        if "curriculum" in tags:
            curriculum_units += 1
            continue
        if "distribution" in tags:
            continue
        if not any(
            k in tags for k in ("fact", "preference", "procedural", "correction")
        ):
            continue
        learnings += 1
        md = getattr(e, "metadata", None) or {}
        try:
            corroborations += float(md.get("corroborated_count", 0) or 0)
        except (TypeError, ValueError):
            pass
    # days_active: from the seat's own journal
    days_active = 0.0
    try:
        recs = read_seat_entries(key, limit=200000)
        first = None
        for r in recs:
            ts = str(r.get("ts", "") or "")
            if not first or ts < first:
                first = ts
        if first:
            from datetime import datetime, timezone

            dt = datetime.fromisoformat(first.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days_active = float(max(0, (datetime.now(timezone.utc) - dt).days))
    except Exception:
        pass
    return {
        "learnings": float(learnings),
        "corroborations": corroborations,
        "days_active": days_active,
        "curriculum_units": float(curriculum_units),
        "cycles": 0.0,
    }


def seat_stage(key: str, store: Any = None) -> Dict[str, Any]:
    """A seat's developmental stage under its own track's thresholds."""
    track = track_for(key)
    stats = seat_stats(key, store=store)
    return _scaled_stage_for(stats, track.stage_scale)


# ---------------------------------------------------------------------------
# The raising cycle
# ---------------------------------------------------------------------------


def _namespaced(learnings: List[Learning], key: str, track: RaisingTrack) -> None:
    """Tag learnings with seat/track provenance before consolidation."""
    for learning in learnings:
        prov = dict(learning.provenance or {})
        prov.setdefault("seat", key)
        prov.setdefault("track", track.track_id)
        prov.setdefault("raise_cycle", True)
        learning.provenance = prov


def run_raising_cycle(
    key: str,
    *,
    use_model: bool = True,
    dry_run: bool = False,
    store: Any = None,
) -> Dict[str, Any]:
    """Run one raising cycle for one seat.

    harvest (the track's sources) -> reflect (rules offline, model when
    available, honest mode reporting) -> consolidate (growth-tagged,
    namespaced per seat) -> journal (append-only, per-seat).

    Idempotent: per-seat watermarks mean re-running never re-harvests.
    A seat with nothing new journals a quiet record. Raises ValueError
    when ``store`` is provided but lacks add()/update().
    """
    seat = roster.get_seat(key)  # deny-open
    track = track_for(key)
    if store is not None and not (hasattr(store, "add") and hasattr(store, "update")):
        raise ValueError(
            "run_raising_cycle: store must provide add() and update(), got %s"
            % type(store).__name__
        )
    cycle_id = _journal.new_cycle_id()
    state = _load_seat_state(key)
    watermarks = dict(state.get("watermarks", {}))

    pool, new_marks = _pool(track.harvest, dict(watermarks))
    experiences = _select_for_track(track, pool)
    if "mentoring" in track.harvest:
        mentoring = _harvest_mentoring(key, watermarks)
        experiences = list(experiences) + mentoring

    report: Dict[str, Any] = {
        "seat": key,
        "track": track.track_id,
        "cycle_id": cycle_id,
        "dry_run": dry_run,
        "seasoned": roster.is_seasoned(key),
        "nature": roster.current_nature(key),
        "experiences": len(experiences),
        "mode": "rules",
        "evidence": {},
        "learnings_proposed": 0,
        "learnings": [],
        "consolidation": {"accepted": 0, "corroborated": 0, "skipped": 0, "writes": []},
        "quiet": not experiences,
    }

    if experiences:
        try:
            from levi.growth.reflect import reflect_detailed
        except Exception:  # pragma: no cover
            reflect_detailed = None  # type: ignore
        if reflect_detailed is not None:
            learnings, mode, evidence = reflect_detailed(
                [
                    e
                    for e in experiences
                    if (getattr(e, "meta", {}) or {}).get("origin") != "cloud"
                ],
                use_model=use_model,
            )
            report["mode"] = mode
            report["evidence"] = evidence
            # Guard line: drop anything asserting sentience before it can
            # be consolidated or journaled — counted, never rephrased.
            clean: List[Learning] = []
            blocked = 0
            for learning in learnings:
                if _guards.check_no_sentience_claim(learning.content or ""):
                    blocked += 1
                    continue
                clean.append(learning)
            report["evidence"]["blocked_sentience"] = (
                int(report["evidence"].get("blocked_sentience", 0)) + blocked
            )
            _namespaced(clean, key, track)
            report["learnings_proposed"] = len(clean)
            report["learnings"] = [l.to_dict() for l in clean]
            report["consolidation"] = consolidate(
                clean,
                cycle_id=cycle_id,
                store=store,
                dry_run=dry_run,
                extra_tags=("raise", _seat_tag(key), "track:" + track.track_id),
                dedup_scope=(_seat_tag(key),),
            )

    if not dry_run:
        watermarks.update(new_marks)
        state["watermarks"] = watermarks
        state["last_cycle"] = cycle_id
        state["cycles"] = int(state.get("cycles", 0)) + 1
        _save_seat_state(key, state)
        append_seat_entry(
            key,
            {
                "id": cycle_id,
                "kind": "raise",
                "track": track.track_id,
                "seasoned": report["seasoned"],
                "experiences": report["experiences"],
                "mode": report["mode"],
                "learnings_proposed": report["learnings_proposed"],
                "accepted": report["consolidation"]["accepted"],
                "corroborated": report["consolidation"]["corroborated"],
                "memory_writes": report["consolidation"]["writes"],
                "quiet": report["quiet"],
            },
        )
    return report


def run_cohort(
    track_id: str,
    *,
    use_model: bool = True,
    dry_run: bool = False,
    store: Any = None,
) -> Dict[str, Any]:
    """Run the raising cycle for every seat on one track."""
    if track_id not in TRACKS:
        raise KeyError("unknown raising track: %r" % track_id)
    track = TRACKS[track_id]
    reports = []
    for key in track.seats:
        try:
            reports.append(
                run_raising_cycle(
                    key, use_model=use_model, dry_run=dry_run, store=store
                )
            )
        except Exception as exc:  # one seat never breaks the cohort
            reports.append({"seat": key, "track": track_id, "error": str(exc)})
    return {
        "track": track_id,
        "seats": len(track.seats),
        "experiences": sum(r.get("experiences", 0) for r in reports),
        "learnings_proposed": sum(r.get("learnings_proposed", 0) for r in reports),
        "accepted": sum(r.get("consolidation", {}).get("accepted", 0) for r in reports),
        "errors": [r for r in reports if "error" in r],
        "reports": reports,
    }


def run_legion(
    *,
    use_model: bool = True,
    dry_run: bool = False,
    store: Any = None,
    tracks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run the raising cycle for all 490 seats (or a subset of tracks).

    Sequential and slow by design — raising is patient work. One seat's
    failure never breaks the legion.
    """
    tids = list(TRACKS) if tracks is None else list(tracks)
    cohorts = []
    for tid in tids:
        cohorts.append(
            run_cohort(tid, use_model=use_model, dry_run=dry_run, store=store)
        )
    return {
        "tracks": tids,
        "cohorts": len(cohorts),
        "seats": sum(c["seats"] for c in cohorts),
        "experiences": sum(c["experiences"] for c in cohorts),
        "accepted": sum(c["accepted"] for c in cohorts),
        "errors": [e for c in cohorts for e in c["errors"]],
    }


# ---------------------------------------------------------------------------
# Raising dashboard
# ---------------------------------------------------------------------------


def raising_status(store: Any = None) -> Dict[str, Any]:
    """The raising dashboard: per-track stage distribution and counts.

    Reads only — never writes. ``seasoned`` comes from the roster's live
    ledger (the teaching track owns flipping it); raising reads it.
    """
    by_track: Dict[str, Any] = {}
    totals = {
        "seats": 0,
        "seasoned": 0,
        "learnings": 0,
        "journals": 0,
        "cycles": 0,
    }
    for tid, track in TRACKS.items():
        seats_info = []
        for key in track.seats:
            stats = seat_stats(key, store=store)
            stage = _scaled_stage_for(stats, track.stage_scale)
            n_cycles = int(_load_seat_state(key).get("cycles", 0))
            n_journal = len(read_seat_entries(key, limit=200000))
            info = {
                "seat": key,
                "stage": stage["name"],
                "learnings": int(stats["learnings"]),
                "seasoned": roster.is_seasoned(key),
                "cycles": n_cycles,
                "journal_records": n_journal,
            }
            seats_info.append(info)
            totals["seats"] += 1
            totals["seasoned"] += 1 if info["seasoned"] else 0
            totals["learnings"] += info["learnings"]
            totals["journals"] += n_journal
            totals["cycles"] += n_cycles
        stage_counts: Dict[str, int] = {}
        for info in seats_info:
            stage_counts[info["stage"]] = stage_counts.get(info["stage"], 0) + 1
        by_track[tid] = {
            "tier": track.tier,
            "wave": track.wave,
            "seats": len(track.seats),
            "seasoned": sum(1 for i in seats_info if i["seasoned"]),
            "learnings": sum(i["learnings"] for i in seats_info),
            "stage_counts": stage_counts,
            "reflect_focus": track.reflect_focus,
            "exceed": track.exceed,
        }
    return {"totals": totals, "tracks": by_track, "track_count": len(TRACKS)}
