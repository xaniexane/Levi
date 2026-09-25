"""Evolution — Mandella and Echo on the Twin Lattice.

The defense mechanism, and the standing law: **never static, never
outdated.**

The camouflage is not a static mask; it is a living one. When the lattice
adds up — the creator seal verifies — Mandella fires (stake selection under
domain pressure) and Echo fires (taken / not-taken / wild branches).
Together they mutate, transform, and upgrade the lattice:

- **mutate**    (security domain): advance the camouflage generation. The
  outward arrangement re-derives from the creator seed — new order, new
  live/shadow roles, new jitter. Blast radius is Mandella's call.
- **transform** (identity domain): rotate FG/BG roles — the shadows step
  forward in a commanded drill. Two self-descriptions conflict; only one
  drives the next commit.
- **upgrade**   (build domain): bump the lattice version and stamp the
  evolution ledger. The history of every shedding is kept.

Every change is derived from the creator seed at a new generation, so the
creator can always reproduce every skin — while anyone trying to
reverse-engineer the lattice is chasing a moving target. That is the
protection: not a wall, a shedding skin.

**RIEM closes the loop.** Every shedding is composted through REIM, and
RIEM promotes the worthy lessons into genome proposals: the defense
mechanism learns. Corroboration compounds — the second shedding of a kind
promotes where the first only composted. Proposals are data, never writes;
applying them is always the creator's decision.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

from levi.organs.echo import run_echo
from levi.organs.mandella import OPTIONS as MANDELLA_OPTIONS
from levi.organs.mandella import run_mandella
from levi.organs.reim import compost_failure
from levi.organs.riem import promote as riem_promote
from levi.twins import convergence as conv
from levi.twins.lattice import TwinLattice

#: Operation → Mandella domain (pressure the stake is selected under).
OP_DOMAINS = {
    "mutate": "security",
    "transform": "identity",
    "upgrade": "build",
}

OPS = tuple(OP_DOMAINS)

#: Kinds whose pairs take part in the transform drill.
TRANSFORM_KINDS = ("agent", "daemon", "shell")

LEDGER_HISTORY_KEEP = 50
PROPOSALS_KEEP = 50


class LatticeDoesNotAddUp(RuntimeError):
    """Raised when evolve() is fired on a lattice whose seal doesn't verify."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _intensity(mandella_result: Dict, domain: str) -> int:
    """Mandella's recommended stake → intensity 1..3.

    The recommended option's position in the domain's option list decides:
    first option = 1, second = 2, third = 3. Deterministic from the seed.
    """
    label = mandella_result["recommended"]
    # mirror run_mandella's fallback: domains without their own option
    # list use the resource list
    opts = MANDELLA_OPTIONS.get(domain) or MANDELLA_OPTIONS["resource"]
    idx = next(i for i, o in enumerate(opts) if o[0] == label)
    return idx + 1


def _ledger(lattice: TwinLattice):
    """Ensure the evolution ledger twin (pairs with itself, like the Ones)."""
    tid = "evolution:ledger:fg"
    tw = lattice.get(tid)
    if tw is None:
        tw = lattice.register(
            "evolution",
            "ledger",
            "fg",
            state={
                "version": 0,
                "generation": 0,
                "history": [],
                "genome_proposals": [],
            },
            notes="every shedding of the skin, and what RIEM learned",
            pair_id=tid,
        )
    return tw


def _append_history(lattice: TwinLattice, entry: Dict) -> Dict:
    ledger = _ledger(lattice)
    hist = list(ledger.state.get("history", []))
    hist.append(entry)
    ledger.state["history"] = hist[-LEDGER_HISTORY_KEEP:]
    ledger.state["generation"] = conv.current_generation(lattice)
    lattice.heartbeat(ledger.twin_id)
    return lattice.get(ledger.twin_id)


def _prior_count(lattice: TwinLattice, op: str) -> int:
    ledger = _ledger(lattice)
    return sum(1 for e in ledger.state.get("history", []) if e.get("op") == op)


def _fire_organs(op: str, generation: int) -> Dict:
    """Fire Mandella and Echo on one operation. Returns their readings."""
    domain = OP_DOMAINS[op]
    seed = f"twin-evolve:{op}:g{generation}"
    m = run_mandella(domain, seed=seed)
    e = run_echo(seed=seed, cycles=3)
    return {
        "domain": domain,
        "mandella": m["recommended"],
        "mandella_risk": next(
            o["risk"] for o in m["options"] if o["label"] == m["recommended"]
        ),
        "echo_taken": next(b for b in e["branches"] if b["kind"] == "taken"),
        "echo_insight": e["insight"],
        "intensity": _intensity(m, domain),
    }


def _compost_shedding(op: str, reading: Dict, detail: str, corroboration: int) -> Dict:
    """Compost one shedding through REIM.

    The standing failure being composted: a static camouflage can
    eventually be mapped. The old skin is burned — retire it, never
    wear it again. Wording keeps the record in the missing-guard
    class so RIEM can promote it into a real guard-rule.
    """
    compost = compost_failure(
        {
            "source": "twin-evolution",
            "what": (
                f"lattice shed its skin via {op}: {detail}. "
                "the old arrangement crossed the observation boundary "
                "with no guard retiring it"
            ),
            "context": (
                f"mandella [{reading['domain']}] stake={reading['mandella']} "
                f"risk={reading['mandella_risk']}; "
                f"echo taken={reading['echo_taken']['label']}"
            ),
            "ts": _utcnow(),
            "severity": "medium",
        }
    )
    # repeated sheddings of a kind corroborate each other
    compost["corroboration"] = corroboration
    return compost


def _record(
    lattice: TwinLattice,
    op: str,
    reading: Dict,
    detail: str,
    extra: Optional[Dict] = None,
) -> Dict:
    """Append one shedding to the ledger, compost it, run RIEM."""
    corroboration = 1 + _prior_count(lattice, op)
    compost = _compost_shedding(op, reading, detail, corroboration)
    proposals = riem_promote([compost])
    entry: Dict = {
        "ts": _utcnow(),
        "op": op,
        "domain": reading["domain"],
        "mandella": reading["mandella"],
        "echo_taken": reading["echo_taken"]["label"],
        "echo_insight": reading["echo_insight"],
        "generation": conv.current_generation(lattice),
        "detail": detail,
        "compost_fp": compost["fingerprint"],
        "corroboration": corroboration,
        "promoted": [p["fingerprint"] for p in proposals],
    }
    if extra:
        entry.update(extra)
    ledger = _append_history(lattice, entry)
    if proposals:
        known = {p["fingerprint"] for p in ledger.state["genome_proposals"]}
        fresh = [p for p in proposals if p["fingerprint"] not in known]
        ledger.state["genome_proposals"] = (ledger.state["genome_proposals"] + fresh)[
            -PROPOSALS_KEEP:
        ]
        lattice.heartbeat(ledger.twin_id)
    return {
        "op": op,
        "domain": reading["domain"],
        "mandella": reading["mandella"],
        "echo_taken": reading["echo_taken"]["label"],
        "detail": detail,
        "generation": entry["generation"],
        "compost_fp": compost["fingerprint"],
        "proposals": len(proposals),
    }


def mutate(lattice: TwinLattice, seed: str, generation: int) -> Dict:
    """Advance the camouflage generation — shed the skin.

    Mandella (security domain) sets the intensity: 1-3 generations.
    The new arrangement is fully seed-derived; the creator reproduces
    it exactly, observers start over.
    """
    reading = _fire_organs("mutate", generation)
    new_gen = generation + reading["intensity"]
    conv.converge(lattice, seed_hex=seed, generation=new_gen)
    return _record(
        lattice,
        "mutate",
        reading,
        f"camouflage generation {generation} -> {new_gen}",
        extra={"generation_from": generation, "generation_to": new_gen},
    )


def _transform_picks(lattice: TwinLattice, seed: str, n: int) -> List[str]:
    """Deterministically pick n FG twins to rotate (seed order)."""
    fg_ids = sorted(
        t.twin_id
        for t in lattice.iter_all()
        if t.kind in TRANSFORM_KINDS and t.side == "fg"
    )
    ranked = sorted(
        fg_ids,
        key=lambda tid: hashlib.sha256(f"{seed}|{tid}".encode()).hexdigest(),
    )
    return ranked[:n]


def transform(lattice: TwinLattice, seed: str, generation: int) -> Dict:
    """Rotate FG/BG roles — the shadows step forward.

    Mandella (identity domain) sets how many pairs rotate. A commanded
    drill: no staleness checks, every rotation recorded.
    """
    reading = _fire_organs("transform", generation)
    picks = _transform_picks(lattice, seed, reading["intensity"])
    rotated = []
    for tid in picks:
        try:
            lattice.rotate(tid)
            rotated.append(tid)
        except (KeyError, ValueError):
            continue
    conv.converge(lattice, seed_hex=seed)  # generation preserved
    return _record(
        lattice,
        "transform",
        reading,
        f"rotated {len(rotated)} pair(s): {', '.join(rotated) or 'none'}",
        extra={"rotated": rotated},
    )


def upgrade(lattice: TwinLattice, seed: str, generation: int) -> Dict:
    """Bump the lattice version and stamp the ledger.

    Mandella (build domain) selects the stake; the ledger version is the
    lattice's age in sheddings — never static, never outdated.
    """
    reading = _fire_organs("upgrade", generation)
    ledger = _ledger(lattice)
    version = int(ledger.state.get("version", 0)) + 1
    ledger.state["version"] = version
    lattice.heartbeat(ledger.twin_id)
    conv.converge(lattice, seed_hex=seed)  # generation preserved
    return _record(
        lattice,
        "upgrade",
        reading,
        f"lattice version -> v{version}",
        extra={"version": version},
    )


_OPS = {"mutate": mutate, "transform": transform, "upgrade": upgrade}


def evolve(lattice: TwinLattice, ops: tuple = OPS) -> Dict:
    """Fire Mandella and Echo on the lattice: mutate, transform, upgrade.

    The gate: the lattice must add up — the creator seal verifies — or
    nothing fires. Each operation re-seals, composts its shedding through
    REIM, and RIEM promotes what the defense has learned into genome
    proposals (data, never writes).
    """
    for op in ops:
        if op not in _OPS:
            raise ValueError(f"unknown evolution op: {op!r} (known: {OPS})")
    seed = conv.load_seed(lattice)
    if seed is None or not conv.verify_camouflage(lattice):
        raise LatticeDoesNotAddUp(
            "the lattice doesn't add up — converge it first, "
            "then fire Mandella and Echo"
        )
    reports = []
    for op in ops:
        generation = conv.current_generation(lattice)
        reports.append(_OPS[op](lattice, seed, generation))
    ledger = _ledger(lattice)
    return {
        "ops": reports,
        "generation": conv.current_generation(lattice),
        "version": ledger.state.get("version", 0),
        "sealed": conv.verify_camouflage(lattice),
        "proposals": len(ledger.state.get("genome_proposals", [])),
    }
