"""LEVI job organ — CHAINED WORKFLOWS. triggers -> conditions -> actions ->
verification -> receipts.

Chains are the organ's automation shape, built on the standing rail:

    trigger -> conditions -> actions -> verification -> receipt

Composition with ``levi.automation.flows``: every chain renders a
flows.py-compatible manifest via :func:`to_flow` (predicate / emit /
note nodes — valid per ``build_flow``, renderable to Mermaid). The
manifest is the visualizable artifact.

The seam (honest): flows.py ``minion`` nodes must reference the signed
automation catalog, and job actions are not catalog minions — so the
flow form is not directly executable via ``run_flow``. Chain execution
happens natively here (:func:`run_chain`), where each action maps to a
real job-engine call. If a sibling registers ``jobs.*`` minions in the
catalog later, the manifests become executable as-is; until then the
native runner is the truth and the manifest is the map.

Gates: every chain ends in a human gate (one of the six hitl kinds).
Dry-run is the default: actions simulate and the gate resolves through
the injected responder without touching a real human.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from levi.automation import flows as flowlib
from levi.automation.hitl import Gate, GateKind, GateRequest, auto_approve

from . import apply as apply_engine
from . import gig as gig_engine
from . import prep as prep_engine
from . import sourcing as sourcing_engine
from . import triage as triage_engine
from .modes import Mode, require
from .profiles import Profile
from .store import Warehouse

Responder = Callable[[GateRequest], Dict[str, Any]]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Conditions: named, serializable, deny-closed (unknown check -> fail)
# ---------------------------------------------------------------------------


def _cond_mode_allows(ctx: Dict[str, Any], arg: Any) -> bool:
    return bool(ctx.get("capabilities", {}).get(arg, False))


def _cond_min_count(ctx: Dict[str, Any], arg: Any) -> bool:
    key, minimum = arg["key"], int(arg["min"])
    items = ctx.get(key, [])
    return len(items) >= minimum if isinstance(items, list) else False


def _cond_flag_true(ctx: Dict[str, Any], arg: Any) -> bool:
    return bool(ctx.get(arg))


CONDITIONS = {
    "mode-allows": _cond_mode_allows,
    "min-count": _cond_min_count,
    "flag-true": _cond_flag_true,
}


# ---------------------------------------------------------------------------
# Actions: named handlers over the engines. Each takes (warehouse,
# profile, ctx, dry_run) and returns a dict merged into ctx.
# ---------------------------------------------------------------------------


def _act_ingest(
    wh: Warehouse, profile: Profile, ctx: Dict[str, Any], dry_run: bool
) -> Dict[str, Any]:
    require(ctx.get("mode", Mode.FULL), "ingest")
    report = sourcing_engine.ingest_listings(
        wh,
        ctx.get("listings", []),
        source_board=ctx.get("source_board", "manual"),
        dry_run=dry_run,
    )
    return {"ingest_report": report}


def _act_triage(
    wh: Warehouse, profile: Profile, ctx: Dict[str, Any], dry_run: bool
) -> Dict[str, Any]:
    require(ctx.get("mode", Mode.FULL), "triage")
    report = triage_engine.triage_buffer(
        wh,
        profile,
        threshold=int(ctx.get("threshold", 7)),
        dry_run=dry_run,
    )
    return {"triage_report": report}


def _act_build_packet(
    wh: Warehouse, profile: Profile, ctx: Dict[str, Any], dry_run: bool
) -> Dict[str, Any]:
    require(ctx.get("mode", Mode.FULL), "draft")
    packet = apply_engine.build_packet(
        wh,
        profile,
        int(ctx["queue_id"]),
        with_cover_letter=bool(ctx.get("with_cover_letter", True)),
        dry_run=dry_run,
        responder=ctx.get("responder", auto_approve),
    )
    return {"packet": packet}


def _act_authorize(
    wh: Warehouse, profile: Profile, ctx: Dict[str, Any], dry_run: bool
) -> Dict[str, Any]:
    # Authorization always runs the real gate path (even in dry-run the
    # responder simulates the human); it never writes unless live.
    return {
        "authorization": apply_engine.authorize_submission(
            wh,
            int(ctx["queue_id"]),
            ctx.get("responder", auto_approve),
            dry_run=dry_run,
        )
    }


def _act_prep_packet(
    wh: Warehouse, profile: Profile, ctx: Dict[str, Any], dry_run: bool
) -> Dict[str, Any]:
    require(ctx.get("mode", Mode.FULL), "draft")
    return {
        "prep_packet": prep_engine.build_prep_packet(
            wh,
            str(ctx.get("job_title", "")),
            str(ctx.get("company", "")),
            interview_date=str(ctx.get("interview_date", "")),
            dry_run=dry_run,
        )
    }


def _act_gig_evaluate(
    wh: Warehouse, profile: Profile, ctx: Dict[str, Any], dry_run: bool
) -> Dict[str, Any]:
    return {
        "gig_report": gig_engine.evaluate_offers(
            wh, ctx.get("gig_rules", {}), dry_run=dry_run
        )
    }


ACTIONS = {
    "jobs.sourcing.ingest": _act_ingest,
    "jobs.triage.run": _act_triage,
    "jobs.apply.build-packet": _act_build_packet,
    "jobs.apply.authorize": _act_authorize,
    "jobs.prep.build-packet": _act_prep_packet,
    "jobs.gig.evaluate": _act_gig_evaluate,
}


# ---------------------------------------------------------------------------
# Chain definitions
# ---------------------------------------------------------------------------


@dataclass
class Chain:
    id: str
    name: str
    trigger: str
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    gate_kind: GateKind = GateKind.NOTIFICATION
    gate_prompt: str = ""
    description: str = ""


CHAINS: Dict[str, Chain] = {
    "morning-sweep": Chain(
        id="morning-sweep",
        name="Morning sweep",
        trigger="manual | schedule: new listings staged for triage",
        conditions=[
            {"check": "mode-allows", "arg": "ingest", "label": "mode allows ingest"},
            {"check": "mode-allows", "arg": "triage", "label": "mode allows triage"},
        ],
        actions=["jobs.sourcing.ingest", "jobs.triage.run"],
        gate_kind=GateKind.NOTIFICATION,
        gate_prompt="Sweep complete: staged and triaged listings.",
        description="Ingest staged listings, score them, promote the best to the Apply Queue.",
    ),
    "apply-packet": Chain(
        id="apply-packet",
        name="Application packet",
        trigger="manual: queue_id chosen",
        conditions=[
            {"check": "mode-allows", "arg": "draft", "label": "mode allows drafting"},
            {"check": "flag-true", "arg": "queue_id", "label": "queue_id provided"},
        ],
        actions=["jobs.apply.build-packet", "jobs.apply.authorize"],
        gate_kind=GateKind.EDIT_APPROVE,
        gate_prompt="Review the packet, amend the cover letter if you like, then approve.",
        description="Build the submission packet and ask the human to authorize it. Never submits.",
    ),
    "interview-prep": Chain(
        id="interview-prep",
        name="Interview prep",
        trigger="manual | interview scheduled",
        conditions=[
            {"check": "mode-allows", "arg": "draft", "label": "mode allows drafting"},
            {"check": "flag-true", "arg": "job_title", "label": "job_title provided"},
        ],
        actions=["jobs.prep.build-packet"],
        gate_kind=GateKind.ACKNOWLEDGE,
        gate_prompt="Prep packet scaffolded — acknowledge when you've seen it.",
        description="Scaffold the prep-hub packet for an upcoming interview.",
    ),
    "gig-watch": Chain(
        id="gig-watch",
        name="Gig watch",
        trigger="manual | new gig offers ingested",
        conditions=[
            {"check": "mode-allows", "arg": "read", "label": "mode allows read"},
        ],
        actions=["jobs.gig.evaluate"],
        gate_kind=GateKind.DIALOG,
        gate_prompt="Gig offers evaluated against your rules — which do you want to grab?",
        description="Evaluate open gig offers against auto-accept rules; the human picks.",
    ),
}


def list_chains() -> List[Chain]:
    return list(CHAINS.values())


# ---------------------------------------------------------------------------
# Native runner
# ---------------------------------------------------------------------------


def run_chain(
    warehouse: Warehouse,
    profile: Profile,
    chain_id: str,
    ctx: Optional[Dict[str, Any]] = None,
    responder: Responder = auto_approve,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Run a chain: trigger -> conditions -> actions -> gate ->
    verification -> receipt. Dry-run default."""
    chain = CHAINS.get(chain_id)
    if chain is None:
        raise ValueError(f"unknown chain {chain_id!r}")
    ctx = dict(ctx or {})
    ctx.setdefault("mode", Mode.FULL)
    ctx["responder"] = responder
    try:
        from .modes import capabilities as _caps

        ctx["capabilities"] = _caps(ctx["mode"])
    except Exception:
        ctx["capabilities"] = {}

    receipt: Dict[str, Any] = {
        "chain_id": chain.id,
        "chain_name": chain.name,
        "trigger": chain.trigger,
        "started_at": _utcnow(),
        "dry_run": dry_run,
        "conditions": [],
        "actions": [],
        "gate": None,
        "verification": None,
        "status": "ok",
    }

    # -- conditions -------------------------------------------------------
    for cond in chain.conditions:
        checker = CONDITIONS.get(cond["check"])
        if checker is None:
            receipt["status"] = "blocked"
            receipt["conditions"].append(
                {
                    "label": cond.get("label", cond["check"]),
                    "passed": False,
                    "reason": f"unknown condition {cond['check']!r}",
                }
            )
            break
        try:
            passed = bool(checker(ctx, cond.get("arg")))
        except Exception as exc:  # deny-closed: a broken check blocks
            passed = False
            receipt["conditions"].append(
                {
                    "label": cond.get("label", cond["check"]),
                    "passed": False,
                    "reason": str(exc),
                }
            )
            receipt["status"] = "blocked"
            break
        receipt["conditions"].append(
            {"label": cond.get("label", cond["check"]), "passed": passed}
        )
        if not passed:
            receipt["status"] = "blocked"
            break

    # -- actions ----------------------------------------------------------
    if receipt["status"] == "ok":
        for action_id in chain.actions:
            handler = ACTIONS.get(action_id)
            if handler is None:
                receipt["status"] = "failed"
                receipt["actions"].append(
                    {
                        "action": action_id,
                        "ok": False,
                        "reason": f"unknown action {action_id!r}",
                    }
                )
                break
            try:
                result = handler(warehouse, profile, ctx, dry_run)
                ctx.update(result)
                receipt["actions"].append({"action": action_id, "ok": True})
            except Exception as exc:
                receipt["status"] = "failed"
                receipt["actions"].append(
                    {"action": action_id, "ok": False, "reason": str(exc)}
                )
                break

    # -- gate ---------------------------------------------------------------
    if receipt["status"] == "ok":
        gate = Gate(
            GateRequest(
                minion_id=f"jobs.chain.{chain.id}",
                kind=chain.gate_kind,
                prompt=chain.gate_prompt or f"Chain {chain.name} finished.",
                context={"chain_id": chain.id, "dry_run": dry_run},
            )
        )
        gate_result = gate.resolve(responder)
        receipt["gate"] = gate_result.to_dict()
        if not gate_result.ok:
            receipt["status"] = "gate-denied"

    # -- verification -------------------------------------------------------
    if receipt["status"] == "ok":
        receipt["verification"] = _verify(warehouse, chain, ctx)
        if not receipt["verification"]["passed"]:
            receipt["status"] = "verify-failed"

    receipt["finished_at"] = _utcnow()
    warehouse.log_automation(
        f"chain:{chain.id}",
        "Success" if receipt["status"] == "ok" else "Fail",
        tool_used="jobs.chains",
        notes=f"status={receipt['status']} dry_run={dry_run}",
    )
    return receipt


def _verify(warehouse: Warehouse, chain: Chain, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Post-run sanity checks per chain. Conservative: verify what the
    chain claims to have done, from the warehouse itself."""
    checks: List[Dict[str, Any]] = []
    if chain.id == "morning-sweep":
        triage = ctx.get("triage_report") or {}
        checks.append(
            {
                "check": "triage scored >= 0 rows",
                "passed": triage.get("scored", -1) >= 0,
            }
        )
    elif chain.id == "apply-packet":
        packet = ctx.get("packet") or {}
        checks.append(
            {
                "check": "packet built",
                "passed": bool(packet.get("queue_id")),
            }
        )
    elif chain.id == "interview-prep":
        pkt = ctx.get("prep_packet") or {}
        checks.append(
            {
                "check": "prep packet scaffolded",
                "passed": bool(pkt.get("job_title")),
            }
        )
    elif chain.id == "gig-watch":
        rep = ctx.get("gig_report") or {}
        checks.append(
            {
                "check": "offers evaluated",
                "passed": rep.get("evaluated", -1) >= 0,
            }
        )
    passed = all(c["passed"] for c in checks)
    return {"passed": passed, "checks": checks}


# ---------------------------------------------------------------------------
# flows.py manifest rendering (the map, not the territory)
# ---------------------------------------------------------------------------


def to_flow(chain_id: str) -> Dict[str, Any]:
    """Render a chain as a flows.py-compatible manifest (predicate / emit /
    note nodes only — valid per build_flow, renderable via to_mermaid).

    Job actions appear as ``note`` nodes naming the ``jobs.*`` handler.
    See the module docstring for the seam: the manifest is not executable
    via run_flow until those handlers exist as catalog minions."""
    chain = CHAINS.get(chain_id)
    if chain is None:
        raise ValueError(f"unknown chain {chain_id!r}")

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    nodes.append(
        {
            "id": "trigger",
            "kind": "note",
            "label": "trigger",
            "text": f"trigger: {chain.trigger}",
        }
    )
    prev = "trigger"

    for i, cond in enumerate(chain.conditions):
        nid = f"cond{i}"
        # predicate exprs must tokenize; the native runner evaluates the
        # real condition — the manifest carries the label, not the logic.
        nodes.append(
            {
                "id": nid,
                "kind": "predicate",
                "label": cond.get("label", nid),
                "expr": "true",
            }
        )
        edges.append({"id": f"e-{prev}-{nid}", "from": prev, "to": nid})
        prev = nid

    for i, action_id in enumerate(chain.actions):
        nid = f"action{i}"
        nodes.append(
            {
                "id": nid,
                "kind": "note",
                "label": action_id,
                "text": f"job action (native runner): {action_id}",
            }
        )
        edges.append(
            {
                "id": f"e-{prev}-{nid}",
                "from": prev,
                "to": nid,
                "when": f"{prev}.passed" if prev.startswith("cond") else "true",
            }
        )
        prev = nid

    nodes.append(
        {
            "id": "gate",
            "kind": "note",
            "label": f"gate: {chain.gate_kind.value}",
            "text": f"human gate ({chain.gate_kind.value}): {chain.gate_prompt}",
        }
    )
    edges.append({"id": f"e-{prev}-gate", "from": prev, "to": "gate"})
    nodes.append(
        {
            "id": "receipt",
            "kind": "emit",
            "label": "receipt",
            "set": {"chain_receipt": '"ok"'},
        }
    )
    edges.append({"id": "e-gate-receipt", "from": "gate", "to": "receipt"})

    definition = {
        "id": f"jobs-chain-{chain.id}",
        "name": f"Job chain: {chain.name}",
        "start": "trigger",
        "nodes": nodes,
        "edges": edges,
    }
    return flowlib.build_flow(definition)


def chain_mermaid(chain_id: str) -> str:
    """Mermaid flowchart string for a chain (via flows.py rendering)."""
    return flowlib.to_mermaid(to_flow(chain_id))
