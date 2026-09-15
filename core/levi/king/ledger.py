"""King continuity ledger — the ONE place word-count/rank totals accrue.

Blueprint §4: King layers a continuity ledger over *both* content engines
(``graph.story_fabric.StoryFabric`` for multi-story work and
``lwp.model_engine.LWPModelEngine`` for single-manuscript work). Both
engines may keep their own internal counters (their own tests depend on
them) — this ledger is an *aggregate* on top, never a replacement.

Rank here is a D2→D5 ladder derived from **word count + bank count**, not
word count alone (blueprint §4). A "bank" is one banked unit of
continuity harvested from an engine drive: a story beat, a manuscript
scene, a crowned REIM track, a ROM scene. King harvests on *every*
engine-driving method (``pulse()``, ``pulse_manuscript()``, and the
reim/deny/approve/rupture pass-throughs), so totals stay honest no
matter which engine produced the words.

Persisted to ``<data_dir>/ledger.json`` with restrictive permissions
(0o600) — continuity data is the user's own writing.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

def _default_data_dir() -> Path:
    return Path.home() / ".levi" / "king"

# D-ladder thresholds. Rank advances on EITHER words or banks — this is
# what makes it "word count + bank count, not word count alone".
_RANK_STEPS = (
    # (rank, min_words, min_banks)
    ("D2", 0, 0),
    ("D3", 5_000, 10),
    ("D4", 20_000, 30),
    ("D5", 80_000, 100),
)

_LEDGER_VERSION = 1


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json_600(path: Path, payload: Dict[str, Any]) -> None:
    """Atomic JSON write with owner-only permissions (0o600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _check_600(path: Path) -> bool:
    try:
        return bool(stat.S_IMODE(path.stat().st_mode) == 0o600)
    except OSError:
        return False


class ContinuityLedger:
    """Entities, causal edges, harvests, and the D2→D5 rank ladder."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else _default_data_dir()
        self.path = self.data_dir / "ledger.json"
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self.harvests: List[Dict[str, Any]] = []
        self.promoted: Optional[Dict[str, Any]] = None
        self._load()

    # -- persistence ----------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            # Corrupt ledger: start clean rather than crash the control
            # plane. History is aggregate-only; engines keep their own.
            return
        if not isinstance(raw, dict):
            return
        self.entities = raw.get("entities", {}) or {}
        self.edges = raw.get("edges", []) or []
        self.harvests = raw.get("harvests", []) or []
        self.promoted = raw.get("promoted")

    def _persist(self) -> None:
        _write_json_600(
            self.path,
            {
                "version": _LEDGER_VERSION,
                "entities": self.entities,
                "edges": self.edges,
                "harvests": self.harvests[-500:],
                "promoted": self.promoted,
            },
        )

    # -- totals ---------------------------------------------------------

    @property
    def total_words(self) -> int:
        return max(0, sum(int(h.get("words", 0)) for h in self.harvests))

    @property
    def total_banks(self) -> int:
        return max(0, sum(int(h.get("banks", 0)) for h in self.harvests))

    # -- rank -----------------------------------------------------------

    def rank(self) -> str:
        """D2→D5 from words + banks (either can advance the ladder)."""
        if self.promoted:
            return "D5"
        words, banks = self.total_words, self.total_banks
        level = "D2"
        for name, min_words, min_banks in _RANK_STEPS:
            if words >= min_words or banks >= min_banks:
                level = name
        return level

    def promote_d5(self, reason: str = "baseline promotion (demo)") -> Dict[str, Any]:
        """Demo baseline promotion: floor the ledger rank at D5.

        Explicitly a *demo* override — recorded with a timestamp and a
        reason, visible in ``status``. It does not fabricate words or
        banks; it floors the derived rank. ``reset_promotion()`` clears
        it.
        """
        self.promoted = {"ts": _utcnow(), "reason": reason, "demo": True}
        self._persist()
        return self.promoted

    def reset_promotion(self) -> bool:
        had = self.promoted is not None
        self.promoted = None
        self._persist()
        return had

    # -- entities & edges -----------------------------------------------

    def register_entity(
        self,
        entity_id: str,
        kind: str,
        name: str = "",
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ent = self.entities.get(entity_id) or {}
        ent.update(
            {
                "id": entity_id,
                "kind": kind,
                "name": name or ent.get("name", ""),
                "ts": ent.get("ts", _utcnow()),
                "updated_ts": _utcnow(),
                "meta": meta if meta is not None else ent.get("meta", {}),
            }
        )
        self.entities[entity_id] = ent
        self._persist()
        return ent

    def add_edge(
        self, src: str, dst: str, relation: str, note: str = ""
    ) -> Dict[str, Any]:
        edge = {
            "src": src,
            "dst": dst,
            "relation": relation,
            "note": note,
            "ts": _utcnow(),
        }
        self.edges.append(edge)
        self._persist()
        return edge

    # -- harvest --------------------------------------------------------

    def harvest(
        self, source: str, words: int, banks: int, event: str = ""
    ) -> Dict[str, Any]:
        """Record one engine drive's contribution to the aggregate totals.

        ``source`` is ``"story_fabric"``, ``"model_engine"``, or
        ``"king"``. Negative word deltas (e.g. a denied scene) are
        recorded as-is; the *total* is floored at zero.
        """
        entry = {
            "source": source,
            "words": int(words),
            "banks": int(banks),
            "event": event,
            "ts": _utcnow(),
        }
        self.harvests.append(entry)
        self._persist()
        return entry

    # -- integrity ------------------------------------------------------

    def fingerprint(self) -> str:
        """Stable sha256 over entities+edges+harvests+totals.

        Used by King's Wyrd-ROM (``rom.py``) to lock a multi-engine
        session's continuity state. Deterministic for identical state.
        """
        canonical = json.dumps(
            {
                "entities": self.entities,
                "edges": self.edges,
                "harvests": self.harvests,
                "total_words": self.total_words,
                "total_banks": self.total_banks,
                "promoted": self.promoted,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def permissions_ok(self) -> bool:
        return _check_600(self.path) if self.path.exists() else True

    def summary(self) -> Dict[str, Any]:
        return {
            "rank": self.rank(),
            "total_words": self.total_words,
            "total_banks": self.total_banks,
            "entities": len(self.entities),
            "edges": len(self.edges),
            "harvests": len(self.harvests),
            "promoted": self.promoted,
            "fingerprint": self.fingerprint()[:16],
        }
