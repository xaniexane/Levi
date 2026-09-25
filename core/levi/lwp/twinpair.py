"""Twin-pair interpenetration engine — L.W.P. rebuild toward true interpenetration.

Canon (Chauncey's law): the original design is INTERPENETRATING AND
INFINITELY COMBINED — not modules, not a pipeline. It is an EXPANDER:
combinations birth new features/engines/capabilities. Honest mixing
happens through MATCHED TWIN-PAIRS (Echo x Mandella, REIM x RIEM); a
CIRCUIT BREAKER vetoes pairings that don't fit — refused, not mixed.
Operation: point them at the insides and watch them grow.

This module wires the four kernel organs (echo, mandella, reim, riem)
into matched twin-pairs. It reimplements nothing: the organs do the
work; the pairs only aim them at the same material and record what the
mix births. Unchosen options become phantoms — fuel if they move
(stake -> haunt -> resolve/compost).

Stdlib-only. Deterministic: identical (material, seed, pairs, rounds)
yields an identical report. No network, no model calls. No
sentience/consciousness claims anywhere — organs and engine describe
processes, not minds.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

from levi.organs import echo as echo_organ
from levi.organs import mandella as mandella_organ
from levi.organs import riem as riem_organ  # failure_to_genome runs REIM compost inside


BORN_FILE = "born.jsonl"
"""Born-registry filename inside the born dir."""

_ENV_BORN_DIR = "LEVI_LWP_BORN_DIR"


# ---------------------------------------------------------------------------
# Twins and twin-pairs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Twin:
    name: str
    role: str
    risk: int


@dataclass(frozen=True)
class TwinPair:
    name: str
    twin_a: Twin
    twin_b: Twin
    seam: str

    def fits(self, material: dict) -> tuple[bool, str]:
        """Does this pair fit this material? Returns (fits, reason).

        Fit rules are registered per canon pair name below. A pair with no
        registered fit rule is refused rather than forced: an honest "no"
        is a complete answer.
        """
        fn = _FIT_RULES.get(self.name)
        if fn is None:
            return (
                False,
                "circuit-breaker: no fit rule registered for pair %r; "
                "refused rather than forced" % (self.name,),
            )
        return fn(material)


def _fits_echo_mandella(material: dict) -> tuple[bool, str]:
    if not isinstance(material, dict):
        return False, "echo×mandella: material must be a dict"
    text = material.get("text")
    if not isinstance(text, str) or not text.strip():
        return (
            False,
            "echo×mandella: material lacks an expandable 'text' surface",
        )
    return (
        True,
        "echo×mandella: 'text' present — expandable surface, fits",
    )


def _fits_reim_riem(material: dict) -> tuple[bool, str]:
    if not isinstance(material, dict):
        return False, "reim×riem: material must be a dict"
    failures = material.get("failures")
    if not isinstance(failures, list) or not failures:
        return (
            False,
            "reim×riem: material has no non-empty 'failures' to compost",
        )
    return (
        True,
        "reim×riem: %d failure record(s) to compost — fits" % len(failures),
    )


ECHO_MANDELLA = TwinPair(
    name="echo×mandella",
    twin_a=Twin(name="echo", role="expands", risk=1),
    twin_b=Twin(name="mandella", role="stakes/phantom-runs under fog", risk=2),
    seam=(
        "Echo expands the material's text into parallel variants; "
        "Mandella stakes the taken variant and phantom-runs the rest "
        "under fog."
    ),
)

REIM_RIEM = TwinPair(
    name="reim×riem",
    twin_a=Twin(name="reim", role="composts failure", risk=1),
    twin_b=Twin(name="riem", role="carries compost-genome", risk=2),
    seam=(
        "REIM composts each failure into lessons; RIEM promotes the "
        "compost into genome proposals and guards."
    ),
)

CANON_PAIRS: tuple = (ECHO_MANDELLA, REIM_RIEM)

_FIT_RULES = {
    ECHO_MANDELLA.name: _fits_echo_mandella,
    REIM_RIEM.name: _fits_reim_riem,
}


# ---------------------------------------------------------------------------
# Circuit breaker — the veto
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VetoVerdict:
    paired: bool
    pair_name: str
    reason: str


class CircuitBreaker:
    """The veto: a pair mixes only when it fits the material.

    "No pair" is a complete answer — the breaker never forces a mix.
    """

    def check(self, pair: TwinPair, material: dict) -> VetoVerdict:
        if not isinstance(pair, TwinPair):
            return VetoVerdict(
                paired=False,
                pair_name="?",
                reason="circuit-breaker: not a TwinPair; refused",
            )
        fits, reason = pair.fits(material)
        return VetoVerdict(paired=bool(fits), pair_name=pair.name, reason=reason)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class PairResult:
    pair_name: str
    material_id: str
    output: dict
    born: list = field(default_factory=list)
    phantoms: list = field(default_factory=list)
    vetoed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExpansionReport:
    material_id: str
    rounds_run: int
    pair_results: list = field(default_factory=list)
    born: list = field(default_factory=list)
    refused: list = field(default_factory=list)  # list[VetoVerdict]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Born registry — append-only JSONL
# ---------------------------------------------------------------------------


def _born_dir() -> Path:
    override = os.environ.get(_ENV_BORN_DIR)
    if override:
        return Path(override)
    home = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
    return home / "lwp"


def born_registry_path() -> Path:
    """Path of the born registry. Env var LEVI_LWP_BORN_DIR overrides the
    default dir ``~/.levi/lwp/``; the file is always ``born.jsonl``."""
    return _born_dir() / BORN_FILE


def list_born(limit: int = 50) -> list[dict]:
    """Read born records, newest-first. Corrupt lines are skipped so one
    bad line never kills the ledger."""
    path = born_registry_path()
    if not path.exists():
        return []
    records: List[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records[::-1][: max(0, int(limit))]


# ---------------------------------------------------------------------------
# Deterministic helpers
# ---------------------------------------------------------------------------


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _det_ts(seed_text: str) -> float:
    """Deterministic timestamp-like float derived from content, not the
    wall clock — keeps identical runs byte-identical."""
    h = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    return 1_750_000_000.0 + (h % 1_000_000)


# ---------------------------------------------------------------------------
# Pair runners — the organs do the work
# ---------------------------------------------------------------------------


def _run_echo_mandella(
    pair_name: str, material: dict, seed: str, round_index: int
) -> PairResult:
    material_id = str(material.get("id", "unknown"))
    run_seed = "%s|%s|r%d|%s" % (seed, material_id, round_index, pair_name)
    domain = str(material.get("domain") or "write").lower()

    # Echo expands the surface into parallel variants.
    echo_res = echo_organ.run_echo(run_seed, cycles=3)
    variants = [
        {"kind": b["kind"], "label": b["label"], "summary": b["summary"]}
        for b in echo_res["branches"]
    ]
    chosen = variants[0]  # the taken path
    unchosen = variants[1:]  # unchosen options -> phantoms (fuel if they move)

    # Mandella stakes the taken variant and phantom-runs the rest under fog.
    m = mandella_organ.run_mandella(domain=domain, seed=run_seed)
    decision = {
        "domain": m["domain"],
        "chosen": chosen["summary"],
        "phantoms": [
            {"label": p["label"], "summary": p["summary"], "kind": p["kind"]}
            for p in unchosen
        ],
        "ts": _det_ts(run_seed + "|stake"),
        "seed": run_seed,
    }
    stake_id = mandella_organ.record_stake(decision)
    # Phantom-run under fog: haunt the open stake so the unchosen keep pressure.
    haunt = mandella_organ.haunt_check(stake_id)

    mandella_phantoms = [
        {
            "label": p["label"],
            "note": p["note"],
            "risk": p["risk"],
            "haunt": p["haunt"],
        }
        for p in m["phantoms"]
    ]

    output = {
        "variants": variants,
        "stakes": {
            "domain": m["domain"],
            "premise": m["premise"],
            "stake_id": stake_id,
            "chosen": decision["chosen"],
            "mandella_recommended": m["recommended"],
            "pressure": haunt["pressure"],
        },
        "phantoms": [dict(p) for p in unchosen] + mandella_phantoms,
    }
    born = [
        {
            "what": "angle: %s — %s" % (v["label"], v["summary"]),
            "parents": ["echo", "mandella"],
            "seed": run_seed,
        }
        for v in variants
    ]
    return PairResult(
        pair_name=pair_name,
        material_id=material_id,
        output=output,
        born=born,
        phantoms=[dict(p) for p in unchosen],
        vetoed=False,
    )


_SEVERITIES = ("low", "medium", "high")


def _normalize_failure(
    failure: dict, material: dict, run_seed: str, index: int
) -> dict:
    """Coerce an outcome record into the shape reim.compost_failure demands.

    Missing fields fall back to the material (source/kind/text); an
    invalid severity is coerced to "medium" rather than raising — the
    organ stays fail-closed on truly malformed input, the expander only
    normalizes the documented optional surface.
    """
    if not isinstance(failure, dict):
        failure = {"what": str(failure)}
    material_id = str(material.get("id", "unknown"))
    severity = failure.get("severity", "medium")
    if severity not in _SEVERITIES:
        severity = "medium"
    what = str(
        failure.get("what")
        or material.get("text")
        or "unnamed failure in %s" % material_id
    ).strip()
    context = (
        str(
            failure.get("context") or material.get("kind") or "twinpair-expansion"
        ).strip()
        or "twinpair-expansion"
    )
    return {
        "source": str(failure.get("source") or material_id),
        "what": what,
        "context": context,
        "ts": str(failure.get("ts") or _det_ts("%s|failure%d" % (run_seed, index))),
        "severity": severity,
    }


def _run_reim_riem(
    pair_name: str, material: dict, seed: str, round_index: int
) -> PairResult:
    material_id = str(material.get("id", "unknown"))
    run_seed = "%s|%s|r%d|%s" % (seed, material_id, round_index, pair_name)
    failures = material.get("failures") or []

    lessons: List[dict] = []
    proposals: List[dict] = []
    for i, failure in enumerate(failures):
        record = _normalize_failure(failure, material, run_seed, i)
        res = riem_organ.failure_to_genome(record)  # compost -> promote
        lessons.append(
            {
                "lesson": res["compost"]["lesson"],
                "compost_class": res["compost"]["compost_class"],
                "fingerprint": res["compost"]["fingerprint"],
            }
        )
        proposals.extend(res["proposals"])
    guards = [p for p in proposals if p["kind"] == "guard-rule"]
    output = {
        "lessons": lessons,
        "genome": {"proposals": proposals, "count": len(proposals)},
        "guards": guards,
    }
    born = [
        {
            "what": "genome: %s" % p["content"],
            "parents": ["reim", "riem"],
            "seed": run_seed,
        }
        for p in proposals
    ]
    return PairResult(
        pair_name=pair_name,
        material_id=material_id,
        output=output,
        born=born,
        phantoms=[],
        vetoed=False,
    )


# ---------------------------------------------------------------------------
# Expander
# ---------------------------------------------------------------------------


class Expander:
    """Points matched twin-pairs at material and watches it grow.

    Each round: every pair is veto-checked; refused pairs are recorded in
    ``report.refused`` and skipped; fitted pairs run, their born entries
    are appended to the born registry, and born outputs are fed back as
    material for the next round (bounded by ``rounds``).
    """

    def __init__(self, seed: str = "", born_dir: str | Path | None = None):
        self.seed = seed
        self.born_dir = Path(born_dir) if born_dir is not None else None
        self.breaker = CircuitBreaker()

    def _registry_path(self) -> Path:
        if self.born_dir is not None:
            return self.born_dir / BORN_FILE
        return born_registry_path()

    def _record_born(self, result: PairResult) -> None:
        """Append this result's born entries to the registry. Append-only:
        entries already present (same deterministic id) are skipped, never
        rewritten — so identical re-runs change nothing on disk."""
        path = self._registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: set = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    existing.add(json.loads(line).get("id"))
                except (json.JSONDecodeError, AttributeError):
                    continue
        new_lines: List[str] = []
        for entry in result.born:
            rec_id = _sha16(
                "|".join(
                    [
                        result.pair_name,
                        entry["what"],
                        ",".join(entry["parents"]),
                        entry["seed"],
                        result.material_id,
                    ]
                )
            )
            if rec_id in existing:
                continue
            existing.add(rec_id)
            new_lines.append(
                json.dumps(
                    {
                        "id": rec_id,
                        "ts": _det_ts(rec_id),
                        "pair_name": result.pair_name,
                        "what": entry["what"],
                        "parents": list(entry["parents"]),
                        "seed": entry["seed"],
                        "material_id": result.material_id,
                    },
                    ensure_ascii=False,
                )
            )
        if new_lines:
            with path.open("a", encoding="utf-8") as fh:
                for line in new_lines:
                    fh.write(line + "\n")

    def _run_pair(self, pair: TwinPair, material: dict, round_index: int) -> PairResult:
        if pair.name == ECHO_MANDELLA.name:
            return _run_echo_mandella(pair.name, material, self.seed, round_index)
        if pair.name == REIM_RIEM.name:
            return _run_reim_riem(pair.name, material, self.seed, round_index)
        raise ValueError(
            "expander: no run rule for pair %r (the veto should have "
            "refused it)" % (pair.name,)
        )

    def expand(
        self,
        material: dict,
        pairs: Sequence[TwinPair] = CANON_PAIRS,
        rounds: int = 2,
    ) -> ExpansionReport:
        """Run the expander. Returns an ExpansionReport; refused pairs land
        in ``report.refused`` as VetoVerdicts, never forced."""
        if not isinstance(material, dict):
            raise ValueError("expand: material must be a dict")
        if isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 1:
            raise ValueError("expand: rounds must be a positive int")
        material_id = str(material.get("id", "unknown"))
        pair_results: list = []
        born: list = []
        refused: list = []
        current: List[Dict] = [material]
        rounds_run = 0
        for r in range(rounds):
            if not current:
                break
            rounds_run += 1
            nxt: List[Dict] = []
            for mat in current:
                for pair in pairs:
                    verdict = self.breaker.check(pair, mat)
                    if not verdict.paired:
                        refused.append(verdict)
                        continue
                    result = self._run_pair(pair, mat, r)
                    self._record_born(result)
                    pair_results.append(result)
                    born.extend(result.born)
                    # Feed born outputs back as material for the next round.
                    for i, entry in enumerate(result.born):
                        nxt.append(
                            {
                                "id": "%s+%s+b%dr%d"
                                % (mat.get("id", "unknown"), pair.name, i, r),
                                "kind": "born-angle",
                                "text": entry["what"],
                                "domain": mat.get("domain"),
                                "failures": [],
                            }
                        )
            current = nxt
        return ExpansionReport(
            material_id=material_id,
            rounds_run=rounds_run,
            pair_results=pair_results,
            born=born,
            refused=refused,
        )
