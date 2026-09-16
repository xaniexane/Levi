"""Mandella — the surgeon (identity variant engine).

Takes Echo's Reflection, repairs detected fractures, then produces
controlled variants: parameter drift, trait swaps/drift, fragment
recombination. Bounded mutations, deterministic under an explicit seed.
"""

from __future__ import annotations

import copy
import random
from typing import Any, Dict, List, Optional

from levi.identity.echo import Reflection

_MAX_PARAM_DRIFT = 0.15
_MAX_TRAIT_DRIFT = 0.10


class MandellaEngine:
    """Reconstruct an identity into repaired + mutated variants."""

    def __init__(self, seed: str = "") -> None:
        self.seed = seed

    def reconstruct(
        self,
        reflection: Reflection,
        n_variants: int = 3,
        seed: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not isinstance(reflection, Reflection):
            raise ValueError(
                "reconstruct: reflection must be a Reflection, got %s"
                % type(reflection).__name__
            )
        if isinstance(n_variants, bool) or not isinstance(n_variants, int):
            raise ValueError("reconstruct: n_variants must be an int")
        if n_variants < 1:
            raise ValueError("reconstruct: n_variants must be >= 1")
        rng = random.Random(self.seed if seed is None else seed)
        parent = copy.deepcopy(reflection.mirror)
        repaired = self._repair(parent, reflection.fractures)
        variants = []
        for i in range(n_variants):
            variant = copy.deepcopy(repaired)
            mutations = self._mutate(variant, rng)
            lineage = list(variant.get("lineage", []))
            lineage.append(parent.get("name", ""))
            variant["name"] = "%s#%d" % (parent.get("name", "unnamed"), i)
            variant["lineage"] = lineage
            variant["mutations"] = mutations
            variant["parent_signature"] = reflection.signature
            variants.append(variant)
        return variants

    # -- repair ---------------------------------------------------------
    def _repair(
        self, identity: Dict[str, Any], fractures: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        for frac in fractures:
            ftype = frac.get("type")
            if ftype == "trait-out-of-range":
                for key, val in identity["traits"].items():
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        identity["traits"][key] = max(0.0, min(1.0, val))
            elif ftype == "fragment-duplicate":
                seen: List[str] = []
                for frag in identity["fragments"]:
                    if frag not in seen:
                        seen.append(frag)
                identity["fragments"] = seen
            elif ftype == "fragment-conflict":
                # keep the positive form; drop the negation (deterministic)
                identity["fragments"] = [
                    f
                    for f in identity["fragments"]
                    if not (isinstance(f, str) and f.startswith("not:"))
                ]
        return identity

    # -- mutation -------------------------------------------------------
    def _mutate(
        self, variant: Dict[str, Any], rng: random.Random
    ) -> List[Dict[str, Any]]:
        ops = ["param-drift", "trait-swap", "trait-drift", "fragment-recombine"]
        chosen = rng.sample(ops, k=rng.randint(1, min(3, len(ops))))
        applied = []
        for op in chosen:
            fn = getattr(self, "_op_" + op.replace("-", "_"))
            detail = fn(variant, rng)
            if detail:
                applied.append({"op": op, "detail": detail})
        return applied

    def _op_param_drift(self, variant: Dict[str, Any], rng: random.Random):
        params = variant.get("params", {})
        if not params:
            return None
        key = rng.choice(sorted(params))
        val = params[key]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return None
        factor = 1.0 + rng.uniform(-_MAX_PARAM_DRIFT, _MAX_PARAM_DRIFT)
        params[key] = val * factor
        return {"param": key, "from": val, "to": params[key]}

    def _op_trait_swap(self, variant: Dict[str, Any], rng: random.Random):
        traits = variant.get("traits", {})
        keys = sorted(traits)
        if len(keys) < 2:
            return None
        a, b = rng.sample(keys, 2)
        traits[a], traits[b] = traits[b], traits[a]
        return {"swapped": [a, b]}

    def _op_trait_drift(self, variant: Dict[str, Any], rng: random.Random):
        traits = variant.get("traits", {})
        keys = sorted(traits)
        if not keys:
            return None
        key = rng.choice(keys)
        val = traits[key]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return None
        new = max(0.0, min(1.0, val + rng.uniform(-_MAX_TRAIT_DRIFT, _MAX_TRAIT_DRIFT)))
        traits[key] = new
        return {"trait": key, "from": val, "to": new}

    def _op_fragment_recombine(self, variant: Dict[str, Any], rng: random.Random):
        frags = variant.get("fragments", [])
        strs = [f for f in frags if isinstance(f, str)]
        if len(strs) < 2:
            return None
        a, b = rng.sample(strs, 2)
        combined = "%s // %s" % (a, b)
        idx = frags.index(a)
        frags[idx] = combined
        return {"recombined": [a, b], "into": combined}
