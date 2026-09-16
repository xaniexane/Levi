"""Echo — the mirror (identity variant engine).

Echo reflects an identity faithfully and scores its coherence, detecting
fractures (out-of-range traits, invalid params, duplicate/conflicting
fragments). It repairs nothing; repair is Mandella's job. Deterministic:
identical input always yields identical reflection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from typing import Any, Dict, List


@dataclass
class Reflection:
    name: str
    signature: str  # sha256 of canonical identity JSON
    coherence: float  # 0.0..1.0
    fractures: List[Dict[str, Any]] = field(default_factory=list)
    mirror: Dict[str, Any] = field(default_factory=dict)


def _canonical(identity: Dict[str, Any]) -> str:
    return json.dumps(identity, sort_keys=True, separators=(",", ":"))


def _signature(identity: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(identity).encode("utf-8")).hexdigest()


class EchoEngine:
    """Reflect an identity: coherence score + detected fractures."""

    def reflect(self, identity: Dict[str, Any]) -> Reflection:
        if not isinstance(identity, dict):
            raise ValueError(
                "reflect: identity must be a dict, got %s" % type(identity).__name__
            )
        coherence = 1.0
        fractures: List[Dict[str, Any]] = []

        def hit(ftype: str, detail: str, penalty: float) -> None:
            nonlocal coherence
            fractures.append({"type": ftype, "detail": detail, "penalty": penalty})
            coherence -= penalty

        name = identity.get("name")
        if not isinstance(name, str) or not name.strip():
            hit("invalid-name", "identity name must be a non-empty string", 0.3)

        traits = identity.get("traits", {})
        if not isinstance(traits, dict):
            hit("invalid-traits", "traits must be a dict", 0.3)
            traits = {}
        for key in sorted(traits):
            val = traits[key]
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                hit("trait-not-numeric", "trait %r is not numeric" % key, 0.1)
            elif not 0.0 <= val <= 1.0:
                hit(
                    "trait-out-of-range",
                    "trait %r = %r outside [0, 1]" % (key, val),
                    0.15,
                )

        params = identity.get("params", {})
        if not isinstance(params, dict):
            hit("invalid-params", "params must be a dict", 0.3)
            params = {}
        for key in sorted(params):
            val = params[key]
            if (
                not isinstance(val, (int, float))
                or isinstance(val, bool)
                or (isinstance(val, float) and (math.isnan(val) or math.isinf(val)))
            ):
                hit("param-invalid", "param %r is not a finite number" % key, 0.1)

        fragments = identity.get("fragments", [])
        if not isinstance(fragments, list):
            hit("invalid-fragments", "fragments must be a list", 0.3)
            fragments = []
        seen = set()
        positives = set()
        for frag in fragments:
            if not isinstance(frag, str):
                hit("fragment-not-string", "fragment is not a string", 0.05)
                continue
            norm = frag.strip()
            if norm in seen:
                hit("fragment-duplicate", "duplicate fragment %r" % norm[:60], 0.05)
            seen.add(norm)
            if norm.startswith("not:"):
                positives.add(norm[4:])
            else:
                positives.add(norm)
        for frag in seen:
            if frag.startswith("not:") and frag[4:] in seen:
                hit(
                    "fragment-conflict",
                    "conflicting fragments %r and %r" % (frag[4:], frag),
                    0.1,
                )

        coherence = max(0.0, min(1.0, coherence))
        mirror = {
            "name": name if isinstance(name, str) else "",
            "traits": dict(traits) if isinstance(traits, dict) else {},
            "params": dict(params) if isinstance(params, dict) else {},
            "fragments": list(fragments) if isinstance(fragments, list) else [],
            "lineage": list(identity.get("lineage", []))
            if isinstance(identity.get("lineage"), list)
            else [],
        }
        return Reflection(
            name=mirror["name"],
            signature=_signature(mirror),
            coherence=round(coherence, 4),
            fractures=fractures,
            mirror=mirror,
        )


def reflection_to_dict(r: Reflection) -> Dict[str, Any]:
    return asdict(r)
