"""
25 premium must-haves for next-gen offline AI software.

Lineage: retired local power tools (ThinkPad-era offline suites, classic IDEs,
BBSes, HyperCard, Palm, early desktop AI) × modern local SI (Ollama, RAG,
HITL agents, glass consoles).

Status: active = wired in kernel · surface = UI/CLI exposed · roadmap = specified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class PremiumFeature:
    id: str
    name: str
    classic: str  # old/retired software DNA
    modern: str  # modern counterpart
    why: str
    status: str  # active | surface | roadmap
    cli: str = ""


FEATURES: List[PremiumFeature] = [
    PremiumFeature(
        "local_first",
        "Local-first core",
        "Palm / Newton / offline Office — work without a pipe",
        "Local-first apps (Ink & Switch pattern)",
        "SI must stay useful when the network dies",
        "active",
        "levi go",
    ),
    PremiumFeature(
        "no_account_gate",
        "No account required",
        "Shrink-wrap software, serial optional",
        "Optional auth only for cloud wings",
        "Open the box, run the tool — identity is yours",
        "active",
        "levi init",
    ),
    PremiumFeature(
        "keyboard_power",
        "Keyboard-first power surface",
        "Vim, DOS, Norton Commander, classic IDEs",
        "Command palette + CLI parity",
        "Hands stay on keys; mouse is optional",
        "active",
        "levi --help",
    ),
    PremiumFeature(
        "full_export",
        "Full export / exit",
        "File → Save As, ZIP archives, print-to-disk",
        "Life-pack zip, open formats",
        "Your continuity leaves with you — no hostage data",
        "active",
        "levi export",
    ),
    PremiumFeature(
        "session_restore",
        "Session restore",
        "Word autosave, IDE workspace restore",
        "Chat sessions + story state under ~/.levi",
        "Crash or reboot — pick up the thread",
        "active",
        "levi chat --list",
    ),
    PremiumFeature(
        "project_files",
        "Self-contained project packs",
        "HyperCard stacks, Scrivener projects",
        "Life-pack + model state bundles",
        "One artifact holds story, prefs, corpus slice",
        "active",
        "levi export / levi import",
    ),
    PremiumFeature(
        "local_search",
        "Search everything local",
        "Desktop search, Grep, Spotlight offline indexes",
        "Corpus query + transcript search",
        "Find the note, beat, or claim without the cloud",
        "active",
        "levi brain --query",
    ),
    PremiumFeature(
        "macros_workflows",
        "Macros & repeatable workflows",
        "Excel macros, AutoHotkey, batch files",
        "Daemon locks + ladder + enterprise gates",
        "Encode the ritual once; rerun under HITL",
        "active",
        "levi ladder / levi daemon",
    ),
    PremiumFeature(
        "undo_history",
        "Reversible history",
        "Multi-level undo, Time Machine mental model",
        "Story REIM forks + session transcripts",
        "Explore without fear of permanent loss",
        "active",
        "levi model reim",
    ),
    PremiumFeature(
        "offline_docs",
        "Offline documentation",
        "WinHelp, man pages, local CHM",
        "levi cognition / si / scorecard / help",
        "Help that works on a plane",
        "active",
        "levi cognition",
    ),
    PremiumFeature(
        "split_workspace",
        "Multi-pane workspace",
        "Classic IDE split, Norton dual-pane",
        "Premium console tabs + glass panels",
        "Chat, story, model, ops in one operator face",
        "surface",
        "levi serve-ui",
    ),
    PremiumFeature(
        "glass_console",
        "Premium textured UI",
        "NeXT / BeOS craft; high-end desktop skins",
        "Glassmorphism + motion mesh console",
        "Software you want to inhabit, not endure",
        "surface",
        "levi serve-ui → console.html",
    ),
    PremiumFeature(
        "persona_lattice",
        "Deep persona lattice",
        "RPG character sheets, MUD classes",
        "230 personas + nervous system routing",
        "Tone and role are instruments, not costumes",
        "active",
        "levi personas / levi chat -p",
    ),
    PremiumFeature(
        "wit_sarcasm",
        "Calibrated wit / sarcasm",
        "Snarky IRC bots, deadpan desktop agents",
        "ND comedy spectrum with crisis mute",
        "Humor with a kill-switch when stakes rise",
        "active",
        "levi wit --tone playful",
    ),
    PremiumFeature(
        "local_llm_optional",
        "Optional local LLM",
        "Early offline expert systems",
        "Ollama / local OpenAI-compatible endpoints",
        "Boost when present; never require the pipe",
        "active",
        "levi ask (Ollama if up)",
    ),
    PremiumFeature(
        "rag_corpus",
        "Personal RAG corpus",
        "Personal Brain, local knowledge bases",
        "A–Z + heavy knowledge + hyperdrive seeds",
        "Your library under provenance labels",
        "active",
        "levi brain --seed-knowledge-heavy",
    ),
    PremiumFeature(
        "hitl_gates",
        "HITL consequential gates",
        "Admin approval workflows, air-gap checklists",
        "Silence ≠ approve; ALWAYS_HITL domains",
        "Agency stays with the human",
        "active",
        "levi enterprise",
    ),
    PremiumFeature(
        "crisis_floor",
        "Crisis-safe floor",
        "Emergency offline procedures manuals",
        "Offline companion crisis path, no server wait",
        "Help works when everything else is down",
        "active",
        "levi chat (crisis detection)",
    ),
    PremiumFeature(
        "literary_engine",
        "Literary physics engine",
        "Interactive fiction, Storyspace, Twine",
        "L.W.P. SSA cascade, scar law, rupture",
        "Story as a first-class organ, not a prompt toy",
        "active",
        "levi story / levi model",
    ),
    PremiumFeature(
        "agent_tools_approve",
        "Tool use under approval",
        "Macro confirm dialogs, UAC-era prompts",
        "Agent actions with HITL before side effects",
        "Power without silent automation",
        "active",
        "levi agent / policy",
    ),
    PremiumFeature(
        "memory_provenance",
        "Memory with provenance",
        "Lab notebooks, versioned archives",
        "OBSERVED / INFERENCE / HYPOTHESIS labels",
        "Know what is fact vs guess in the store",
        "active",
        "levi brain",
    ),
    PremiumFeature(
        "scorecard_eval",
        "Built-in quality scorecard",
        "Self-test diagnostics in BIOS / memtest",
        "10/10 SI cloud model scorecard",
        "Measure the posture; don’t market it",
        "active",
        "levi scorecard",
    ),
    PremiumFeature(
        "crypto_local_keys",
        "Local keys · optional sync crypto",
        "PGP offline, TrueCrypt-era local vaults",
        "Argon2id CMK design + ratchet protocol map",
        "Cloud never owns the content master key",
        "active",
        "levi cloud crypto",
    ),
    PremiumFeature(
        "batch_story",
        "Batch / long-form generation",
        "Overnight renders, batch compilers",
        "Manuscript expand + gold-path cascade",
        "Long work without babysitting every token",
        "active",
        "levi model expand / manuscript",
    ),
    PremiumFeature(
        "si_identity",
        "Synthetic Intelligence identity",
        "Expert systems with explicit scope",
        "SI definition + symbiotic method pillars",
        "Clear what it is — and what it refuses to pretend",
        "active",
        "levi si",
    ),
    PremiumFeature(
        "batch_eval_harness",
        "Eval harness hooks",
        "Compiler test suites, memtest",
        "Golden transcripts for registers",
        "Regression for voice and policy",
        "roadmap",
        "levi x100",
    ),
    PremiumFeature(
        "voice_local_hooks",
        "Local voice hooks",
        "Dictation utilities, offline speech toys",
        "STT/TTS behind HITL",
        "Hands-free without cloud mic servers",
        "roadmap",
        "future: levi voice",
    ),
    PremiumFeature(
        "signed_skills",
        "Signed skill allowlist",
        "Signed plugins, package trust",
        "Skill manifest + hash pin",
        "Power tools without random code exec",
        "roadmap",
        "levi plugins",
    ),
    PremiumFeature(
        "kai_matrix_12",
        "KAI-9000 matrix (12)",
        "Multi-mode expert systems",
        "Twelve SI registers with forbids",
        "Instrument switching under policy",
        "active",
        "levi kai",
    ),
    PremiumFeature(
        "max_corpus",
        "MAX densified corpus",
        "Local encyclopedic digests",
        "2500+ operator literacy units",
        "Heavy local knowledge without cloud RAG tax",
        "active",
        "levi brain --seed-max",
    ),
    PremiumFeature(
        "x100_rail",
        "×100 / MAX upgrade rail",
        "BIOS diagnostics + service menus",
        "Status · law · next slices",
        "Operator sees posture honestly",
        "active",
        "levi max",
    ),
    PremiumFeature(
        "glassmorphism_ui",
        "Glassmorphism operator UI",
        "High-end desktop skinning eras",
        "Frosted panels + mesh + motion",
        "Inhabitable local console",
        "surface",
        "levi serve-ui",
    ),
    PremiumFeature(
        "story_genre_grid",
        "Genre×beat craft grid",
        "Storyspace / Twine discipline",
        "Scar-aware beat literacy in corpus",
        "Literary physics taught as units",
        "active",
        "levi brain --seed-max",
    ),
    PremiumFeature(
        "phase_literacy",
        "Phase A/B/C literacy pack",
        "Air-gapped ops manuals",
        "Phase rules in corpus + CLI",
        "Cloud wings never redefine core law",
        "active",
        "levi cloud",
    ),
    PremiumFeature(
        "operator_grid",
        "Operator verb×noun grid",
        "Runbook libraries",
        "Prefer/Refuse/Measure… × defaults/secrets…",
        "Dense operational language for SI",
        "active",
        "levi brain --seed-max",
    ),
    PremiumFeature(
        "evidence_drills",
        "Evidence drills (200+)",
        "Lab notebook checklists",
        "Label · weakest premise · disconfirm",
        "Epistemic hygiene as practice",
        "active",
        "levi brain --seed-max",
    ),
    PremiumFeature(
        "care_notes",
        "Care notes under distress",
        "Emergency procedure cards",
        "Reduce options · mute wit · one step",
        "Care is encoded, not improvised only",
        "active",
        "levi kai -v care",
    ),
    PremiumFeature(
        "runbook_density",
        "Runbook density (300+)",
        "NOC runbook binders",
        "Verify · contain · owner · evidence",
        "Incident language ready offline",
        "active",
        "levi brain --seed-max",
    ),
    PremiumFeature(
        "build_notes",
        "Build notes (300+)",
        "Engineering notebook culture",
        "Smallest slice proving riskiest assumption",
        "Anti-astronautics bias in corpus",
        "active",
        "levi kai -v builder",
    ),
    PremiumFeature(
        "principle_series",
        "Principle series (400+)",
        "Aphorism books + field manuals",
        "Reversibility and explicit trade-offs",
        "Compressed judgment aids",
        "active",
        "levi brain --seed-max",
    ),
    PremiumFeature(
        "x10_expansion",
        "×10 MAX expansion pack",
        "Service-pack style cumulative updates",
        "2888+ additional literacy units",
        "Second wave densify on top of MAX 2518",
        "active",
        "levi brain --seed-x10",
    ),
    PremiumFeature(
        "interpenetrate_mesh",
        "Interpenetration mesh",
        "System diagrams in field manuals",
        "20+ organ coupling edges",
        "Features couple by law, not brochure",
        "active",
        "levi interpenetrate",
    ),
    PremiumFeature(
        "condensed_console",
        "Condensed modern console",
        "Late-era tight UI toolkits",
        "Single shell · rail · stage",
        "Density over decoration; CLI authority",
        "surface",
        "levi serve-ui",
    ),
    PremiumFeature(
        "kai_attribution_clear",
        "KAI attribution clarity",
        "Honest lineage notes in manuals",
        "Original LEVI; reverse-engineered concept; heavily modified",
        "No third-party source confusion",
        "active",
        "levi kai",
    ),
    PremiumFeature(
        "max10_rail",
        "MAX×10 operator rail",
        "Diagnostics + pack inventory",
        "Combined counts MAX+x10",
        "One command for densest posture",
        "active",
        "levi max10",
    ),
    PremiumFeature(
        "field_checks_800",
        "Field checks (800+)",
        "Pre-flight checklists",
        "Owner · label · HITL · rollback · offline",
        "Consequential path hygiene",
        "active",
        "levi brain --seed-x10",
    ),
    PremiumFeature(
        "couple_drills",
        "Organ couple drills",
        "Cross-training manuals",
        "si↔kai↔story↔cloud coherence drills",
        "Change one organ without breaking another",
        "active",
        "levi interpenetrate",
    ),
    PremiumFeature(
        "ui_kernel_authority",
        "UI defers to kernel",
        "Thin client / thick logic split",
        "Console copies CLI; does not own continuity",
        "Modern face, local-first brain",
        "active",
        "levi serve-ui",
    ),
    PremiumFeature(
        "combined_corpus_5k",
        "Combined corpus 5k+",
        "Local library stacks",
        "MAX + ×10 ≈ 5400 units when both seeded",
        "Heavy offline literacy without cloud RAG tax",
        "active",
        "levi brain --seed-max && levi brain --seed-x10",
    ),
    PremiumFeature(
        "expand2_pack",
        "Expansion pack II",
        "Cumulative content packs",
        "Couple literacy + condensed UI notes",
        "Interpenetration taught as units",
        "active",
        "levi brain --seed-expand2",
    ),
]


def feature_ids() -> List[str]:
    return [f.id for f in FEATURES]


def feature_by_id(fid: str) -> Optional[PremiumFeature]:
    for f in FEATURES:
        if f.id == fid:
            return f
    return None


def format_features(verbose: bool = True) -> str:
    active = sum(1 for f in FEATURES if f.status == "active")
    surface = sum(1 for f in FEATURES if f.status == "surface")
    lines = [
        "══ LEVI Premium · must-haves (next-gen offline SI) ══",
        f"count={len(FEATURES)}  active={active}  surface={surface}",
        "DNA: retired local power tools × modern local AI",
        "",
    ]
    for i, f in enumerate(FEATURES, 1):
        flag = {"active": "●", "surface": "○", "roadmap": "·"}.get(f.status, "·")
        lines.append(f"{i:2}. {flag} {f.name}")
        if verbose:
            lines.append(f"     classic: {f.classic}")
            lines.append(f"     modern:  {f.modern}")
            lines.append(f"     why:     {f.why}")
            if f.cli:
                lines.append(f"     cli:     {f.cli}")
            lines.append("")
    lines.append("● active in kernel · ○ UI surface · · roadmap")
    return "\n".join(lines)


def format_compact() -> str:
    lines = [f"LEVI Premium {len(FEATURES)}"]
    for i, f in enumerate(FEATURES, 1):
        lines.append(f"  {i:2}. [{f.status[:1].upper()}] {f.name}")
    return "\n".join(lines)
