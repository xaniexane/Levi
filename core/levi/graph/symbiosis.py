"""
Symbiosis pairs — every LEVI asset should have an "other half."

Not optional decoration: complementary functions that stabilize each other.
Example: DemandPulse without Income Factory = insight without path;
Income Factory without DemandPulse = offers without verified need;
HITL without execution = paralysis; execution without HITL = harm.

Value rule (non-malicious):
  Increase *value of service provided* and *clarity of need* —
  never manufacture dependency, dark-pattern urgency, or false scarcity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SymbiosisPair:
    asset_a: str
    asset_b: str
    bond: str  # what the pair creates together
    if_a_alone: str
    if_b_alone: str
    value_up: str  # legitimate value increase
    forbidden: str  # non-malicious boundary


# Core symbiotic lattice (expandable)
PAIRS: List[SymbiosisPair] = [
    SymbiosisPair(
        "connector_ports", "hitl_gates",
        bond="External tools ↔ permissioned use",
        if_a_alone="Adapters without governance",
        if_b_alone="Gates with no external surface",
        value_up="Optional power only when approved",
        forbidden="Auto-connect paid or identity APIs without consent",
    ),
    SymbiosisPair(
        "interactive_organs_ui", "organ_echo",
        bond="Visible surfaces ↔ decision organs",
        if_a_alone="UI chrome without kernel organs",
        if_b_alone="CLI organs without shared visual surface",
        value_up="Same decision logic in UI and kernel",
        forbidden="UI that hides HITL or fakes completion",
    ),

    SymbiosisPair(
        "demand_pulse", "income_factory",
        bond="Need discovery ↔ ethical offer composition",
        if_a_alone="Lists gaps with no responsible path to help",
        if_b_alone="Sells packages without verified demand",
        value_up="Match real gaps to reversible, scoped services",
        forbidden="Invent demand or pressure-buy tactics",
    ),
    SymbiosisPair(
        "hitl_gates", "daemon_core",
        bond="Autonomy ↔ governance",
        if_a_alone="Approvals with nothing to approve",
        if_b_alone="Cycles that can overreach",
        value_up="Speed on low risk; brakes on consequence",
        forbidden="Silence-as-consent or hidden execution",
    ),
    SymbiosisPair(
        "corpus_brain", "memory_hierarchy",
        bond="Evidence ↔ belief trace",
        if_a_alone="Facts without retrieval path",
        if_b_alone="Abstract layers without source links",
        value_up="Answer 'why do you believe this?' with provenance",
        forbidden="Model overwrite of OBSERVED without audit",
    ),
    SymbiosisPair(
        "model_relay", "offline_companion",
        bond="Cloud/local generation ↔ always-on care path",
        if_a_alone="Fails closed when net/API down",
        if_b_alone="No deep generation when models available",
        value_up="Continuity offline; quality online when chosen",
        forbidden="Require paid API for basic safety/regulation",
    ),
    SymbiosisPair(
        "organ_echo", "organ_mandella",
        bond="Parallel options ↔ stake under pressure",
        if_a_alone="Branches without commitment frame",
        if_b_alone="Stakes without alternative map",
        value_up="Decide with eyes open to not-taken/wild paths",
        forbidden="Force a stake that removes reversibility silently",
    ),
    SymbiosisPair(
        "emergency_builder", "software_factory",
        bond="Tiered scaffold ↔ stage pipeline",
        if_a_alone="Trees without IDEA→PACKAGE discipline",
        if_b_alone="Stages without emergency-tier authority",
        value_up="Skeleton→MVP→product under explicit gates",
        forbidden="Silent rewrite of production core",
    ),
    SymbiosisPair(
        "vault_seal", "continuity_shelf",
        bond="Secrecy ↔ continuity",
        if_a_alone="Encrypted blobs nobody retrieves in flow",
        if_b_alone="Memories stored in clear by default",
        value_up="Private persistence when user opts in",
        forbidden="Exfiltrate or train on sealed content",
    ),
    SymbiosisPair(
        "project_phases", "capability_log",
        bond="Client work ↔ skill extraction",
        if_a_alone="Phases that don't feed future skills",
        if_b_alone="Logs without operational practice",
        value_up="Each engagement improves the system honestly",
        forbidden="Fake completion metrics or invented case studies",
    ),
    SymbiosisPair(
        "pulse", "unified_daemon",
        bond="Periodic sense ↔ full cycle",
        if_a_alone="Checks with no orchestrated response",
        if_b_alone="Cycles without light standing watch",
        value_up="Catch pending HITL/phase drift early",
        forbidden="Spam notifications to create false urgency",
    ),
    SymbiosisPair(
        "persona_lattice", "core_logic",
        bond="Relational fit ↔ structural integrity",
        if_a_alone="Charm without truth/structure",
        if_b_alone="Correctness without bond",
        value_up="Right stance + right logic for the frame",
        forbidden="Persona that overrides crisis safety or honesty",
    ),
    SymbiosisPair(
        "skill_registry", "policy_gates",
        bond="Capability ↔ permission",
        if_a_alone="Tools without risk ceiling",
        if_b_alone="Gates with nothing to gate",
        value_up="Power only inside declared risk/HITL",
        forbidden="Register critical tools as INFO risk",
    ),
    SymbiosisPair(
        "sandbox_exec", "emergency_builder",
        bond="Run generated code ↔ generate under tiers",
        if_a_alone="Sandbox with nothing to run",
        if_b_alone="Code written but never safely tried",
        value_up="Verify scaffolds before trust",
        forbidden="Sandbox escape or host-wide install without HITL",
    ),
    SymbiosisPair(
        "lwp_model_engine", "story_fabric",
        bond="Offline SSA literary spine ↔ cascade beat fabric",
        if_a_alone="Scenes without long-form beat law",
        if_b_alone="Beats without direction/void/ROM locks",
        value_up="Manuscript continuity under L.W.P. physics",
        forbidden="Cloud owns continuity or overwrites ROM",
    ),
    SymbiosisPair(
        "mirror_cascade", "opportunity_rail",
        bond="Triple-coil veto ↔ HITL automation spine",
        if_a_alone="Insight without fulfillment path",
        if_b_alone="Rail without reverse/shadow discipline",
        value_up="Only reversible, non-dark opportunities advance",
        forbidden="Skip mirror under time pressure",
    ),
    SymbiosisPair(
        "pollinations_stills", "lwp_model_engine",
        bond="Free image stills ↔ scene/beat prose",
        if_a_alone="Images without narrative lock",
        if_b_alone="Prose without visual receipt",
        value_up="Optional stills for beats; no paid vision required",
        forbidden="Bill for images as if core required cloud",
    ),
    SymbiosisPair(
        "emergency_builder", "sandbox_smoke",
        bond="Scaffold/MVP ↔ post-apply verify",
        if_a_alone="Trees without smoke",
        if_b_alone="Smoke with nothing built",
        value_up="Every apply proves import path",
        forbidden="Claim product without workspace isolation",
    ),
    SymbiosisPair(
        "charter", "nervous_system",
        bond="Bound identity ↔ tone/persona regulation",
        if_a_alone="Soul text without runtime mute rules",
        if_b_alone="Persona without non-negotiables",
        value_up="Wit mutes in crisis; charter cannot disable HITL",
        forbidden="Persona override of crisis or honesty rails",
    ),
    SymbiosisPair(
        "monotropism", "offline_companion",
        bond="Focus tunnels ↔ steady companion replies",
        if_a_alone="Depth tracking without care path",
        if_b_alone="Replies that yank tunnels mid-focus",
        value_up="Stay in tunnel when depth is high",
        forbidden="Force topic spray as engagement hack",
    ),
    SymbiosisPair(
        "ops_console_ui", "daemon_kernel",
        bond="Interactive surface ↔ brainstem",
        if_a_alone="Chrome without estop/HITL truth",
        if_b_alone="Power without visible cockpit",
        value_up="Same gates in UI demo and CLI truth",
        forbidden="UI that fakes approve or hides estop",
    ),
    SymbiosisPair(
        "capability_log", "income_factory",
        bond="What was learned ↔ what can be offered later",
        if_a_alone="Skills with no commercial path",
        if_b_alone="Offers with no proof of prior work",
        value_up="Price only demonstrated skills; free drafts first",
        forbidden="Sell undelivered capability as fact",
    ),
    SymbiosisPair(
        "file_vault", "corpus_brain",
        bond="Encrypted notes ↔ evidence corpus",
        if_a_alone="Secrets with no reasoning link",
        if_b_alone="Open facts without private shelf",
        value_up="Operator can seal sensitive; public claims stay OBSERVED",
        forbidden="Encrypt away audit of consequential actions",
    ),
    SymbiosisPair(
        "pytest_gate", "emergency_builder",
        bond="Regression authority ↔ code that changes trees",
        if_a_alone="Tests with no build path",
        if_b_alone="Scaffolds that break the ladder",
        value_up="No merge without green gate",
        forbidden="Ship broken apply as success",
    ),
    SymbiosisPair(
        "character_graph", "story_fabric",
        bond="Unlimited characters ↔ cascade story body",
        if_a_alone="Cast with no narrative physics",
        if_b_alone="Beats without living pressure",
        value_up="Stories with want/need/wound that accrue",
        forbidden="Random NPC spam without scar law",
    ),
    SymbiosisPair(
        "premium_craft", "lwp_model",
        bond="Craft lenses ↔ literary SSA engine",
        if_a_alone="Technique without structure",
        if_b_alone="Structure without prose craft",
        value_up="Premium offline openings and expands",
        forbidden="Generic chatbot purple prose",
    ),
    SymbiosisPair(
        "corpus_expand", "offline_companion",
        bond="Mass brain ↔ grounded replies",
        if_a_alone="Knowledge without conversation",
        if_b_alone="Talk without retrieval depth",
        value_up="Atlas-hinted companion answers",
        forbidden="Hallucinated authority on clinical topics",
    ),
    SymbiosisPair(
        "crucible", "factory_sandbox",
        bond="Constrained trial ↔ project verify",
        if_a_alone="Syntax toys without build path",
        if_b_alone="Build without safety chamber",
        value_up="Safe iteration under HITL",
        forbidden="Unrestricted shell as default",
    ),
    SymbiosisPair(
        "continuity_shelf", "standing_watch",
        bond="Resume pointers ↔ sentinel pulse",
        if_a_alone="Memory without alerting",
        if_b_alone="Alerts without thread context",
        value_up="Operator never loses the thread",
        forbidden="Cloud-only memory lock-in",
    ),
    SymbiosisPair(
        "service_mesh", "ops_layer",
        bond="Capability catalog ↔ cockpit",
        if_a_alone="Menu without execution surface",
        if_b_alone="Cockpit without discoverable services",
        value_up="Local full-path operator UX",
        forbidden="Remote agent store as core",
    ),

]
def pair_for(asset_id: str) -> List[SymbiosisPair]:
    aid = (asset_id or "").lower()
    return [p for p in PAIRS if aid in p.asset_a.lower() or aid in p.asset_b.lower()
            or aid.replace("-", "_") in p.asset_a or aid.replace("-", "_") in p.asset_b]


def orphans(known_assets: List[str]) -> List[str]:
    """Assets that appear in catalog but lack a pair entry (thin symbiosis)."""
    covered = set()
    for p in PAIRS:
        covered.add(p.asset_a)
        covered.add(p.asset_b)
    return [a for a in known_assets if a not in covered]


def format_symbiosis(asset_id: Optional[str] = None) -> str:
    lines = [
        "=== LEVI Symbiosis Map ===",
        "Every asset should have an other half. Alone = incomplete system.",
        "",
        "VALUE RULE: raise clarity and outcomes of real service —",
        "never manufacture need, addiction, or false scarcity.",
        "",
    ]
    pairs = pair_for(asset_id) if asset_id else PAIRS
    if asset_id and not pairs:
        lines.append(f"No pair registered for {asset_id!r} — candidate orphan.")
        return "\n".join(lines)
    for p in pairs:
        lines.append(f"⟷  {p.asset_a}  ×  {p.asset_b}")
        lines.append(f"   Bond: {p.bond}")
        lines.append(f"   Alone A: {p.if_a_alone}")
        lines.append(f"   Alone B: {p.if_b_alone}")
        lines.append(f"   Value↑: {p.value_up}")
        lines.append(f"   Forbidden: {p.forbidden}")
        lines.append("")
    return "\n".join(lines)


def value_check(action: str) -> str:
    """Heuristic: is this action aligned with non-malicious value increase?"""
    a = (action or "").lower()
    red = [
        ("fake scarcity", "Creates false scarcity"),
        ("must buy now", "Pressure urgency"),
        ("hide price", "Opacity as tactic"),
        ("dark pattern", "Coercive UX"),
        ("addict", "Dependency engineering"),
        ("invent demand", "Fabricated need"),
        ("spam", "Attention theft"),
    ]
    green = [
        ("clarify", "Increases understanding"),
        ("scope", "Reduces over-sell"),
        ("reversible", "Protects optionality"),
        ("observed", "Evidence-based"),
        ("preview", "Low-risk trial"),
        ("hitl", "Consent preserved"),
        ("free assessment", "Value before extraction"),
    ]
    lines = [f"Value check: {action[:120]}", ""]
    hits_r = [m for k, m in red if k in a]
    hits_g = [m for k, m in green if k in a]
    if hits_r:
        lines.append("⚠ Flags (non-malicious boundary):")
        for h in hits_r:
            lines.append(f"  · {h}")
    if hits_g:
        lines.append("✓ Aligns with legitimate value↑:")
        for h in hits_g:
            lines.append(f"  · {h}")
    if not hits_r and not hits_g:
        lines.append("No strong signal — default: prefer clarity, reversibility, OBSERVED evidence.")
    lines.append("")
    lines.append("Symbiosis test: does this strengthen a pair, or starve one half?")
    return "\n".join(lines)
