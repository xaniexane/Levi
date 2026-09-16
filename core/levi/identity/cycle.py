"""IdentityCycle — the full variant loop (identity variant engine).

Single identity: reflect -> reconstruct -> evaluate (pluggable scorer) ->
compost outcome -> compress lessons -> genome update.

Whole organism (--scope all): the same loop per manifest module, with
controlled interpenetration — a variant may inherit traits from another
module, with provenance recorded. Variants are candidates for review only;
module code is never touched.
"""

from __future__ import annotations

import random
from typing import Any, Callable, Dict, List, Optional

from levi.identity.echo import EchoEngine, reflection_to_dict
from levi.identity.genome import GenomeStore
from levi.identity.mandella import MandellaEngine
from levi.identity.reim import REIM
from levi.identity.riem import RIEM
from levi.identity.scope import (
    iter_module_identities,
    module_fracture_notes,
)

Scorer = Callable[[Dict[str, Any]], float]


def _default_scorer(variant: Dict[str, Any]) -> float:
    return EchoEngine().reflect(variant).coherence


class IdentityCycle:
    """Run the reflect/reconstruct/evaluate/compost/compress loop."""

    def __init__(
        self,
        store: Optional[GenomeStore] = None,
        scorer: Optional[Scorer] = None,
        threshold: float = 0.7,
    ) -> None:
        self.store = store or GenomeStore()
        self.scorer = scorer or _default_scorer
        self.threshold = threshold
        self.echo = EchoEngine()
        self.reim = REIM()
        self.riem = RIEM()

    def run(
        self,
        identity: Dict[str, Any],
        n_variants: int = 3,
        seed: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        reflection = self.echo.reflect(identity)
        variants = MandellaEngine(seed).reconstruct(reflection, n_variants, seed)
        scored = sorted(
            ((self.scorer(v), i, v) for i, v in enumerate(variants)),
            key=lambda t: (-t[0], t[1]),
        )
        best_score, _, winner = scored[0]
        success = best_score >= self.threshold
        failures = (
            []
            if success
            else [
                "winner score %.4f below threshold %.2f" % (best_score, self.threshold)
            ]
        )
        outcome = {
            "identity": winner.get("name", ""),
            "success": success,
            "score": round(best_score, 4),
            "notes": notes,
            "failures": failures,
        }
        lessons = self.reim.compost(outcome)
        genome_before = self.store.load()
        deltas = self.riem.compress(lessons, genome_before)
        genome_after = self.store.apply_deltas(deltas)
        return {
            "reflection": reflection_to_dict(reflection),
            "variants": [
                {
                    "name": v.get("name"),
                    "score": round(s, 4),
                    "mutations": v.get("mutations", []),
                }
                for s, _, v in scored
            ],
            "winner": winner.get("name"),
            "winner_score": round(best_score, 4),
            "outcome": outcome,
            "lessons": lessons,
            "deltas": deltas,
            "genome_traits": genome_after["traits"],
        }

    def run_scope_all(
        self,
        n_variants: int = 2,
        seed: str = "",
        cross_pollenate: bool = True,
    ) -> Dict[str, Any]:
        """Run the loop for every manifest module, with interpenetration."""
        identities = iter_module_identities()
        rng = random.Random("scope-all:" + seed)
        donor_pool = {ident["name"]: ident for ident in identities}
        results = []
        for ident in identities:
            reflection = self.echo.reflect(ident)
            # fold module-level fracture notes into the reflection record
            extra = module_fracture_notes(ident)
            reflection.fractures.extend(extra)
            reflection.coherence = round(
                max(
                    0.0,
                    min(1.0, reflection.coherence - sum(f["penalty"] for f in extra)),
                ),
                4,
            )
            variants = MandellaEngine(seed).reconstruct(
                reflection, n_variants, "%s:%s" % (seed, ident["name"])
            )
            if cross_pollenate:
                self._cross_pollenate(ident["name"], variants, donor_pool, rng)
            self.store.record_candidates(ident["name"], variants)
            results.append(
                {
                    "module": ident["name"],
                    "coherence": reflection.coherence,
                    "fractures": len(reflection.fractures),
                    "variants": [v.get("name") for v in variants],
                    "inherited": [
                        v.get("provenance", {}).get("inherited_traits", {})
                        for v in variants
                    ],
                }
            )
        return {
            "scope": "all",
            "modules": len(identities),
            "results": results,
            "genome_candidates": sorted(donor_pool),
        }

    def _cross_pollenate(
        self,
        module: str,
        variants: List[Dict[str, Any]],
        donor_pool: Dict[str, Dict[str, Any]],
        rng: random.Random,
    ) -> None:
        """Controlled trait inheritance between modules, provenance recorded."""
        donors = sorted(d for d in donor_pool if d != module)
        if not donors:
            return
        for variant in variants:
            donor_name = rng.choice(donors)
            donor_traits = donor_pool[donor_name].get("traits", {})
            strong = sorted(
                t
                for t, v in donor_traits.items()
                if isinstance(v, (int, float)) and v >= 0.5
            )
            if not strong:
                continue
            trait = rng.choice(strong)
            value = donor_traits[trait]
            variant.setdefault("traits", {})[trait] = value
            prov = variant.setdefault("provenance", {}).setdefault(
                "inherited_traits", {}
            )
            prov[trait] = {"from": donor_name, "value": value}
            variant.setdefault("mutations", []).append(
                {
                    "op": "cross-pollinate",
                    "detail": {"trait": trait, "from": donor_name},
                }
            )
