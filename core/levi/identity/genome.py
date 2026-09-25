"""Genome — heritable trait store (identity variant engine).

JSON-backed at ``~/.levi/identity/genome.json`` (overridable for tests).
Owner-only permissions: directory 0o700, file 0o600. New identities
inherit genome traits as their starting mix.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_TRAITS = {"caution": 0.5, "novelty": 0.5, "stability": 0.5}
_MAX_GUARDS = 200
_MAX_CANDIDATES_PER_MODULE = 50


def _default_genome() -> Dict[str, Any]:
    return {
        "version": 1,
        "traits": dict(DEFAULT_TRAITS),
        "guards": [],
        "signatures": {},
        "lineage": [],
        "candidates": {},
        # champions: name -> {"variant": {...}, "score": float, "generation": int}
        # The reigning best version of each identity. Evolution is elitist:
        # a challenger only dethrones the champion by scoring strictly
        # higher under the active fitness function. The champion never
        # gets worse — that is the "positive improved/upgraded" guarantee.
        "champions": {},
        "cycles": 0,
    }


class GenomeStore:
    """Load, mutate, and persist the heritable genome."""

    def __init__(self, home: Optional[Path] = None) -> None:
        base = Path(home) if home is not None else Path.home() / ".levi"
        self.dir = base / "identity"
        self.path = self.dir / "genome.json"

    def _ensure_dir(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)

    def load(self) -> Dict[str, Any]:
        genome = _default_genome()
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                data = {}
            if isinstance(data, dict):
                for key in genome:
                    if key in data:
                        genome[key] = data[key]
        # normalize types defensively
        if not isinstance(genome.get("traits"), dict):
            genome["traits"] = dict(DEFAULT_TRAITS)
        for trait, default in DEFAULT_TRAITS.items():
            genome["traits"].setdefault(trait, default)
        for key in ("guards", "lineage"):
            if not isinstance(genome.get(key), list):
                genome[key] = []
        for key in ("signatures", "candidates", "champions"):
            if not isinstance(genome.get(key), dict):
                genome[key] = {}
        return genome

    def save(self, genome: Dict[str, Any]) -> None:
        self._ensure_dir()
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(genome, indent=2, sort_keys=True), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)

    def apply_deltas(self, deltas: Dict[str, Any]) -> Dict[str, Any]:
        """Apply RIEM deltas to the stored genome and persist. Returns genome."""
        genome = self.load()
        for trait, delta in (deltas.get("trait_adjustments") or {}).items():
            current = float(genome["traits"].get(trait, 0.5))
            genome["traits"][trait] = round(max(0.0, min(1.0, current + delta)), 4)
        for guard in deltas.get("new_guards", []):
            if guard not in genome["guards"]:
                genome["guards"].append(guard)
        genome["guards"] = genome["guards"][:_MAX_GUARDS]
        for entry in deltas.get("promoted", []):
            sig = entry.get("failure_signature", "")
            if sig:
                genome["signatures"][sig] = int(genome["signatures"].get(sig, 0)) + 1
        genome["cycles"] = int(genome.get("cycles", 0)) + 1
        self.save(genome)
        return genome

    def record_candidates(
        self, module: str, variants: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Store candidate identity variants for review. Never mutates modules."""
        genome = self.load()
        genome["candidates"][module] = variants[:_MAX_CANDIDATES_PER_MODULE]
        self.save(genome)
        return genome

    def inherit_traits(self) -> Dict[str, float]:
        """Trait mix a new identity inherits from the genome."""
        return {k: float(v) for k, v in self.load()["traits"].items()}

    def get_champion(self, name: str) -> Optional[Dict[str, Any]]:
        """The reigning best variant of ``name``, or None if never crowned."""
        champ = self.load().get("champions", {}).get(name)
        return champ if isinstance(champ, dict) else None

    def set_champion(
        self, name: str, variant: Dict[str, Any], score: float, generation: int
    ) -> Dict[str, Any]:
        """Crown a new champion. Callers enforce elitism (strictly better)."""
        genome = self.load()
        genome["champions"][name] = {
            "variant": variant,
            "score": round(score, 4),
            "generation": generation,
        }
        self.save(genome)
        return genome
