"""REIM/RIEM twin variant — the compost/dream twin pair.

Canon (Chauncey's words — his words are the spec):
- Quetta runs "through Echo, REIM, RIEM, Mandella, variating combos
  without end" (docs/LEXICON.md:709-710).
- REIM = Recursion Echo Inverse Mapping — failure-compost intelligence:
  a failed mutation is inverse-mapped back through Echo into compost,
  a structured failure lesson (what was tried, why it failed).
- RIEM = Recursion Inverse Echo Mapping — dream-compression
  intelligence: composted lessons are mapped forward into the genome,
  persistent learned patterns steering future projections.
- REIM failure-compost and RIEM dream-compression are canon peers in
  the unattempted-intelligence pool (docs/LEXICON.md:783-785).

This module is the TWIN VARIANT of the loop Quetta-Pan already runs
internally (:mod:`levi.quetta_pan`): Twin A (REIM compost twin) ingests
failed attempts and inverse-maps them into structured compost; Twin B
(RIEM dream twin) compresses compost into the heritable genome and
steers future traversals. It extends what Quetta-Pan is — the same
:class:`levi.quetta_pan.reim.ReimCompost` and
:class:`levi.quetta_pan.riem.RiemGenome` classes, the same consult
policy — in twin form. A pair pointed at a QuettaPanEngine's
``store_dir`` shares its compost and genome files with the engine.

Both twins stand behind the universal Operator contract
(:mod:`levi.operator.contract`) and are contract-validated at spawn,
like :mod:`levi.twins.symbiotic` pairs. The symbiotic link is recorded
both ways: each twin names its symbiont. Bidirectional flow: A's
compost feed flows to B; B's genome consult steers A's next attempts.

TWIN INVARIANTS (law -> guard -> prove; each has a test in
``tests/test_reim_riem_twin.py``):
1. No lesson compacts without a composted failure behind it. Twin B
   folds only entries Twin A actually composted — verified against the
   compost store by ``mutation_id``. Anything else raises.
2. Genome consulted before generation. The pair's ``advise()`` is the
   gate: a suppressed rule never gets a "proceed" verdict from this
   pair.
3. Bidirectional link never silently broken. A write on one side is
   visible on the other: both twins name each other, and every
   exchange carries one event id recorded on both twins and in the
   journal. :meth:`ReimRiemPair.verify_link` raises on any mismatch.
4. Fail-closed on guard errors. Invalid failures raise (never dropped
   silently); a refused fold leaves the genome untouched and the
   compost intact (append-only); both twins are contract-validated at
   spawn.

stdlib-only.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from levi.operator.contract import (
    SI,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
)
from levi.quetta_pan.reim import ReimCompost
from levi.quetta_pan.riem import RiemGenome

__all__ = [
    "PAIR_VERSION",
    "LinkBrokenError",
    "ReimTwin",
    "RiemTwin",
    "ReimRiemPair",
    "default_store_dir",
]

PAIR_VERSION = "1.0.0"


class LinkBrokenError(Exception):
    """The bidirectional twin link failed verification."""


def _twins_home() -> Path:
    override = os.environ.get("LEVI_TWINS_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".levi" / "twins"


def default_store_dir() -> Path:
    p = _twins_home() / "reim_riem"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Twin A — REIM compost twin


class ReimTwin(Operator):
    """Twin A: ingests failed attempts, inverse-maps them into compost.

    Thin twin shell over :class:`ReimCompost` — the twin does not
    reimplement composting, it operates it behind the Operator
    contract.
    """

    def __init__(
        self,
        *,
        name: str,
        symbiont_id: str,
        compost: ReimCompost,
        persona_style: str = "precise",
        version: str = PAIR_VERSION,
    ) -> None:
        self.name = name
        self.kind = SI
        self.version = version
        self.lineage = "levi:twins:reim-riem"
        self.is_foreign = False
        self.archetype = "composter"
        self.persona_style = persona_style
        self.symbiont_id = symbiont_id
        self.link_mode = "symbiotic"
        self.compost = compost
        self.last_event_id = ""

    @property
    def identity_label(self) -> str:
        return f"{self.kind}:{self.name}[{self.archetype}/{self.persona_style}]"

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=("failure_compost", "lesson_distill"),
            streaming=False,
            memory_access=True,
            context_window=8192,
            tool_use_loop=False,
            notes=(
                "REIM failure-compost intelligence: every failed attempt "
                "inverse-mapped into append-only compost; nothing dropped "
                "silently."
            ),
        )

    def ingest_failure(self, failure: Dict[str, Any]) -> Dict[str, Any]:
        """Inverse-map one failure into compost.

        Fail-closed: missing keys raise ValueError (from the compost
        layer) — the failure is never dropped silently and nothing is
        half-written.
        """
        return self.compost.compost(failure)

    def recent_lessons(self, n: int = 10) -> List[Dict[str, Any]]:
        return self.compost.recent(n)

    def compost_count(self) -> int:
        return self.compost.count()

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        t0 = time.perf_counter()
        return OperatorResult(
            text=(
                f"[{self.identity_label}] compost twin: "
                f"{self.compost_count()} lessons composted; symbiont "
                f"{self.symbiont_id}; last exchange {self.last_event_id or 'none'}. "
                "Feed me failures; I return inverse lessons."
            ),
            operator=self.name,
            kind=self.kind,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            finish_reason="stop",
            note="reim-riem twin A: standing by",
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="compost twin healthy")


# ---------------------------------------------------------------------------
# Twin B — RIEM dream twin


class RiemTwin(Operator):
    """Twin B: compresses compost into the heritable genome.

    Thin twin shell over :class:`RiemGenome`. Folding is guarded by
    invariant 1: only entries the compost twin actually composted are
    compacted — verified against the compost store.
    """

    def __init__(
        self,
        *,
        name: str,
        symbiont_id: str,
        genome: RiemGenome,
        persona_style: str = "dry",
        version: str = PAIR_VERSION,
    ) -> None:
        self.name = name
        self.kind = SI
        self.version = version
        self.lineage = "levi:twins:reim-riem"
        self.is_foreign = False
        self.archetype = "dreamer"
        self.persona_style = persona_style
        self.symbiont_id = symbiont_id
        self.link_mode = "symbiotic"
        self.genome = genome
        self.last_event_id = ""

    @property
    def identity_label(self) -> str:
        return f"{self.kind}:{self.name}[{self.archetype}/{self.persona_style}]"

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=("dream_compress", "genome_seal"),
            streaming=False,
            memory_access=True,
            context_window=8192,
            tool_use_loop=False,
            notes=(
                "RIEM dream-compression intelligence: composted lessons "
                "folded into the heritable genome; consulted before any "
                "new attempt is generated."
            ),
        )

    def fold_compost(
        self, entry: Dict[str, Any], compost: ReimCompost
    ) -> Dict[str, Any]:
        """Compact one composted lesson into the genome.

        Invariant 1 guard: the entry must carry a ``mutation_id`` that
        exists in the compost store and a derived ``inverse_lesson``.
        Anything else raises ValueError — no lesson compacts without a
        composted failure behind it.
        """
        mid = entry.get("mutation_id")
        found = bool(
            mid
            and any(
                e.get("mutation_id") == mid for e in compost.lessons()
            )
        )
        if not found:
            raise ValueError(
                "refusing to compact an uncomposted lesson "
                f"(mutation_id={mid!r}); compost it through Twin A first"
            )
        if not entry.get("inverse_lesson"):
            raise ValueError(
                "refusing to compact an entry with no derived inverse lesson"
            )
        return self.genome.learn_compost_entry(entry)

    def consult(self, rule_id: str, context: str) -> Tuple[str, str]:
        """Pre-generation verdict: (verdict, reason)."""
        verdict = self.genome.consult(rule_id, context)
        reason = (
            self.genome.suppression_reason(rule_id, context)
            if verdict == "suppress"
            else f"genome verdict for {rule_id} in {context}: {verdict}"
        )
        return verdict, reason

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        t0 = time.perf_counter()
        n_patterns = sum(
            len(rules) for rules in self.genome.patterns().values()
        )
        return OperatorResult(
            text=(
                f"[{self.identity_label}] dream twin: {n_patterns} genome "
                f"patterns held; symbiont {self.symbiont_id}; last exchange "
                f"{self.last_event_id or 'none'}. Consult me before you "
                "generate; I steer with yesterday's compost."
            ),
            operator=self.name,
            kind=self.kind,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            finish_reason="stop",
            note="reim-riem twin B: standing by",
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="dream twin healthy")


# ---------------------------------------------------------------------------
# The pair — symbiotic link, journaled


class ReimRiemPair:
    """One symbiotic REIM/RIEM twin pair, journaled.

    Owns the shared compost + genome stores (point ``store_dir`` at a
    QuettaPanEngine's store dir to share its loop), spawns both twins
    behind the Operator contract, and runs the bidirectional exchange:
    A composts -> B folds -> B's consult steers the next attempt.
    """

    def __init__(
        self,
        *,
        store_dir: Optional[Path | str] = None,
        pair_id: Optional[str] = None,
    ) -> None:
        self.store_dir = (
            Path(store_dir) if store_dir else default_store_dir()
        )
        self.store_dir.mkdir(parents=True, exist_ok=True)
        # Engine-identical store filenames: pointing store_dir at a
        # QuettaPanEngine's store dir shares its compost and genome
        # files with the engine, live.
        self.compost = ReimCompost(self.store_dir / ".quetta_compost.jsonl")
        self.genome = RiemGenome(self.store_dir / ".quetta_genome.json")
        self.journal_path = self.store_dir / "pair_journal.jsonl"

        self.pair_id = pair_id or f"rr-{time.strftime('%Y%m%d%H%M%S')}"
        self.twin_a = ReimTwin(
            name=f"reim-{self.pair_id}",
            symbiont_id=f"riem-{self.pair_id}",
            compost=self.compost,
        )
        self.twin_b = RiemTwin(
            name=f"riem-{self.pair_id}",
            symbiont_id=f"reim-{self.pair_id}",
            genome=self.genome,
        )
        # Contract gate: a pair that fails validation is never born.
        self.twin_a.validate()
        self.twin_b.validate()

        self._journal(
            {
                "event": "pair_spawned",
                "twin_a": self.twin_a.name,
                "twin_b": self.twin_b.name,
                "link_mode": "symbiotic",
                "bidirectional": True,
                "version": PAIR_VERSION,
            }
        )

    # ---- journal ----------------------------------------------------------

    def _journal(self, record: Dict[str, Any]) -> Dict[str, Any]:
        rec = {"ts": _now_iso(), "pair_id": self.pair_id, **record}
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec

    def read_journal(self) -> List[Dict[str, Any]]:
        out = []
        if self.journal_path.is_file():
            with open(self.journal_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        return out

    # ---- the bidirectional exchange ---------------------------------------

    def cycle(self, failure: Dict[str, Any]) -> Dict[str, Any]:
        """One full exchange: A ingests the failure, B folds the lesson.

        Fail-closed: if ingest raises, nothing is written anywhere; if
        fold raises, the compost entry stands (append-only) and the
        genome is untouched.
        """
        entry = self.twin_a.ingest_failure(failure)
        slot = self.twin_b.fold_compost(entry, self.compost)
        event_id = f"ev-{entry['mutation_id']}"
        # Invariant 3: one event id, visible on both sides.
        self.twin_a.last_event_id = event_id
        self.twin_b.last_event_id = event_id
        self._journal(
            {
                "event": "exchange",
                "event_id": event_id,
                "mutation_id": entry["mutation_id"],
                "rule_id": entry["rule_id"],
                "context": entry["context"],
                "failure_class": entry["failure_class"],
                "twin_a": self.twin_a.name,
                "twin_b": self.twin_b.name,
            }
        )
        return {"entry": entry, "genome_slot": slot, "event_id": event_id}

    def advise(self, rule_id: str, context: str) -> Dict[str, Any]:
        """Invariant 2 gate: consult the genome BEFORE generating.

        Returns the verdict Twin B gives Twin A's next attempt. A
        suppressed rule never gets ``proceed: True`` from this pair.
        """
        verdict, reason = self.twin_b.consult(rule_id, context)
        rec = self._journal(
            {
                "event": "consult",
                "rule_id": rule_id,
                "context": context,
                "verdict": verdict,
                "reason": reason,
            }
        )
        return {
            "rule_id": rule_id,
            "context": context,
            "verdict": verdict,
            "reason": reason,
            "proceed": verdict != "suppress",
            "journal_ts": rec["ts"],
        }

    def verify_link(self) -> bool:
        """Invariant 3 guard: raise LinkBrokenError on any mismatch."""
        a, b = self.twin_a, self.twin_b
        if a.symbiont_id != b.name:
            raise LinkBrokenError(
                f"twin A names symbiont {a.symbiont_id!r}, expected {b.name!r}"
            )
        if b.symbiont_id != a.name:
            raise LinkBrokenError(
                f"twin B names symbiont {b.symbiont_id!r}, expected {a.name!r}"
            )
        if a.last_event_id != b.last_event_id:
            raise LinkBrokenError(
                f"exchange visibility diverged: A={a.last_event_id!r} "
                f"B={b.last_event_id!r}"
            )
        return True
