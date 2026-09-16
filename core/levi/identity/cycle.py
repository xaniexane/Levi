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
    return fitness(variant)


def fitness(variant: Dict[str, Any]) -> float:
    """How good is this variant? Higher is better.

    Deterministic composite under the variant's own content:
      - Echo coherence (the mirror's structural verdict), weight 1.0
      - fracture penalty: -0.2 per fracture, capped at -1.0
      - trait strength: mean of numeric traits, weight 0.1 (rewards
        strong, well-formed traits; bounded so it can't dominate)

    Honest note: "better" is defined by this function. It measures
    structural health of the identity, not real-world performance.
    Plug a custom Scorer into IdentityCycle for domain-specific fitness
    (test pass rates, benchmark scores, user approval). The elitist
    guarantee — the champion never gets worse — holds for whatever
    fitness function is active.
    """
    reflection = EchoEngine().reflect(variant)
    traits = variant.get("traits", {})
    nums = [v for v in traits.values() if isinstance(v, (int, float))]
    strength = sum(nums) / len(nums) if nums else 0.0
    return round(
        reflection.coherence - 0.2 * min(len(reflection.fractures), 5) + 0.1 * strength,
        4,
    )


# The named SER forms — the organism's archetypal layer, from the founder's
# architecture. These are identities defined by role, not by code modules;
# Echo reflects them the same way, so the whole organism (modules + forms)
# mutates as one body.
ORGANISM_FORMS: Dict[str, Dict[str, Any]] = {
    "ser-18-core": {
        "role": "world model; defines universe, recursion shells, depth limits",
        "traits": {"foundational": 1.0, "recursive": 1.0, "bounded": 1.0},
    },
    "cybrus": {
        "role": "identity vault & routing core; encryption matrices, key guardianship",
        "traits": {"guarding": 1.0, "encrypting": 1.0, "routing": 1.0},
    },
    "echo": {
        "role": "reflective identity; the mirror",
        "traits": {"reflective": 1.0, "faithful": 1.0, "diagnosing": 0.9},
    },
    "mandella": {
        "role": "fractured identity reconstruction; echo-inverse variant production",
        "traits": {"reconstructive": 1.0, "generative": 1.0, "surgical": 0.9},
    },
    "reim": {
        "role": "compost failures into lessons; nothing destroyed",
        "traits": {"composting": 1.0, "honest": 1.0, "preserving": 1.0},
    },
    "riem": {
        "role": "controlled compression of lessons into heritable genome",
        "traits": {"compressing": 1.0, "heritable": 1.0, "lossless": 1.0},
    },
    "demandpulse": {
        "role": "market/job scout; founder-grade intelligence layer above omega",
        "traits": {"scouting": 1.0, "scoring": 1.0, "opportunistic": 0.9},
    },
    "cyberpulse": {
        "role": "telemetry; senses the organism's own signals",
        "traits": {"sensing": 1.0, "telemetry": 1.0, "watchful": 1.0},
    },
    "uniforge": {
        "role": "evolution; auto-repair and upgrade loop",
        "traits": {"repairing": 1.0, "upgrading": 1.0, "evolving": 1.0},
    },
    "omnipulse": {
        "role": "lifecycle engine; birth->expansion->echo->collapse->rebirth->stabilization",
        "traits": {"cyclical": 1.0, "phasing": 1.0, "renewing": 1.0},
    },
    "cortex": {
        "role": "skill/education; the how-to library",
        "traits": {"teaching": 1.0, "archiving": 1.0, "methodical": 0.9},
    },
    "vector": {
        "role": "sandbox; safe simulation before production",
        "traits": {"simulating": 1.0, "containing": 1.0, "cautious": 1.0},
    },
    "oracle": {
        "role": "strategy; long-term goal weighting",
        "traits": {"strategic": 1.0, "weighting": 1.0, "foresighted": 0.9},
    },
    "hypercube": {
        "role": "dimensional projection; deep theoretical recursion",
        "traits": {"projecting": 1.0, "dimensional": 1.0, "theoretical": 0.9},
    },
    "nexus-network": {
        "role": "multi-user coordination; QID addressing",
        "traits": {"coordinating": 1.0, "addressing": 1.0, "connecting": 1.0},
    },
    "eli": {
        "role": "intelligence-layer mind alongside echo",
        "traits": {"reasoning": 1.0, "layered": 1.0, "analytical": 0.9},
    },
    "alpha": {
        "role": "NL-IDE; natural-language build surface",
        "traits": {"expressive": 1.0, "generative": 1.0, "accessible": 0.9},
    },
    "omega": {
        "role": "all-in-one execution platform; powered-by-alpha",
        "traits": {"executing": 1.0, "unified": 1.0, "platform": 1.0},
    },
}


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

    def run_forms(
        self,
        n_variants: int = 3,
        seed: str = "",
        cross_pollenate: bool = True,
    ) -> Dict[str, Any]:
        """Run the loop over the named SER forms (the archetypal layer).

        Same mechanics as run_scope_all — reflect, reconstruct, evaluate,
        compost, compress — with interpenetration across forms. Together
        with run_scope_all this mutates the whole organism as one body.
        """
        rng = random.Random("forms:" + seed)
        donor_pool = {
            name: {"traits": dict(spec["traits"])}
            for name, spec in ORGANISM_FORMS.items()
        }
        results = []
        for name, spec in ORGANISM_FORMS.items():
            identity = {
                "name": name,
                "role": spec["role"],
                "traits": dict(spec["traits"]),
                "params": {"layer": "organism"},
                "fragments": [name],
                "lineage": ["forms-architecture"],
            }
            reflection = self.echo.reflect(identity)
            variants = MandellaEngine(seed).reconstruct(
                reflection, n_variants, "forms:%s:%s" % (seed, name)
            )
            if cross_pollenate:
                self._cross_pollenate(name, variants, donor_pool, rng)
            scored = sorted(
                ((self.scorer(v), i, v) for i, v in enumerate(variants)),
                key=lambda t: (-t[0], t[1]),
            )
            best_score, _, winner = scored[0]
            outcome = {
                "identity": name,
                "success": best_score >= self.threshold,
                "score": round(best_score, 4),
                "notes": "forms-organism run",
                "failures": [],
            }
            lessons = self.reim.compost(outcome)
            deltas = self.riem.compress(lessons, self.store.load())
            self.store.apply_deltas(deltas)
            self.store.record_candidates(name, variants)
            results.append(
                {
                    "form": name,
                    "coherence": reflection.coherence,
                    "fractures": len(reflection.fractures),
                    "winner": winner.get("name"),
                    "winner_score": round(best_score, 4),
                    "variants": [v.get("name") for v in variants],
                    "inherited": [
                        v.get("provenance", {}).get("inherited_traits", {})
                        for v in variants
                    ],
                }
            )
        return {
            "scope": "forms",
            "forms": len(ORGANISM_FORMS),
            "results": results,
        }

    def evolve(
        self,
        generations: int = 3,
        n_variants: int = 4,
        seed: str = "",
        cross_pollenate: bool = True,
    ) -> Dict[str, Any]:
        """Elitist evolution across the whole organism (modules + forms).

        Each identity keeps a champion — its reigning best version. Every
        generation produces challengers from the champion; a challenger
        dethrones the champion ONLY by scoring strictly higher under the
        active fitness function. The champion never gets worse, so every
        recorded step is a positive improvement, never a regression.

        This is how the founder's version stays the best: his canonical
        organism IS the champion lineage. Mutations are tried in the
        arena; only upgrades survive.
        """
        identities = list(iter_module_identities())
        for name, spec in ORGANISM_FORMS.items():
            identities.append(
                {
                    "name": name,
                    "role": spec["role"],
                    "traits": dict(spec["traits"]),
                    "params": {"layer": "organism"},
                    "fragments": [name],
                    "lineage": ["forms-architecture"],
                    "module_meta": {},
                }
            )
        donor_pool = {ident["name"]: ident for ident in identities}
        summary: List[Dict[str, Any]] = []
        for ident in identities:
            name = ident["name"]
            champ = self.store.get_champion(name)
            if champ is not None:
                champion = champ["variant"]
                champ_score = float(champ["score"])
                start_gen = int(champ["generation"]) + 1
            else:
                champion = ident
                champ_score = self.scorer(ident)
                start_gen = 0
                self.store.set_champion(name, ident, champ_score, 0)
            dethroned = 0
            for gen in range(start_gen, start_gen + generations):
                gseed = "evolve:%s:g%d:%s" % (seed, gen, name)
                reflection = self.echo.reflect(champion)
                variants = MandellaEngine(seed).reconstruct(
                    reflection, n_variants, gseed
                )
                if cross_pollenate:
                    self._cross_pollenate(
                        name, variants, donor_pool, random.Random(gseed)
                    )
                contenders = [(self.scorer(v), v) for v in variants]
                contenders.append((champ_score, champion))  # champion defends
                best_score, best = max(contenders, key=lambda t: t[0])
                if best_score > champ_score and best is not champion:
                    champion, champ_score = best, best_score
                    self.store.set_champion(name, best, best_score, gen + 1)
                    dethroned += 1
                # every generation's outcome is composted; only real
                # improvements compress into the genome
                lessons = self.reim.compost(
                    {
                        "identity": name,
                        "success": best_score >= champ_score,
                        "score": round(best_score, 4),
                        "notes": "evolve generation %d" % (gen + 1),
                        "failures": [],
                    }
                )
                deltas = self.riem.compress(lessons, self.store.load())
                self.store.apply_deltas(deltas)
            self.store.record_candidates(name, [champion])
            summary.append(
                {
                    "name": name,
                    "champion_score": round(champ_score, 4),
                    "generation": start_gen + generations,
                    "dethroned": dethroned,
                }
            )
        genome = self.store.load()
        genome["lineage"].append(
            {
                "event": "evolution",
                "seed": seed,
                "generations": generations,
                "identities": len(identities),
            }
        )
        self.store.save(genome)
        improved = sum(1 for s in summary if s["dethroned"] > 0)
        return {
            "scope": "evolve",
            "identities": len(identities),
            "generations": generations,
            "improved": improved,
            "results": summary,
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
