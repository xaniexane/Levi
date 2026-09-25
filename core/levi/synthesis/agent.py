"""Synthesis agentic loop — agency as an architecture pillar, not a bolt-on.

One goal flows through five honest stages::

    perceive → reason → act → verify → receipt

* **perceive** — gather local context: memory recall, growth learnings,
  live subsystem status. Best-effort; never fatal.
* **reason** — the synthesis :class:`~levi.synthesis.mind.SynthesisMind`
  deliberates first (native brain consulted, rules engine decides).
  The verdict frames the task the loop acts on.
* **act** — the canonical step-level tool loop
  (:func:`levi.agent.loop.run_subtask`) with the deterministic offline
  planner (``provider="local"``) and the real sandboxed
  :class:`~levi.agent.tools.ToolRegistry`. Gated tools
  (file_write, file_edit, shell_exec, …) require explicit ``consent`` —
  that flag IS the Permission step of
  Plan → Preview → Permission → Execute → Verify → Receipt.
  Without it the loop ends honestly at the gate; it never retries a
  denied gate.
* **verify** — the transcript is inspected: steps taken, tools called,
  gates hit, outcome ok or not. No greenwashing.
* **receipt** — an append-only JSONL receipt lands in
  ``~/.levi/synthesis/receipts.jsonl`` (or ``$LEVI_SYNTHESIS_DIR`` when the
  operator redirects the front door's state). Every run leaves a trail.

The whole run executes inside
:class:`~levi.synthesis.offline.OfflineGuard`: zero network, enforced,
not promised. Network-shaped tools (web_search, web_fetch,
http_request, news_*) fail closed under the guard and the receipt says
so plainly.

Delegation (:func:`delegate_goals`) fans one goal out to bounded
sub-runs — one coordinator, N workers, one merged receipt. Scheduling
(:func:`schedule_goal` / :func:`tick_schedules`) is a small local
interval store; the heavy-duty timed choreography already lives in
:mod:`levi.copper` and the daemon kernel.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.synthesis.config import SynthesisConfig
from levi.synthesis.mind import ask as mind_ask
from levi.synthesis.offline import OfflineGuard


def _default_config() -> SynthesisConfig:
    return SynthesisConfig.load()


# Re-entrancy guard for the B6 scan route: the middle team's reference
# adapter currently re-enters delegate_goals(mind="scan") instead of
# executing scan-mind sub-runs (flagged as a contract conflict, B6).
# Without this guard the route recurses to RecursionError; with it the
# conflict fails loudly and honestly.
_SCAN_ROUTE_DEPTH = 0


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _synthesis_home() -> Path:
    """State home for receipts and schedules.

    Honors ``LEVI_SYNTHESIS_DIR`` — the same override the config uses —
    so a redirected front door keeps ALL of its state (config, receipts,
    schedules) in one place instead of splitting config from receipts.
    """
    override = os.environ.get("LEVI_SYNTHESIS_DIR")
    home = Path(override) if override else Path.home() / ".levi" / "synthesis"
    home.mkdir(parents=True, exist_ok=True)
    return home


def receipts_path() -> Path:
    return _synthesis_home() / "receipts.jsonl"


def schedules_path() -> Path:
    return _synthesis_home() / "schedule.jsonl"


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------


@dataclass
class AgentReceipt:
    """The complete, honest record of one agentic run.

    ``kind`` discriminates receipt flavours in the shared substrate log:
    "goal" for agentic runs, "tick" for schedule-cycle receipts, and —
    per the middle-team contract — preserved ``kind`` values for flagship
    receipts (scan/board/firing/define/arbitration) when the flagship
    adopts this log. ``governance`` is the frozen frame the reason step
    read (B5): (goal, consent, standing limits, safety signals).
    """

    goal: str
    ok: bool
    started_at: str
    finished_at: str
    duration_s: float
    substrate: str
    brain: Dict[str, Any]
    verdict: str
    kind: str = "goal"
    steps_taken: int = 0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    gates_hit: List[str] = field(default_factory=list)
    final: str = ""
    error: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    governance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def write_receipt(receipt: AgentReceipt) -> Path:
    path = receipts_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt.to_dict()) + "\n")
    return path


def write_receipt_entry(entry: Dict[str, Any]) -> Path:
    """Append an arbitrary receipt entry (any ``kind``) to the substrate log.

    The log is append-only and one per substrate: the middle team's
    flagship writes its own receipt dicts (scan/board/firing/define/
    arbitration) through this entry point so the ``kind`` discriminator
    survives and the audit trail stays unified.
    """
    path = receipts_path()
    record = dict(entry)
    record.setdefault("kind", "entry")
    record.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return path


def read_receipts(limit: int = 10) -> List[Dict[str, Any]]:
    path = receipts_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out: List[Dict[str, Any]] = []
    for line in lines[-max(limit, 1) :]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# The loop: perceive → reason → act → verify → receipt
# ---------------------------------------------------------------------------


def _perceive(registry: Any, goal: str, notes: List[str]) -> str:
    """Gather local context. Best-effort: perception never kills a run."""
    context_bits: List[str] = []
    for tool_name, args in (
        ("memory_read", {"name": goal[:64]}),
        ("levi_status", {}),
        ("growth_context", {}),
    ):
        try:
            result = registry.execute(tool_name, args)
            if result.ok and result.output:
                context_bits.append(f"[{tool_name}] {result.output[:800]}")
        except Exception as exc:  # perception is advisory
            notes.append(f"perceive: {tool_name} unavailable ({exc})")
    return "\n".join(context_bits)


def _deliberation_context(
    goal: str,
    mind_report: Dict[str, Any],
    perception: str,
    governance: Dict[str, Any],
) -> str:
    """The reason-step output, handed to the loop as prior context.

    Kept OUT of the goal string so tools (e.g. memory_write) receive the
    clean goal instead of a goal polluted with framing text. The governance
    frame is frozen before perception (B5): the reason step reads this
    snapshot, not values re-fetched mid-run.
    """
    verdict = mind_report.get("verdict", "")
    proposals = mind_report.get("proposals", [])
    lines = [
        "Prior deliberation on this goal (native brain consulted, "
        "rules engine decided):",
        f"Verdict: {verdict}",
        "Governance frame (frozen before perception; do not re-derive): "
        + json.dumps(governance),
    ]
    for p in proposals[:4]:
        lines.append(f"- proposed: {p}")
    if perception:
        lines += ["", "Local context already gathered:", perception[:1500]]
    lines.append(
        "Act on the operator's goal with the tools available. Use only "
        "tools that genuinely apply; report what you did and what remains."
    )
    return "\n".join(lines)


def _verify(transcript: Any, notes: List[str]) -> Dict[str, Any]:
    tool_calls: List[Dict[str, Any]] = []
    gates_hit: List[str] = []
    for step in transcript.steps:
        for call in step.tool_calls:
            tool_calls.append(
                {
                    "step": step.index,
                    "tool": call.get("name"),
                    "ok": next(
                        (
                            r.get("ok")
                            for r in step.results
                            if r.get("tool") == call.get("name")
                        ),
                        None,
                    ),
                }
            )
    final = transcript.final or ""
    if not transcript.ok and transcript.error:
        err = transcript.error
        if "confirmation" in err.lower() or "consent" in err.lower():
            gates_hit.append(err[:300])
            notes.append(
                "verify: a gated tool was blocked — run ended at the "
                "permission gate, nothing consequential executed."
            )
    return {
        "tool_calls": tool_calls,
        "gates_hit": gates_hit,
        "final": final,
        "error": transcript.error,
    }


def run_goal(
    goal: str,
    *,
    config: Optional[SynthesisConfig] = None,
    max_steps: int = 10,
    consent: bool = False,
) -> AgentReceipt:
    """Run one goal through perceive → reason → act → verify → receipt.

    ``consent=True`` is the explicit Permission step for gated tools
    (file_write, shell_exec, …). Without it, consequential acts stop at
    the gate and the receipt records the block honestly.
    """
    from levi.agent.loop import run_subtask
    from levi.agent.providers import ChatMessage
    from levi.agent.tools import build_default_registry

    cfg = config or _default_config()
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    notes: List[str] = []

    # B5 — governance frame: frozen (goal, consent, standing limits, safety
    # signals) BEFORE perception. It is never mutated afterwards; the
    # reason step reads this snapshot, and it ships in the receipt.
    governance: Dict[str, Any] = {
        "goal": goal,
        "consent": bool(consent),
        "max_steps": max_steps,
        "brain_policy": cfg.brain_policy,
        "offline_enforced": cfg.offline_enforced,
        "scan_budget_ms": cfg.scan_budget_ms,
        "permission_law": "gated tools need explicit consent; "
        "a denied gate is a recorded block, never a silent retry",
        "frozen_at": started,
    }

    registry = build_default_registry()
    # -- perceive ---------------------------------------------------------
    with OfflineGuard():
        perception = _perceive(registry, goal, notes)

        # -- reason --------------------------------------------------------
        report = mind_ask(goal, brain_policy=cfg.brain_policy)
        context = _deliberation_context(goal, report, perception, governance)

        # -- act -----------------------------------------------------------
        # The deliberation rides along as prior context (history), NOT
        # embedded in the goal string — so tools receive the clean goal.
        try:
            transcript = run_subtask(
                goal,
                provider="local",
                registry=registry,
                consent=consent,
                max_steps=max_steps,
                history=[
                    ChatMessage(role="assistant", content=context),
                ],
            )
        except Exception as exc:  # the loop is honest, never fatal
            transcript = None
            notes.append(f"act: loop raised ({exc})")

    # -- verify ------------------------------------------------------------
    if transcript is not None:
        verification = _verify(transcript, notes)
        ok = transcript.ok
    else:
        verification = {
            "tool_calls": [],
            "gates_hit": [],
            "final": "",
            "error": notes[-1] if notes else "unknown",
        }
        ok = False

    finished = datetime.now(timezone.utc).isoformat()
    receipt = AgentReceipt(
        goal=goal,
        ok=ok,
        started_at=started,
        finished_at=finished,
        duration_s=round(time.perf_counter() - t0, 3),
        substrate=report.get("substrate", "unknown"),
        brain=report.get("brain", {}),
        verdict=report.get("verdict", ""),
        kind="goal",
        steps_taken=len(transcript.steps) if transcript is not None else 0,
        tool_calls=verification["tool_calls"],
        gates_hit=verification["gates_hit"],
        final=verification["final"][:2000],
        error=verification["error"],
        notes=notes,
        governance=governance,
    )
    write_receipt(receipt)
    return receipt


# ---------------------------------------------------------------------------
# Delegation — one coordinator, N bounded workers, one merged receipt
# ---------------------------------------------------------------------------


def delegate_goals(
    goals: List[str],
    *,
    config: Optional[SynthesisConfig] = None,
    max_steps: int = 6,
    consent: bool = False,
    mind: str = "goal",
) -> Dict[str, Any]:
    """Fan out to bounded sub-runs and merge the receipts.

    Sequential and in-process — deterministic, zero network. Each worker
    is a full perceive → reason → act → verify → receipt cycle with a
    smaller step budget; the coordinator receipt merges them.

    ``mind`` selects the worker mind (B6, middle-team contract):
    "goal" (default) runs each sub-goal through :func:`run_goal`;
    "scan" routes supervisory sub-goals to the Phase 2 scan-mind through
    the middle team's ``levi.gtpm.adapters.delegate_scan``. The adapter
    is resolved lazily so synthesis imports with zero Phase 2 footprint;
    when the flagship is unavailable this raises honestly instead of
    pretending to delegate.
    """
    if mind not in ("goal", "scan"):
        raise ValueError(
            f"delegate_goals: unknown mind {mind!r}; want 'goal' or 'scan'"
        )
    cfg = config or _default_config()
    if mind == "scan":
        global _SCAN_ROUTE_DEPTH
        try:
            from levi.gtpm.adapters import delegate_scan
        except ImportError as exc:
            raise RuntimeError(
                "delegate_goals(mind='scan'): the scan-mind adapter "
                f"(levi.gtpm.adapters.delegate_scan) is unavailable ({exc}); "
                "no sub-goals were delegated"
            ) from exc
        # The adapter's own signature is the contract surface
        # (delegate_scan(goals, config, max_steps)); the synthesis-side
        # consent gate stays with run_goal workers, not scan sub-runs.
        _SCAN_ROUTE_DEPTH += 1
        try:
            if _SCAN_ROUTE_DEPTH > 1:
                raise RuntimeError(
                    "contract conflict B6: levi.gtpm.adapters.delegate_scan "
                    "re-entered delegate_goals(mind='scan') instead of "
                    "executing scan-mind sub-runs — the scan route is "
                    "circular on the middle-team side. Flagged, not "
                    "executed; no sub-goals were delegated"
                )
            return delegate_scan(goals, config=cfg, max_steps=max_steps)
        finally:
            _SCAN_ROUTE_DEPTH -= 1
    started = datetime.now(timezone.utc).isoformat()
    sub_receipts: List[Dict[str, Any]] = []
    for goal in goals:
        receipt = run_goal(goal, config=cfg, max_steps=max_steps, consent=consent)
        sub_receipts.append(receipt.to_dict())
    merged = {
        "coordinator": "synthesis.delegate_goals",
        "mind": mind,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "workers": len(sub_receipts),
        "workers_ok": sum(1 for r in sub_receipts if r["ok"]),
        "sub_receipts": sub_receipts,
    }
    path = _synthesis_home() / "delegations.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(merged) + "\n")
    return merged


# ---------------------------------------------------------------------------
# Scheduling — small local interval store; copper/daemon for heavy duty
# ---------------------------------------------------------------------------


def schedule_goal(
    goal: str, every_seconds: int, *, consent: bool = False
) -> Dict[str, Any]:
    if every_seconds <= 0:
        raise ValueError("schedule_goal: 'every_seconds' must be positive")
    entry = {
        "goal": goal,
        "every_seconds": every_seconds,
        "consent": consent,
        "next_run": time.time(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path = schedules_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def list_schedules() -> List[Dict[str, Any]]:
    path = schedules_path()
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def tick_schedules(
    *,
    config: Optional[SynthesisConfig] = None,
    max_steps: int = 6,
) -> List[Dict[str, Any]]:
    """One scan per tick: FREEZE → EXECUTE → FLUSH → HOUSEKEEPING.

    FREEZE — the due set is snapshotted once, together with each entry's
    consent flag and the governing config: entry N+1 cannot perceive
    entry N's mutations through the tick frame (perception stays
    advisory best-effort at the tool layer, honest about that limit).
    EXECUTE — one rung (one :func:`run_goal`) per due schedule, until the
    operator-tunable cycle budget (``config.scan_budget_ms``) is spent;
    goals that don't fit are skipped honestly, never silently.
    FLUSH — the updated schedule store is written once.
    HOUSEKEEPING — a cycle receipt (``kind="tick"``) joins the receipts
    log so the audit trail records what ran and what didn't.
    """
    cfg = config or _default_config()
    entries = list_schedules()
    if not entries:
        return []
    now = time.time()
    budget_ms = cfg.scan_budget_ms

    # FREEZE — fixed due set; consent and goal captured per entry, not
    # re-read after sibling entries mutate the world.
    due: List[Dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if entry.get("next_run", 0) <= now:
            due.append(
                {
                    "index": index,
                    "goal": entry.get("goal", ""),
                    "consent": bool(entry.get("consent", False)),
                    "every_seconds": entry.get("every_seconds", 60),
                }
            )

    # EXECUTE — one rung per due entry, under the cycle budget.
    deadline = now + budget_ms / 1000.0
    ran: List[Dict[str, Any]] = []
    for frozen in due:
        entry = entries[frozen["index"]]
        if time.time() >= deadline:
            ran.append(
                {
                    "goal": frozen["goal"],
                    "ok": False,
                    "steps": 0,
                    "skipped": True,
                    "reason": f"cycle budget exhausted ({budget_ms} ms)",
                }
            )
            continue
        receipt = run_goal(
            frozen["goal"],
            config=cfg,
            max_steps=max_steps,
            consent=frozen["consent"],
        )
        entry["next_run"] = now + frozen["every_seconds"]
        entry["last_run"] = receipt.finished_at
        entry["last_ok"] = receipt.ok
        ran.append(
            {
                "goal": frozen["goal"],
                "ok": receipt.ok,
                "steps": receipt.steps_taken,
                "skipped": False,
            }
        )

    # FLUSH — write the updated store once.
    path = schedules_path()
    with path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")

    # HOUSEKEEPING — one cycle receipt in the substrate log.
    write_receipt_entry(
        {
            "kind": "tick",
            "coordinator": "synthesis.tick_schedules",
            "tick_at": datetime.now(timezone.utc).isoformat(),
            "due": len(due),
            "ran": sum(1 for r in ran if not r["skipped"]),
            "skipped": sum(1 for r in ran if r["skipped"]),
            "budget_ms": budget_ms,
            "summaries": ran,
        }
    )
    return ran
