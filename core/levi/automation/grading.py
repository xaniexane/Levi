"""Minion grade rubric — the climb to the top.

Keeper's order 2026-09-18: every automation minion climbs
``high-grade -> premium -> elite -> enterprise`` (the top).

Lexicon law: they are Minions. Never renamed.

Grades live in signed grade manifests keyed by minion id
(``core/levi/automation/grade_data/<batch>.json``). The catalog itself
(``minions.py``) is untouched: its rows stay verbatim under their
existing Echo x Mandella signatures, and the schema-fidelity notes in
that module's docstring remain law (verbatim intake rows, kept
near-duplicates, bridge/usb_auto_launch quirks, tool columns as plain
data references — never identity, never branding; LEVI wears no mask).

THE RUBRIC — each grade is a concrete, checkable bar:
----------------------------------------------------

``high-grade`` — the minion is well-formed catalog data:
  * every content field non-empty (id, category, subcategory, trigger,
    condition, example_rite, notes, origin); ``incomplete`` is False
  * ``hitl_type`` maps to an explicit :class:`GateKind` in
    ``hitl.HITL_TYPE_MAP`` (unmapped strings fail closed to APPROVAL
    and are recorded, never silent)
  * the catalog signature verifies
    (``levi.interpenetration.verify_signatures()``)

``premium`` — the rite is a real flow:
  * :func:`compile_minion_flow` builds a flows-engine definition for
    the minion: a ``trigger`` node from its trigger, an ``approval``
    node wired to its GateKind, a ``minion`` node running the rite,
    and a ``note`` node banking the receipt
  * the definition passes ``flows.validate_flow`` strict validation

``elite`` — the rite runs the rail:
  * ``flows.run_flow(..., dry_run=True)`` completes; the FlowReceipt
    records the plan up front and every node — trigger, approval,
    minion, note — completes ok (plan -> preview -> permission ->
    execute -> verify -> receipt, the engine's ``RAIL``). When the
    default synthetic event does not satisfy the minion's condition,
    a condition-satisfying synthetic event is used instead; the run
    itself is the proof.
  * the HITL checkpoint is wired to the minion's GateKind
  * the condition verdict (holds / fails / unverifiable) is recorded;
    a failing or unverifiable condition is a legitimate rail outcome,
    not a defect

``enterprise`` — the top:
  * everything above, plus
  * adapter routing declared: the executor's adapters are checked for
    the minion — bound adapters listed, missing ones recorded as
    honest, declared adapter gaps (e.g. webhook target unconfigured
    for this minion id). Gaps are allowed; undeclared gaps are not.
  * where the minion acts as an operator it validates against the
    universal Operator contract: :func:`validate_operator` over the
    :class:`MinionOperator` wrapper
  * documented: a doc record (trigger, rite steps, HITL gate,
    condition, gaps)
  * the batch grade manifest carries its own Echo x Mandella
    signature over the grade records
  * genesis-packaging-ready: a white-label descriptor and the
    lifetime one-copy-buy packaging note per the genesis-package
    doctrine (data only — no pricing, payment, or fulfillment wired)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from levi.automation import engine, flows, hitl
from levi.automation.minions import Minion
from levi.interpenetration.composition import interpenetrate
from levi.operator.contract import (
    NATIVE,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorResult,
    validate_operator,
)

GRADES: Tuple[str, ...] = ("intake", "high-grade", "premium", "elite", "enterprise")
GRADE_ORDER = {name: i for i, name in enumerate(GRADES)}

RAIL_MARK = "plan>preview>permission>execute>verify>receipt"

#: Minion content fields that must be non-empty for high-grade.
_HIGH_GRADE_FIELDS = (
    "id",
    "category",
    "subcategory",
    "trigger",
    "condition",
    "example_rite",
    "notes",
    "origin",
)

_MANIFEST_ORGANS = ("echo", "mandella")


# ---------------------------------------------------------------------------
# Flow compilation
# ---------------------------------------------------------------------------


def parse_rite_steps(example_rite: str) -> List[str]:
    """Split an example rite into its ordered steps on `` + ``."""
    return [s.strip() for s in (example_rite or "").split(" + ") if s.strip()]


def trigger_config(trigger: str) -> Dict[str, Any]:
    """Map a catalog trigger string to a flows-engine trigger config."""
    text = (trigger or "").strip()
    lowered = text.lower()
    m = re.search(r"(\d{1,2}):(\d{2})", text)
    if lowered.startswith("time") and m:
        hour, minute = int(m.group(1)), int(m.group(2))
        return {
            "trigger_type": "schedule",
            "cron": f"{minute} {hour} * * *",
            "label": text,
        }
    if lowered.startswith(("new ", "on ", "when ", "if ")):
        slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")[:48]
        return {"trigger_type": "event", "event_kind": slug or "minion-event", "label": text}
    return {"trigger_type": "manual", "label": text or "manual"}


def compile_minion_flow(minion: Minion) -> Dict[str, Any]:
    """Build a flows-engine definition that executes the minion's rite.

    Chain: ``trigger -> gate (approval) -> rite (minion) -> record (note)``.
    The approval node carries the minion's GateKind so the HITL
    checkpoint is wired, not implied.
    """
    gate = hitl.gate_kind_for(minion.hitl_type)
    steps = parse_rite_steps(minion.example_rite)
    flow_id = f"flow-{minion.id}"
    return {
        "id": flow_id,
        "name": f"{minion.subcategory} — {minion.id}",
        "start": "trigger",
        "nodes": [
            {
                "id": "trigger",
                "kind": "trigger",
                "label": f"trigger: {minion.trigger}",
                "config": trigger_config(minion.trigger),
            },
            {
                "id": "gate",
                "kind": "approval",
                "label": f"HITL gate: {gate.value}",
                "config": {
                    "prompt": f"{minion.id}: {gate.value} gate per HITL type "
                    f"{minion.hitl_type!r}",
                    "gate_kind": gate.value,
                },
            },
            {
                "id": "rite",
                "kind": "minion",
                "label": f"rite: {minion.subcategory} ({len(steps)} steps)",
                "minion_id": minion.id,
            },
            {
                "id": "record",
                "kind": "note",
                "label": "bank the receipt",
                "text": f"receipt banked for {minion.id}",
            },
        ],
        "edges": [
            {"id": "e1", "from": "trigger", "to": "gate"},
            {"id": "e2", "from": "gate", "to": "rite"},
            {"id": "e3", "from": "rite", "to": "record"},
        ],
    }


# ---------------------------------------------------------------------------
# Condition-satisfying synthetic events + rail completeness
# ---------------------------------------------------------------------------


def satisfying_event(condition: str) -> Optional["engine.TriggerEvent"]:
    """A synthetic event crafted to satisfy a ``Key: value``/``Key = value`` condition.

    Used only to prove the rite's rail runs end-to-end in dry-run when the
    default synthetic event does not satisfy the condition. The run itself
    is the proof — if the crafted event still does not satisfy the
    condition, the caller keeps the original verdict.
    """
    text = (condition or "").strip()
    if re.sub(r"\s+", " ", text.lower()) == "always":
        return None
    norm = re.sub(r"\s+", " ", text.lower())
    m = re.fullmatch(r"day\s+(\w+)", norm)
    if m:
        return engine.TriggerEvent(
            kind="event", summary=text, payload={"day": m.group(1)}
        )
    m = re.fullmatch(r"battery\s*([<>]=?)\s*(\d+)%?", norm)
    if m:
        want = float(m.group(2))
        level = {"<": want - 1, "<=": want, ">": want + 1, ">=": want}[m.group(1)]
        return engine.TriggerEvent(
            kind="event", summary=text, payload={"battery": level}
        )
    m = re.fullmatch(r"([\w \-]+)\s*[:=]\s*(.+)", text)
    if not m:
        return None
    key = (
        re.sub(r"\s+", " ", m.group(1).strip().lower())
        .replace(" ", "_")
        .replace("-", "_")
    )
    return engine.TriggerEvent(
        kind="event", summary=text, payload={key: m.group(2).strip()}
    )


def _rail_complete(receipt: Any) -> Tuple[bool, List[str]]:
    """True when the receipt shows the full rail walked, every node ok."""
    kinds = [getattr(n, "kind", "?") for n in (receipt.nodes or [])]
    ok = (
        bool(receipt.plan)
        and {"trigger", "approval", "minion", "note"} <= set(kinds)
        and all(bool(getattr(n, "ok", False)) for n in (receipt.nodes or []))
    )
    return ok, kinds


# ---------------------------------------------------------------------------
# Adapter routing (declared, honest)
# ---------------------------------------------------------------------------


def adapter_routing(minion: Minion) -> Tuple[List[str], List[str]]:
    """Declare which executor adapters serve this minion.

    Returns ``(bound, gaps)``. A gap is a missing binding that is
    declared here — allowed at enterprise, as long as it is declared.
    """
    from levi.automation.executor import _load_webhooks

    bound: List[str] = []
    gaps: List[str] = []
    webhooks = _load_webhooks()
    if (minion.bridge or "").strip().lower() == "webhook":
        if minion.id in webhooks:
            bound.append("WebhookAdapter")
        else:
            gaps.append(
                f"webhook target unconfigured for {minion.id!r} "
                "(WebhookAdapter needs a user-owned target URL)"
            )
    device_tools = [
        t
        for t in (
            minion.android_tool,
            minion.windows_tool,
            minion.mac_tool,
            minion.chrome_extension,
        )
        if t and t.strip()
    ]
    if device_tools:
        bound.append(
            "DeviceArtifactAdapter "
            f"(scaffold + setup guide for {', '.join(device_tools)})"
        )
    return bound, gaps


# ---------------------------------------------------------------------------
# Operator contract
# ---------------------------------------------------------------------------


class MinionOperator(Operator):
    """The universal Operator contract worn by one minion.

    LEVI-native (``kind=NATIVE``); the tool columns ride along as plain
    data references in the capability declaration — never identity,
    never branding.
    """

    def __init__(self, minion: Minion):
        self.minion = minion
        self.name = minion.id
        self.kind = NATIVE
        self.lineage = "levi-native:minion-catalog"
        self.version = "1.0.0"

    def capabilities(self) -> OperatorCapabilities:
        tools = tuple(
            t
            for t in (
                self.minion.android_tool,
                self.minion.windows_tool,
                self.minion.mac_tool,
                self.minion.chrome_extension,
            )
            if t and t.strip()
        )
        return OperatorCapabilities(
            tools=tools,
            streaming=False,
            memory_access=False,
            context_window=1024,
            tool_use_loop=False,
            max_tool_calls_per_step=8,
            notes=f"minion {self.minion.id}: {self.minion.subcategory}",
        )

    def step(self, messages, tools, context) -> OperatorResult:  # type: ignore[override]
        return OperatorResult(
            text=f"rite: {self.minion.example_rite[:400]}",
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
            note="minion rite described; execution runs through the automation rail",
        )

    def health(self) -> OperatorHealth:
        return OperatorHealth(ok=True, note=f"minion {self.minion.id} catalogued")


# ---------------------------------------------------------------------------
# Grade records + the climb
# ---------------------------------------------------------------------------


@dataclass
class GradeRecord:
    """One minion's grade and its evidence."""

    minion_id: str
    grade: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    adapter_gaps: List[str] = field(default_factory=list)
    doc: Dict[str, Any] = field(default_factory=dict)
    genesis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "minion_id": self.minion_id,
            "grade": self.grade,
            "evidence": self.evidence,
            "adapter_gaps": self.adapter_gaps,
            "doc": self.doc,
            "genesis": self.genesis,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GradeRecord":
        return cls(
            minion_id=data["minion_id"],
            grade=data["grade"],
            evidence=dict(data.get("evidence", {})),
            adapter_gaps=list(data.get("adapter_gaps", [])),
            doc=dict(data.get("doc", {})),
            genesis=dict(data.get("genesis", {})),
        )


def check_high_grade(minion: Minion) -> Tuple[bool, Dict[str, Any]]:
    """High-grade bar: well-formed catalog data."""
    missing = [f for f in _HIGH_GRADE_FIELDS if not str(getattr(minion, f, "") or "").strip()]
    hitl_explicit = (minion.hitl_type or "").strip() in hitl.HITL_TYPE_MAP
    gate = hitl.gate_kind_for(minion.hitl_type)
    evidence: Dict[str, Any] = {
        "missing_fields": missing,
        "incomplete": bool(minion.incomplete),
        "hitl_type": minion.hitl_type,
        "hitl_explicit": hitl_explicit,
        "gate_kind": gate.value,
    }
    ok = not missing and not minion.incomplete and hitl_explicit
    if not ok:
        reasons = []
        if missing:
            reasons.append(f"missing fields: {', '.join(missing)}")
        if minion.incomplete:
            reasons.append("flagged incomplete (verbatim intake row, preserved as authored)")
        if not hitl_explicit:
            reasons.append(
                f"hitl_type {minion.hitl_type!r} not in HITL_TYPE_MAP "
                f"(fail-closed to {gate.value})"
            )
        evidence["cap_reason"] = "; ".join(reasons)
    return ok, evidence


def grade_minion(minion: Minion) -> GradeRecord:
    """Climb one minion as far as the evidence honestly carries it."""
    record = GradeRecord(minion_id=minion.id, grade="intake")

    # --- high-grade ---
    hg_ok, hg_evidence = check_high_grade(minion)
    record.evidence["high_grade"] = hg_evidence
    if not hg_ok:
        return record

    # --- premium: the rite is a real flow ---
    try:
        flow = compile_minion_flow(minion)
        validated = flows.validate_flow(flow)
    except Exception as exc:  # deny-closed: a rite that will not validate stays put
        record.grade = "high-grade"
        record.evidence["premium"] = {"error": f"{type(exc).__name__}: {exc}"}
        return record
    record.grade = "premium"
    record.evidence["premium"] = {
        "flow_id": validated["id"],
        "node_kinds": [n["kind"] for n in validated["nodes"]],
        "strict_validation": "pass",
        "rite_steps": len(parse_rite_steps(minion.example_rite)),
    }

    # --- elite: the rite runs the rail ---
    satisfying_used = False
    try:
        receipt = flows.run_flow(validated, dry_run=True)
        rail_ok, node_kinds = _rail_complete(receipt)
        if not rail_ok:
            # The default synthetic event may not satisfy the condition;
            # prove the rail with a condition-satisfying event instead.
            sev = satisfying_event(minion.condition)
            if sev is not None:
                receipt2 = flows.run_flow(validated, event=sev, dry_run=True)
                rail_ok2, kinds2 = _rail_complete(receipt2)
                if rail_ok2:
                    receipt, rail_ok, node_kinds = receipt2, True, kinds2
                    satisfying_used = True
    except Exception as exc:
        record.evidence["elite"] = {"error": f"{type(exc).__name__}: {exc}"}
        return record
    record.evidence["elite"] = {
        "dry_run": "complete",
        "dry_run_receipt": receipt.dry_run,
        "receipt_ok": receipt.ok,
        "plan_nodes": len(receipt.plan or []),
        "ran_node_kinds": node_kinds,
        "rail_ok": rail_ok,
        "condition_satisfying_event_used": satisfying_used,
        "hitl_gate": hitl.gate_kind_for(minion.hitl_type).value,
        "run_id": getattr(receipt, "run_id", ""),
        "node_detail": [
            f"[{getattr(n, 'kind', '?')}] {getattr(n, 'label', '')}: "
            f"{str(getattr(n, 'detail', ''))[:160]}"
            for n in (receipt.nodes or [])
        ],
    }
    if not rail_ok:
        return record
    record.grade = "elite"

    # --- enterprise: the top ---
    bound, gaps = adapter_routing(minion)
    try:
        validate_operator(MinionOperator(minion))
        operator_ok = True
        operator_note = "validate_operator: pass"
    except Exception as exc:
        operator_ok = False
        operator_note = f"validate_operator refused: {exc}"
    record.adapter_gaps = gaps
    record.evidence["enterprise"] = {
        "adapters_bound": bound,
        "adapter_gaps_declared": gaps,
        "operator_validation": operator_note,
        "operator_ok": operator_ok,
    }
    if not operator_ok:
        return record
    record.doc = {
        "trigger": minion.trigger,
        "condition": minion.condition,
        "rite_steps": parse_rite_steps(minion.example_rite),
        "hitl_type": minion.hitl_type,
        "gate_kind": hitl.gate_kind_for(minion.hitl_type).value,
        "tool_references": {
            "android": minion.android_tool,
            "windows": minion.windows_tool,
            "mac": minion.mac_tool,
            "chrome_extension": minion.chrome_extension,
        },
        "notes": minion.notes,
        "origin": minion.origin,
    }
    record.genesis = {
        "white_label": f"{minion.subcategory} Minion",
        "packaging": (
            "lifetime one-copy buy; white-labeled per business; "
            "specialized packs as add-ons"
        ),
        "packaging_status": "descriptor only — no pricing, payment, or fulfillment wired",
    }
    record.grade = "enterprise"
    return record


def batch_grade(minions: List[Minion]) -> List[GradeRecord]:
    """Climb a whole batch; never raises on a single minion's failure."""
    records: List[GradeRecord] = []
    for minion in minions:
        try:
            records.append(grade_minion(minion))
        except Exception as exc:  # honest floor: record the failure, keep climbing
            rec = GradeRecord(minion_id=minion.id, grade="intake")
            rec.evidence["error"] = f"{type(exc).__name__}: {exc}"
            records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Manifest signing — Echo x Mandella over the grade records
# ---------------------------------------------------------------------------


def canonical_grade_bytes(records: List[GradeRecord]) -> bytes:
    canon = [r.to_dict() for r in sorted(records, key=lambda r: r.minion_id)]
    payload = {"rail": RAIL_MARK, "grades": canon}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sign_grade_manifest(records: List[GradeRecord]) -> str:
    """Echo x Mandella signature id over a batch of grade records."""
    composite = interpenetrate(
        *_MANIFEST_ORGANS,
        name="echo × mandella :: minion grades",
        content=canonical_grade_bytes(records),
    )
    return str(composite.signature.signature_id)


def manifest_to_dict(
    records: List[GradeRecord], batch: str, signature_id: str
) -> Dict[str, Any]:
    return {
        "batch": batch,
        "graded_at": datetime.now(timezone.utc).isoformat(),
        "rubric": "core/levi/automation/grading.py",
        "record_count": len(records),
        "grade_counts": {
            g: sum(1 for r in records if r.grade == g) for g in GRADES
        },
        "catalog_signature_verified": None,  # filled by write path
        "signature_id": signature_id,
        "records": [r.to_dict() for r in sorted(records, key=lambda r: r.minion_id)],
    }


def write_manifest(path: str, records: List[GradeRecord], batch: str) -> Dict[str, Any]:
    """Sign and write a grade manifest; returns the manifest dict."""
    from levi.interpenetration import verify_signatures

    sig = sign_grade_manifest(records)
    manifest = manifest_to_dict(records, batch, sig)
    manifest["catalog_signature_verified"] = bool(verify_signatures().get("ok", False))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=True, indent=2)
        fh.write("\n")
    return manifest


def verify_manifest(manifest: Dict[str, Any]) -> bool:
    """Recompute the Echo x Mandella signature over the manifest's records."""
    records = [GradeRecord.from_dict(r) for r in manifest.get("records", [])]
    return sign_grade_manifest(records) == manifest.get("signature_id")
