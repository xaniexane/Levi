"""
Free integration lattice — prehistoric engines × modern local stack × LEVI DNA.

Monetizable later via HITL-scoped services; core stays free-first.
Nothing here requires paid SaaS to boot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class FreeIntegration:
    id: str
    era: str  # prehistoric | modern | levi-unique | hybrid
    name: str
    free_how: str
    combines_with: Tuple[str, ...]
    monetize_later: str
    unreplicable: str


CATALOG: List[FreeIntegration] = [
    FreeIntegration(
        "json_state", "prehistoric", "Flat-file JSON state (~/.levi)",
        "stdlib only",
        ("corpus", "rail", "builder", "lwp_model", "hitl"),
        "Hosted backup / multi-device sync (optional paid)",
        "Operator-owned files; no vendor lock for core truth",
    ),
    FreeIntegration(
        "cli_argparse", "prehistoric", "CLI control plane",
        "stdlib argparse",
        ("ops", "rail", "story", "builder", "serve_ui"),
        "Managed training / white-label CLI packs",
        "Full organism reachable without a web account",
    ),
    FreeIntegration(
        "pytest_gate", "prehistoric", "Test-as-merge-authority",
        "pytest (dev)",
        ("builder", "ci_fast_gate", "ladder"),
        "CI minutes on private runners you own",
        "Ladder+integrate unique to LEVI DNA",
    ),
    FreeIntegration(
        "markdown_export", "prehistoric", "Manuscript / handoff markdown",
        "text files",
        ("lwp_model", "story_fabric", "bible"),
        "Editorial polish service (HITL human)",
        "L.W.P. ROM/void locks travel with export",
    ),
    FreeIntegration(
        "local_http_static", "prehistoric", "Local static UI server",
        "stdlib http.server",
        ("ops_console", "lwp_model_html", "mirror_demo"),
        "Custom themed consoles for clients",
        "Not a multi-tenant agent marketplace UI",
    ),
    FreeIntegration(
        "sqlite_optional", "prehistoric", "Optional SQLite shelf",
        "stdlib sqlite3 when enabled",
        ("corpus", "capability_log", "rail_history"),
        "Analytics dashboard for your own jobs",
        "Default remains JSON; SQL is opt-in depth",
    ),
    FreeIntegration(
        "pollinations", "modern", "Free stills URL generation",
        "image.pollinations.ai (no key required for basic)",
        ("lwp_model", "story_beats", "social_media_mode"),
        "Premium art direction packs under HITL",
        "Stills bound to cascade beats + ROM law",
    ),
    FreeIntegration(
        "ollama_local", "modern", "Local LLM when present",
        "localhost:11434 optional",
        ("model_relay", "offline_companion", "story_enhance"),
        "Hardware consult / model pack guides",
        "Crisis path never requires Ollama or cloud",
    ),
    FreeIntegration(
        "rss_watch", "hybrid", "RSS/Atom opportunity seeds",
        "stdlib urllib + light feed parse",
        ("demand_pulse", "mirror_cascade", "rail"),
        "Curated vertical watch lists as a service",
        "Seeds always Mirror+HITL before offer",
    ),
    FreeIntegration(
        "imap_readonly", "hybrid", "Optional local mail triage drafts",
        "stdlib imaplib when user enables",
        ("hitl", "demand_pulse", "capability_log"),
        "Human-reviewed inbox ops packages",
        "Never auto-send; drafts only until HITL",
    ),
    FreeIntegration(
        "cron_pulse", "prehistoric", "OS cron / Task Scheduler pulse",
        "user crontab calling levi pulse",
        ("ops", "rail_pending", "hitl_list"),
        "Managed pulse hosting on your VPS",
        "Daemon remains local-first; cron is dumb wake",
    ),
    FreeIntegration(
        "git_handoff", "modern", "Private git as continuity shelf",
        "git CLI user-owned",
        ("builder_workspace", "round_log", "license"),
        "Private repo setup / recovery service",
        "Proprietary LICENSE; not open-core bait",
    ),
    FreeIntegration(
        "mirror_cascade", "levi-unique", "Triple-coil reverse cross-check",
        "pure Python",
        ("rail", "demand", "income", "value_check"),
        "Vertical Mirror packs (advisory only)",
        "Forward+reverse+shadow + HITL veto fingerprint",
    ),
    FreeIntegration(
        "opportunity_rail", "levi-unique", "HITL automation spine",
        "pure Python",
        ("mirror", "income", "corpus", "capability_log"),
        "Done-with-you fulfillment (human in loop paid)",
        "Silence≠approve; demand_signal_id symbiosis",
    ),
    FreeIntegration(
        "lwp_ssa", "levi-unique", "L.W.P. Model offline literary SSA",
        "pure Python + static HTML",
        ("story_fabric", "pollinations", "rom", "void_ghost"),
        "Manuscript coaching / genre packs under HITL",
        "Directions+REIM+void+ROM+gold path sealed L.W.P.",
    ),
    FreeIntegration(
        "organism_graph", "levi-unique", "Interpenetration bloodstream",
        "pure Python",
        ("all_organs", "symbiosis_pairs", "integrate_audit"),
        "Custom organ design for client orgs",
        "One organism law — no side-app Factory",
    ),
    FreeIntegration(
        "symbiosis_value", "levi-unique", "Other-half + non-malicious value rules",
        "pure Python",
        ("demand_income", "hitl_daemon", "ui_kernel"),
        "Ethics review as paid second opinion",
        "Forbids manufactured need / fake scarcity",
    ),
    FreeIntegration(
        "charter_bound", "levi-unique", "Bound soul analogue",
        "pure Python",
        ("nervous", "core_logic", "hitl"),
        "Charter workshop for teams",
        "Cannot disable HITL or crisis rails",
    ),
    FreeIntegration(
        "monotropism_physics", "levi-unique", "Attention tunnel interaction physics",
        "pure Python",
        ("persona", "offline_companion", "tone"),
        "Focus-coaching content (non-clinical)",
        "Tunnel-friendly lens bias; not a diagnosis product",
    ),
    FreeIntegration(
        "alchemy_core", "levi-unique", "Hardwired core logic (alchemy/equation/chess)",
        "pure Python",
        ("offline_companion", "control_daemon", "crisis"),
        "Facilitated decision sessions",
        "No pure loss; x+y=z; life chess — LEVI-hardwired",
    ),
    FreeIntegration(
        "cron_watch", "hybrid", "Standing Watch via cron",
        "system cron / Task Scheduler calling levi watch",
        ("standing_watch", "continuity", "hitl"),
        "Managed local alerting",
        "Silence≠approve still enforced",
    ),
    FreeIntegration(
        "character_graph", "levi-unique", "L.W.P. Character Graph",
        "pure Python combinatorics",
        ("story_fabric", "premium_craft", "lwp_model"),
        "Custom character packs",
        "1.6M+ axis types — not stock NPCs",
    ),
    FreeIntegration(
        "premium_craft", "levi-unique", "Premium craft lenses",
        "classical×modern×L.W.P. offline prose",
        ("story_fabric", "character_graph", "cascade"),
        "Editorial coaching HITL",
        "Scar law + cascade lock",
    ),
    FreeIntegration(
        "corpus_expand", "levi-unique", "Mass corpus expander",
        "combinatorial principle generator",
        ("offline_brain", "companion", "search"),
        "Domain packs with human review",
        "LEVI lenses not scraped dumps",
    ),
    FreeIntegration(
        "crucible", "levi-unique", "Crucible constrained chamber",
        "AST/syntax/literal only",
        ("factory_sandbox", "builder", "hitl"),
        "Safe trial environments",
        "No free shell",
    ),
    FreeIntegration(
        "rss_seed", "hybrid", "RSS signal seeds",
        "stdlib urllib",
        ("demand_pulse", "rail", "mirror"),
        "Curated intel desks",
        "HYPOTHESIS until OBSERVED",
    ),
    FreeIntegration(
        "imap_draft", "hybrid", "IMAP read-only drafts",
        "stdlib imaplib optional",
        ("rail", "hitl", "continuity"),
        "Inbox triage service",
        "Never send without HITL",
    ),
    FreeIntegration(
        "zip_handoff", "prehistoric", "Zip life-pack export",
        "stdlib zipfile",
        ("shelf", "corpus", "charter"),
        "Migration concierge",
        "No hostage data",
    ),
    FreeIntegration(
        "sha_provenance", "prehistoric", "Hash provenance stamps",
        "stdlib hashlib",
        ("charter", "closed_source_dna", "audit"),
        "Compliance export packs",
        "Proves not foreign rebrand",
    ),
    FreeIntegration(
        "env_relay", "modern", "Env-based model relay",
        "OLLAMA_HOST optional",
        ("model_relay", "companion", "story"),
        "Optional hosted boost",
        "Offline never blocked",
    ),
    FreeIntegration(
        "service_mesh_cli", "levi-unique", "Local service mesh",
        "CLI organ map",
        ("ops", "watch", "continuity"),
        "Operator manuals",
        "Not remote marketplace",
    ),
    FreeIntegration(
        "neuro_atlas", "levi-unique", "Neuroplasticity atlas",
        "curated offline units",
        ("corpus", "learning", "companion"),
        "Education modules non-clinical",
        "Literacy not diagnosis",
    ),
    FreeIntegration(
        "continuity_shelf", "levi-unique", "Continuity Shelf",
        "local JSON pointers",
        ("hitl", "rail", "lwp", "ask"),
        "Session resume coaching",
        "Not SaaS memory vault",
    ),
    FreeIntegration(
        "fast_gate_sh", "prehistoric", "Shell fast gate",
        "bash + pytest",
        ("ladder", "ci", "builder"),
        "Private runner minutes",
        "Merge authority local",
    ),
]



def free_catalog() -> List[FreeIntegration]:
    return list(CATALOG)


def format_catalog() -> str:
    lines = [
        "=== LEVI Free Integration Lattice ===",
        "Prehistoric x modern x LEVI-unique — monetize later under HITL only",
        "",
    ]
    by_era = {}
    for c in CATALOG:
        by_era.setdefault(c.era, []).append(c)
    for era in ("prehistoric", "hybrid", "modern", "levi-unique"):
        items = by_era.get(era) or []
        if not items:
            continue
        lines.append(f"-- {era.upper()} ({len(items)}) --")
        for c in items:
            lines.append(f"  [{c.id}] {c.name}")
            lines.append(f"       free: {c.free_how}")
            lines.append(f"       x {', '.join(c.combines_with[:5])}")
            lines.append(f"       later $: {c.monetize_later}")
            lines.append(f"       unique: {c.unreplicable}")
        lines.append("")
    lines.append(f"Total free integrations: {len(CATALOG)}")
    lines.append("Core boots with zero paid APIs. Upsells never gate crisis/HITL/offline.")
    return "\n".join(lines)


def interpenetration_matrix() -> str:
    """Human-readable interpenetration view: flat edge list + graph metrics.

    The flat edge list is kept for backward compatibility; the graph-model
    summary below it is the canonical diagnostic — computed from the real
    graph in levi.integrations.free_graph, not prose.
    """
    from levi.integrations.free_graph import build_free_graph

    g = build_free_graph()
    lines = ["=== Max Interpenetration Matrix ===", ""]
    declared = 0
    for c in CATALOG:
        for p in c.combines_with:
            lines.append(f"  {c.id} <-> {p}")
            declared += 1
    pair_count = 0
    try:
        from levi.graph.symbiosis import PAIRS
        pair_count = len(PAIRS)
        lines.append("")
        lines.append(f"Symbiosis formal pairs: {pair_count}")
        for pair in PAIRS:
            lines.append(f"  {pair.asset_a} <-> {pair.asset_b}  ({pair.bond[:50]})")
    except Exception as e:
        lines.append(f"symbiosis: {e}")
    counts = g.counts()
    lines.append("")
    lines.append("--- Graph model (weighted undirected) ---")
    lines.append(f"  nodes: {counts['nodes']}  edges: {counts['edges']}  "
                 f"total bond weight: {counts['total_weight']:.1f}")
    lines.append("  weighting: declared combines_with = 1.0; symbiosis formal pair = 2.0;")
    lines.append("             same pair declared in both registries => weights add (3.0)")
    dang = g.dangling_refs()
    lines.append(f"  dangling refs: {len(dang)}" + ("" if not dang else f" ({', '.join(dang)})"))
    lines.append("    (combines_with targets with no catalog entry; kept as external nodes)")
    lines.append("  strongest bonds:")
    for a, b, w, kinds in g.strongest_bonds(5):
        lines.append(f"    {a} <-> {b}  (w={w:.1f})")
    lines.append("  top assets by weighted degree:")
    top = sorted(((n, g.weighted_degree(n)) for n in g.nodes),
                 key=lambda t: (-t[1], t[0]))[:5]
    for nid, w in top:
        lines.append(f"    {nid}  (wdeg={w:.1f}, deg={g.degree(nid)})")
    orphans = g.orphans()
    if orphans:
        lines.append(f"  ORPHAN DEFECTS: {', '.join(orphans)}")
    else:
        lines.append("  orphans: none - every asset has an other half")
    lines.append("")
    lines.append(f"Total declared interpenetration edges: {declared + pair_count}")
    lines.append("Rule: orphans are defects — every asset needs an other half.")
    return "\n".join(lines)
