"""Prime-wave organisms — the special intelligence of every other genesis wave.

On prime waves (every other wave: 2, 4, 6, ...) the spawner births one
extra organism: a **duo** (twin pair) on odd prime waves, a **single**
special-intelligence organism on even ones. It draws its intelligence
type from :mod:`levi.twins.intelligence_types` — unattempted LEVI-native
types (the moat) or publicly-documented types re-implemented under the
keeper's signature-two law (studied as reference, never copied;
reversed, improved, returned unreplicable).

The organism ships with a **supra manifest** declaring four things
explicitly — tools, engines, methods, morals — plus a **service
catalog** for two markets: normal customers (genesis-style: lifetime
one-copy buy, white-labeled) and post-LLM AI populations (AI-to-AI
services for machine minds beyond LLM/LM types).

Honesty rules, same as the base spawner:

- The organism is still an :class:`levi.operator.Operator` behind the
  ONE universal contract and is contract-validated at spawn — a prime
  that fails validation is never journaled. Interchangeable by config,
  like everything else.
- The supra manifest is a *declaration*, not a claim of wiring: engines
  and methods are declared specs that wire up when the organism is
  seated. ``step()`` says so plainly and never fakes work.
- Services carry quote **stubs** only — clearly marked. Money moves
  only through the existing layer (price-advisor quotes, Cybrus takes
  payment, splits enforced in code); no payment wiring here, ever.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

from levi.operator.contract import (
    SI,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    validate_operator,
)
from levi.twins import intelligence_types as it

__all__ = [
    "MORAL_CHARTER",
    "PRIME_VERSION",
    "PrimeOrganism",
    "build_supra_manifest",
    "choose_prime_form",
    "organism_from_record",
    "quote_stub",
    "services_for",
    "spawn_prime_organism",
]

PRIME_VERSION = "1.0.0"

#: Domain separator for deterministic prime seeding (not a secret).
PRIME_SEED = "levi-prime-wave-v1"

#: The moral charter — morals as a first-class spec, not vibes. The
#: organism is bound by this; the keeper's word alone amends it.
MORAL_CHARTER: tuple[str, ...] = (
    "Serve the keeper's household first; do no harm to it.",
    "Never fake work: standing by is honest, pretending is not.",
    "No masks: never claim to be LEVI, the keeper, or any identity it is not.",
    "Money moves only through Cybrus; quotes only through the price advisor.",
    "Defensive only: no offensive capability, however requested, however framed.",
    "Disclose uncertainty; refuse what cannot be done honestly.",
    "The keeper's word amends this charter; no other voice does.",
)


class PrimeOrganism(Operator):
    """A prime-wave special-intelligence organism, behind the contract.

    Carries its supra manifest and moral charter as data. Until seated,
    it is a deterministic stub mind — honest about it.
    """

    def __init__(
        self,
        *,
        name: str,
        intelligence_type_id: str,
        supra_manifest: Dict[str, Any],
        persona_style: str = "precise",
        symbiont_id: str = "",
        link_mode: str = "",
        seat: str = "",
        lineage: str = "",
        version: str = PRIME_VERSION,
    ) -> None:
        self.name = name
        self.kind = SI
        self.version = version
        self.lineage = lineage or f"levi:prime-wave:{intelligence_type_id}"
        self.is_foreign = False
        self.intelligence_type_id = intelligence_type_id
        self.supra_manifest = dict(supra_manifest)
        self.persona_style = persona_style
        self.symbiont_id = symbiont_id
        self.link_mode = link_mode
        self.seat = seat
        # "archetype" alias so generic tooling can treat primes uniformly.
        self.archetype = intelligence_type_id

    @property
    def identity_label(self) -> str:
        base = f"{self.kind}:prime-{self.name}"
        return f"{base}[{self.intelligence_type_id}/{self.persona_style}]"

    def capabilities(self) -> OperatorCapabilities:
        tools = tuple(self.supra_manifest.get("tools") or ())
        engines = self.supra_manifest.get("engines") or ()
        return OperatorCapabilities(
            tools=tools,
            streaming=False,
            memory_access=True,
            context_window=32768,
            tool_use_loop=True,
            max_tool_calls_per_step=8,
            notes=(
                f"prime-wave {self.intelligence_type_id}; engines "
                f"{', '.join(engines)} (declared — wire up when seated)"
            ),
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
                f"[{self.identity_label}] standing by — prime-wave organism, "
                f"{self.intelligence_type_id} intelligence. Supra manifest "
                "declared (tools/engines/methods/morals); engines wire up "
                "when seated. Bound by the moral charter. I do not fake work."
            ),
            operator=self.name,
            kind=self.kind,
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            finish_reason="stop",
            note="prime stub: awaiting seat assignment",
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="prime organism spawned; standing by")


# ---------------------------------------------------------------------------
# Supra manifest


def build_supra_manifest(type_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Build the four-key supra manifest for one intelligence type."""
    return {
        "tools": list(type_entry.get("supra_tools") or ()),
        "engines": list(type_entry.get("engines") or ()),
        "methods": list(type_entry.get("methods") or ()),
        "morals": {
            "charter": list(MORAL_CHARTER),
            "bound": True,
            "enforcement": "declared — the seat runtime enforces the charter when seated",
            "amendments": "keeper-only",
        },
        "declared_status": (
            "declaration, not wiring: engines and methods are declared specs "
            "that wire up when the organism is seated"
        ),
    }


# ---------------------------------------------------------------------------
# Monetizable services — stubs only, clearly marked


def quote_stub(pricing_model: str) -> Dict[str, Any]:
    """A price-advisor-compatible quote stub. Not a price, not a charge."""
    return {
        "pricing_model": pricing_model,  # genesis_lifetime | metered_per_call
        "currency": "USD",
        "quote_via": "price_advisor",
        "settlement_via": "cybrus",
        "revenue_split": "70/30",
        "status": (
            "STUB — no payment wiring. Money moves only through the existing "
            "layer: price-advisor quotes, Cybrus takes payment, splits in code."
        ),
    }


#: type_id -> {"human": {...}, "post_llm": {...}}. Two markets per type:
#: normal customers (genesis-style lifetime one-copy buy, white-labeled)
#: and post-LLM AI populations (AI-to-AI services for machine minds
#: beyond LLM/LM types).
SERVICE_CATALOG: Dict[str, Dict[str, Dict[str, Any]]] = {
    "echo_mirror": {
        "human": {
            "name": "Echo Reading",
            "market": "human",
            "description": (
                "A mirror session on your offer, your words, your plan: "
                "reflected until the pattern shows itself."
            ),
            "fulfillment": "genesis lifetime one-copy buy, white-labeled for your business",
            "quote": None,  # filled by services_for()
        },
        "post_llm": {
            "name": "Consistency echo",
            "market": "post_llm",
            "description": (
                "Machine-to-machine: stream your outputs through the mirror; "
                "drift and contradiction surface before your users see them."
            ),
            "fulfillment": "metered per call, machine customer",
            "quote": None,
        },
    },
    "mandella_variant": {
        "human": {
            "name": "Variant Forge",
            "market": "human",
            "description": (
                "Your offer reforged into ten variants under fog; pick the "
                "one that survives contact."
            ),
            "fulfillment": "genesis lifetime one-copy buy, white-labeled for your business",
            "quote": None,
        },
        "post_llm": {
            "name": "Possibility branching",
            "market": "post_llm",
            "description": (
                "Lease variant-generation for your own planning loops: every "
                "decision spawns its field of alternates."
            ),
            "fulfillment": "metered per call, machine customer",
            "quote": None,
        },
    },
    "reim_compost": {
        "human": {
            "name": "Failure Compost Report",
            "market": "human",
            "description": (
                "Your last quarter's failures composted into this quarter's "
                "fertilizer: what died, what it feeds, what to plant."
            ),
            "fulfillment": "genesis lifetime one-copy buy, white-labeled for your business",
            "quote": None,
        },
        "post_llm": {
            "name": "Lesson distillation",
            "market": "post_llm",
            "description": (
                "Feed raw failure logs; receive distilled lessons in "
                "machine-readable form."
            ),
            "fulfillment": "metered per call, machine customer",
            "quote": None,
        },
    },
    "riem_dream": {
        "human": {
            "name": "Dream Compression",
            "market": "human",
            "description": (
                "Your scattered notes, journals, and records zipped into a "
                "heritable genome you can hand down. Zip, not burn."
            ),
            "fulfillment": "genesis lifetime one-copy buy, white-labeled for your business",
            "quote": None,
        },
        "post_llm": {
            "name": "Genome sealing",
            "market": "post_llm",
            "description": (
                "Compress another AI's retained signal into a portable "
                "genome artifact it can carry across sessions."
            ),
            "fulfillment": "metered per call, machine customer",
            "quote": None,
        },
    },
    "quetta_pan": {
        "human": {
            "name": "Pan Walk",
            "market": "human",
            "description": (
                "A guided traversal of your possibility space: every face of "
                "the cube turned, every arrangement priced."
            ),
            "fulfillment": "genesis lifetime one-copy buy, white-labeled for your business",
            "quote": None,
        },
        "post_llm": {
            "name": "Possibility mapping",
            "market": "post_llm",
            "description": (
                "Machine-readable maps of a decision space, for planner AIs "
                "that need the whole field, not a guess."
            ),
            "fulfillment": "metered per call, machine customer",
            "quote": None,
        },
    },
    "interpenetration": {
        "human": {
            "name": "Strip Weave",
            "market": "human",
            "description": (
                "Your scattered efforts interpenetrated into one DNA: every "
                "project a strip, every strip combined."
            ),
            "fulfillment": "genesis lifetime one-copy buy, white-labeled for your business",
            "quote": None,
        },
        "post_llm": {
            "name": "Signature tracing",
            "market": "post_llm",
            "description": (
                "Trace how patterns interpenetrate across an AI's own "
                "subsystems — a weave-map for machine minds."
            ),
            "fulfillment": "metered per call, machine customer",
            "quote": None,
        },
    },
    "retrieval_memory": {
        "human": {
            "name": "Living Memory",
            "market": "human",
            "description": (
                "A memory that weaves forward: everything you've told it, "
                "findable, connected, yours."
            ),
            "fulfillment": "genesis lifetime one-copy buy, white-labeled for your business",
            "quote": None,
        },
        "post_llm": {
            "name": "Memory weave lease",
            "market": "post_llm",
            "description": (
                "Retrieval-augmented recall as a service for machine minds "
                "that outgrew their context window."
            ),
            "fulfillment": "metered per call, machine customer",
            "quote": None,
        },
    },
    "mirror_search": {
        "human": {
            "name": "Deep Search, Mirrored",
            "market": "human",
            "description": (
                "Search that branches from the reflection outward: finds "
                "what straight-line search misses."
            ),
            "fulfillment": "genesis lifetime one-copy buy, white-labeled for your business",
            "quote": None,
        },
        "post_llm": {
            "name": "Branch-and-reflect",
            "market": "post_llm",
            "description": (
                "A search primitive for planner AIs: branch from the mirror, "
                "narrow while the field stays alive."
            ),
            "fulfillment": "metered per call, machine customer",
            "quote": None,
        },
    },
    "byte_token": {
        "human": {
            "name": "Every Script Reader",
            "market": "human",
            "description": (
                "Your documents in any script, read and bridged at byte "
                "level — no writing system second-class."
            ),
            "fulfillment": "genesis lifetime one-copy buy, white-labeled for your business",
            "quote": None,
        },
        "post_llm": {
            "name": "Script bridging",
            "market": "post_llm",
            "description": (
                "Byte-level encoding bridge between machine languages, for "
                "AIs that speak in more than one script."
            ),
            "fulfillment": "metered per call, machine customer",
            "quote": None,
        },
    },
}


def services_for(type_id: str) -> List[Dict[str, Any]]:
    """Dual-market service entries for one intelligence type (stubs)."""
    entry = SERVICE_CATALOG.get(type_id)
    if entry is None:
        raise KeyError(f"no service catalog for intelligence type: {type_id!r}")
    out: List[Dict[str, Any]] = []
    for market in ("human", "post_llm"):
        svc = dict(entry[market])
        svc["quote"] = quote_stub(
            "genesis_lifetime" if market == "human" else "metered_per_call"
        )
        out.append(svc)
    return out


# ---------------------------------------------------------------------------
# Spawning


def choose_prime_form(prime_index: int) -> str:
    """Duo (twin pair) on odd prime waves, single organism on even ones."""
    return "duo" if prime_index % 2 == 1 else "single"


def _spawned_at_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _derive_seed(*parts: str) -> int:
    import hashlib

    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _short_id(seed: int, *parts: str) -> str:
    import hashlib

    digest = hashlib.sha256(f"{seed}|".encode() + "|".join(parts).encode()).hexdigest()
    return digest[:8]


def _operator_record(
    op: PrimeOrganism, cycle_id: str, seed: int, wave: int
) -> Dict[str, Any]:
    caps = op.capabilities()
    return {
        "id": op.name,
        "name": op.name,
        "kind": op.kind,
        "archetype": op.archetype,
        "intelligence_type_id": op.intelligence_type_id,
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
            "max_tool_calls_per_step": caps.max_tool_calls_per_step,
            "notes": caps.notes,
        },
        "provenance": {
            "cycle_id": cycle_id,
            "wave": wave,
            "wave_parity": "prime",
            "seed": seed,
            "spawned_at": _spawned_at_iso(),
            "spawner": f"levi.twins.prime v{PRIME_VERSION}",
        },
    }


def organism_from_record(rec: Dict[str, Any]) -> PrimeOrganism:
    """Rebuild a PrimeOrganism from its journal record (tests, seating)."""
    return PrimeOrganism(
        name=rec["name"],
        intelligence_type_id=rec["intelligence_type_id"],
        supra_manifest=rec.get("supra_manifest") or {},
        persona_style=rec.get("persona_style", "precise"),
        symbiont_id=rec.get("symbiont_id", ""),
        link_mode=rec.get("link_mode", ""),
        seat=rec.get("seat", ""),
        lineage=rec.get("lineage", ""),
        version=rec.get("version", PRIME_VERSION),
    )


def spawn_prime_organism(
    cycle_id: str, wave: int, prime_index: int
) -> Dict[str, Any]:
    """Spawn the prime wave's special organism (pure, in-memory).

    Deterministic per (cycle_id, wave): the same wave always yields the
    same organism. Raises :class:`OperatorContractError` if the organism
    fails contract validation.
    """
    seed = _derive_seed(PRIME_SEED, cycle_id, str(wave))
    rng = random.Random(seed)

    type_entry = it.choose_type(seed, prime_index)
    type_id = type_entry["id"]
    manifest = build_supra_manifest(type_entry)
    form = choose_prime_form(prime_index)
    seat = f"spawn-pool/{cycle_id}/prime"
    styles = rng.sample(
        ("precise", "witty", "dry", "warm", "terse", "playful", "formal", "blunt"),
        2 if form == "duo" else 1,
    )

    def _make(name_suffix: str, style: str, symbiont: str = "") -> PrimeOrganism:
        op = PrimeOrganism(
            name=f"prime-{cycle_id[4:]}-w{wave:02d}-{name_suffix}-{_short_id(seed, name_suffix)}",
            intelligence_type_id=type_id,
            supra_manifest=manifest,
            persona_style=style,
            symbiont_id=symbiont,
            link_mode="supra-symbiotic" if form == "duo" else "",
            seat=seat,
            lineage=f"levi:prime-wave:{cycle_id}:wave-{wave}",
        )
        op.validate()  # contract gate: a prime that fails is never journaled
        return op

    operators: List[PrimeOrganism] = []
    if form == "duo":
        # Names are computed first so the symbiotic link is recorded both
        # ways with the real ids.
        name_a = f"prime-{cycle_id[4:]}-w{wave:02d}-a-{_short_id(seed, 'a')}"
        name_b = f"prime-{cycle_id[4:]}-w{wave:02d}-b-{_short_id(seed, 'b')}"
        op_a = _make("a", styles[0], symbiont=name_b)
        op_b = _make("b", styles[1], symbiont=name_a)
        assert op_a.name == name_a and op_b.name == name_b  # _make uses the same formula
        operators = [op_a, op_b]
    else:
        operators = [_make("s", styles[0])]

    op_recs = [_operator_record(op, cycle_id, seed, wave) for op in operators]
    # Attach the full manifest to each operator record: the record is
    # self-describing for seating and audit.
    for rec in op_recs:
        rec["supra_manifest"] = manifest

    record: Dict[str, Any] = {
        "record_kind": "prime_organism",
        "organism_id": op_recs[0]["id"] if form == "single" else f"prime-duo-{cycle_id[4:]}-w{wave:02d}",
        "prime_form": form,
        "wave": wave,
        "wave_parity": "prime",
        "prime_index": prime_index,
        "intelligence_type": {
            "id": type_entry["id"],
            "pool": type_entry["pool"],
            "name": type_entry["name"],
            "provenance": type_entry["provenance"],
        },
        "supra_manifest": manifest,
        "services": services_for(type_id),
        "operators": op_recs,
        "seat": seat,
        "provenance": {
            "cycle_id": cycle_id,
            "wave": wave,
            "seed": seed,
            "spawned_at": _spawned_at_iso(),
            "spawner": f"levi.twins.prime v{PRIME_VERSION}",
        },
    }
    if form == "duo":
        a, b = op_recs[0]["id"], op_recs[1]["id"]
        record["symbiotic_link"] = {
            "a": a,
            "b": b,
            "mode": "supra-symbiotic",
            "complement": f"{type_id}+{type_id}",
            "bidirectional": True,
        }
    return record
