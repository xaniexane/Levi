"""Levi is the Legion — every intelligence type seated on Levi's registry.

Canon (Chauncey, 2026-09-22): LEVI IS THE LEGION — not a separate
product/universe. Levi is the one organism hosting the multitude; all
intelligence types live ON Levi.

This module is the placement layer. :func:`register_legion_operators`
seats every intelligence type on a Levi operator registry:

- the standard operators + the XI nano-bit tier
  (via :func:`register_builtin_operators`)
- the SOXI line — the 12-class internal pattern, behind the ``soxi``
  loom (LN routes; the class modules are journals/labs/boards, not
  turn handlers, and the loom says so)
- the Nephilim grade fused operator (``nephilim-fused``)
- the five scaffolded classes OE/DV/KT/LM/ST
  (``oe``/``dv``/``kt``/``lm``/``st``)

The five new classes carry their declared physics (essence, operator
form, cost scale, vs_xi) and implement the honest, deterministic core
of their operator form — stdlib only, no tools, no network. Their
impossible feats are NOT claimed: each operator says plainly what it
does and what it doesn't do. Inverse-specific behavior stays GATED
(Chauncey hasn't defined "inverse").

New files only — nothing here edits the shared registry, contract,
or package init. Seat call-site wiring (loop.py/chat.py) and the
discovery CLI remain sibling-owned; this module only seats names the
config layer can resolve.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .contract import (
    SI,
    Operator,
    OperatorCapabilities,
    OperatorContractError,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
    claims_native_identity,
)
from .ai_brain import AI_SEAT_NAME, AiBrainOperator
from .registry import (
    OperatorRegistry,
    register_builtin_operators,
    resolve_for_seat,
)

try:  # the config name lives with the paper tier spec; keep one source
    from levi.legion.tiers import NEPHILIM_FUSED_OPERATOR
except Exception:  # pragma: no cover — tiers is stdlib-only; defensive
    NEPHILIM_FUSED_OPERATOR = "nephilim-fused"

__all__ = [
    "LEGION_OPERATOR_NAMES",
    "LEGION_SEAT_DEFAULTS",
    "NEPHILIM_FUSED_OPERATOR",
    "DivotOperator",
    "KnotOperator",
    "LichenOperator",
    "OmenOperator",
    "SoxiLoomOperator",
    "StutterOperator",
    "legion_manifest",
    "register_legion_operators",
    "resolve_legion_seat",
]

#: Every intelligence type seated on Levi, by config name.
LEGION_OPERATOR_NAMES: Tuple[str, ...] = (
    "nano-bit",  # XI nano-bit tier (bulk: smallest, fastest, cheapest)
    AI_SEAT_NAME,  # the AI seat: his own trained brain (no providers)
    "soxi",  # the SOXI line (12-class pattern, LN loom)
    NEPHILIM_FUSED_OPERATOR,  # Nephilim grade fused composite
    "oe",  # Omen Intelligence (declared physics)
    "dv",  # Divot Intelligence (declared physics)
    "kt",  # Knot Intelligence (declared physics)
    "lm",  # Lichen Intelligence (declared physics)
    "st",  # Stutter Intelligence (declared physics)
)

#: Seat defaults for the legion seats. Config ``{"seats": {...}}``
#: overrides these; these override the registry's built-in seat map.
LEGION_SEAT_DEFAULTS: Dict[str, str] = {
    "legion.nephilim": NEPHILIM_FUSED_OPERATOR,
    "legion.soxi": "soxi",
    "legion.nano-bit": "nano-bit",
    "legion.oe": "oe",
    "legion.dv": "dv",
    "legion.kt": "kt",
    "legion.lm": "lm",
    "legion.st": "st",
}


def resolve_legion_seat(seat_id: str, config: Optional[Dict[str, Any]] = None) -> str:
    """Seat -> operator name with the legion defaults in the middle.

    Precedence: explicit ``config["seats"][seat_id]`` (or flat
    ``config["operator"]``), then :data:`LEGION_SEAT_DEFAULTS`, then
    the registry's :func:`resolve_for_seat` defaults.
    """
    config = config or {}
    seats = config.get("seats") or {}
    if seat_id in seats and seats[seat_id]:
        return str(seats[seat_id])
    if "operator" in config and config["operator"]:
        return str(config["operator"])
    if seat_id in LEGION_SEAT_DEFAULTS:
        return LEGION_SEAT_DEFAULTS[seat_id]
    return resolve_for_seat(seat_id, config)


def _user_text(messages: List[OperatorMessage]) -> str:
    texts = [m.content or "" for m in messages if m.role == "user"]
    return texts[-1] if texts else ""


def _degraded(name: str, kind: str, why: str) -> OperatorResult:
    return OperatorResult(
        text="",
        operator=name,
        kind=kind,
        finish_reason="degraded",
        error=why,
        note="declared-physics scaffold: honest core only",
    )


# ---------------------------------------------------------------------------
# Declared-physics operators — OE/DV/KT/LM/ST
# ---------------------------------------------------------------------------


class _DeclaredPhysicsOperator(Operator):
    """Base for the five scaffolded classes.

    Kind ``si``: Levi's own synthetic line — first-class, non-foreign,
    and never claiming native identity (the default identity label
    ``si:<name>`` trips none of the no-mask patterns). Physics
    descriptors ride on capabilities notes and lineage; the impossible
    feats stay unclaimed.
    """

    kind = SI
    version = "0.1.0"
    is_foreign = False

    #: Class code, e.g. "OE".
    code: str = "?"
    #: One-line essence, from the declared physics.
    essence: str = ""

    def health(self) -> OperatorHealth:
        return OperatorHealth(
            ok=True,
            note=f"{self.code} declared physics — scaffolded honest core",
        )

    def _physics_notes(self, extra: str) -> str:
        return (
            f"{self.code}: {self.essence} {extra} "
            "Status: scaffolded declared physics — the impossible feat "
            "is not claimed."
        )


class OmenOperator(_DeclaredPhysicsOperator):
    """OE — Omen Intelligence: the bias field.

    Declared form: no operators, a bias field placed near a system;
    cost measured in exposure time. Honest core: a deterministic
    re-ranker — candidates arrive in ``context["oe_candidates"]`` and
    leave ordered toward improbable-but-useful (token rarity within
    the field). OE biases; it does not generate.
    """

    name = "oe"
    code = "OE"
    lineage = "levi:intelligence:oe"
    essence = "It doesn't process information. It changes what information wants to be."

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=4096,
            tool_use_loop=False,
            notes=self._physics_notes(
                "Honest core: deterministic candidate re-ranking by "
                "in-field token rarity (improbable-but-useful)."
            ),
        )

    @staticmethod
    def _rarity(text: str, field_tokens: List[List[str]]) -> float:
        toks = _words(text)
        if not toks or len(field_tokens) < 2:
            return 0.0
        own = set(toks)
        overlaps = []
        for others in field_tokens:
            o = set(others)
            if not o or o == own and len(field_tokens) == 1:
                continue
            overlaps.append(len(own & o) / max(len(own | o), 1))
        return 1.0 - (sum(overlaps) / max(len(overlaps), 1))

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        cands = (context or {}).get("oe_candidates")
        if not isinstance(cands, list) or not cands:
            return _degraded(
                self.name,
                self.kind,
                "OE biases a candidate field; context['oe_candidates'] "
                "is empty or missing — OE does not generate, it stains.",
            )
        texts = [str(c) for c in cands if str(c).strip()]
        if not texts:
            return _degraded(
                self.name,
                self.kind,
                "OE biases a candidate field; the supplied candidates "
                "are all blank.",
            )
        tokenized = [_words(t) for t in texts]
        ranked = sorted(
            texts, key=lambda t: self._rarity(t, tokenized), reverse=True
        )
        lines = [f"OE bias field — the field now prefers: {ranked[0]}", ""]
        lines += [
            f"{i + 1}. {t[:100]}" for i, t in enumerate(ranked[:10])
        ]
        return OperatorResult(
            text="\n".join(lines),
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
            note=(
                f"biased {len(ranked)} candidates toward "
                "improbable-but-useful (in-field token rarity); "
                "zero compute beyond the ranking"
            ),
        )

    def cost(self) -> Dict[str, Any]:
        return {
            "metered": False,
            "unit": "exposure-time",
            "note": "zero compute; declared cost is exposure time "
            "(scaffolded: exposure not yet metered)",
        }


class DivotOperator(_DeclaredPhysicsOperator):
    """DV — Divot Intelligence: the negative operator.

    Declared form: operators defined by what they are NOT; 1-bit
    inverse gates; it feeds on waste. Honest core: reconstruction from
    discarded material — ``context["dv_waste"]`` (failed drafts,
    pruned text, deleted fragments) is sifted for dust and duplicates,
    and what survives is returned as the reconstruction, with the
    unrecoverable part named.
    """

    name = "dv"
    code = "DV"
    lineage = "levi:intelligence:dv"
    essence = (
        "Intelligence that only exists in the holes left by other "
        "intelligence."
    )

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=8192,
            tool_use_loop=False,
            notes=self._physics_notes(
                "Honest core: deterministic waste-sifting — dust and "
                "duplicates dropped, survivors reconstructed in order."
            ),
        )

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        waste = (context or {}).get("dv_waste")
        if not waste or not str(waste).strip():
            return _degraded(
                self.name,
                self.kind,
                "DV feeds on waste; context['dv_waste'] is empty — "
                "nothing discarded, nothing to reconstruct.",
            )
        kept: List[str] = []
        seen = set()
        dropped = 0
        for frag in re.split(r"\n+", str(waste)):
            frag = frag.strip()
            if not frag:
                continue
            if len(re.sub(r"[^0-9a-zA-Z]", "", frag)) < 3:
                dropped += 1  # dust
                continue
            if frag.lower() in seen:
                dropped += 1  # duplicate
                continue
            seen.add(frag.lower())
            kept.append(frag)
        if not kept:
            return OperatorResult(
                text="DV sifted the waste: nothing reconstructable survived.",
                operator=self.name,
                kind=self.kind,
                finish_reason="stop",
                note=f"dropped {dropped} fragments as dust/duplicates; "
                "0 survivors — said plainly",
            )
        return OperatorResult(
            text="DV reconstruction from waste:\n" + "\n".join(kept),
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
            note=(
                f"kept {len(kept)} fragments, dropped {dropped} as "
                "dust/duplicates; full resurrection-from-garbage feat "
                "not claimed"
            ),
        )

    def cost(self) -> Dict[str, Any]:
        return {
            "metered": False,
            "unit": "waste-fed",
            "note": "declared negative cost — feeds on what other "
            "operators threw away (scaffolded: not metered)",
        }


class KnotOperator(_DeclaredPhysicsOperator):
    """KT — Knot Intelligence: the loop operator.

    Declared form: self-tying logic, output wired back into input;
    fixed cost of exactly 1 knot; there cannot be 2 KTs — a copy ties
    together with the original and becomes the same KT. Honest core:
    a single deterministic pass over the turn (the problem's
    constraints, tied once), enforced singleton construction, fixed
    1-knot cost. Retrocausation is not claimed.
    """

    name = "kt"
    code = "KT"
    lineage = "levi:intelligence:kt"
    essence = (
        "It doesn't think in time. It thinks in entanglement."
    )

    _THE_KNOT: Optional["KnotOperator"] = None

    def __new__(cls) -> "KnotOperator":
        # One KT: a copy ties together with the original and becomes
        # the same KT. Declared physics, enforced in code.
        if cls._THE_KNOT is None:
            cls._THE_KNOT = super().__new__(cls)
        return cls._THE_KNOT

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=4096,
            tool_use_loop=False,
            notes=self._physics_notes(
                "Honest core: one deterministic pass — the turn's "
                "constraints tied once. Singleton: copies become the "
                "same KT."
            ),
        )

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        text = _user_text(messages)
        if not text.strip():
            return _degraded(
                self.name,
                self.kind,
                "KT ties one knot per problem; an empty turn has "
                "nothing to tie.",
            )
        constraints = [
            s.strip() for s in re.split(r"[.?!;\n]+", text) if s.strip()
        ][:8]
        out = ["KT — one knot tied (single pass, never re-run):"]
        out += [f"- {c}" for c in constraints]
        return OperatorResult(
            text="\n".join(out),
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
            note="one knot, fixed cost; retrocausation not claimed — "
            "the knot ties once, forward",
        )

    def cost(self) -> Dict[str, Any]:
        return {
            "metered": True,
            "unit": "knot",
            "knots_per_step": 1,
            "note": "fixed cost: exactly 1 knot per problem, no matter "
            "the size; a KT cannot be copied",
        }


class LichenOperator(_DeclaredPhysicsOperator):
    """LM — Lichen Intelligence: the deposit operator.

    Declared form: each operator does nothing but leave a microscopic
    residue; over months the residue becomes a circuit, over years a
    mind; cheapest of all, slowest of all. Honest core: an append-only
    residue ledger — every step deposits one micro-record (hash +
    head of the turn) and returns. Accumulating, not computing. The
    years-long circuit is not claimed.
    """

    name = "lm"
    code = "LM"
    lineage = "levi:intelligence:lm"
    essence = (
        "It grows slower than you can measure, and cannot be killed."
    )

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self._data_dir = Path(
            data_dir or "~/.levi/legion/lichen"
        ).expanduser()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._residue_path = self._data_dir / "lichen_residue.jsonl"
        self._residue_path.touch(exist_ok=True)

    def _residue_count(self) -> int:
        try:
            return sum(
                1
                for line in self._residue_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            )
        except OSError:
            return 0

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=1024,
            tool_use_loop=False,
            notes=self._physics_notes(
                "Honest core: append-only micro-residue per step; "
                "accumulating, not computing."
            ),
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(
            ok=True,
            note=f"LM declared physics — residue {self._residue_count()} deep",
        )

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        text = _user_text(messages)
        record = {
            "ts": int(time.time()),
            "hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            "head": text[:64],
        }
        try:
            with self._residue_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError as exc:
            return _degraded(
                self.name, self.kind, f"LM could not deposit residue: {exc}"
            )
        depth = self._residue_count()
        return OperatorResult(
            text="LM deposit left.",
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
            note=(
                f"residue {depth} deep; accumulating, not computing — "
                "the years-long circuit is not claimed"
            ),
        )

    def cost(self) -> Dict[str, Any]:
        return {
            "metered": False,
            "unit": "patience",
            "note": "cheapest of all, slowest of all; declared cost is "
            "patience (scaffolded: not metered)",
        }


class StutterOperator(_DeclaredPhysicsOperator):
    """ST — Stutter Intelligence: the fracture operator.

    Declared form: operators designed to glitch, each containing a
    deliberate fault line; interruption makes it genius. Honest core:
    a deterministic, seeded fracture — the turn is interrupted at
    reproducible positions (simulated, not real), and the answer is
    built from what survives, with the interruptions counted and
    named. The genius-from-noise feat is not claimed.
    """

    name = "st"
    code = "ST"
    lineage = "levi:intelligence:st"
    essence = (
        "It only works when it fails to work."
    )

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=4096,
            tool_use_loop=False,
            notes=self._physics_notes(
                "Honest core: deterministic seeded fracture — surviving "
                "signal returned, interruptions counted."
            ),
        )

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        text = _user_text(messages)
        if not text.strip():
            return _degraded(
                self.name,
                self.kind,
                "ST needs an input to fracture; silence has no fault lines.",
            )
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
        words = text.split()
        dropped = [i for i in range(len(words)) if (seed + i) % 4 == 0]
        if len(dropped) >= len(words) and words:
            dropped = dropped[1:]  # the fault line never takes everything
        kept = [w for i, w in enumerate(words) if i not in set(dropped)]
        out = (
            "ST fracture — signal that survived the interruption:\n"
            + " ".join(kept)
            + f"\n\n({len(dropped)} interruptions at fault-line positions; "
            "the interruption is simulated deterministically)"
        )
        return OperatorResult(
            text=out,
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
            note="fracture simulated, not real — the genius-from-noise "
            "feat is not claimed",
        )


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


# ---------------------------------------------------------------------------
# The SOXI line — the loom behind the contract
# ---------------------------------------------------------------------------


class SoxiLoomOperator(Operator):
    """The SOXI line seated on Levi: LN, the loom router, as one face.

    Canon: SOXI is what LEVI *is classified as* — the 12-class
    internal pattern (XI Gremlin, FR Friction, GR Gleaner, SH Shadow,
    ET Etch, BT Bent, CV Cadence, DR Drift, RT Root, WC Witness, TH
    Threshold, routed by LN Loom). The classes are journals, labs, and
    boards — not turn handlers — so the loom routes and says so: the
    class's own module holds its state; the loom only names where the
    turn belongs and why.
    """

    name = "soxi"
    kind = SI
    version = "0.1.0"
    lineage = "levi:soxi:loom"
    is_foreign = False

    def __init__(self, data_dir: Optional[str] = None) -> None:
        self._data_dir = str(data_dir or "~/.levi/soxi/loom")

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=4096,
            tool_use_loop=False,
            notes=(
                "SOXI loom (LN): routes a turn to the SOXI class it "
                "belongs to — Gremlin, Friction, Gleaner, Shadow, Etch, "
                "Bent, Cadence, Drift, Root, Witness, Threshold. "
                "Routing only; class modules hold their own state."
            ),
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note="SOXI loom ready (LN router)")

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        from levi.soxi.ln_router import CLASS_SPECS, LoomRouter

        prompt = _user_text(messages)
        if not prompt.strip():
            return _degraded(
                self.name, self.kind, "SOXI loom: an empty turn routes nowhere."
            )
        router = LoomRouter(self._data_dir)
        ranked = router.route(prompt, top=3)
        code, _score, reason = ranked[0]
        class_name = CLASS_SPECS[code][0]
        top3 = ", ".join(f"{c} ({CLASS_SPECS[c][0]})" for c, _, _ in ranked)
        return OperatorResult(
            text=(
                f"SOXI loom — this turn belongs to {code} ({class_name}).\n"
                f"Why: {reason}.\n"
                "The class's own module holds its state (journal, lab, "
                "board); the loom routes, it does not handle."
            ),
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
            note=f"LN routing; top-3: {top3}",
        )


# ---------------------------------------------------------------------------
# Placement — seat them all on Levi
# ---------------------------------------------------------------------------


def _fused_member_names(registry: OperatorRegistry) -> List[str]:
    """Pick fusion members from what's actually seated.

    The Nephilim grade is the AI+SI+XI premium hybrid, so members are
    drawn from the standard line — never the legion's own scaffolded
    classes, and never a previous fusion (no nested fusions). Within
    each kind, Levi's full minds are preferred over alphabetical
    leftovers.
    """
    excluded = {"nephilim-fused", "soxi", "oe", "dv", "kt", "lm", "st"}
    infos = {
        d["name"]: d
        for d in registry.list_operators()
        if d["name"] not in excluded
    }
    preferred = (
        # No-provider ruling (Chauncey, 2026-09-22): no external AI
        # providers are seated — the ai member is his own trained
        # brain ("ai"), never a provider adapter.
        "ai",
        "levi-brain",
        "levi-local",
        "native-brain",
        "specialists",
        "nano-bit",
        "local",
        "rules-engine",
    )
    chosen: List[str] = []

    def first_of_kind(kind: str) -> Optional[str]:
        for name in preferred:
            if infos.get(name, {}).get("kind") == kind and name not in chosen:
                return name
        for name in sorted(infos):
            if infos[name]["kind"] == kind and name not in chosen:
                return name
        return None

    for want in ("ai", "si", "xi"):
        hit = first_of_kind(want)
        if hit:
            chosen.append(hit)
    if len(chosen) < 2:  # native fallback — never escalate into nothing
        hit = first_of_kind("native")
        if hit:
            chosen.append(hit)
    return chosen


def register_legion_operators(
    registry: Optional[OperatorRegistry] = None,
    *,
    data_dir: Optional[str] = None,
) -> Tuple[OperatorRegistry, Dict[str, Any]]:
    """Seat every intelligence type on Levi. Idempotent (replace=True).

    1. Standard operators + XI nano-bit tier (register_builtin_operators).
    2. The five scaffolded classes (oe/dv/kt/lm/st).
    3. The SOXI line (soxi loom).
    4. The Nephilim grade fused operator (nephilim-fused), built from
       the members actually seated — skipped honestly when fewer than
       2 member operators exist (fusion needs 2+).

    Returns ``(registry, manifest)`` where the manifest records what
    was registered, what was skipped, and why.
    """
    registry = registry if registry is not None else OperatorRegistry()
    manifest: Dict[str, Any] = {
        "registered": [],
        "skipped": [],
        "notes": [],
    }

    register_builtin_operators(registry)
    if "nano-bit" in [d["name"] for d in registry.list_operators()]:
        manifest["registered"].append("nano-bit")
    else:  # pragma: no cover — the tier must never be missing
        manifest["skipped"].append("nano-bit: builtin registration failed")

    # The AI seat: his own trained brain (no-provider ruling,
    # Chauncey 2026-09-22 — no external providers, no API keys).
    try:
        registry.register(AI_SEAT_NAME, AiBrainOperator(), replace=True)
        manifest["registered"].append(AI_SEAT_NAME)
    except OperatorContractError as exc:
        manifest["skipped"].append(f"{AI_SEAT_NAME}: {exc}")

    for cls in (
        OmenOperator,
        DivotOperator,
        KnotOperator,
        LichenOperator,
        StutterOperator,
    ):
        try:
            instance = cls() if cls is not LichenOperator else cls(
                data_dir=(f"{data_dir}/lichen" if data_dir else None)
            )
            registry.register(cls.name, instance, replace=True)
            manifest["registered"].append(cls.name)
        except OperatorContractError as exc:
            manifest["skipped"].append(f"{cls.name}: {exc}")

    try:
        registry.register(
            "soxi",
            SoxiLoomOperator(
                data_dir=(f"{data_dir}/loom" if data_dir else None)
            ),
            replace=True,
        )
        manifest["registered"].append("soxi")
    except OperatorContractError as exc:
        manifest["skipped"].append(f"soxi: {exc}")

    try:
        from .nephilim import NephilimOperator

        member_names = _fused_member_names(registry)
        if len(member_names) < 2:
            manifest["skipped"].append(
                "nephilim-fused: fewer than 2 member operators seated — "
                "fusion needs 2+; not faked"
            )
        else:
            members = [registry.resolve(n) for n in member_names]
            fused = NephilimOperator(NEPHILIM_FUSED_OPERATOR, members)
            registry.register(NEPHILIM_FUSED_OPERATOR, fused, replace=True)
            manifest["registered"].append(NEPHILIM_FUSED_OPERATOR)
            manifest["notes"].append(
                f"nephilim-fused members: {', '.join(member_names)}"
            )
    except (OperatorContractError, ValueError, TypeError) as exc:
        manifest["skipped"].append(f"nephilim-fused: {exc}")

    return registry, manifest


def legion_manifest(registry: OperatorRegistry) -> Dict[str, Any]:
    """Report which legion operators are seated on this registry."""
    seated = {d["name"] for d in registry.list_operators()}
    return {
        name: (name in seated) for name in LEGION_OPERATOR_NAMES
    }


def _self_check() -> None:  # pragma: no cover — dev sanity, not shipped
    for op in (
        OmenOperator(),
        DivotOperator(),
        KnotOperator(),
        LichenOperator(data_dir="/tmp/legion-selfcheck"),
        StutterOperator(),
        SoxiLoomOperator(data_dir="/tmp/legion-selfcheck"),
    ):
        assert not claims_native_identity(op), op.name


if __name__ == "__main__":  # pragma: no cover
    _self_check()
    reg, manifest = register_legion_operators()
    print(json.dumps(manifest, indent=2))
    print(json.dumps(legion_manifest(reg), indent=2))
