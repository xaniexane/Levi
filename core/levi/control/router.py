"""AI router — Enterprise Phase 2 (blueprint §7/§34, first version).

Maps a task to ``(model, agent category, tools, execution strategy)``.

First version is heuristic + ledger-informed:

1. Heuristic: complexity class (see :mod:`levi.control.routing`),
   category by keyword scoring over the fleet registry, tools from the
   category, strategy by complexity (direct / single_worker / swarm).
2. Learning: consults the decision ledger's per-(model, category) stats
   for the task's complexity class. A combo with ≥3 recorded runs and
   ≥60% success that is cheaper than the heuristic pick wins, and the
   explanation says so. With no history, the router says it's running
   on heuristics — learning needs history to be useful.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from levi.control.routing import (
    classify_complexity,
    plan_route,
    MODEL_COSTS,
    COST_UNIT_NOTE,
)


@dataclass
class RoutePlan:
    """The router's decision for one task."""

    task: str
    complexity: str
    model: str
    category: str
    tools: List[str] = field(default_factory=list)
    strategy: str = "direct"
    strategy_detail: str = ""
    est_cost_units: float = 0.0
    learned_from_history: bool = False
    explanation: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task[:300],
            "complexity": self.complexity,
            "model": self.model,
            "category": self.category,
            "tools": self.tools,
            "strategy": self.strategy,
            "strategy_detail": self.strategy_detail,
            "est_cost_units": round(self.est_cost_units, 2),
            "learned_from_history": self.learned_from_history,
            "explanation": self.explanation,
            "cost_note": COST_UNIT_NOTE,
        }


# Keyword → fleet category scoring. Kept small and legible; the fleet
# registry's role text is the tiebreaker, not a second keyword table.
_CATEGORY_HINTS: List[Tuple[str, Tuple[str, ...]]] = [
    ("research", ("research", "investigate", "find out", "compare", "survey",
                  "sources", "evidence")),
    ("coding", ("code", "bug", "function", "script", "program", "implement",
                "refactor", "debug")),
    ("architect", ("architecture", "system design", "blueprint")),
    ("document", ("write", "draft", "report", "essay", "memo", "doc",
                  "summarize", "summary")),
    ("data", ("data", "csv", "spreadsheet", "dataset", "metrics",
              "analytics")),
    ("finance", ("finance", "stocks", "portfolio", "budget", "money",
                 "invest")),
    ("security", ("security", "vulnerability", "harden", "threat")),
    ("qa", ("test", "qa", "validate", "verify")),
    ("devops", ("deploy", "ci", "docker", "server", "infra")),
    ("automation", ("automate", "schedule", "workflow", "cron")),
    ("browser", ("browse", "website", "web page", "scrape")),
    ("communication", ("email", "message", "notify", "send")),
    ("marketing", ("market", "campaign", "seo", "launch")),
    ("planning", ("plan", "roadmap", "milestones")),
    ("memory", ("remember", "recall", "notes")),
    ("dispatch", ("dispatch", "assign", "field work", "technician")),
    ("bidding", ("bid", "quote", "estimate", "pricing")),
    ("coach", ("coach", "advice", "mentor", "improve")),
    ("guardian", ("property", "maintenance", "home", "landlord")),
    ("compliance", ("compliance", "regulation", "license", "permit")),
    ("fraud_risk", ("fraud", "scam", "anomaly", "suspicious")),
    ("support", ("support", "customer", "help desk", "ticket")),
]


def pick_category(task: str) -> Tuple[str, List[str]]:
    """Score fleet categories by keyword hits; default ``supervisor``.

    Returns (category_name, matched_keywords). Falls back to the fleet
    registry default when nothing matches.
    """
    lowered = (task or "").lower()
    best: Tuple[str, int, List[str]] = ("supervisor", 0, [])
    for category, keywords in _CATEGORY_HINTS:
        hits = [k for k in keywords if k in lowered]
        if len(hits) > best[1]:
            best = (category, len(hits), hits)
    name = best[0]
    # Validate against the real registry — a hinted name that doesn't
    # exist must not leak through.
    try:
        from levi.fleet.categories import get_category
        get_category(name)
    except Exception:
        name = "supervisor"
    return name, best[2]


def _category_tools(category: str) -> List[str]:
    try:
        from levi.fleet.categories import get_category
        return list(get_category(category).tools)
    except Exception:
        return []


def _learned_pick(complexity: str, heuristic_model: str,
                  heuristic_category: str,
                  home=None) -> Optional[Dict[str, Any]]:
    """Ask the ledger which (model, category) actually worked cheapest.

    Returns a better pick or None. Requires ≥3 runs and ≥60% success
    for a combo to qualify — thin history is not evidence.
    """
    try:
        from levi.control.ledger import LedgerWriter
        stats = LedgerWriter(home=home).model_category_stats()
    except Exception:
        return None
    heur_cost = MODEL_COSTS.get(heuristic_model, {}).get("cost_per_1k", 1e9)
    best: Optional[Dict[str, Any]] = None
    for row in stats:
        if row["task_class"] != complexity:
            continue
        runs = row["runs"]
        if runs < 3:
            continue
        success_rate = (row["successes"] or 0) / runs
        if success_rate < 0.6:
            continue
        cost = MODEL_COSTS.get(row["model"], {}).get("cost_per_1k", 1e9)
        if cost < heur_cost:
            if best is None or cost < best["cost"]:
                best = {"model": row["model"], "category": row["category"],
                        "cost": cost, "runs": runs,
                        "success_rate": round(success_rate, 2)}
    return best


def plan(task: str, *, user_id: str = "local",
         budget_units: Optional[float] = None,
         privacy: str = "standard",
         home=None) -> RoutePlan:
    """Route one task → (model, category, tools, strategy) + explanation."""
    complexity, reasons = classify_complexity(task)
    category, cat_hits = pick_category(task)

    candidates: Optional[List[str]] = None
    explanation: List[str] = []
    if privacy == "local-only":
        candidates = ["levi-tiny", "levi-0.6b", "levi-4b"]
        explanation.append("privacy=local-only: cloud sources excluded")

    route = plan_route(task, budget_units=budget_units,
                       candidates=candidates)
    explanation.append(
        f"complexity={complexity} ({'; '.join(reasons)})")
    if cat_hits:
        explanation.append(
            f"category={category} (keywords: {', '.join(cat_hits)})")
    else:
        explanation.append(
            "category=supervisor (no specialist keywords matched)")
    explanation.append(f"model: {route.reason}")
    if not route.within_budget:
        explanation.append(
            "WARNING: cheapest viable model exceeds the task budget — "
            "quality bar kept, budget flagged")

    learned_from_history = False
    learned = _learned_pick(complexity, route.model, category, home=home)
    if learned is not None:
        learned_from_history = True
        explanation.append(
            f"ledger: {learned['model']} succeeded "
            f"{learned['success_rate'] * 100:.0f}% over {learned['runs']} "
            f"recorded {complexity} runs at lower relative cost — "
            "preferred over the heuristic pick")
        route = plan_route(task, budget_units=budget_units,
                           candidates=[learned["model"]])

    if complexity == "simple":
        strategy, detail = "direct", "single agentic turn, no swarm"
    elif complexity == "medium":
        strategy, detail = ("single_worker",
                            f"one {category} worker, ≤8 steps")
    else:
        strategy, detail = ("swarm",
                            f"fleet swarm: supervisor decomposes, "
                            f"{category} specialists execute, budgets enforced")

    return RoutePlan(
        task=task,
        complexity=complexity,
        model=route.model,
        category=category,
        tools=_category_tools(category),
        strategy=strategy,
        strategy_detail=detail,
        est_cost_units=route.est_cost_units,
        learned_from_history=learned_from_history,
        explanation=explanation,
    )
