"""DemandPulse signal packs — shippable product bundles of opportunity signals.

Chauncey's order: "Create signal packs for users and businesses."

A pack is a ranked bundle of ``signal_strength`` advisories, framed for its
audience and shippable as both a human-readable report and schema-versioned
structured data. Two products:

  * **user pack** — personal opportunity signals, written for a
    non-technical reader: plain-language summaries, actions ordered
    easiest-first, watch conditions in plain words, honest caveats.
  * **business pack** — market/competitive opportunity signals: market
    read, defensibility/moat, competition gap, and monetization path
    prominent, with the analyst's ranked actions and the full math kept
    visible.

INVARIANTS (law-guard-prove — enforced by tests/test_demand_signal_packs.py):
  PK1. Audience framing is structural, not cosmetic: user packs present
      each opportunity's actions ordered low -> medium -> high effort and
      lead with the plain summary; business packs keep the analyst's
      ranked action order and lead with monetization / defensibility /
      competition-gap framing.
  PK2. Schema-versioned envelope: every pack carries PACK_SCHEMA_VERSION
      plus the embedded signal SCHEMA_VERSION; to_dict/from_dict
      round-trips byte-stable (canonical JSON), and from_dict rejects
      unknown pack kinds.
  PK3. No anonymous packs: pack_id, built_at (caller-supplied, never
      read from the clock), and refined_by (refiner identity) are all
      required non-empty strings.
  PK4. Deterministic: no clock reads, no randomness. source_hashes is the
      sha256 of each card's canonical serialization — provenance, not
      decoration.
  PK5. Real signals only: packs never invent dimensions, evidence, or
      actions — everything rendered comes from the embedded cards.
  PK6. Entitlement is a gate description only: entitlement_gate() names
      the hookup point in core/levi/demandpulse/entitlements.py. No
      charging, no payment calls, no live checks — packs are never free,
      but the money switch lives outside this module.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from levi.demand import signal_strength
from levi.demand.signal_strength import (
    SCHEMA_VERSION,
    AdvisorReport,
    StrengthCard,
    rank_advisories,
)

PACK_SCHEMA_VERSION = "1"

PACK_KINDS = ("user", "business")

EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2}

# Business framing: the dimensions that lead a business pack, in order.
BUSINESS_LEAD_DIMENSIONS = (
    "monetization_path",
    "defensibility",
    "timing_window",
)


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return value


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _source_hash(card: StrengthCard) -> str:
    return hashlib.sha256(_canonical(card.to_dict()).encode("utf-8")).hexdigest()


def _dim(card: StrengthCard, name: str):
    for d in card.dimensions:
        if d.name == name:
            return d
    raise ValueError(f"card {card.opportunity_id!r} missing dimension {name!r}")


def _effort_ranked_actions(card: StrengthCard) -> List[Any]:
    """Card actions ordered low -> medium -> high effort (stable)."""
    indexed = list(enumerate(card.actions))
    indexed.sort(key=lambda pair: (EFFORT_ORDER[pair[1].effort], pair[0]))
    return [a for _, a in indexed]


@dataclass
class SignalPack:
    """A shippable bundle of ranked signal advisories for one audience."""

    pack_id: str
    pack_kind: str
    title: str
    built_at: str
    refined_by: str
    advisories: List[AdvisorReport]
    cards: Dict[str, StrengthCard]
    notes: str = ""
    source_hashes: Dict[str, str] = field(default_factory=dict)
    pack_schema_version: str = field(default=PACK_SCHEMA_VERSION, init=False)
    signal_schema_version: str = field(default=SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        _require_text("pack_id", self.pack_id)
        if self.pack_kind not in PACK_KINDS:
            raise ValueError(
                f"pack_kind must be one of {PACK_KINDS}, "
                f"got {self.pack_kind!r}"
            )
        _require_text("title", self.title)
        _require_text("built_at", self.built_at)
        _require_text("refined_by", self.refined_by)
        if not isinstance(self.notes, str):
            raise ValueError("notes must be a string")
        if not isinstance(self.advisories, (list, tuple)) or not all(
            isinstance(a, AdvisorReport) for a in self.advisories
        ):
            raise ValueError("advisories must be a list of AdvisorReport")
        if not self.advisories:
            raise ValueError("a pack needs at least one advisory")
        if not isinstance(self.cards, dict) or not all(
            isinstance(c, StrengthCard) for c in self.cards.values()
        ):
            raise ValueError("cards must be a dict of StrengthCard")
        adv_ids = [a.opportunity_id for a in self.advisories]
        if set(adv_ids) != set(self.cards):
            raise ValueError(
                "advisories and cards must cover the same opportunities: "
                f"advisories={sorted(adv_ids)} cards={sorted(self.cards)}"
            )
        if len(set(adv_ids)) != len(adv_ids):
            raise ValueError("duplicate opportunity in advisories")
        # Directive ranks must be 1..n in advisory order (ranked strongest first).
        for i, a in enumerate(self.advisories, 1):
            if a.directive.rank != i:
                raise ValueError(
                    f"advisory {a.opportunity_id!r} has rank "
                    f"{a.directive.rank}, expected {i} — run "
                    "rank_advisories() before building the pack"
                )
        object.__setattr__(
            self, "advisories", list(self.advisories))
        object.__setattr__(self, "cards", dict(self.cards))
        object.__setattr__(
            self,
            "source_hashes",
            {oid: _source_hash(self.cards[oid]) for oid in adv_ids},
        )

    @property
    def opportunity_order(self) -> List[str]:
        return [a.opportunity_id for a in self.advisories]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pack_schema_version": self.pack_schema_version,
            "signal_schema_version": self.signal_schema_version,
            "pack_id": self.pack_id,
            "pack_kind": self.pack_kind,
            "title": self.title,
            "built_at": self.built_at,
            "refined_by": self.refined_by,
            "notes": self.notes,
            "opportunity_order": self.opportunity_order,
            "cards": {oid: self.cards[oid].to_dict()
                      for oid in self.opportunity_order},
            "advisories": {oid: next(
                a for a in self.advisories
                if a.opportunity_id == oid).to_dict()
                for oid in self.opportunity_order},
            "source_hashes": dict(self.source_hashes),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SignalPack":
        data = dict(raw)
        pack_schema = data.get("pack_schema_version")
        if pack_schema != PACK_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported pack_schema_version {pack_schema!r}; "
                f"this build reads {PACK_SCHEMA_VERSION!r}"
            )
        order = list(data["opportunity_order"])
        cards = {
            oid: StrengthCard.from_dict(data["cards"][oid]) for oid in order
        }
        advisories = [
            AdvisorReport.from_dict(data["advisories"][oid]) for oid in order
        ]
        return cls(
            pack_id=data["pack_id"],
            pack_kind=data["pack_kind"],
            title=data["title"],
            built_at=data["built_at"],
            refined_by=data["refined_by"],
            advisories=advisories,
            cards=cards,
            notes=data.get("notes", ""),
        )

    # ------------------------------------------------------------------
    # Rendering — audience framing.
    # ------------------------------------------------------------------

    def render_report(self) -> str:
        if self.pack_kind == "user":
            return _render_user_report(self)
        return _render_business_report(self)


def _render_user_report(pack: SignalPack) -> str:
    """Plain-language report for a non-technical user."""
    lines = [
        f"SIGNAL PACK — {pack.title} (for you)",
        f"Built {pack.built_at} by {pack.refined_by} · pack {pack.pack_id}",
        f"{len(pack.advisories)} opportunities, strongest first.",
        "",
    ]
    for i, adv in enumerate(pack.advisories, 1):
        card = pack.cards[adv.opportunity_id]
        lines.append(f"{i}. {card.title}")
        lines.append(f"   {card.plain_summary()}")
        actions = _effort_ranked_actions(card)
        if actions:
            first = actions[0]
            lines.append(
                f"   Your first move ({first.effort} effort): "
                f"{first.action} — {first.rationale}"
            )
            for a in actions[1:]:
                lines.append(
                    f"   Also worth doing ({a.effort} effort): {a.action}"
                )
        if card.watch_conditions:
            lines.append("   Watch for:")
            for w in card.watch_conditions:
                lines.append(f"   - {w.condition} → {w.would_change}")
        if card.low_confidence_dimensions:
            names = ", ".join(
                d.name.replace("_", " ")
                for d in card.low_confidence_dimensions
            )
            lines.append(
                f"   Honest note: we're least sure about {names} — "
                "treat those reads as provisional."
            )
        lines.append("")
    lines.append(
        "These are assessed signals with stated reasons — not guarantees. "
        "Low-confidence reads are flagged, never hidden."
    )
    if pack.notes:
        lines.append(f"Pack notes: {pack.notes}")
    return "\n".join(lines)


def _render_business_report(pack: SignalPack) -> str:
    """Market/competitive report for a business reader."""
    lines = [
        f"SIGNAL PACK — {pack.title} (business edition)",
        f"Built {pack.built_at} by {pack.refined_by} · pack {pack.pack_id}",
        f"{len(pack.advisories)} opportunities, ranked strongest first.",
        "",
    ]
    for i, adv in enumerate(pack.advisories, 1):
        card = pack.cards[adv.opportunity_id]
        lines.append(
            f"{i}. {card.title} — combined {adv.combined:.4f} "
            f"({adv.tier}) · strength {card.strength:.0f}/100"
        )
        money = _dim(card, "monetization_path")
        moat = _dim(card, "defensibility")
        timing = _dim(card, "timing_window")
        lines.append(
            f"   MARKET READ — monetization path {money.value:.0f}/100: "
            f"{money.basis}"
        )
        lines.append(
            f"   DEFENSIBILITY / MOAT — {moat.value:.0f}/100: {moat.basis}"
        )
        lines.append(
            f"   COMPETITION GAP — defensibility {moat.value:.0f}/100 "
            f"against a timing window of {timing.value:.0f}/100: "
            f"{timing.basis}"
        )
        if card.risks:
            worst = max(
                card.risks, key=lambda r: (r.severity, r.description))
            lines.append(
                f"   TOP RISK — severity {worst.severity:.0f}/100: "
                f"{worst.description} ({worst.basis})"
            )
        if card.actions:
            lines.append("   RECOMMENDED ACTIONS (analyst-ranked):")
            for j, a in enumerate(card.actions, 1):
                lines.append(
                    f"   {j}. [{a.effort} effort] {a.action} — {a.rationale}"
                )
        if card.watch_conditions:
            lines.append("   WATCH CONDITIONS:")
            for w in card.watch_conditions:
                lines.append(f"   - if {w.condition} → {w.would_change}")
        lines.append(f"   scoring: {adv.math}")
        lines.append(f"   verdict: {adv.verdict} ({adv.verdict_math})")
        lines.append("")
    lines.append(
        "Dimension values are analyst judgments with stated bases and "
        "confidence — see the structured pack data for the full audit trail."
    )
    if pack.notes:
        lines.append(f"Pack notes: {pack.notes}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Builders.
# ---------------------------------------------------------------------------


def build_pack(
    pack_id: str,
    pack_kind: str,
    title: str,
    cards: Sequence[StrengthCard],
    advisories: Sequence[AdvisorReport],
    built_at: str,
    refined_by: str,
    notes: str = "",
) -> SignalPack:
    """Build a signal pack of either kind. Pure and deterministic.

    Advisories are ranked strongest-first (rank_advisories) so the pack
    always opens with the best opportunity.
    """
    if pack_kind not in PACK_KINDS:
        raise ValueError(
            f"pack_kind must be one of {PACK_KINDS}, got {pack_kind!r}"
        )
    ranked = rank_advisories(list(advisories))
    card_map = {c.opportunity_id: c for c in cards}
    if len(card_map) != len(list(cards)):
        raise ValueError("duplicate opportunity in cards")
    return SignalPack(
        pack_id=pack_id,
        pack_kind=pack_kind,
        title=title,
        built_at=built_at,
        refined_by=refined_by,
        advisories=ranked,
        cards=card_map,
        notes=notes,
    )


def build_user_pack(
    pack_id: str,
    title: str,
    cards: Sequence[StrengthCard],
    advisories: Sequence[AdvisorReport],
    built_at: str,
    refined_by: str,
    notes: str = "",
) -> SignalPack:
    """Build the user product: personal opportunity signals, plain language."""
    return build_pack(
        pack_id, "user", title, cards, advisories, built_at, refined_by,
        notes,
    )


def build_business_pack(
    pack_id: str,
    title: str,
    cards: Sequence[StrengthCard],
    advisories: Sequence[AdvisorReport],
    built_at: str,
    refined_by: str,
    notes: str = "",
) -> SignalPack:
    """Build the business product: market/competitive opportunity signals."""
    return build_pack(
        pack_id, "business", title, cards, advisories, built_at, refined_by,
        notes,
    )


# ---------------------------------------------------------------------------
# Entitlement gate — the hookup point, not live money code.
# ---------------------------------------------------------------------------


def entitlement_gate(pack_kind: str) -> Dict[str, Any]:
    """Describe where the pack's paywall hooks in. Descriptive only.

    Packs are products and are never free; the actual key issue/check
    lives in core/levi/demandpulse/entitlements.py and is NOT called here.
    """
    if pack_kind not in PACK_KINDS:
        raise ValueError(
            f"pack_kind must be one of {PACK_KINDS}, got {pack_kind!r}"
        )
    return {
        "product": f"demandpulse-signal-pack-{pack_kind}",
        "rule": "packs are never free — access requires an issued "
                "entitlement key",
        "store_module": "core/levi/demandpulse/entitlements.py",
        "issue_key": "entitlements.issue(email, months, ...)",
        "validate_key": "entitlements.validate_key_format(key)",
        "status": "gate point only — no charging, no payment wiring, "
                  "no live checks in this module",
    }


def requires_entitlement(pack: SignalPack) -> bool:
    """Every pack requires an entitlement. Always True — the gate is real,
    the check itself happens at the entitlement store, not here."""
    if not isinstance(pack, SignalPack):
        raise ValueError(
            f"pack must be a SignalPack, got {type(pack).__name__}"
        )
    return True
