"""Symbiotic hybrid twin spawning — the keeper's round-the-clock order.

Round the clock, 4 times a day, spawn 5-10 sets of symbiotic hybrid
twins + team members.

A *set* is one symbiotic hybrid twin pair plus a small crew:

- **twin pair** — two operators with *complementary* hybrid capability
  domains (analytical+creative, cyber-defender+companion, ...). The
  link is symbiotic and cooperative, recorded *both ways*
  (each twin names its symbiont); never adversarial. This is the
  symbiotic flavor of twins — distinct from the inverse-twin red-team
  arrangement, which keeps its own machinery.
- **team members** — Xi nano-bit operators (the default bulk tier for
  trivial turns) plus a specialist, matched to the pair's work.

Every spawned operator is built behind the ONE universal Operator
contract (:mod:`levi.operator.contract`): native, si, ai, and xi are
interchangeable in any seat by config. Each spawned operator is
contract-validated at spawn time — a set that fails validation is
never journaled.

Personality matrix applies: every spawned mind is highly intelligent
and stylistically distinctive (precise, pattern-oriented, witty);
personas affect delivery, never competence. Punch at the problem,
never the person.

Determinism: internal seeding only (sha256 over a fixed keeper seed
+ the cycle id), stdlib ``random.Random`` — no outside randomness
services, fully auditable. Re-running a cycle reproduces it
bit-for-bit (idempotent provenance); different cycles never collide.

State lives under ``~/.levi/twins/symbiotic/`` (``$LEVI_TWINS_HOME``
override respected): ``spawn_journal.jsonl`` (append-only, one record
per set — plus one ``prime_organism`` record on prime waves) and
``state.json`` (per-cycle dedup). A spawn record is also appended to
the growth journal (``levi.growth.journal``) so the
harvest→reflect→consolidate→journal loop can see new blood.

Waves: every spawn cycle is a genesis wave, numbered from the journal
(append-only, so first-appearance order is chronological). Every other
wave — 2, 4, 6, ... — is a *prime wave*: it births one extra
prime-wave organism (a duo/twin pair on odd prime waves, a single
special-intelligence organism on even ones), drawn from the
intelligence-type catalog (:mod:`levi.twins.intelligence_types`) with
a supra manifest (tools, engines, methods, morals) and a dual-market
service catalog. Standard waves keep the original behavior.

XI track: within a cycle the sets are already in randomized order;
the odd-numbered ones (``set_index`` 1, 3, 5, ...) are earmarked with
``xi_organism_track: true`` — flagged to mature into XI-grade
organisms (the nano-bit tier: smallest, fastest, cheapest — the bulk
product line). The earmark is recorded in the journal and survives
re-runs (idempotent: deterministic from the set order).

Usage:
    python -m levi.twins.symbiotic spawn [--cycle sym-YYYYMMDD-HH00]
    python -m levi.twins.symbiotic status
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.operator.contract import (
    AI,
    NATIVE,
    SI,
    XI,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    validate_operator,
)

__all__ = [
    "HYBRID_ARCHETYPES",
    "PERSONA_STYLES",
    "SPECIALIST_ARCHETYPES",
    "SpawnedOperator",
    "current_cycle_id",
    "run_cycle",
    "spawn_cycle",
    "spawn_journal_path",
    "state_path",
]

SPAWNER_VERSION = "1.1.0"

#: Domain separator for deterministic seeding (not a secret).
KEEPER_SEED = "levi-symbiotic-twins-v1"

#: Complementary hybrid archetype pairs: (twin_a_domain, twin_b_domain).
#: Hybrid = blended capability domains; the two halves of a pair are
#: complementary, never adversarial.
HYBRID_ARCHETYPES: tuple[tuple[str, str], ...] = (
    ("analytical", "creative"),
    ("cyber-defender", "companion"),
    ("strategist", "builder"),
    ("archivist", "scout"),
    ("healer", "challenger"),
    ("planner", "improviser"),
    ("researcher", "teacher"),
    ("auditor", "advocate"),
    ("watcher", "messenger"),
    ("librarian", "storyteller"),
)

#: Specialist archetypes for the crew member that backs a pair.
SPECIALIST_ARCHETYPES: tuple[str, ...] = (
    "coordinator",
    "memory-keeper",
    "tool-runner",
    "liaison",
)

#: Personality styles — delivery only, never competence. Each twin
#: gets one; the two halves of a pair always differ.
PERSONA_STYLES: tuple[str, ...] = (
    "precise",
    "witty",
    "dry",
    "warm",
    "terse",
    "playful",
    "formal",
    "blunt",
)

#: Archetype -> honest capability declaration for spawned operators.
ARCHETYPE_TOOLS: Dict[str, tuple[str, ...]] = {
    "analytical": ("analyze_text", "summarize"),
    "creative": ("draft_text", "brainstorm"),
    "cyber-defender": ("assess_posture",),
    "companion": ("converse",),
    "strategist": ("plan_steps",),
    "builder": ("draft_text", "plan_steps"),
    "archivist": ("summarize",),
    "scout": ("analyze_text",),
    "healer": ("converse",),
    "challenger": ("analyze_text", "plan_steps"),
    "planner": ("plan_steps",),
    "improviser": ("draft_text",),
    "researcher": ("analyze_text", "summarize"),
    "teacher": ("converse", "draft_text"),
    "auditor": ("assess_posture", "analyze_text"),
    "advocate": ("draft_text", "converse"),
    "watcher": ("analyze_text",),
    "messenger": ("converse",),
    "librarian": ("summarize",),
    "storyteller": ("draft_text", "brainstorm"),
    "coordinator": ("plan_steps",),
    "memory-keeper": ("summarize",),
    "tool-runner": ("analyze_text",),
    "liaison": ("converse",),
}

ARCHETYPE_NOTES: Dict[str, str] = {
    "analytical": "pattern-first reasoning; precise, evidence-led",
    "creative": "generative ideation; novel angles, bold drafts",
    "cyber-defender": "defensive blue-team posture; scoped, careful",
    "companion": "steady presence; warm, attentive delivery",
    "strategist": "long-horizon planning; sees three moves ahead",
    "builder": "makes things; turns plans into working form",
    "archivist": "records faithfully; nothing lost, all sourced",
    "scout": "ranges ahead; reports back what it finds",
    "healer": "repairs and steadies; restores working order",
    "challenger": "opposable force; pushes, never coddles",
    "planner": "orders the work; sequences and schedules",
    "improviser": "adapts in the moment; fast, fluid, honest",
    "researcher": "digs deep; verifies before it claims",
    "teacher": "makes the complex plain; patient, clear",
    "auditor": "checks the books; honest accounting only",
    "advocate": "argues the case; sharp, principled",
    "watcher": "keeps watch; notices what changes",
    "messenger": "carries word faithfully; no embellishment",
    "librarian": "orders knowledge; finds anything fast",
    "storyteller": "gives shape to facts; narrative with spine",
    "coordinator": "runs the crew; keeps every member fed with work",
    "memory-keeper": "holds the thread across cycles",
    "tool-runner": "does the legwork; fast, tireless",
    "liaison": "bridges teams; translates between domains",
}


# ---------------------------------------------------------------------------
# Paths


def twins_home() -> Path:
    import os

    override = os.environ.get("LEVI_TWINS_HOME")
    p = Path(override).expanduser() if override else Path.home() / ".levi" / "twins"
    return p


def symbiotic_home() -> Path:
    p = twins_home() / "symbiotic"
    p.mkdir(parents=True, exist_ok=True)
    return p


def spawn_journal_path() -> Path:
    return symbiotic_home() / "spawn_journal.jsonl"


def state_path() -> Path:
    return symbiotic_home() / "state.json"


# ---------------------------------------------------------------------------
# Spawned operator — one contract, every kind


class SpawnedOperator(Operator):
    """A spawned twin or team member, behind the universal contract.

    Deterministic stub mind: standing by until seated. Honest about
    it — never fakes work, never claims native identity unless it is
    one (spawned twins are ``si``; nano-bit crew are ``xi``).
    """

    def __init__(
        self,
        *,
        name: str,
        kind: str,
        archetype: str,
        persona_style: str,
        symbiont_id: str = "",
        link_mode: str = "",
        seat: str = "",
        lineage: str = "",
        version: str = SPAWNER_VERSION,
    ) -> None:
        self.name = name
        self.kind = kind
        self.version = version
        self.lineage = lineage or f"levi:symbiotic-twins:{archetype}"
        self.is_foreign = False
        self.archetype = archetype
        self.persona_style = persona_style
        self.symbiont_id = symbiont_id
        self.link_mode = link_mode
        self.seat = seat

    @property
    def identity_label(self) -> str:
        base = f"{self.kind}:{self.name}"
        if self.archetype:
            base += f"[{self.archetype}/{self.persona_style}]"
        return base

    def capabilities(self) -> OperatorCapabilities:
        tools = ARCHETYPE_TOOLS.get(self.archetype, ())
        if self.kind == XI:
            tools = ()  # nano-bits: no tools, trivial turns only
        return OperatorCapabilities(
            tools=tools,
            streaming=False,
            memory_access=False,
            context_window=1024 if self.kind == XI else 8192,
            tool_use_loop=False,
            notes=ARCHETYPE_NOTES.get(self.archetype, ""),
        )

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        t0 = time.perf_counter()
        return OperatorResult(
            text=(
                f"[{self.identity_label}] standing by — "
                f"{self.archetype} mind, {self.persona_style} delivery. "
                "Seat me to serve; I do not fake work."
            ),
            operator=self.name,
            kind=self.kind,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            finish_reason="stop",
            note="spawned stub: awaiting seat assignment",
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="spawned; standing by")


# ---------------------------------------------------------------------------
# Deterministic spawning


def _derive_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _short_id(seed: int, *parts: str) -> str:
    digest = hashlib.sha256(f"{seed}|".encode() + "|".join(parts).encode()).hexdigest()
    return digest[:8]


def current_cycle_id(now: Optional[float] = None) -> str:
    """Cycle id snapped to the 6h grid in America/Chicago.

    Rounds the clock at 00:00, 06:00, 12:00, 18:00 keeper time.
    """
    from zoneinfo import ZoneInfo

    ts = now if now is not None else time.time()
    import datetime as _dt

    local = _dt.datetime.fromtimestamp(ts, tz=ZoneInfo("America/Chicago"))
    slot = (local.hour // 6) * 6
    return f"sym-{local.strftime('%Y%m%d')}-{slot:02d}00"


def _spawned_at_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class SpawnedSet:
    set_id: str
    twin_a: Dict[str, Any]
    twin_b: Dict[str, Any]
    symbiotic_link: Dict[str, Any]
    team: List[Dict[str, Any]] = field(default_factory=list)
    seat: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "set_id": self.set_id,
            "twin_a": self.twin_a,
            "twin_b": self.twin_b,
            "symbiotic_link": self.symbiotic_link,
            "team": self.team,
            "seat": self.seat,
            "provenance": self.provenance,
        }


def _operator_record(op: SpawnedOperator, cycle_id: str, seed: int) -> Dict[str, Any]:
    caps = op.capabilities()
    return {
        "id": op.name,
        "name": op.name,
        "kind": op.kind,
        "archetype": op.archetype,
        "persona_style": op.persona_style,
        "symbiont_id": op.symbiont_id,
        "link_mode": op.link_mode,
        "seat": op.seat,
        "lineage": op.lineage,
        "version": op.version,
        "identity_label": op.identity_label,
        "capabilities": {
            "tools": list(caps.tools),
            "streaming": caps.streaming,
            "memory_access": caps.memory_access,
            "context_window": caps.context_window,
            "tool_use_loop": caps.tool_use_loop,
            "notes": caps.notes,
        },
        "provenance": {
            "cycle_id": cycle_id,
            "seed": seed,
            "spawned_at": _spawned_at_iso(),
            "spawner": f"levi.twins.symbiotic v{SPAWNER_VERSION}",
        },
    }


def spawn_cycle(cycle_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Spawn one cycle of symbiotic hybrid twin sets (pure, in-memory).

    Returns 5-10 set dicts. Deterministic per cycle id: the same
    cycle id always yields the same sets. Raises
    :class:`OperatorContractError` if any spawned operator fails
    contract validation.
    """
    cycle_id = cycle_id or current_cycle_id()
    seed = _derive_seed(KEEPER_SEED, cycle_id)
    rng = random.Random(seed)

    n_sets = 5 + rng.randrange(6)  # 5..10, keeper's band
    pair_order = list(range(len(HYBRID_ARCHETYPES)))
    rng.shuffle(pair_order)

    sets: List[Dict[str, Any]] = []
    for idx in range(n_sets):
        pair = HYBRID_ARCHETYPES[pair_order[idx % len(pair_order)]]
        arch_a, arch_b = pair
        style_a, style_b = rng.sample(PERSONA_STYLES, 2)
        seat = f"spawn-pool/{cycle_id}/set-{idx:02d}"

        suffix_a = _short_id(seed, "set", str(idx), "A")
        suffix_b = _short_id(seed, "set", str(idx), "B")
        name_a = f"twin-{cycle_id[4:]}-{idx:02d}a-{suffix_a}"
        name_b = f"twin-{cycle_id[4:]}-{idx:02d}b-{suffix_b}"

        twin_a = SpawnedOperator(
            name=name_a,
            kind=SI,
            archetype=arch_a,
            persona_style=style_a,
            symbiont_id=name_b,
            link_mode="symbiotic",
            seat=seat,
            lineage=f"levi:symbiotic-twins:{cycle_id}",
        )
        twin_b = SpawnedOperator(
            name=name_b,
            kind=SI,
            archetype=arch_b,
            persona_style=style_b,
            symbiont_id=name_a,
            link_mode="symbiotic",
            seat=seat,
            lineage=f"levi:symbiotic-twins:{cycle_id}",
        )
        # Contract gate: a set that fails validation is never born.
        twin_a.validate()
        twin_b.validate()

        # Crew: 2 Xi nano-bits (bulk tier, trivial turns) + 1 specialist.
        team: List[SpawnedOperator] = []
        for m in range(2):
            xi_name = f"xi-{cycle_id[4:]}-{idx:02d}{m}-{_short_id(seed, 'xi', str(idx), str(m))}"
            xi = SpawnedOperator(
                name=xi_name,
                kind=XI,
                archetype="liaison" if m == 0 else "tool-runner",
                persona_style=rng.choice(PERSONA_STYLES),
                seat=seat,
                lineage=f"levi:symbiotic-twins:{cycle_id}",
            )
            xi.validate()
            team.append(xi)
        spec = SpawnedOperator(
            name=f"spec-{cycle_id[4:]}-{idx:02d}-{_short_id(seed, 'spec', str(idx))}",
            kind=SI,
            archetype=rng.choice(SPECIALIST_ARCHETYPES),
            persona_style=rng.choice(PERSONA_STYLES),
            seat=seat,
            lineage=f"levi:symbiotic-twins:{cycle_id}",
        )
        spec.validate()
        team.append(spec)

        rec_a = _operator_record(twin_a, cycle_id, seed)
        rec_b = _operator_record(twin_b, cycle_id, seed)
        team_recs = [_operator_record(m, cycle_id, seed) for m in team]

        sets.append(
            {
                "set_id": f"set-{cycle_id}-{idx:02d}",
                "twin_a": rec_a,
                "twin_b": rec_b,
                "symbiotic_link": {
                    "a": rec_a["id"],
                    "b": rec_b["id"],
                    "mode": "symbiotic",
                    "complement": f"{arch_a}+{arch_b}",
                    "bidirectional": True,
                },
                "team": team_recs,
                "seat": seat,
                "provenance": {
                    "cycle_id": cycle_id,
                    "seed": seed,
                    "spawned_at": _spawned_at_iso(),
                    "spawner": f"levi.twins.symbiotic v{SPAWNER_VERSION}",
                },
            }
        )
    return sets


# ---------------------------------------------------------------------------
# Cycle runner: journal + state + growth hook


def _read_state() -> Dict[str, Any]:
    p = state_path()
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _write_state(state: Dict[str, Any]) -> None:
    p = state_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def _journal_records(records: List[Dict[str, Any]]) -> None:
    p = spawn_journal_path()
    with p.open("a", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Genesis waves: every cycle is a wave; every other wave is prime


def _wave_parity(wave: int) -> str:
    return "prime" if wave % 2 == 0 else "standard"


def _journal_cycle_ids_in_order() -> List[str]:
    """Distinct cycle ids from the journal, in first-appearance order.

    The journal is append-only, so this order is chronological.
    """
    seen: List[str] = []
    p = spawn_journal_path()
    if p.is_file():
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cid = (rec.get("provenance") or {}).get("cycle_id")
                if cid and cid not in seen:
                    seen.append(cid)
    return seen


def _backfill_wave_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Give every known cycle a wave number, deterministically.

    Waves are assigned 1..N in chronological order (journal
    first-appearance, then state leftovers by spawned_at). Entries that
    already carry a wave keep it. Pre-existing completed cycles are
    marked completed so their ids stay idempotent.
    """
    cycles = state.setdefault("cycles", {})
    ordered: List[str] = []
    for cid in _journal_cycle_ids_in_order():
        if cid not in ordered:
            ordered.append(cid)
    leftovers = sorted(
        (cid for cid in cycles if cid not in ordered),
        key=lambda cid: (
            (cycles[cid] or {}).get("spawned_at", "")
            if isinstance(cycles[cid], dict)
            else "",
            cid,
        ),
    )
    ordered.extend(leftovers)
    for i, cid in enumerate(ordered, start=1):
        entry = cycles[cid]
        if not isinstance(entry, dict):
            entry = {}
            cycles[cid] = entry
        if "wave" not in entry:
            entry["wave"] = i
            entry["wave_parity"] = _wave_parity(i)
            entry["wave_backfilled"] = True
        # Cycles written by spawner v1.0.0 were fully journaled before
        # the summary was stored: they are completed.
        entry.setdefault("completed", True)
    return state


def _growth_hook(summary: Dict[str, Any]) -> None:
    """Let the growth loop see new blood (best-effort, never fatal)."""
    try:
        from levi.growth.journal import append_entry

        append_entry(
            {
                "kind": "twin_spawn",
                "cycle_id": summary["cycle_id"],
                "wave": summary.get("wave"),
                "wave_parity": summary.get("wave_parity"),
                "sets_spawned": summary["sets_spawned"],
                "operators_spawned": summary["operators_spawned"],
                "xi_track_sets": summary.get("xi_track_sets"),
                "prime_organism_id": summary.get("prime_organism_id"),
                "engine": f"levi.twins.symbiotic v{SPAWNER_VERSION}",
                "note": "round-the-clock symbiotic hybrid twin spawning",
            }
        )
    except Exception:
        pass


def run_cycle(cycle_id: Optional[str] = None) -> Dict[str, Any]:
    """Run one spawn cycle (= one genesis wave): spawn, journal, state, growth hook.

    Idempotent per cycle id: re-running a completed cycle returns the
    recorded summary without spawning duplicates. Wave numbers are
    assigned from journal state, so every other wave (2, 4, 6, ...) is
    deterministically prime.
    """
    cycle_id = cycle_id or current_cycle_id()
    state = _backfill_wave_state(_read_state())
    cycles = state["cycles"]
    existing = cycles.get(cycle_id)
    if isinstance(existing, dict) and existing.get("completed"):
        prior = dict(existing)
        prior["duplicate_run"] = True
        return prior

    wave = max(
        (e.get("wave", 0) for e in cycles.values() if isinstance(e, dict)),
        default=0,
    ) + 1
    parity = _wave_parity(wave)

    sets = spawn_cycle(cycle_id)
    # Annotate every set: record kind, position, wave, and the XI track.
    # The sets are already in randomized order; odd positions (1, 3, 5,
    # ...) are earmarked to mature into XI-grade organisms.
    for idx, s in enumerate(sets):
        s["record_kind"] = "set"
        s["set_index"] = idx
        s["wave"] = wave
        s["wave_parity"] = parity
        s["xi_organism_track"] = (idx % 2 == 1)

    records: List[Dict[str, Any]] = list(sets)
    prime_record: Optional[Dict[str, Any]] = None
    if parity == "prime":
        from levi.twins import prime as _prime

        prime_record = _prime.spawn_prime_organism(
            cycle_id, wave, prime_index=wave // 2
        )
        records.append(prime_record)
    _journal_records(records)

    n_operators = sum(2 + len(s["team"]) for s in sets)
    summary = {
        "cycle_id": cycle_id,
        "completed": True,
        "wave": wave,
        "wave_parity": parity,
        "sets_spawned": len(sets),
        "operators_spawned": n_operators,
        "xi_track_sets": sum(1 for s in sets if s["xi_organism_track"]),
        "prime_organism_id": (
            prime_record["organism_id"] if prime_record else None
        ),
        "prime_intelligence_type": (
            prime_record["intelligence_type"]["id"] if prime_record else None
        ),
        "set_ids": [s["set_id"] for s in sets],
        "spawned_at": _spawned_at_iso(),
        "spawner": f"levi.twins.symbiotic v{SPAWNER_VERSION}",
        "duplicate_run": False,
    }
    cycles[cycle_id] = summary
    state["last_cycle"] = cycle_id
    state["wave_count"] = max(state.get("wave_count", 0), wave)
    state["total_sets"] = state.get("total_sets", 0) + len(sets)
    state["total_operators"] = state.get("total_operators", 0) + n_operators
    if prime_record:
        state["total_prime_organisms"] = state.get("total_prime_organisms", 0) + 1
    _write_state(state)
    _growth_hook(summary)
    return summary


# ---------------------------------------------------------------------------
# CLI


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="levi.twins.symbiotic")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_spawn = sub.add_parser("spawn", help="run one spawn cycle")
    p_spawn.add_argument("--cycle", default=None, help="cycle id (default: current 6h slot)")

    sub.add_parser("status", help="spawning state overview")

    args = ap.parse_args(argv)
    if args.cmd == "spawn":
        summary = run_cycle(args.cycle)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.cmd == "status":
        state = _read_state()
        journal = spawn_journal_path()
        n_records = 0
        if journal.is_file():
            with journal.open(encoding="utf-8") as fh:
                n_records = sum(1 for _ in fh)
        print(
            json.dumps(
                {
                    "state": state,
                    "journal_records": n_records,
                    "journal_path": str(journal),
                    "current_cycle": current_cycle_id(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
