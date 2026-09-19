"""Genesis odd-law set assembler.

Keeper's canon (2026-09-18, his words): "Nod odd number sets — odd
counts of agents put in Genesis."

The odd law: every Genesis package holds an ODD count of agents — 1,
3, 5, 7, 9 … never even. The pattern, not the textbook: odd counts
can't deadlock — counsel deliberation and twin-merge always resolve by
majority.

Counts are over AGENTS (the 471 in ``levi.agent``'s registry). Each
agent brings its twin pair (2 bodies, 2 minds — left and right
hemispheres); the count is over agents, not bodies.

This module is the *set* assembler: it draws odd-count enterprise
agent sets and mints Genesis package descriptors. It is distinct from
:mod:`levi.genesis.assemble`, which forges packs of *remixed variants*
— never the raw originals. An odd-law Genesis package ships real
agents (white-labeled), not remixes.

Selection is deterministic and auditable: no outside randomness
services — a ``hashlib``-seeded ``random.Random`` draws from the
enterprise pool. Only enterprise-grade agents ship: the agent must be
``enterprise`` in the agent registry AND ``enterprise`` in its grade
manifest AND carry a banked genesis descriptor. The single
intake-capped row can never ship.

Editions intersection (reported, not rewritten): the 11 sector
editions in :mod:`levi.editions.catalog` hold 42 roster slots, 16 of
which draw even counts (``count=2``). Those slots predate the odd law
and the agent-twin canon — they describe edition *rosters*, not Genesis
packages. A Genesis package assembled for a sector edition must still
resolve to an odd agent total; the editions themselves are left as
authored per the keeper's standing rule against unilateral rewrites.

Stdlib only. Dynasty eyes-only.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ASSEMBLER_VERSION = "1.0.0"
FORM_NAME = "genesis.odd_sets"

ENTERPRISE = "enterprise"

# Canonical class -> counsel mapping. Authority is levi.ci.mapping
# (class_for_minion); this mirrors it so the module stays stdlib-only
# and import-light. verify_genesis_package re-checks every agent
# against it.
CLASS_COUNSEL = {
    "AI": "AICI",
    "SI": "SICI",
    "XI": "XICI",
}

# Remainder distribution for class balancing: classes are filled base
# each, then leftover seats go to the largest enterprise pools first
# (ties broken alphabetically). Deterministic and documented.
def _class_priority(pool_sizes: Dict[str, int]) -> List[str]:
    return sorted(pool_sizes, key=lambda c: (-pool_sizes[c], c))


# The one row that can never ship: truncated verbatim intake row,
# capped at intake by schema-fidelity law.
INTAKE_CAPPED_ID = "productivity-calendar-conflict-03"

# White-label law: the customer's name on the package, never LEVI
# branding on the customer-facing surface. Internal provenance fields
# (module paths, lineage) are not customer-facing and are exempt.
_BRAND_TOKEN = "LEVI"

EDITION_INTERSECTION_NOTE = (
    "The 11 sector editions (levi.editions.catalog) hold 42 roster "
    "slots; 16 draw even counts (count=2). Those slots predate the odd "
    "law and describe edition rosters, not Genesis packages. Genesis "
    "packages follow the odd law; the editions were not rewritten."
)


class GenesisOddLawError(ValueError):
    """Fail-closed: any odd-law violation raises, never warns-and-continues."""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    # core/levi/genesis/odd_sets.py -> parents[3] is the repo root.
    return Path(__file__).resolve().parents[3]


def default_registry_path() -> Path:
    return _repo_root() / "core" / "levi" / "agent" / "agent_data" / "agent_registry.json"


def default_grade_dir() -> Path:
    return _repo_root() / "core" / "levi" / "automation" / "grade_data"


def load_agent_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the 471-agent twin registry as data."""
    p = Path(path) if path else default_registry_path()
    if not p.is_file():
        raise GenesisOddLawError("agent registry not found: %s" % p)
    return json.loads(p.read_text(encoding="utf-8"))


def load_grade_index(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Index grade records by minion id across all grade manifests.

    Skips the ci_class_map.json sidecar (not a grade manifest).
    Value per id: grade, batch, signature_id, graded_at, genesis dict,
    and the white_label display name.
    """
    d = Path(path) if path else default_grade_dir()
    if not d.is_dir():
        raise GenesisOddLawError("grade data dir not found: %s" % d)
    index: Dict[str, Dict[str, Any]] = {}
    for f in sorted(d.glob("*.json")):
        if f.name == "ci_class_map.json":
            continue
        manifest = json.loads(f.read_text(encoding="utf-8"))
        for record in manifest.get("records", []):
            mid = record.get("minion_id")
            if not mid:
                continue
            genesis = record.get("genesis") or {}
            index[mid] = {
                "grade": record.get("grade"),
                "batch": manifest.get("batch"),
                "signature_id": manifest.get("signature_id"),
                "graded_at": manifest.get("graded_at"),
                "genesis": genesis,
                "white_label": genesis.get("white_label", ""),
            }
    return index


def enterprise_pool(
    registry: Optional[Dict[str, Any]] = None,
    grade_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """The shippable pool: enterprise in the registry AND the manifest.

    Fail-closed on three gates per agent: registry grade, manifest
    grade, and a banked (non-empty) genesis descriptor. The
    intake-capped row fails all three and can never ship.
    """
    registry = registry if registry is not None else load_agent_registry()
    grade_index = grade_index if grade_index is not None else load_grade_index()
    pool = []
    for agent in registry.get("agents", []):
        aid = agent.get("agent_id")
        if agent.get("grade") != ENTERPRISE:
            continue
        graded = grade_index.get(aid)
        if not graded or graded.get("grade") != ENTERPRISE:
            continue
        if not graded.get("genesis"):
            continue
        pool.append(agent)
    return pool


# ---------------------------------------------------------------------------
# Odd-law validation (fail-closed)
# ---------------------------------------------------------------------------

def check_count(count: Any) -> int:
    """Validate the requested agent count. Returns it, or raises."""
    if isinstance(count, bool) or not isinstance(count, int):
        raise GenesisOddLawError(
            "Genesis count must be an integer, got %r" % (count,)
        )
    if count <= 0:
        raise GenesisOddLawError(
            "Genesis count must be positive, got %d" % count
        )
    if count % 2 == 0:
        raise GenesisOddLawError(
            "Genesis count must be ODD (1, 3, 5, 7, 9 …), got %d — "
            "even counts deadlock counsel deliberation" % count
        )
    return count


def check_white_label(customer_name: str, package_name: str) -> List[str]:
    """White-label law on the customer-facing surface. Returns problems."""
    problems = []
    if not customer_name or not customer_name.strip():
        problems.append("customer name is required for a white-labeled package")
        return problems
    if customer_name.strip() not in package_name:
        problems.append(
            "package name %r does not carry the customer name %r"
            % (package_name, customer_name)
        )
    for field, value in (("package_name", package_name),
                         ("customer_name", customer_name)):
        if _BRAND_TOKEN in value.upper():
            # Case-insensitive token hunt on the display surface only.
            problems.append(
                "%s carries LEVI branding — Genesis packages are white-labeled"
                % field
            )
    return problems


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def plan_class_counts(count: int, pool_by_class: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
    """Spread `count` seats across AI/SI/XI as evenly as possible.

    Each class gets count // 3; the remainder goes to the largest
    enterprise pools first (ties alphabetical). Fail-closed if a class
    cannot fill its seats.
    """
    check_count(count)
    classes = [c for c in ("AI", "SI", "XI") if c in pool_by_class]
    if not classes:
        raise GenesisOddLawError("no class pools available")
    base, remainder = divmod(count, len(classes))
    plan = {c: base for c in classes}
    for c in _class_priority({c: len(pool_by_class[c]) for c in classes})[:remainder]:
        plan[c] += 1
    for c, n in plan.items():
        if n > len(pool_by_class[c]):
            raise GenesisOddLawError(
                "class %s pool too small: need %d, have %d"
                % (c, n, len(pool_by_class[c]))
            )
    return plan


def _draw_seed(customer_name: str, sector: str, tier: str, count: int,
               seed: Optional[str]) -> str:
    raw = "%s|%s|%s|%d|%s" % (
        customer_name.strip(), sector.strip(), tier.strip(), count, seed or "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _draw_agents(count: int, pool: List[Dict[str, Any]], seed_hex: str) -> List[Dict[str, Any]]:
    if count > len(pool):
        raise GenesisOddLawError(
            "Genesis count %d exceeds the enterprise pool (%d shippable agents)"
            % (count, len(pool))
        )
    pool_by_class: Dict[str, List[Dict[str, Any]]] = {}
    for agent in pool:
        pool_by_class.setdefault(agent.get("class_tag", "?"), []).append(agent)
    plan = plan_class_counts(count, pool_by_class)
    rng = random.Random(int(seed_hex, 16))
    chosen: List[Dict[str, Any]] = []
    for class_tag in ("AI", "SI", "XI"):
        n = plan.get(class_tag, 0)
        if not n:
            continue
        ids = sorted(a["agent_id"] for a in pool_by_class[class_tag])
        rng.shuffle(ids)
        by_id = {a["agent_id"]: a for a in pool_by_class[class_tag]}
        chosen.extend(by_id[i] for i in ids[:n])
    # Stable output order: sorted by agent id.
    chosen.sort(key=lambda a: a["agent_id"])
    return chosen


def _grade_proof(agent_id: str, grade_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    graded = grade_index[agent_id]
    return {
        "grade": graded["grade"],
        "manifest_batch": graded["batch"],
        "signature_id": graded["signature_id"],
        "graded_at": graded["graded_at"],
    }


def _agent_entry(agent: Dict[str, Any], grade_index: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    aid = agent["agent_id"]
    graded = grade_index[aid]
    genesis = graded["genesis"]
    left = agent.get("left", {}) or {}
    right = agent.get("right", {}) or {}
    return {
        "agent_id": aid,
        "minion_id": agent.get("minion_id", aid),
        "white_label": graded["white_label"],
        "class_tag": agent.get("class_tag"),
        "counsel": agent.get("counsel_name"),
        "grade": agent.get("grade"),
        "grade_proof": _grade_proof(aid, grade_index),
        "twin_pair": {
            "pair_id": agent.get("pair_id"),
            "left": {
                "hemisphere_id": left.get("hemisphere_id"),
                "twin_id": left.get("twin_id"),
                "role": left.get("role"),
            },
            "right": {
                "hemisphere_id": right.get("hemisphere_id"),
                "twin_id": right.get("twin_id"),
                "role": right.get("role"),
            },
        },
        # Banked genesis descriptor, referenced — history not rewritten.
        "genesis_descriptor": dict(genesis),
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_genesis_set(
    count: int,
    *,
    customer_name: str,
    sector: str = "general",
    tier: str = "genesis",
    agent_ids: Optional[List[str]] = None,
    seed: Optional[str] = None,
    registry: Optional[Dict[str, Any]] = None,
    grade_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Assemble a Genesis package: an odd-count set of enterprise agents.

    `agent_ids` (optional) selects the set explicitly — it must still be
    odd-length, all enterprise, and duplicate-free. Otherwise the set is
    drawn deterministically from the enterprise pool, class-balanced
    across AI/SI/XI.

    Returns the Genesis package descriptor (data only — no pricing, no
    payment, no fulfillment wired). Fail-closed: any violation raises
    GenesisOddLawError.
    """
    count = check_count(count)
    registry = registry if registry is not None else load_agent_registry()
    grade_index = grade_index if grade_index is not None else load_grade_index()
    pool = enterprise_pool(registry, grade_index)
    by_id = {a["agent_id"]: a for a in pool}

    if agent_ids is not None:
        if len(agent_ids) != count:
            raise GenesisOddLawError(
                "explicit agent_ids length %d != odd count %d"
                % (len(agent_ids), count)
            )
        if len(set(agent_ids)) != len(agent_ids):
            dupes = sorted({i for i in agent_ids if agent_ids.count(i) > 1})
            raise GenesisOddLawError(
                "duplicate agents refused: %s" % ", ".join(dupes)
            )
        missing = [i for i in agent_ids if i not in by_id]
        if missing:
            raise GenesisOddLawError(
                "agents refused (not enterprise-grade or unknown): %s"
                % ", ".join(missing)
            )
        chosen = [by_id[i] for i in sorted(agent_ids)]
        method = "explicit selection"
        class_plan = {a["class_tag"]: 0 for a in chosen}
        for a in chosen:
            class_plan[a["class_tag"]] = class_plan.get(a["class_tag"], 0) + 1
    else:
        seed_hex = _draw_seed(customer_name, sector, tier, count, seed)
        chosen = _draw_agents(count, pool, seed_hex)
        method = "deterministic seeded draw"
        pool_by_class: Dict[str, List[Dict[str, Any]]] = {}
        for a in pool:
            pool_by_class.setdefault(a.get("class_tag", "?"), []).append(a)
        class_plan = plan_class_counts(count, pool_by_class)

    seed_hex = _draw_seed(customer_name, sector, tier, count, seed)
    package_name = "%s Genesis %d" % (customer_name.strip(), count)
    wl_problems = check_white_label(customer_name, package_name)
    if wl_problems:
        raise GenesisOddLawError("; ".join(wl_problems))

    agent_entries = [_agent_entry(a, grade_index) for a in chosen]
    counsel_map: Dict[str, List[str]] = {}
    for entry in agent_entries:
        counsel_map.setdefault(entry["counsel"], []).append(entry["agent_id"])

    canonical_inputs = {
        "customer_name": customer_name.strip(),
        "sector": sector.strip(),
        "tier": tier.strip(),
        "count": count,
        "agent_ids": sorted(e["agent_id"] for e in agent_entries),
        "seed_hex": seed_hex,
        "method": method,
    }
    package_id = "genesis-odd-%s" % hashlib.sha256(
        json.dumps(canonical_inputs, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]

    package = {
        "form": FORM_NAME,
        "assembler": "levi.genesis.odd_sets v%s" % ASSEMBLER_VERSION,
        "package_id": package_id,
        "odd_law": {
            "law": "odd counts of agents in Genesis — 1, 3, 5, 7, 9 … never even",
            "count": count,
            "rationale": (
                "odd counts can't deadlock — counsel deliberation and "
                "twin-merge always resolve by majority"
            ),
        },
        "customer": {
            "name": customer_name.strip(),
            "sector": sector.strip(),
            "tier": tier.strip(),
            "package_name": package_name,
            "white_labeled": True,
        },
        "agents": agent_entries,
        "counsel_map": counsel_map,
        "selection": {
            "method": method,
            "seed_hex": seed_hex,
            "class_plan": class_plan,
            "pool_size": len(pool),
        },
        "packaging": {
            "model": "lifetime one-copy buy",
            "note": (
                "lifetime one-copy buy; white-labeled per business "
                "(%s); specialized packs as add-ons" % customer_name.strip()
            ),
            "status": "descriptor only — no pricing, payment, or fulfillment wired",
            "money_seam": (
                "paper only — see levi.genesis.money for paper quotes; "
                "no payment rail wired without the keeper's explicit order"
            ),
        },
        "inputs": canonical_inputs,
    }

    # Defense in depth: the assembled package must verify before it ships.
    verdict = verify_genesis_package(package, registry=registry, grade_index=grade_index)
    if not verdict["ok"]:
        raise GenesisOddLawError(
            "assembled package failed verification: %s" % "; ".join(verdict["problems"])
        )
    return package


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_genesis_package(
    package: Dict[str, Any],
    *,
    registry: Optional[Dict[str, Any]] = None,
    grade_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Re-check a Genesis package descriptor against the odd law.

    Returns {"ok": bool, "problems": [...]}. Never raises on a bad
    package — it reports.
    """
    problems: List[str] = []
    try:
        registry = registry if registry is not None else load_agent_registry()
        grade_index = grade_index if grade_index is not None else load_grade_index()
    except GenesisOddLawError as exc:
        return {"ok": False, "problems": ["loader: %s" % exc]}

    agents = package.get("agents") or []
    count = package.get("odd_law", {}).get("count", len(agents))

    # 1. The odd law itself.
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        problems.append("count is not a positive integer: %r" % (count,))
    elif count % 2 == 0:
        problems.append("even count %d refused — Genesis takes odd counts only" % count)
    if count != len(agents):
        problems.append(
            "declared count %s != agent entries %d" % (count, len(agents)))

    # 2. No duplicates.
    ids = [a.get("agent_id") for a in agents]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        problems.append("duplicate agents: %s" % ", ".join(dupes))

    # 3. Enterprise gates + grade proofs, per agent.
    reg_by_id = {a.get("agent_id"): a for a in registry.get("agents", [])}
    for entry in agents:
        aid = entry.get("agent_id")
        reg = reg_by_id.get(aid)
        if reg is None:
            problems.append("%s: not in the agent registry" % aid)
            continue
        if reg.get("grade") != ENTERPRISE:
            problems.append("%s: registry grade %r is not enterprise — refused"
                            % (aid, reg.get("grade")))
        graded = grade_index.get(aid)
        if not graded or graded.get("grade") != ENTERPRISE:
            problems.append("%s: no enterprise grade manifest — refused" % aid)
            continue
        proof = entry.get("grade_proof") or {}
        for field in ("manifest_batch", "signature_id"):
            if proof.get(field) != graded.get("batch" if field == "manifest_batch" else "signature_id"):
                problems.append(
                    "%s: grade proof %s mismatch (package %r vs manifest %r)"
                    % (aid, field, proof.get(field),
                       graded.get("batch" if field == "manifest_batch" else "signature_id")))
        if not entry.get("genesis_descriptor"):
            problems.append("%s: missing banked genesis descriptor" % aid)
        # 4. Counsel mapping consistency.
        expected = CLASS_COUNSEL.get(reg.get("class_tag"))
        if entry.get("counsel") != expected or reg.get("counsel_name") != expected:
            problems.append(
                "%s: counsel %r != expected %r for class %r"
                % (aid, entry.get("counsel"), expected, reg.get("class_tag")))
        # 5. Twin pair present.
        pair = entry.get("twin_pair") or {}
        if not pair.get("pair_id"):
            problems.append("%s: twin pair_id missing" % aid)

    # 6. The intake-capped row can never ship.
    if INTAKE_CAPPED_ID in ids:
        problems.append(
            "%s: intake-capped row — refused by schema-fidelity law" % INTAKE_CAPPED_ID)

    # 7. White-label law on the display surface.
    customer = package.get("customer") or {}
    problems.extend(
        check_white_label(customer.get("name", ""), customer.get("package_name", "")))

    # 8. Package id recomputes from canonical inputs.
    inputs = package.get("inputs")
    if not inputs:
        problems.append("canonical inputs missing — package id unverifiable")
    else:
        recomputed = "genesis-odd-%s" % hashlib.sha256(
            json.dumps(inputs, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        if recomputed != package.get("package_id"):
            problems.append(
                "package_id mismatch: recomputed %s != %s"
                % (recomputed, package.get("package_id")))

    return {"ok": not problems, "problems": problems}


def package_summary(package: Dict[str, Any]) -> str:
    """One-screen human summary of a Genesis package."""
    customer = package.get("customer", {})
    lines = [
        "Genesis package %s" % package.get("package_id"),
        "  customer : %s (%s / %s)" % (
            customer.get("name"), customer.get("sector"), customer.get("tier")),
        "  agents   : %d (odd law holds)" % package.get("odd_law", {}).get("count"),
        "  counsels : %s" % ", ".join(
            "%s×%d" % (c, len(v)) for c, v in sorted(package.get("counsel_map", {}).items())),
    ]
    for entry in package.get("agents", []):
        pair = entry.get("twin_pair", {})
        lines.append("  - %s [%s → %s] pair %s — %s" % (
            entry["agent_id"], entry["class_tag"], entry["counsel"],
            pair.get("pair_id"), entry.get("white_label") or "unnamed"))
    lines.append("  packaging: %s" % package.get("packaging", {}).get("note"))
    lines.append("  money    : %s" % package.get("packaging", {}).get("status"))
    return "\n".join(lines)
