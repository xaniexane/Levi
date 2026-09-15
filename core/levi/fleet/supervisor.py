"""LEVI Fleet — supervisor: objective → subtask DAG (Enterprise Phase 1, §2).

The supervisor decomposes a user objective into a directed acyclic graph of
subtasks, each assigned to a fleet category with acceptance criteria. Two
paths:

- **Model path** (``use_model=True``): drives the existing agentic loop
  (:func:`levi.agent.loop.run_subtask`) to emit a strict ``NODE`` line
  format, which is parsed into the DAG.
- **Heuristic path** (default): deterministic keyword routing — hermetic,
  testable, and honest about being a first draft. The model path refines it.

Plans are inspectable: ``levi fleet plan "<objective>"`` prints the DAG.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from levi.fleet.categories import get_category

# ---------------------------------------------------------------------------
# Plan model
# ---------------------------------------------------------------------------


@dataclass
class PlanNode:
    """One subtask in the plan DAG."""

    id: str
    category: str
    task: str
    acceptance: str
    deps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "task": self.task,
            "acceptance": self.acceptance,
            "deps": list(self.deps),
        }


@dataclass
class Plan:
    """A subtask DAG for one objective."""

    objective: str
    nodes: List[PlanNode] = field(default_factory=list)
    method: str = "heuristic"  # heuristic | model

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "method": self.method,
            "nodes": [n.to_dict() for n in self.nodes],
        }

    def validate(self) -> List[str]:
        """Check DAG integrity; returns problems (empty = OK)."""
        problems: List[str] = []
        ids = {n.id for n in self.nodes}
        for n in self.nodes:
            try:
                get_category(n.category)
            except KeyError:
                problems.append(f"{n.id}: unknown category {n.category!r}")
            if not n.task.strip():
                problems.append(f"{n.id}: empty task")
            if not n.acceptance.strip():
                problems.append(f"{n.id}: empty acceptance criteria")
            for d in n.deps:
                if d not in ids:
                    problems.append(f"{n.id}: dep {d!r} not in plan")
                if d == n.id:
                    problems.append(f"{n.id}: self-dependency")
        # Cycle check (Kahn).
        indeg = {n.id: 0 for n in self.nodes}
        children: Dict[str, List[str]] = {n.id: [] for n in self.nodes}
        for n in self.nodes:
            for d in n.deps:
                if d in indeg:
                    indeg[n.id] += 1
                    children[d].append(n.id)
        queue = [i for i, d in indeg.items() if d == 0]
        seen = 0
        while queue:
            cur = queue.pop()
            seen += 1
            for c in children[cur]:
                indeg[c] -= 1
                if indeg[c] == 0:
                    queue.append(c)
        if seen != len(self.nodes):
            problems.append("plan contains a dependency cycle")
        return problems


def format_plan(plan: Plan) -> str:
    """Human-readable DAG rendering for ``levi fleet plan``."""
    lines = [f"Objective: {plan.objective}", f"Method: {plan.method}", ""]
    for n in plan.nodes:
        deps = f"  [after: {', '.join(n.deps)}]" if n.deps else "  [root]"
        lines.append(f"  {n.id}  {n.category}{deps}")
        lines.append(f"       task: {n.task}")
        lines.append(f"       accept: {n.acceptance}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Heuristic decomposition (deterministic, hermetic)
# ---------------------------------------------------------------------------

# keyword → category hint, checked in order
_KEYWORDS: List[tuple] = [
    (("research", "investigate", "survey", "compare", "benchmark"), "research"),
    (("write", "document", "blog", "draft"), "document"),
    (("deploy", "release", "pipeline", "ci/cd"), "devops"),
    (("test", "qa", "validate"), "qa"),
    (("secure", "harden", "vulnerability", "audit"), "security"),
    (("automate", "workflow", "schedule", "cron"), "automation"),
    (("market", "campaign", "seo", "launch"), "marketing"),
    (("support", "ticket", "customer"), "support"),
    (("data", "dataset", "analytics", "metrics", "spreadsheet"), "data"),
    (("design", "ui", "interface", "mockup"), "uiux"),
    (("database", "schema", "migration"), "database"),
    (("build", "app", "implement", "feature", "code", "api", "website",
      "saas", "program", "script"), "coding"),
]


def _heuristic_categories(objective: str) -> List[str]:
    text = objective.lower()
    hits: List[str] = []
    for keywords, category in _KEYWORDS:
        if any(k in text for k in keywords) and category not in hits:
            hits.append(category)
    if not hits:
        hits = ["research"]
    return hits


def heuristic_plan(objective: str) -> Plan:
    """Deterministic keyword-routed plan. Honest first draft, not genius."""
    cats = _heuristic_categories(objective)
    nodes: List[PlanNode] = []
    seq = 0

    def add(category: str, task: str, acceptance: str,
            deps: Optional[List[str]] = None) -> str:
        nonlocal seq
        seq += 1
        nid = f"n{seq}"
        nodes.append(PlanNode(id=nid, category=category, task=task,
                             acceptance=acceptance, deps=deps or []))
        return nid

    # Always open with planning, close with verification.
    plan_id = add(
        "planning",
        f"Break down the objective into executable steps: {objective}",
        "A step list with owners and acceptance criteria exists.",
    )
    roots = [plan_id]
    if "research" in cats or len(cats) > 1:
        res_id = add(
            "research",
            f"Gather background, prior art, and evidence for: {objective}",
            "Findings are cited and summarized; gaps are named.",
            deps=[plan_id],
        )
        roots.append(res_id)

    last_ids = list(roots)
    for cat in cats:
        if cat in ("research",):
            continue
        if cat == "coding":
            # Software gets the fuller pipeline.
            arch = add(
                "architect",
                f"Design the architecture for: {objective}",
                "Components, boundaries, and data flow are documented.",
                deps=last_ids,
            )
            code = add(
                "coding",
                f"Implement per the architecture: {objective}",
                "Code exists, runs, and matches the design.",
                deps=[arch],
            )
            qa = add(
                "qa",
                f"Test the implementation: {objective}",
                "Tests pass; failures are reported precisely.",
                deps=[code],
            )
            last_ids = [qa]
        else:
            nid = add(
                cat,
                f"Execute the {cat} work for: {objective}",
                f"The {cat} deliverable is complete and reviewable.",
                deps=last_ids,
            )
            last_ids = [nid]

    add(
        "verification",
        f"Independently verify all deliverables for: {objective}",
        "Every acceptance criterion is checked; failures are specific.",
        deps=last_ids,
    )
    plan = Plan(objective=objective, nodes=nodes, method="heuristic")
    problems = plan.validate()
    if problems:  # pragma: no cover — internal consistency guard
        raise ValueError(f"heuristic plan invalid: {problems}")
    return plan


# ---------------------------------------------------------------------------
# Model-assisted decomposition (uses the existing agentic loop)
# ---------------------------------------------------------------------------

_NODE_RE = re.compile(
    r"^NODE\s+(\S+)\s*\|\s*([a-z_]+)\s*\|\s*(.+?)\s*\|\s*acceptance:\s*(.+?)"
    r"(?:\s*\|\s*after:\s*(.+))?\s*$",
    re.IGNORECASE,
)

_DECOMP_PROMPT = """You are the fleet SUPERVISOR. Decompose the user objective
into a subtask DAG. Emit ONLY lines in this exact format, one per subtask:

NODE <id> | <category> | <task> | acceptance: <criteria> | after: <id1,id2>

Rules:
- <id> like n1, n2. <category> must be one of: {categories}.
- <task> is one concrete subtask. <criteria> is how to verify it.
- "after:" lists dependency ids, or omit it for root nodes.
- No commentary, no markdown, only NODE lines.

Objective: {objective}"""


def model_plan(objective: str, provider: Any = None) -> Plan:
    """Decompose via the existing agentic loop; falls back to heuristic."""
    from levi.agent.loop import run_subtask

    cats = ", ".join(sorted(
        n for n in (
            "executive supervisor project_manager planning research coding "
            "architect uiux database devops qa security automation browser "
            "computer device communication finance payment support sales "
            "marketing data document memory learning verification fraud_risk "
            "compliance"
        ).split()
    ))
    prompt = _DECOMP_PROMPT.format(categories=cats, objective=objective)
    try:
        transcript = run_subtask(
            prompt, provider=provider, max_steps=4,
            system_prompt="You are the fleet supervisor. Emit NODE lines only.",
        )
        text = getattr(transcript, "final", "") or ""
    except Exception:
        text = ""
    nodes: List[PlanNode] = []
    for line in text.splitlines():
        m = _NODE_RE.match(line.strip())
        if not m:
            continue
        nid, cat, task, acceptance, after = m.groups()
        deps = [d.strip() for d in (after or "").split(",") if d.strip()]
        nodes.append(PlanNode(id=nid, category=cat.strip().lower(),
                              task=task.strip(),
                              acceptance=acceptance.strip(), deps=deps))
    plan = Plan(objective=objective, nodes=nodes, method="model")
    if not nodes or plan.validate():
        # Model output unusable — honest fallback, flagged as heuristic.
        return heuristic_plan(objective)
    return plan


def plan_objective(objective: str, *, use_model: bool = False,
                   provider: Any = None) -> Plan:
    """Decompose an objective into a subtask DAG."""
    if use_model:
        return model_plan(objective, provider=provider)
    return heuristic_plan(objective)


def replan_remaining(plan: Plan, failed_ids: List[str]) -> Plan:
    """One-shot replan: rebuild the remaining DAG after failures.

    Failed nodes are re-routed through the planning category as recovery
    nodes (``<id>-r``); dependents of failed nodes are re-pointed at the
    recovery nodes so the DAG stays valid. Returns a new Plan.
    """
    failed = set(failed_ids)
    remap = {fid: f"{fid}-r" for fid in failed}
    nodes: List[PlanNode] = []
    for n in plan.nodes:
        if n.id in failed:
            nodes.append(PlanNode(
                id=remap[n.id],
                category="planning",
                task=f"Recover failed subtask {n.id} ({n.category}): {n.task}",
                acceptance=n.acceptance,
                deps=[remap.get(d, d) for d in n.deps],
            ))
        else:
            nodes.append(PlanNode(
                id=n.id,
                category=n.category,
                task=n.task,
                acceptance=n.acceptance,
                deps=[remap.get(d, d) for d in n.deps],
            ))
    return Plan(objective=plan.objective + " (replanned)", nodes=nodes,
                method=plan.method + "+replan")
