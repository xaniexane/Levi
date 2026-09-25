"""Editions re-forged onto the new canon.

``catalog.py``'s 11 EditionManifests stay authored exactly as they are —
the keeper's sector intent is not rewritten. This module is the re-forge
layer that adapts those manifests onto:

- **Agent-twins**: rosters resolve to twin-pair agents from the 471-agent
  registry (AI 220 / SI 120 / XI 130 / intake 1), each carrying its left
  (sequence/logic/execution) and right (pattern/variation/intuition)
  hemispheres. Twin law: the +1 intake-capped row can NEVER ship.
- **The genesis odd law** (``levi.genesis.odd_sets``): an edition's roster
  resolves to an ODD agent total. Editions that authored an even total
  gain exactly one appended *odd-law majority seat* — machinery changed,
  purpose untouched.
- **CI counsels** (``levi.ci.mapping.COUNSEL_FOR_CLASS``): AICI counsels
  AI-class agents, SICI counsels SI-class agents, XICI counsels XI
  nano-bit agents. Every resolved seat maps to its counsel.
- **NFT license descriptors** (``levi.genesis.nft.economics``): each
  edition gets a license-descriptor builder carrying the buyer's business
  name (white-label law), with odd-law enforcement baked in.

The catalog's public names (``EDITIONS``, ``list_editions``,
``get_edition``, ``editions_for_ring``, the 11 manifests) are untouched
and stable. Dynasty eyes-only: this module must not appear in README,
docs/ published copies, web/, artifacts, feed, or your_files/.

Stdlib only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .catalog import EDITIONS, EditionManifest, RosterSlot
from .manifest import Ring

try:
    from levi.ci.mapping import COUNSEL_FOR_CLASS
except Exception:  # pragma: no cover — import-light fallback
    COUNSEL_FOR_CLASS = {"AI": "AICI", "SI": "SICI", "XI": "XICI"}

try:
    from levi.genesis.nft.economics import (
        NftEconomicsError,
        check_white_label,
    )
except Exception:  # pragma: no cover — import-light fallback

    class NftEconomicsError(ValueError):
        """Fail-closed on any economics violation."""

    def check_white_label(buyer_name: str) -> str:
        name = (buyer_name or "").strip()
        if not name:
            raise NftEconomicsError(
                "buyer business name is required (white-label law)"
            )
        if "levi" in name.lower():
            raise NftEconomicsError(
                "buyer name must not carry LEVI branding (white-label law)"
            )
        if len(name) > 120:
            raise NftEconomicsError("buyer name too long (max 120 chars)")
        return name


FORM_NAME = "levi.editions.reforge"
REFORGE_VERSION = "1.0.0"

#: The one intake-capped row that can never ship (schema-fidelity law).
INTAKE_CAPPED_ID = "productivity-calendar-conflict-03"

#: Catalog `side` -> agent `class_tag`. "either" rotates AI/SI/XI.
SIDE_CLASS = {"ai": "AI", "si": "SI", "either": None}

LICENSE_TERMS_VERSION = "genesis-nft-terms-1"


class ReforgeError(ValueError):
    """Fail-closed: any re-forge violation raises, never warns-and-continues."""


# ---------------------------------------------------------------------------
# Odd-law seats
# ---------------------------------------------------------------------------

ODD_LAW_SEAT = RosterSlot(
    "Odd-law majority seat",
    (),
    side="either",
    count=1,
    purpose=(
        "one extra enterprise twin agent so the edition resolves to an odd "
        "agent total per the genesis odd law — counsel deliberation and "
        "twin-merge always resolve by majority. Filled like every other seat."
    ),
)


def forged_slots(manifest: EditionManifest) -> List[RosterSlot]:
    """The manifest's roster as authored, plus the odd-law seat if needed.

    The open-creational edition ships no agents (structure only — the
    mold, not the cast) and is exempt by design: the odd law governs
    Genesis *packages*, and open-creational never becomes one.
    """
    slots = list(manifest.roster)
    if manifest.ring is Ring.OPEN_CREATIONAL:
        return slots
    if sum(s.count for s in slots) % 2 == 0:
        slots.append(ODD_LAW_SEAT)
    return slots


def forged_size(manifest: EditionManifest) -> int:
    return sum(s.count for s in forged_slots(manifest))


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    # core/levi/editions/reforge.py -> parents[3] is the repo root.
    return Path(__file__).resolve().parents[3]


def default_registry_path() -> Path:
    return _repo_root() / "core" / "levi" / "agent" / "agent_data" / "agent_registry.json"


def load_agents(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load the twin-agent registry as working-tree data.

    Enterprise-only? No — callers filter. The intake-capped row rides
    along so the fail-closed check can prove it was refused, not missed.
    """
    p = Path(path) if path else default_registry_path()
    if not p.is_file():
        raise ReforgeError("agent registry not found: %s" % p)
    data = json.loads(p.read_text(encoding="utf-8"))
    return list(data.get("agents", []))


def enterprise_agents(agents: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Only enterprise-grade twin agents — the shippable pool."""
    agents = agents if agents is not None else load_agents()
    return [a for a in agents if a.get("grade") == "enterprise"]


# ---------------------------------------------------------------------------
# Forged resolution: roster slots -> twin-pair agents
# ---------------------------------------------------------------------------

def _class_pools(agents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    pools: Dict[str, List[Dict[str, Any]]] = {"AI": [], "SI": [], "XI": []}
    for a in sorted(agents, key=lambda a: a.get("agent_id", "")):
        cls = a.get("class_tag")
        if cls in pools:
            pools[cls].append(a)
    return pools


def resolve_forged_roster(
    manifest: EditionManifest,
    agents: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Fill the forged roster from enterprise twin agents. Deterministic.

    A slot with side "ai"/"si" draws from that class pool; "either" draws
    in AI/SI/XI rotation so counsels stay balanced. Agents are never
    reused within an edition. Order is stable: slots in manifest order,
    agents sorted by id within each pick.
    """
    pool = enterprise_agents(agents)
    class_pools = _class_pools(pool)
    used: set = set()
    filled: List[Dict[str, Any]] = []

    def take(class_tag: str) -> Optional[Dict[str, Any]]:
        for a in class_pools[class_tag]:
            if a["agent_id"] not in used:
                used.add(a["agent_id"])
                return a
        return None

    rotation = ["AI", "SI", "XI"]
    for slot in forged_slots(manifest):
        side = slot.side
        if side not in SIDE_CLASS:
            raise ReforgeError("bad side on slot: %r" % (side,))
        need = slot.count
        for _ in range(need):
            if side == "either":
                chosen = None
                for _round in range(len(rotation)):
                    cls = rotation[0]
                    rotation = rotation[1:] + rotation[:1]
                    chosen = take(cls)
                    if chosen is not None:
                        break
                if chosen is None:
                    raise ReforgeError(
                        "%s: pool exhausted filling 'either' slot (%s)"
                        % (manifest.id, slot.category)
                    )
            else:
                chosen = take(SIDE_CLASS[side])
                if chosen is None:
                    raise ReforgeError(
                        "%s: %s pool too small for slot %s (wants %d)"
                        % (manifest.id, SIDE_CLASS[side], slot.category, need)
                    )
            filled.append(chosen)
    return filled


def counsel_for(agent: Dict[str, Any]) -> str:
    """The CI counsel that counsels this agent, by its class."""
    class_tag = agent.get("class_tag")
    expected = COUNSEL_FOR_CLASS.get(class_tag)
    if expected is None:
        raise ReforgeError("unknown class %r on agent %r"
                           % (class_tag, agent.get("agent_id")))
    return expected


def slot_counsel(slot: RosterSlot) -> Optional[str]:
    """The counsel a slot's class demands — None when the slot is 'either'."""
    class_tag = SIDE_CLASS.get(slot.side)
    if class_tag is None:
        return None
    return COUNSEL_FOR_CLASS[class_tag]


def counsel_map_for(resolved: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Counsel -> agent ids, as the odd-set assembler banks it."""
    counsel_map: Dict[str, List[str]] = {}
    for agent in resolved:
        counsel_map.setdefault(counsel_for(agent), []).append(agent["agent_id"])
    return counsel_map


# ---------------------------------------------------------------------------
# Verification (fail-closed)
# ---------------------------------------------------------------------------

def verify_forged(
    manifest: EditionManifest,
    resolved: Optional[List[Dict[str, Any]]] = None,
    *,
    agents: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """Re-check a forged edition against the canon. [] means sound."""
    problems: List[str] = []
    resolved = resolved if resolved is not None else resolve_forged_roster(
        manifest, agents=agents)

    # 1. The odd law (open-creational exempt by design — ships nothing).
    total = len(resolved)
    if manifest.ring is not Ring.OPEN_CREATIONAL:
        if total % 2 == 0 or total < 1:
            problems.append(
                "%s: resolved total %d is not odd — genesis odd law" % (manifest.id, total))
    else:
        if total:
            problems.append(
                "%s: open-creational ships no agents, resolved %d" % (manifest.id, total))

    # 2. No duplicates.
    ids = [a.get("agent_id") for a in resolved]
    if len(set(ids)) != len(ids):
        problems.append(
            "%s: duplicate agents: %s" % (
                manifest.id,
                ", ".join(sorted({i for i in ids if ids.count(i) > 1}))))

    # 3. Enterprise-only + the intake-capped row refused.
    if INTAKE_CAPPED_ID in ids:
        problems.append(
            "%s: intake-capped row shipped — refused by schema-fidelity law" % manifest.id)
    for a in resolved:
        if a.get("grade") != "enterprise":
            problems.append(
                "%s: agent %s grade %r is not enterprise — refused"
                % (manifest.id, a.get("agent_id"), a.get("grade")))

    # 4. Counsel mapping: every agent counseled by its class's counsel.
    for a in resolved:
        expected = COUNSEL_FOR_CLASS.get(a.get("class_tag"))
        actual = a.get("counsel_name")
        if actual != expected:
            problems.append(
                "%s: agent %s counsel %r != %r for class %r"
                % (manifest.id, a.get("agent_id"), actual, expected, a.get("class_tag")))

    # 5. Twin pairs present: left/right hemispheres, pair link.
    for a in resolved:
        pair_id = a.get("pair_id")
        left = a.get("left") or {}
        right = a.get("right") or {}
        if not pair_id or not left.get("hemisphere_id") or not right.get("hemisphere_id"):
            problems.append(
                "%s: agent %s missing twin-pair linkage (pair %r)"
                % (manifest.id, a.get("agent_id"), pair_id))
    return problems


def check_slot_counsel_consistency(manifest: EditionManifest,
                                   resolved: List[Dict[str, Any]]) -> List[str]:
    """Every agent's counsel matches the counsel its slot demanded."""
    problems: List[str] = []
    slots = forged_slots(manifest)
    cursor = 0
    for slot in slots:
        demand = slot_counsel(slot)
        for _ in range(slot.count):
            if cursor >= len(resolved):
                problems.append("%s: slot %s overruns resolved roster"
                                % (manifest.id, slot.category))
                break
            a = resolved[cursor]
            cursor += 1
            if demand is not None and a.get("counsel_name") != demand:
                problems.append(
                    "%s: slot %s demands %s, agent %s counseled by %s"
                    % (manifest.id, slot.category, demand,
                       a.get("agent_id"), a.get("counsel_name")))
    return problems


# ---------------------------------------------------------------------------
# NFT license descriptors — white-label buyer naming, odd-law enforced
# ---------------------------------------------------------------------------

def build_edition_license_descriptor(
    manifest: EditionManifest,
    *,
    buyer_business_name: str,
    resolved: Optional[List[Dict[str, Any]]] = None,
    series_year: int = 2026,
    agents: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """One edition's license descriptor, white-labeled for the buyer.

    The descriptor carries the buyer's business name — never LEVI
    branding — and fail-closes on even agent counts (the odd law is
    enforced in the metadata itself, mirroring
    ``levi.genesis.nft.economics.build_token_metadata``).

    This is the *license* layer, pre-pack: it names the edition, the
    buyer, the odd count, the counsel map, and the twin pairs the
    license covers. The chain-issued token (one token, one pack hash)
    still comes from the NFT economics module at mint.
    """
    buyer = check_white_label(buyer_business_name)
    if manifest.ring is Ring.OPEN_CREATIONAL:
        raise ReforgeError(
            "open-creational carries no agents and no licenses — "
            "structure only, the mold not the cast")
    resolved = resolved if resolved is not None else resolve_forged_roster(
        manifest, agents=agents)
    agent_count = len(resolved)
    if agent_count % 2 == 0 or agent_count < 1:
        raise ReforgeError(
            "edition %r: license descriptor refused — agent count %d is not odd "
            "(keeper's odd law)" % (manifest.id, agent_count))

    descriptor_id = "%s:%s" % (manifest.id, buyer.lower().replace(" ", "-"))
    twin_pairs = [
        {
            "agent_id": a.get("agent_id"),
            "white_label": a.get("minion_id", a.get("agent_id")),
            "pair_id": a.get("pair_id"),
            "class_tag": a.get("class_tag"),
            "counsel": a.get("counsel_name"),
            "left": {
                "hemisphere_id": (a.get("left") or {}).get("hemisphere_id"),
                "twin_id": (a.get("left") or {}).get("twin_id"),
            },
            "right": {
                "hemisphere_id": (a.get("right") or {}).get("hemisphere_id"),
                "twin_id": (a.get("right") or {}).get("twin_id"),
            },
        }
        for a in resolved
    ]
    return {
        "form": FORM_NAME,
        "reforge": "levi.editions.reforge v%s" % REFORGE_VERSION,
        "descriptor_id": descriptor_id,
        "edition": {
            "id": manifest.id,
            "name": manifest.name,
            "sector": manifest.sector,
            "ring": manifest.ring.value,
            "tagline": manifest.tagline,
        },
        "buyer_business": buyer,
        "license": {
            "kind": "lifetime one-copy buy",
            "terms": LICENSE_TERMS_VERSION,
            "note": (
                "A scarce lifetime license for the %s edition: %d enterprise "
                "twin agents, white-labeled for %s. Sold as a license, not "
                "an investment: the company promises no profit and no "
                "rising value."
                % (manifest.id, agent_count, buyer)
            ),
        },
        "odd_law": {
            "law": "odd counts of agents in Genesis — 1, 3, 5, 7, 9 … never even",
            "agent_count": agent_count,
            "rationale": (
                "odd counts can't deadlock — counsel deliberation and "
                "twin-merge always resolve by majority"
            ),
        },
        "counsel_map": counsel_map_for(resolved),
        "twin_pairs": twin_pairs,
        "series": "GENESIS-%d" % int(series_year),
        "packaging": {
            "status": "license descriptor only — token mint paper-only, "
                      "no chain deploy, no funds, without the keeper's word",
            "money_seam": "paper only",
        },
    }


def descriptor_for_edition(
    edition_id: str,
    *,
    buyer_business_name: str,
    resolved: Optional[List[Dict[str, Any]]] = None,
    series_year: int = 2026,
    agents: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """License descriptor by edition id — the per-edition entry point."""
    manifest = EDITIONS.get(edition_id)
    if manifest is None:
        raise ReforgeError("unknown edition: %r" % (edition_id,))
    return build_edition_license_descriptor(
        manifest,
        buyer_business_name=buyer_business_name,
        resolved=resolved,
        series_year=series_year,
        agents=agents,
    )


# ---------------------------------------------------------------------------
# Edition-level summary
# ---------------------------------------------------------------------------

def edition_forge_report(
    manifest: EditionManifest,
    agents: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """One forged edition as data: roster, counsels, twin pairs, verdict."""
    resolved = resolve_forged_roster(manifest, agents=agents)
    return {
        "edition_id": manifest.id,
        "edition_name": manifest.name,
        "sector": manifest.sector,
        "ring": manifest.ring.value,
        "authored_slots": len(manifest.roster),
        "forged_slots": len(forged_slots(manifest)),
        "odd_law_seat_added": (
            manifest.ring is not Ring.OPEN_CREATIONAL
            and manifest.roster_size() % 2 == 0
        ),
        "agent_count": len(resolved),
        "odd_law_holds": (
            manifest.ring is Ring.OPEN_CREATIONAL or len(resolved) % 2 == 1
        ),
        "counsel_map": counsel_map_for(resolved) if resolved else {},
        "agent_ids": [a.get("agent_id") for a in resolved],
        "problems": verify_forged(manifest, resolved),
    }
