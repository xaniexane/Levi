"""LEVI Fleet — budgeted swarm runner (Enterprise Phase 1, §4).

Executes a supervisor plan DAG with ephemeral workers under hard budget
enforcement. Charter budgets:

- ``max_depth`` — recursion depth ceiling (no uncontrolled spawning)
- ``max_agents`` — total workers spawned per run
- ``max_time_seconds`` — wall-clock deadline
- ``max_tool_calls`` — total tool calls across all workers
- ``max_cost_units`` — cost = Σ tool calls × cost-class weight (relative
  units, NOT dollars — see :mod:`levi.fleet.categories`)

Budgets exceeded → the swarm halts with a structured report, never
silently. Workers share a thread-safe blackboard, can request
verification, report failures, and the run replans at most once.

Reuses: :func:`levi.agent.loop.run_subtask`, :class:`levi.agent.tools.ToolRegistry`,
category tool subsets. Does NOT fork them.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.fleet.categories import (
    AgentCategory,
    cost_per_call,
    get_category,
    tool_risk_level,
    tool_risk_name,
)
from levi.fleet.supervisor import Plan, PlanNode, replan_remaining
from levi.fleet.verify import verify_node
from levi.policy.gates import RiskLevel

try:
    from levi.control.approvals import ApprovalBlocked
except Exception:  # control plane unavailable: approvals degrade to refusal

    class ApprovalBlocked(Exception):  # type: ignore[no-redef]
        def __init__(self, record=None, reason=""):
            super().__init__(reason or "approval blocked")
            self.record = record or {}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FleetError(Exception):
    """Base fleet error."""


class BudgetExceeded(FleetError):
    """A charter budget was hit. Carries a structured reason."""

    def __init__(self, budget: str, limit: Any, spent: Any):
        super().__init__(f"budget exceeded: {budget} (limit={limit}, spent={spent})")
        self.budget = budget
        self.limit = limit
        self.spent = spent


class FleetRefusal(FleetError):
    """A worker refused: stub category without approval wiring, etc."""


class MaxDepthExceeded(FleetError):
    """Explicit sub-swarm spawn beyond max_depth."""


# ---------------------------------------------------------------------------
# Budgets / ledger / blackboard
# ---------------------------------------------------------------------------


@dataclass
class SwarmBudgets:
    max_depth: int = 3
    max_agents: int = 12
    max_time_seconds: int = 600
    max_tool_calls: int = 200
    max_cost_units: int = 400

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_depth": self.max_depth,
            "max_agents": self.max_agents,
            "max_time_seconds": self.max_time_seconds,
            "max_tool_calls": self.max_tool_calls,
            "max_cost_units": self.max_cost_units,
        }


@dataclass
class Ledger:
    """Thread-safe spend counters + per-call audit log for one run."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    agents_spawned: int = 0
    tool_calls: int = 0
    cost_units: int = 0
    tool_log: List[Dict[str, Any]] = field(default_factory=list)

    def log_tool(self, tool: str, category: str, risk: str, ok: bool) -> None:
        with self.lock:
            self.tool_log.append(
                {
                    "tool": tool,
                    "category": category,
                    "risk": risk,
                    "ok": ok,
                }
            )

    def risk_summary(self) -> Dict[str, int]:
        with self.lock:
            summary: Dict[str, int] = {}
            for entry in self.tool_log:
                summary[entry["risk"]] = summary.get(entry["risk"], 0) + 1
            return summary

    def to_dict(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "agents": self.agents_spawned,
                "tool_calls": self.tool_calls,
                "cost_units": self.cost_units,
                "by_risk": {
                    k: sum(1 for e in self.tool_log if e["risk"] == k)
                    for k in ("info", "low", "moderate")
                },
            }


class Blackboard:
    """Thread-safe shared structured state + artifact exchange."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {}

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._state.get(key, default)

    def publish_artifact(self, name: str, payload: Any) -> None:
        self.put(f"artifact:{name}", payload)

    def snapshot(self, limit: int = 4000) -> Dict[str, Any]:
        with self._lock:
            snap = dict(self._state)
        text = json.dumps(snap, default=str)
        if len(text) > limit:
            return {"_truncated": True, "preview": text[:limit]}
        return snap


@dataclass
class WorkerContext:
    """Per-run agent context (blueprint §6, stdlib).

    ``permissions`` is the explicit grant for this worker — the category's
    tool subset. A tool outside the grant is refused, never executed.
    ``max_steps`` bounds the worker's agentic loop.
    """

    blackboard: Blackboard
    ledger: Ledger
    budgets: SwarmBudgets
    run_id: str
    depth: int = 0
    provider: Any = None
    permissions: List[str] = field(default_factory=list)
    max_steps: int = 8
    user_id: str = "local"
    tenant_id: str = "local"
    # Universal approval engine (enterprise phase 2): when set, MODERATE+
    # tool calls route through it instead of executing ad hoc.
    # ``approval_timeout``: 0 = non-blocking (pending → escalate at once);
    # >0 = wait that many seconds for a human decision (cross-process:
    # the CLI can decide while the worker waits).
    approval_engine: Any = None
    approval_timeout: float = 0.0

    def check_permission(self, tool_name: str) -> None:
        """Permission-engine check (blueprint §6/§9, phase-1 form).

        The category subset is the grant. Anything outside it → refusal.
        The universal approval engine (L0–L4 with real-time approval UI)
        is enterprise phase 2; here, MODERATE+ tools without consent raise
        through the tool organ's own confirmation gate and escalate.
        """
        if self.permissions and tool_name not in self.permissions:
            raise FleetRefusal(
                f"tool {tool_name!r} is outside this worker's permission "
                f"grant {self.permissions}"
            )


# ---------------------------------------------------------------------------
# Counting registry (decorates, never forks, ToolRegistry)
# ---------------------------------------------------------------------------


def _check_budgets(ledger: Ledger, budgets: SwarmBudgets, deadline: float) -> None:
    with ledger.lock:
        calls, cost = ledger.tool_calls, ledger.cost_units
    if calls >= budgets.max_tool_calls:
        raise BudgetExceeded("max_tool_calls", budgets.max_tool_calls, calls)
    if cost >= budgets.max_cost_units:
        raise BudgetExceeded("max_cost_units", budgets.max_cost_units, cost)
    if time.time() >= deadline:
        raise BudgetExceeded(
            "max_time_seconds",
            budgets.max_time_seconds,
            round(time.time() - (deadline - budgets.max_time_seconds), 1),
        )


def make_counting_registry(
    tool_names: List[str], category: AgentCategory, ctx: WorkerContext, deadline: float
):
    """Build a subset ToolRegistry that counts calls and enforces budgets.

    The ``delegate`` tool is always excluded from worker registries:
    recursion happens only through the explicit, depth-counted
    :func:`spawn_subswarm` API.

    Every call is permission-checked against the worker's grant and
    audit-logged with its risk level (blueprint §8–9).
    """
    from levi.agent.tools import ToolRegistry, build_default_registry

    full = build_default_registry()
    unit = cost_per_call(category.cost_class)

    class CountingRegistry(ToolRegistry):
        def execute(self, name: str, args: dict, exec_ctx: Any = None):  # type: ignore[override]
            ctx.check_permission(name)
            risk_level = tool_risk_level(name)
            if risk_level >= 2 and ctx.approval_engine is not None:
                _guard_tool_call(ctx, category, name, args or {}, risk_level)
            _check_budgets(ctx.ledger, ctx.budgets, deadline)
            result = super().execute(name, args, exec_ctx)
            risk = tool_risk_name(name)
            with ctx.ledger.lock:
                ctx.ledger.tool_calls += 1
                ctx.ledger.cost_units += unit
                calls, cost = ctx.ledger.tool_calls, ctx.ledger.cost_units
            ctx.ledger.log_tool(name, category.name, risk, bool(result.ok))
            # Post-call check is strictly-greater: it exists only to catch
            # a multi-thread overshoot race. Pre-call >= keeps "exactly N
            # calls allowed" semantics for max_tool_calls=N.
            if calls > ctx.budgets.max_tool_calls:
                raise BudgetExceeded(
                    "max_tool_calls", ctx.budgets.max_tool_calls, calls
                )
            if cost > ctx.budgets.max_cost_units:
                raise BudgetExceeded("max_cost_units", ctx.budgets.max_cost_units, cost)
            return result

    reg = CountingRegistry()
    for tname in tool_names:
        if tname == "delegate":
            continue  # depth is enforced via spawn_subswarm, not delegate
        tool = full.get(tname)
        if tool is not None:
            reg.register(tool)
    return reg


def _guard_tool_call(
    ctx: WorkerContext,
    category: AgentCategory,
    name: str,
    args: Dict[str, Any],
    risk_level: int,
) -> None:
    """Route a MODERATE+ tool call through the universal approval engine.

    Uses :meth:`ApprovalEngine.require`: approved → proceed; pending or
    denied → :class:`ApprovalBlocked` and the tool never executes.
    ``approval_timeout=0`` (default) escalates at once; a positive
    timeout waits for a human (the CLI decides cross-process); an
    ``approve_once`` decision is claimed exactly once on the next call.
    """
    arg_preview = ", ".join(f"{k}={str(v)[:60]}" for k, v in sorted(args.items()))
    ctx.approval_engine.require(
        description=f"fleet tool call: {name}({arg_preview})",
        risk_level=RiskLevel(risk_level),
        reason=(
            f"worker of category {category.name!r} (run {ctx.run_id}) "
            f"invoked a {tool_risk_name(name)}-risk tool"
        ),
        affected_systems=[f"tool:{name}"],
        estimated_impact=f"args: {arg_preview or '(none)'}",
        reversible=name not in ("shell_exec", "file_write", "file_edit"),
        action_key=name,
        workflow_key=ctx.run_id,
        task_id=ctx.run_id,
        user_id=ctx.user_id,
        timeout=ctx.approval_timeout or None,
    )


def select_worker_provider(category: AgentCategory, ctx: WorkerContext) -> Any:
    """Minimal honest model router (blueprint §7, phase-1 form).

    Light (read-only, low-complexity) work stays on the local provider:
    cheapest and most private. Everything else uses the run's provider
    (default: LEVI's shared provider chain). Full cost-aware routing with
    token estimates and quality thresholds is enterprise phase 2.
    """
    if category.cost_class == "light":
        return "local"
    return ctx.provider


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

WorkerFn = Callable[[PlanNode, AgentCategory, WorkerContext], Dict[str, Any]]


def default_worker(
    node: PlanNode, category: AgentCategory, ctx: WorkerContext
) -> Dict[str, Any]:
    """Run one subtask through the existing agentic loop.

    Stub categories (finance/payment) refuse: real money movement stays
    HITL-gated per the control plane.
    """
    if category.stub:
        raise FleetRefusal(
            f"category {category.name!r} is a stub: refusing without "
            "explicit human approval wiring. Real money movement stays "
            "HITL-gated per the control plane (enterprise phase 2)."
        )
    from levi.agent.loop import run_subtask

    registry = make_counting_registry(
        category.tools,
        category,
        ctx,
        deadline=time.time() + ctx.budgets.max_time_seconds,
    )
    ctx.permissions = [t for t in category.tools if t != "delegate"]
    board = ctx.blackboard.snapshot()
    system_prompt = (
        f"{category.prompt}\n\n"
        f"You are a fleet worker (run {ctx.run_id}, node {node.id}). "
        "You are ephemeral: do your subtask, report, terminate. "
        "Acceptance criteria for your subtask:\n"
        f"{node.acceptance}\n\n"
        f"Shared blackboard state:\n{json.dumps(board, default=str)[:3000]}\n\n"
        "Finish with a concise summary of what you did and the outcome."
    )
    transcript = run_subtask(
        node.task,
        registry=registry,
        max_steps=ctx.max_steps,
        system_prompt=system_prompt,
        provider=select_worker_provider(category, ctx),
    )
    with ctx.ledger.lock:
        calls = ctx.ledger.tool_calls
    return {
        "ok": transcript.ok,
        "summary": transcript.final or transcript.error or "",
        "artifacts": [],
        "provider": transcript.provider_name,
        "ledger_tool_calls": calls,
    }


# ---------------------------------------------------------------------------
# Explicit sub-swarm spawning (depth-counted)
# ---------------------------------------------------------------------------


def spawn_subswarm(
    objective: str, *, depth: int, budgets: SwarmBudgets, **kwargs: Any
) -> Dict[str, Any]:
    """Spawn a child swarm. Refused beyond ``max_depth`` — never silent."""
    if depth > budgets.max_depth:
        raise MaxDepthExceeded(
            f"sub-swarm spawn refused: depth {depth} exceeds "
            f"max_depth={budgets.max_depth}"
        )
    runner = SwarmRunner(budgets=budgets, depth=depth, **kwargs)
    return runner.run(objective)


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------


def _fleet_dir() -> Path:
    d = Path.home() / ".levi" / "fleet" / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


class SwarmRunner:
    """Executes a plan DAG under budget with verification and one replan."""

    def __init__(
        self,
        budgets: Optional[SwarmBudgets] = None,
        depth: int = 0,
        worker_fn: Optional[WorkerFn] = None,
        verify_fn: Optional[Callable[..., Any]] = None,
        semantic_verify: bool = False,
        provider: Any = None,
        approval_engine: Any = None,
        approval_timeout: float = 0.0,
    ) -> None:
        self.budgets = budgets or SwarmBudgets()
        self.depth = depth
        self.worker_fn = worker_fn or default_worker
        self.verify_fn = verify_fn
        self.semantic_verify = semantic_verify
        self.provider = provider
        # Universal approval engine (phase 2): MODERATE+ tool calls in
        # workers route through it. ``approval_timeout=0`` escalates at
        # once; pass >0 to wait for a human decision mid-run.
        if approval_engine is None:
            try:
                from levi.control.approvals import ApprovalEngine

                approval_engine = ApprovalEngine()
            except Exception:
                approval_engine = None
        self.approval_engine = approval_engine
        self.approval_timeout = approval_timeout

    # -- public API ------------------------------------------------------

    def run(self, objective: str | Plan, plan: Optional[Plan] = None) -> Dict[str, Any]:
        """Run an objective (or a prebuilt Plan). Returns a structured report."""
        from levi.fleet.supervisor import plan_objective

        the_plan = (
            plan
            if plan is not None
            else (
                objective if isinstance(objective, Plan) else plan_objective(objective)
            )
        )
        run_id = uuid.uuid4().hex[:12]
        blackboard = Blackboard()
        ledger = Ledger()
        deadline = time.time() + self.budgets.max_time_seconds
        ctx = WorkerContext(
            blackboard=blackboard,
            ledger=ledger,
            budgets=self.budgets,
            run_id=run_id,
            depth=self.depth,
            provider=self.provider,
            approval_engine=self.approval_engine,
            approval_timeout=self.approval_timeout,
        )
        report = self._execute(
            the_plan,
            ctx,
            deadline,
            run_id,
            objective if isinstance(objective, str) else the_plan.objective,
        )
        self._persist(run_id, report)
        self._record_ledger(run_id, the_plan, report, ctx)
        return report

    @staticmethod
    def load(run_id: str) -> Optional[Dict[str, Any]]:
        path = _fleet_dir() / f"{run_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    # -- internals -------------------------------------------------------

    def _persist(self, run_id: str, report: Dict[str, Any]) -> None:
        # Decision journal for the fleet: every run is recorded.
        (_fleet_dir() / f"{run_id}.json").write_text(
            json.dumps(report, indent=2, default=str)
        )

    def _record_ledger(
        self, run_id: str, plan: Plan, report: Dict[str, Any], ctx: WorkerContext
    ) -> None:
        """Write the run into the decision ledger (blueprint §15).

        Never fatal: ledger failures must not break a swarm run.
        """
        try:
            from levi.control.ledger import LedgerWriter
            from levi.control.routing import classify_complexity
        except Exception:
            return
        try:
            ledger = LedgerWriter()
            ledger.record_task(
                run_id,
                objective=report.get("objective", ""),
                user_id=ctx.user_id,
                tenant_id=ctx.tenant_id,
                plan_version=str(plan.version if hasattr(plan, "version") else "1"),
                status="running",
            )
            spent = report.get("budgets", {}).get("spent", {})
            nodes = {n.id: n for n in plan.nodes}
            for nid, n in report.get("nodes", {}).items():
                node = nodes.get(nid)
                task_text = node.task if node is not None else ""
                complexity, _ = classify_complexity(task_text)
                verification = n.get("verification", "")
                ledger.record_step(
                    run_id,
                    agent=f"fleet:{n.get('category', '?')}",
                    category=n.get("category", ""),
                    task_class=complexity,
                    model=str(n.get("provider", "") or report.get("provider", "")),
                    decision_summary=(
                        f"fleet worker executed plan node: {task_text[:300]}"
                    ),
                    action=task_text[:500],
                    expected_result=(node.acceptance if node is not None else ""),
                    actual_result=str(n.get("summary", ""))[:2000],
                    verification={"notes": verification},
                    error=str(n.get("error", ""))[:1000],
                    outcome=str(n.get("status", "")),
                )
            ledger.set_task_status(
                run_id,
                str(report.get("status", "completed")),
                cost_units=float(spent.get("cost_units", 0) or 0),
                latency_ms=float(spent.get("seconds", 0) or 0) * 1000.0,
            )
        except Exception:
            pass  # ledger is telemetry, never load-bearing

    def _execute(
        self,
        plan: Plan,
        ctx: WorkerContext,
        deadline: float,
        run_id: str,
        objective: str,
    ) -> Dict[str, Any]:
        started = time.time()
        nodes: Dict[str, PlanNode] = {n.id: n for n in plan.nodes}
        status: Dict[str, str] = {nid: "pending" for nid in nodes}
        results: Dict[str, Dict[str, Any]] = {}
        escalations: List[Dict[str, Any]] = []
        halt_reason: Optional[Dict[str, Any]] = None
        replanned = False
        status_lock = threading.Lock()

        def set_status(nid: str, value: str) -> None:
            with status_lock:
                status[nid] = value

        def ready() -> List[str]:
            out = []
            for nid, node in nodes.items():
                if status[nid] != "pending":
                    continue
                dep_status = [status[d] for d in node.deps]
                if all(s == "ok" for s in dep_status):
                    out.append(nid)
                elif any(
                    s
                    in (
                        "failed",
                        "escalated",
                        "skipped",
                        "refused",
                        "awaiting_approval",
                    )
                    for s in dep_status
                ):
                    set_status(nid, "skipped")
            return [nid for nid in out if status[nid] == "pending"]

        def run_node(nid: str) -> None:
            node = nodes[nid]
            category = get_category(node.category)
            set_status(nid, "running")
            # Budget gate: agents.
            with ctx.ledger.lock:
                if ctx.ledger.agents_spawned >= self.budgets.max_agents:
                    raise BudgetExceeded(
                        "max_agents", self.budgets.max_agents, ctx.ledger.agents_spawned
                    )
                ctx.ledger.agents_spawned += 1
            _check_budgets(ctx.ledger, ctx.budgets, deadline)

            attempts = 0
            while attempts < 2:  # initial try + exactly one retry
                attempts += 1
                try:
                    result = self.worker_fn(node, category, ctx)
                except (BudgetExceeded, MaxDepthExceeded):
                    raise
                except FleetRefusal as exc:
                    results[nid] = {
                        "status": "refused",
                        "error": str(exc),
                        "attempts": attempts,
                    }
                    set_status(nid, "refused")
                    escalations.append(
                        {"node": nid, "reason": "refused", "detail": str(exc)}
                    )
                    return
                except ApprovalBlocked as exc:
                    approval_id = exc.record.get("id", "?")
                    results[nid] = {
                        "status": "awaiting_approval",
                        "approval_id": approval_id,
                        "error": str(exc),
                        "attempts": attempts,
                    }
                    set_status(nid, "awaiting_approval")
                    escalations.append(
                        {
                            "node": nid,
                            "reason": "awaiting_approval",
                            "approval_id": approval_id,
                            "detail": (
                                f"decide with: levi approve approve {approval_id}"
                            ),
                        }
                    )
                    return
                except Exception as exc:  # worker blew up
                    result = {
                        "ok": False,
                        "summary": "",
                        "error": f"worker exception: {exc}",
                        "artifacts": [],
                    }
                # Publish artifacts to the blackboard.
                for art in result.get("artifacts") or []:
                    name = art.get("name") if isinstance(art, dict) else art
                    if name:
                        ctx.blackboard.publish_artifact(
                            name, art if isinstance(art, dict) else {}
                        )
                verification = verify_node(
                    node.to_dict(),
                    result,
                    ctx.blackboard,
                    judge=self.verify_fn,
                    semantic=self.semantic_verify,
                    provider=ctx.provider,
                )
                if verification.ok:
                    results[nid] = {
                        "status": "ok" if attempts == 1 else "ok_after_retry",
                        "category": node.category,
                        "summary": result.get("summary", ""),
                        "attempts": attempts,
                        "verification": verification.notes,
                    }
                    set_status(nid, "ok")
                    return
                if attempts >= 2:
                    results[nid] = {
                        "status": "escalated",
                        "category": node.category,
                        "summary": result.get("summary", ""),
                        "attempts": attempts,
                        "verification": verification.notes,
                    }
                    set_status(nid, "escalated")
                    escalations.append(
                        {
                            "node": nid,
                            "reason": "verification",
                            "detail": verification.notes,
                        }
                    )

        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                while True:
                    batch = ready()
                    if not batch:
                        break
                    futures = {pool.submit(run_node, nid): nid for nid in batch}
                    for fut in as_completed(futures):
                        fut.result()  # raises BudgetExceeded outward
                    # One replan after a wave with failures.
                    failed = [
                        nid for nid, s in status.items() if s in ("failed", "escalated")
                    ]
                    if failed and not replanned:
                        recovery = replan_remaining(plan, failed)
                        for rn in recovery.nodes:
                            if rn.id not in nodes:
                                nodes[rn.id] = rn
                                status[rn.id] = "pending"
                        replanned = True
        except (BudgetExceeded, MaxDepthExceeded) as exc:
            halt_reason = {
                "type": "budget",
                "budget": getattr(exc, "budget", "max_depth"),
                "detail": str(exc),
            }
        except Exception as exc:  # pragma: no cover — defensive
            halt_reason = {"type": "error", "detail": str(exc)}

        # Anything still pending can never run → skipped.
        for nid, s in status.items():
            if s in ("pending", "running"):
                status[nid] = "skipped"
                results.setdefault(nid, {"status": "skipped"})

        elapsed = round(time.time() - started, 2)
        if halt_reason:
            final_status = "halted"
        elif escalations:
            final_status = "completed_with_escalations"
        else:
            final_status = "completed"
        return {
            "run_id": run_id,
            "objective": objective,
            "status": final_status,
            "halt_reason": halt_reason,
            "depth": self.depth,
            "nodes": {
                nid: {"status": s, **results.get(nid, {})} for nid, s in status.items()
            },
            "budgets": {
                "limits": self.budgets.to_dict(),
                "spent": {**ctx.ledger.to_dict(), "seconds": elapsed},
            },
            "tool_audit": list(ctx.ledger.tool_log),
            "escalations": escalations,
            "replanned": replanned,
        }
