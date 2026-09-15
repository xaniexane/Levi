"""Cost-aware model routing — Enterprise Phase 2 (blueprint §7).

Every task gets a cost budget::

    TASK → classify complexity → estimate tokens → estimate relative cost
         → select cheapest model meeting the quality bar → execute
         → track actuals back into the ledger

Cost units are RELATIVE, not dollars — see :data:`COST_UNIT_NOTE`. They
rank models against each other so the router can prefer cheaper ones;
they are not prices and must never be presented as money.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

COST_UNIT_NOTE = (
    "Cost units are RELATIVE (levi-tiny = 1). They rank models against "
    "each other for routing decisions. They are not dollars, not prices, "
    "and must never be presented as money."
)

# Relative cost per 1k tokens, derived from the LEVI model family
# (core/levi/agent/model_family.py): bigger weights ≈ more compute.
# `priced=False` entries are honest placeholders — ranked, not measured.
MODEL_COSTS: Dict[str, Dict[str, Any]] = {
    "levi-tiny": {
        "cost_per_1k": 1.0,
        "priced": True,
        "note": "Native brain, CPU, cheapest. Cannot emit tool calls.",
        "tools_capable": False,
    },
    "levi-0.6b": {
        "cost_per_1k": 3.0,
        "priced": True,
        "note": "Levi remix of Qwen3-0.6B. Tool-capable, small judgment.",
        "tools_capable": True,
    },
    "levi-4b": {
        "cost_per_1k": 10.0,
        "priced": True,
        "note": "Levi remix of Qwen3-4B. Best local reasoning, slower.",
        "tools_capable": True,
    },
    # Selectable non-family sources: ranked above family, unpriced.
    "local": {
        "cost_per_1k": 3.0,
        "priced": False,
        "note": "Generic local provider — ranked like levi-0.6b, unmeasured.",
        "tools_capable": True,
    },
    "openai": {
        "cost_per_1k": 50.0,
        "priced": False,
        "note": "Cloud source — ranked most expensive; not a real price.",
        "tools_capable": True,
    },
    "anthropic": {
        "cost_per_1k": 50.0,
        "priced": False,
        "note": "Cloud source — ranked most expensive; not a real price.",
        "tools_capable": True,
    },
}

# Complexity → expected output length (tokens, heuristic).
_OUTPUT_TOKENS = {"simple": 150, "medium": 600, "hard": 1500}

_HARD_WORDS = frozenset(
    {
        "research",
        "architecture",
        "strategy",
        "plan",
        "design",
        "build",
        "implement",
        "debug",
        "analyze",
        "compare",
        "evaluate",
        "multi-step",
        "swarm",
        "system",
        "enterprise",
        "comprehensive",
        "thorough",
        "investigate",
        "audit",
    }
)
_MEDIUM_WORDS = frozenset(
    {
        "write",
        "summarize",
        "explain",
        "draft",
        "review",
        "list",
        "outline",
        "convert",
        "translate",
        "improve",
        "refactor",
    }
)


def classify_complexity(task: str) -> Tuple[str, List[str]]:
    """Crude heuristic complexity class + the reasons why.

    Honest limits: this is keyword/shape matching, not understanding.
    ``simple`` = short single question; ``medium`` = compositional work;
    ``hard`` = research/planning/building language or long input.
    """
    text = (task or "").strip()
    lowered = text.lower()
    words = set(lowered.replace("-", " ").split())
    reasons: List[str] = []
    hard_hits = sorted(words & _HARD_WORDS)
    medium_hits = sorted(words & _MEDIUM_WORDS)

    if hard_hits:
        reasons.append(f"hard keywords: {', '.join(hard_hits)}")
        return "hard", reasons
    if len(text) > 600:
        reasons.append(f"long input ({len(text)} chars)")
        return "hard", reasons
    if medium_hits or len(text) > 200 or text.count("?") > 1:
        if medium_hits:
            reasons.append(f"medium keywords: {', '.join(medium_hits)}")
        if len(text) > 200:
            reasons.append(f"multi-part input ({len(text)} chars)")
        if text.count("?") > 1:
            reasons.append("multiple questions")
        return "medium", reasons
    reasons.append("short single request, no complexity keywords")
    return "simple", reasons


def estimate_tokens(task: str, complexity: str) -> Tuple[int, int]:
    """(input_tokens, output_tokens) — rough heuristic, ~4 chars/token."""
    in_tokens = max(8, len(task or "") // 4 + 64)  # +64: system prompt share
    return in_tokens, _OUTPUT_TOKENS[complexity]


def _meets_bar(model: str, complexity: str, needs_tools: bool) -> bool:
    info = MODEL_COSTS[model]
    if needs_tools and not info["tools_capable"]:
        return False
    if complexity == "simple":
        return True
    if complexity == "medium":
        # tiny is out for anything compositional even without tools:
        # its output is fluent-ish gibberish (docs/BRAIN_TRAINING.md).
        return model != "levi-tiny"
    # hard: prefer the strongest local weight
    return model in ("levi-4b", "openai", "anthropic")


@dataclass
class Route:
    """A cost-aware routing decision for one task."""

    task: str
    complexity: str
    complexity_reasons: List[str] = field(default_factory=list)
    needs_tools: bool = False
    model: str = ""
    est_input_tokens: int = 0
    est_output_tokens: int = 0
    est_cost_units: float = 0.0
    quality_ok: bool = True
    within_budget: bool = True
    reason: str = ""
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task[:300],
            "complexity": self.complexity,
            "complexity_reasons": self.complexity_reasons,
            "needs_tools": self.needs_tools,
            "model": self.model,
            "est_input_tokens": self.est_input_tokens,
            "est_output_tokens": self.est_output_tokens,
            "est_cost_units": round(self.est_cost_units, 2),
            "quality_ok": self.quality_ok,
            "within_budget": self.within_budget,
            "reason": self.reason,
            "alternatives": self.alternatives,
            "cost_note": COST_UNIT_NOTE,
        }


def _available_models(prefer: Optional[List[str]] = None) -> List[str]:
    """Family-first ordering; caller may restrict the candidate set."""
    order = ["levi-tiny", "levi-0.6b", "levi-4b"]
    if prefer:
        order = [m for m in prefer if m in MODEL_COSTS]
    return order


def plan_route(
    task: str,
    *,
    budget_units: Optional[float] = None,
    needs_tools: Optional[bool] = None,
    candidates: Optional[List[str]] = None,
    only_downloaded: bool = True,
) -> Route:
    """Choose the cheapest model meeting the quality bar.

    ``needs_tools`` defaults to a verb heuristic when not given.
    ``only_downloaded`` restricts family candidates to weights actually
    present (via :mod:`levi.agent.model_family`); falls back to the full
    family when the check is unavailable.
    """
    complexity, reasons = classify_complexity(task)
    if needs_tools is None:
        lowered = (task or "").lower()
        needs_tools = any(
            verb in lowered
            for verb in (
                "write file",
                "create",
                "send",
                "run",
                "build",
                "deploy",
                "schedule",
                "delete",
                "edit",
                "search files",
                "execute",
            )
        )
    in_tokens, out_tokens = estimate_tokens(task, complexity)

    models = _available_models(candidates)
    if only_downloaded:
        models = _filter_downloaded(models) or models

    def cost_of(model: str) -> float:
        per_1k = MODEL_COSTS[model]["cost_per_1k"]
        return (in_tokens + out_tokens) / 1000.0 * per_1k

    viable = [m for m in models if _meets_bar(m, complexity, needs_tools)]
    if not viable:
        viable = models  # degrade honestly: pick cheapest of what's there
        quality_ok = False
    else:
        quality_ok = True
    viable.sort(key=cost_of)

    alternatives = [
        {
            "model": m,
            "est_cost_units": round(cost_of(m), 2),
            "priced": MODEL_COSTS[m]["priced"],
        }
        for m in viable[1:4]
    ]
    chosen = viable[0] if viable else "levi-tiny"
    est = cost_of(chosen)
    within = budget_units is None or est <= budget_units
    if budget_units is not None and not within:
        # Budget too tight for the quality bar: say so, keep the pick.
        reason = (
            f"cheapest viable model {chosen} costs ~{est:.1f} units, "
            f"over budget {budget_units:.1f} — quality bar kept, budget "
            "flagged rather than silently downgraded"
        )
    else:
        reason = (
            f"{chosen} is the cheapest model meeting the {complexity} "
            f"quality bar"
            + (" (tool-capable)" if needs_tools else "")
            + f" at ~{est:.1f} relative units"
        )
    return Route(
        task=task,
        complexity=complexity,
        complexity_reasons=reasons,
        needs_tools=needs_tools,
        model=chosen,
        est_input_tokens=in_tokens,
        est_output_tokens=out_tokens,
        est_cost_units=est,
        quality_ok=quality_ok,
        within_budget=within,
        reason=reason,
        alternatives=alternatives,
    )


def _filter_downloaded(models: List[str]) -> List[str]:
    """Keep only family models whose weights are actually on disk."""
    try:
        from levi.agent import model_family
    except Exception:
        return models
    kept = []
    for m in models:
        if m not in model_family.family_names():
            kept.append(m)  # non-family candidate: leave the choice alone
            continue
        try:
            if model_family.status(m)["downloaded"]:
                kept.append(m)
        except Exception:
            continue
    return kept


def record_actual(
    task_id: str,
    route: Route,
    *,
    input_tokens: int,
    output_tokens: int,
    outcome: str,
    latency_ms: float = 0.0,
    home=None,
) -> int:
    """Track actuals back into the ledger as a router step row."""
    from levi.control.ledger import LedgerWriter

    per_1k = MODEL_COSTS.get(route.model, {}).get("cost_per_1k", 0.0)
    actual_cost = (input_tokens + output_tokens) / 1000.0 * per_1k
    ledger = LedgerWriter(home=home)
    return ledger.record_step(
        task_id,
        agent="cost_router",
        category="router",
        task_class=route.complexity,
        model=route.model,
        decision_summary=(
            f"routed: {route.reason} "
            f"(est {route.est_cost_units:.1f}u, "
            f"actual {actual_cost:.1f}u)"
        ),
        action="select_model",
        expected_result=f"~{route.est_cost_units:.1f} relative units",
        actual_result=(
            f"{input_tokens} in / {output_tokens} out tokens, "
            f"~{actual_cost:.1f} relative units"
        ),
        outcome=outcome,
        cost_units=actual_cost,
        latency_ms=latency_ms,
    )
