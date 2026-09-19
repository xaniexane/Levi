"""Seeded survivability catalog entries and verification machinery.

Schema (each entry is a plain dict):
    id            stable machine name
    capability    what the user experiences
    primary_path  how it normally works (online/optimal)
    fallback_path what takes over when the primary is unavailable
    degraded_mode what the user loses in fallback (honest, plain language)
    offline_ok    bool — True if the capability survives with zero network
    verify        {"kind": "import", "target": "levi.x.y"} or
                  {"kind": "path", "target": "core/levi/..."} — checked by
                  check_entry() to confirm the fallback is actually present.
"""

import importlib
import os
from typing import Dict, List, Optional

Entry = Dict[str, object]

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

ENTRIES: List[Entry] = [
    {
        "id": "agent-provider-chain",
        "capability": "Agentic chat / task execution",
        "primary_path": "Best LEVI-family weight (levi-brain or levi-local), selected via explicit flag > LEVI_PROVIDER > auto",
        "fallback_path": "Deterministic rule-based planner in levi.agent.providers (LocalProvider)",
        "degraded_mode": "No neural generation — canned pattern-matching answers only",
        "offline_ok": True,
        "verify": {"kind": "import", "target": "levi.agent.providers"},
    },
    {
        "id": "local-model-runner",
        "capability": "Local LLM inference (GGUF via llama-server)",
        "primary_path": "levi-local provider serving local GGUF weights from ~/.levi/models",
        "fallback_path": "Rule-based agent core (no model process required)",
        "degraded_mode": "No model inference at all — rules engine answers",
        "offline_ok": True,
        "verify": {"kind": "import", "target": "levi.agent.local_model"},
    },
    {
        "id": "native-brain-weights",
        "capability": "LEVI's own trained brain",
        "primary_path": "Native tiny-gpt weights (core/levi/brain/weights/tiny-gpt.pt, explicit-only)",
        "fallback_path": "Rules-only provider mode (no weights needed)",
        "degraded_mode": "Learning-free deterministic answers; no brain inference",
        "offline_ok": True,
        "verify": {"kind": "path", "target": "core/levi/brain/weights/tiny-gpt.pt"},
    },
    {
        "id": "finance-broker",
        "capability": "Finance simulation / paper trading",
        "primary_path": "SimulatedBroker paper broker (levi.finance.broker)",
        "fallback_path": "None needed — live transport is deliberately unwired; nothing to fall back from",
        "degraded_mode": "Paper-only by design; orders never leave the machine",
        "offline_ok": True,
        "verify": {"kind": "import", "target": "levi.finance.broker"},
    },
    {
        "id": "news-ingestion",
        "capability": "Daily news corpus",
        "primary_path": "RSS refresh from BBC, Reuters, AP, Hacker News, arXiv (levi news refresh)",
        "fallback_path": "Cached dated corpus in core/levi/knowledge/news/days/",
        "degraded_mode": "Stale corpus — search works on old days, no refresh",
        "offline_ok": True,
        "verify": {"kind": "import", "target": "levi.knowledge.news.search"},
    },
    {
        "id": "courses-knowledge",
        "capability": "Awesome-courses knowledge base",
        "primary_path": "Local queryable catalog (core/levi/knowledge/courses/catalog.json)",
        "fallback_path": "None needed — fully local by design",
        "degraded_mode": "Search-only; outbound course links are dead offline",
        "offline_ok": True,
        "verify": {
            "kind": "path",
            "target": "core/levi/knowledge/courses/catalog.json",
        },
    },
    {
        "id": "growth-loop",
        "capability": "Growth: harvest -> reflect -> consolidate",
        "primary_path": "Model-assisted reflection when a provider is reachable",
        "fallback_path": "Rule-based offline reflection engine (distills experiences conservatively)",
        "degraded_mode": "Conservative heuristic learnings only; nuanced insights wait for a model",
        "offline_ok": True,
        "verify": {"kind": "import", "target": "levi.growth.cycle"},
    },
    {
        "id": "skills-registry",
        "capability": "Skills library registration",
        "primary_path": "Full skill library with data-driven frontmatter registration",
        "fallback_path": "Directory scan — registration needs no network, only markdown on disk",
        "degraded_mode": "Lazy load; unregistered skills are invisible until scanned",
        "offline_ok": True,
        "verify": {"kind": "import", "target": "levi.skill.registry"},
    },
    {
        "id": "cyber-playbooks",
        "capability": "Defensive cybersecurity playbooks",
        "primary_path": "823 local playbooks under core/levi/skill/playbooks/cyber/",
        "fallback_path": "None needed — markdown on disk, zero dependencies",
        "degraded_mode": "Read-only; no live enrichment (threat feeds are online-only)",
        "offline_ok": True,
        "verify": {"kind": "path", "target": "core/levi/skill/playbooks/cyber"},
    },
    {
        "id": "control-plane",
        "capability": "Approvals ledger + control CLI",
        "primary_path": "Local approvals ledger with automation triggers",
        "fallback_path": "Manual deny/approve via the control CLI",
        "degraded_mode": "No automation triggers; every action is manual",
        "offline_ok": True,
        "verify": {"kind": "import", "target": "levi.control"},
    },
    {
        "id": "king-orchestration",
        "capability": "King control plane (cross-organ orchestration)",
        "primary_path": "King orchestration over story_fabric + model_engine",
        "fallback_path": "Direct CLI per subsystem (levi king status/pulse/... )",
        "degraded_mode": "No cross-organ orchestration; subsystems run standalone",
        "offline_ok": True,
        "verify": {"kind": "import", "target": "levi.king"},
    },
    {
        "id": "eula-linter",
        "capability": "EULA / terms hostile-clause linting",
        "primary_path": "Local rule-based linter (levi.eula)",
        "fallback_path": "None needed — zero dependencies by design, never goes online",
        "degraded_mode": "n/a — fully offline always",
        "offline_ok": True,
        "verify": {"kind": "import", "target": "levi.eula"},
    },
]


def catalog() -> List[Entry]:
    """Return all survivability catalog entries."""
    return list(ENTRIES)


def get(entry_id: str) -> Optional[Entry]:
    """Return one entry by id, or None."""
    for entry in ENTRIES:
        if entry["id"] == entry_id:
            return entry
    return None


def check_entry(entry: Entry) -> Dict[str, object]:
    """Verify an entry's fallback is actually present (importable or on disk).

    Returns {"id": ..., "ok": bool, "detail": str}.
    """
    spec = entry.get("verify", {})
    kind = spec.get("kind")
    target = spec.get("target")
    try:
        if kind == "import":
            importlib.import_module(target)
            return {"id": entry["id"], "ok": True, "detail": "import %s OK" % target}
        if kind == "path":
            full = os.path.join(_REPO_ROOT, target)
            if os.path.exists(full):
                return {
                    "id": entry["id"],
                    "ok": True,
                    "detail": "path %s present" % target,
                }
            return {
                "id": entry["id"],
                "ok": False,
                "detail": "path %s MISSING" % target,
            }
        return {
            "id": entry["id"],
            "ok": False,
            "detail": "unknown verify kind %r" % kind,
        }
    except Exception as exc:  # noqa: BLE001 - verification must never raise
        return {
            "id": entry["id"],
            "ok": False,
            "detail": "import %s failed: %s" % (target, exc),
        }


def check_all() -> List[Dict[str, object]]:
    """Run check_entry() over the whole catalog."""
    return [check_entry(entry) for entry in catalog()]
