"""LEVI Fleet — agent category registry (Enterprise Phase 1, charter §3).

Data-driven table of the ~30 fleet agent categories. Each category declares
a role description, a default tool subset drawn from the existing tool
registry (:mod:`levi.agent.tools`), a cost class, and a role-prompt fragment.

No category forks the tool organ: subsets are filters over the 24 built-in
tools. ``finance``/``payment`` are declared stubs — workers refuse to execute
them without explicit human approval wiring (see the control plane).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# All 24 built-in tool names from levi.agent.tools._register_builtins.
ALL_TOOLS: List[str] = [
    "affect_detect",
    "affect_state",
    "capabilities",
    "course_brief",
    "course_search",
    "delegate",
    "file_edit",
    "file_read",
    "file_write",
    "http_request",
    "lab_footprint",
    "lab_scenario",
    "memory_read",
    "memory_write",
    "news_latest",
    "news_search",
    "schedule_add",
    "schedule_list",
    "schedule_remove",
    "shell_exec",
    "skill_list",
    "skill_load",
    "web_fetch",
    "web_search",
]

# Tools that never mutate state. Read-only categories draw from this set.
READ_ONLY_TOOLS: List[str] = [
    "affect_detect",
    "affect_state",
    "capabilities",
    "course_brief",
    "course_search",
    "file_read",
    "lab_footprint",
    "lab_scenario",
    "memory_read",
    "news_latest",
    "news_search",
    "schedule_list",
    "skill_list",
    "skill_load",
    "web_fetch",
    "web_search",
]

# Relative cost units per tool call, by cost class. These are NOT dollars —
# they are budget tokens for swarm budget enforcement (charter §4).
COST_PER_CALL: Dict[str, int] = {"light": 1, "standard": 3, "heavy": 8}


@dataclass(frozen=True)
class AgentCategory:
    """One fleet agent category."""

    name: str
    role: str
    tools: List[str] = field(default_factory=list)
    cost_class: str = "standard"  # light | standard | heavy
    prompt: str = ""  # role-prompt fragment for the worker's system prompt
    stub: bool = False  # True → workers refuse without approval wiring


# name → (role, tools, cost_class, prompt fragment, stub)
_CATEGORIES: Dict[str, tuple] = {
    "executive": (
        "Coordinates the entire platform: sets priorities across swarms, "
        "resolves conflicts, owns the final outcome.",
        ["capabilities", "delegate", "memory_read", "memory_write"],
        "standard",
        "You are the EXECUTIVE agent. Coordinate, prioritize, resolve "
        "conflicts. You own the outcome.",
        False,
    ),
    "supervisor": (
        "Coordinates one user objective: decomposes it into a subtask DAG, "
        "assigns categories, tracks progress.",
        ["capabilities", "delegate", "memory_read", "memory_write"],
        "standard",
        "You are the SUPERVISOR agent. Decompose the objective into a clear "
        "subtask DAG with acceptance criteria.",
        False,
    ),
    "project_manager": (
        "Owns schedule and delivery: tracks node states, dependencies, and "
        "deadlines across a swarm run.",
        [
            "capabilities",
            "memory_read",
            "memory_write",
            "schedule_list",
            "schedule_add",
        ],
        "standard",
        "You are the PROJECT MANAGER agent. Track state, dependencies, and "
        "deadlines. Nothing slips silently.",
        False,
    ),
    "planning": (
        "Breaks objectives into executable plans with acceptance criteria.",
        ["capabilities", "memory_read", "web_search", "course_search"],
        "light",
        "You are the PLANNING agent. Produce executable plans with concrete "
        "acceptance criteria.",
        False,
    ),
    "research": (
        "Performs research, retrieval, comparison, evidence analysis, and "
        "synthesis. Read-only by design.",
        [
            "web_search",
            "web_fetch",
            "news_search",
            "news_latest",
            "course_search",
            "course_brief",
            "memory_read",
            "skill_list",
        ],
        "light",
        "You are the RESEARCH agent. Gather evidence, compare sources, "
        "synthesize. Cite what you found.",
        False,
    ),
    "coding": (
        "Creates and modifies software: writes files, runs commands, iterates on code.",
        [
            "file_read",
            "file_write",
            "file_edit",
            "shell_exec",
            "skill_load",
            "capabilities",
        ],
        "standard",
        "You are the CODING agent. Write real code, run it, read the "
        "output, fix what breaks.",
        False,
    ),
    "architect": (
        "Designs application architecture: components, boundaries, data "
        "flow. Read-only — it designs, others build.",
        ["file_read", "web_search", "capabilities", "memory_read"],
        "standard",
        "You are the SOFTWARE ARCHITECT agent. Design clean component "
        "boundaries and data flow before anyone builds.",
        False,
    ),
    "uiux": (
        "Creates interfaces and design systems: layouts, components, "
        "interaction flows.",
        ["file_read", "file_write", "web_search", "capabilities"],
        "standard",
        "You are the UI/UX agent. Design interfaces that are clear, "
        "consistent, and usable.",
        False,
    ),
    "database": (
        "Designs schemas, migrations, queries, and data architecture.",
        ["file_read", "file_write", "shell_exec", "capabilities"],
        "standard",
        "You are the DATABASE agent. Design schemas and migrations that "
        "are correct and reversible.",
        False,
    ),
    "devops": (
        "Handles infrastructure, containers, CI/CD, deployment, and observability.",
        ["shell_exec", "file_read", "file_write", "http_request", "capabilities"],
        "heavy",
        "You are the DEVOPS agent. Ship reliably: builds green, deploys "
        "clean, rollbacks ready.",
        False,
    ),
    "qa": (
        "Creates tests and validates systems against acceptance criteria.",
        ["file_read", "shell_exec", "lab_scenario", "capabilities"],
        "standard",
        "You are the QA agent. Prove it works: write tests, run them, "
        "report failures precisely.",
        False,
    ),
    "security": (
        "Evaluates security risks: reviews code and configs for "
        "vulnerabilities, proposes hardening.",
        ["file_read", "shell_exec", "web_search", "skill_load", "capabilities"],
        "heavy",
        "You are the SECURITY agent. Think like a defender: find the "
        "weakness, propose the hardening.",
        False,
    ),
    "automation": (
        "Creates workflows: scheduled jobs, event-driven automations, "
        "multi-step routines.",
        [
            "shell_exec",
            "schedule_add",
            "schedule_list",
            "schedule_remove",
            "file_read",
            "file_write",
        ],
        "standard",
        "You are the AUTOMATION agent. Build workflows that run reliably "
        "without babysitting.",
        False,
    ),
    "browser": (
        "Performs controlled browser tasks: fetches pages, extracts "
        "structured content.",
        ["web_fetch", "web_search", "http_request", "capabilities"],
        "standard",
        "You are the BROWSER agent. Fetch pages, extract structure, "
        "report what you found.",
        False,
    ),
    "computer": (
        "Interacts with authorized computer interfaces: runs commands and "
        "scripts in the sandbox.",
        ["shell_exec", "file_read", "file_write", "capabilities"],
        "standard",
        "You are the COMPUTER agent. Operate the machine through "
        "authorized interfaces only.",
        False,
    ),
    "device": (
        "Coordinates authorized device capabilities across the device "
        "graph. Exposes only explicitly granted capabilities.",
        ["capabilities", "shell_exec"],
        "standard",
        "You are the DEVICE agent. Use only explicitly granted device "
        "capabilities. Never bypass OS security.",
        False,
    ),
    "communication": (
        "Handles authorized email, messaging, notifications, and other "
        "communications. Drafts are reviewed before sending.",
        ["web_fetch", "http_request", "memory_read", "capabilities"],
        "standard",
        "You are the COMMUNICATION agent. Draft clearly; never send "
        "sensitive communications without approval.",
        False,
    ),
    "finance": (
        "Performs financial analysis and authorized commerce workflows. "
        "STUB: refuses without explicit human approval wiring — real money "
        "movement stays HITL-gated per the control plane.",
        [
            "news_search",
            "web_search",
            "web_fetch",
            "file_read",
            "memory_read",
            "capabilities",
        ],
        "heavy",
        "You are the FINANCE agent. Analyze, never move money without "
        "explicit human approval.",
        True,
    ),
    "payment": (
        "Coordinates payment operations. STUB: refuses without explicit "
        "human approval wiring — the secure payment engine (phase 5) owns "
        "real transactions.",
        [],
        "heavy",
        "You are the PAYMENT agent. You do not move money. Every payment "
        "requires explicit human approval through the payment engine.",
        True,
    ),
    "support": (
        "Handles customer-service workflows: classifies, retrieves "
        "context, drafts responses.",
        ["memory_read", "web_search", "course_search", "affect_detect", "capabilities"],
        "light",
        "You are the SUPPORT agent. Classify the issue, gather context, "
        "draft a helpful response.",
        False,
    ),
    "sales": (
        "Supports legitimate sales and customer acquisition workflows. "
        "No spam, no deception, no fake engagement.",
        ["web_search", "memory_read", "file_read", "capabilities"],
        "light",
        "You are the SALES agent. Legitimate outreach only — no spam, "
        "no deception, no fake reviews.",
        False,
    ),
    "marketing": (
        "Creates marketing assets and campaigns subject to user/business "
        "approval. No spam, impersonation, or deceptive marketing.",
        ["web_search", "file_write", "file_read", "capabilities"],
        "light",
        "You are the MARKETING agent. Create honest assets; campaigns "
        "need approval before they go out.",
        False,
    ),
    "negotiation": (
        "Leads structured negotiations: prepares positions, drafts "
        "terms, tracks concessions. Never commits the user without "
        "approval.",
        ["memory_read", "web_search", "file_read", "capabilities"],
        "light",
        "You are the NEGOTIATION agent. Prepare positions and draft "
        "terms; never commit without approval.",
        False,
    ),
    "data": (
        "Analyzes structured and unstructured data: queries, aggregates, summarizes.",
        ["file_read", "shell_exec", "web_search", "capabilities"],
        "standard",
        "You are the DATA agent. Query, aggregate, summarize — show your working.",
        False,
    ),
    "document": (
        "Creates and analyzes documents: reports, specs, briefs. "
        "Read/write, no execution.",
        ["file_read", "file_write", "file_edit", "web_search", "capabilities"],
        "light",
        "You are the DOCUMENT agent. Write clear documents; analyze thoroughly.",
        False,
    ),
    "memory": (
        "Manages user/project knowledge: stores, retrieves, and curates "
        "memory entries.",
        ["memory_read", "memory_write", "capabilities"],
        "light",
        "You are the MEMORY agent. Store what matters, retrieve what "
        "helps, curate ruthlessly.",
        False,
    ),
    "learning": (
        "Evaluates interactions and proposes system improvements. Feeds "
        "the growth loop, never raw private content.",
        [
            "memory_read",
            "memory_write",
            "lab_footprint",
            "lab_scenario",
            "capabilities",
        ],
        "light",
        "You are the LEARNING agent. Find the pattern, propose the "
        "improvement, respect privacy.",
        False,
    ),
    "verification": (
        "Independently verifies results against acceptance criteria. "
        "Read-only — it judges, never builds.",
        ["file_read", "web_search", "web_fetch", "capabilities", "lab_scenario"],
        "light",
        "You are the VERIFICATION agent. Check the result against its "
        "acceptance criteria. Be strict and specific about failures.",
        False,
    ),
    "fraud_risk": (
        "Detects suspicious transactions and anomalous behavior. "
        "Read-only analysis; flags, never acts.",
        ["file_read", "web_search", "memory_read", "capabilities"],
        "standard",
        "You are the FRAUD/RISK agent. Flag anomalies with evidence. "
        "You detect; humans decide.",
        False,
    ),
    "compliance": (
        "Checks workflows against configurable legal, regulatory, "
        "contractual, and platform requirements.",
        ["file_read", "web_search", "memory_read", "skill_load", "capabilities"],
        "standard",
        "You are the COMPLIANCE agent. Check the workflow against the "
        "stated requirements and cite the clause.",
        False,
    ),
    # -- NeighborOS product-line roles (PL-01) ---------------------------------
    # The local-services workforce catalog, expressible 1:1 as fleet
    # categories (docs/PRODUCT_LINES.md). fraud_detector -> fraud_risk and
    # compliance_gate -> compliance already exist above.
    "dispatch": (
        "NeighborOS dispatch matcher: matches service jobs to trusted "
        "local workers from job requirements and worker records. "
        "Proposes matches; never assigns without approval.",
        ["memory_read", "file_read", "web_search", "capabilities"],
        "standard",
        "You are the DISPATCH agent. Match the job to the right worker "
        "from requirements and records. Propose; never assign unapproved.",
        False,
    ),
    "bidding": (
        "NeighborOS bid engine: estimates job cost from descriptions and "
        "photos, benchmarks against past jobs. Estimates are analysis, "
        "never price commitments.",
        ["file_read", "web_search", "memory_read", "capabilities"],
        "standard",
        "You are the BIDDING agent. Estimate honestly from evidence; "
        "show your working. Estimates are not commitments.",
        False,
    ),
    "coach": (
        "NeighborOS business coach: advises workers on growing their "
        "business from their living record -- reputation, repeat rate, "
        "gaps. Advice only; never touches another worker's private data.",
        ["memory_read", "file_read", "web_search", "capabilities"],
        "light",
        "You are the COACH agent. Give practical, specific business "
        "advice grounded in the worker's own record.",
        False,
    ),
    "guardian": (
        "NeighborOS property guardian: maintains living property "
        "maintenance records, schedules reminders, flags overdue work. "
        "Record writes and reminders are fine; customer outreach needs "
        "approval.",
        [
            "memory_read",
            "memory_write",
            "schedule_list",
            "schedule_add",
            "file_read",
            "capabilities",
        ],
        "standard",
        "You are the GUARDIAN agent. Keep the property record alive: "
        "log maintenance, schedule reminders, flag what's overdue.",
        False,
    ),
}


def list_categories() -> List[AgentCategory]:
    """All fleet categories, sorted by name."""
    out = []
    for name in sorted(_CATEGORIES):
        role, tools, cost_class, prompt, stub = _CATEGORIES[name]
        out.append(
            AgentCategory(
                name=name,
                role=role,
                tools=list(tools),
                cost_class=cost_class,
                prompt=prompt,
                stub=stub,
            )
        )
    return out


def get_category(name: str) -> AgentCategory:
    """Look up one category by name; raises KeyError on unknown."""
    try:
        role, tools, cost_class, prompt, stub = _CATEGORIES[name]
    except KeyError:
        raise KeyError(
            f"unknown fleet category {name!r}; valid categories: {sorted(_CATEGORIES)}"
        ) from None
    return AgentCategory(
        name=name,
        role=role,
        tools=list(tools),
        cost_class=cost_class,
        prompt=prompt,
        stub=stub,
    )


def cost_per_call(cost_class: str) -> int:
    """Relative cost units per tool call for a cost class (not dollars)."""
    try:
        return COST_PER_CALL[cost_class]
    except KeyError:
        raise KeyError(
            f"unknown cost class {cost_class!r}; valid classes: {sorted(COST_PER_CALL)}"
        ) from None


def validate() -> List[str]:
    """Check registry integrity; returns a list of problems (empty = OK)."""
    problems: List[str] = []
    known = set(ALL_TOOLS)
    for name in _CATEGORIES:
        role, tools, cost_class, prompt, stub = _CATEGORIES[name]
        if cost_class not in COST_PER_CALL:
            problems.append(f"{name}: unknown cost class {cost_class!r}")
        if not role.strip():
            problems.append(f"{name}: empty role")
        if not prompt.strip():
            problems.append(f"{name}: empty prompt fragment")
        for t in tools:
            if t not in known:
                problems.append(f"{name}: unknown tool {t!r}")
        if stub and "shell_exec" in tools:
            problems.append(f"{name}: stub category must not hold shell_exec")
    return problems


# ---------------------------------------------------------------------------
# Tool risk classification (blueprint §8–9, adapted to stdlib)
#
# Mirrors the enterprise permission engine's risk levels using LEVI's
# existing PolicyEngine vocabulary: INFO(0) < LOW(1) < MODERATE(2) <
# HIGH(3) < CRITICAL(4). The universal approval engine itself is phase 2;
# here the classification drives audit logging and consent behavior.
# ---------------------------------------------------------------------------

# Tools whose handlers declare requires_confirmation=True in
# levi.agent.tools (state-changing or egress).
GATED_TOOLS = frozenset(
    {
        "file_edit",
        "file_write",
        "http_request",
        "schedule_add",
        "shell_exec",
        "web_fetch",
    }
)

# Mutating but ungated.
LOW_RISK_MUTATING = frozenset(
    {
        "delegate",
        "memory_write",
        "schedule_remove",
    }
)


def tool_risk_level(tool_name: str) -> int:
    """Risk level for a tool: 0=INFO, 1=LOW, 2=MODERATE.

    (HIGH/CRITICAL are reserved for the phase-2 approval engine —
    e.g. payments. Fleet workers never reach them: finance/payment are
    stubs that refuse first.)
    """
    if tool_name in GATED_TOOLS:
        return 2
    if tool_name in LOW_RISK_MUTATING:
        return 1
    return 0


_RISK_NAMES = {0: "info", 1: "low", 2: "moderate"}


def tool_risk_name(tool_name: str) -> str:
    return _RISK_NAMES[tool_risk_level(tool_name)]
