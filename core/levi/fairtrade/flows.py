"""Flow declarations — the symmetric data-flow ledger.

The inversion of the opaque bargain: TikTok's undisclosed ranking signals,
Discord's hidden community retention, Copilot's undisclosed training use.
Any service — LEVI's own included — declares its data flows in plain,
machine-checkable form.

The symmetry rule (the ATT inversion, enforced in code): the declarant's
OWN collection must be declared too. A declaration that exempts the
rule-maker fails loudly — asymmetry is the tell of a weapon.

A flow is a plain dict::

    {
        "collector": "us" | "first-party" | "<service name>" | "third-party: <name>",
        "data": "what is collected, in plain words",
        "purpose": "why it is collected",
        "retention": "how long it is kept, in plain words",
        "user_control": "opt-out | export | delete | none — what the user can do",
    }

``declare_flows`` validates deny-closed: malformed declarations are refused,
never half-accepted. ``audit_flows`` scores 0-100:

- no self-declared flow (the declarant exempts its own collection): -40,
  the asymmetry tell;
- per flow: empty purpose -10, no user control -10, unstated retention -5,
  unnamed third-party collector -5.

Verdicts: >=80 transparent, 50-79 murky, <50 opaque. Missing information is
scored as murky, never as clean.

stdlib-only, local-first, no network, no telemetry.
"""

from __future__ import annotations

from typing import Any, Dict, List

FLOW_FORMAT = 1

REQUIRED_KEYS = ("collector", "data", "purpose", "retention", "user_control")

_SELF_COLLECTORS = {
    "us",
    "we",
    "ours",
    "ourselves",
    "first-party",
    "first party",
    "1st-party",
    "1st party",
}


class FlowError(Exception):
    """Malformed flow declaration — refused, never half-accepted."""


def _is_self_flow(collector: str, service: str) -> bool:
    c = collector.strip().lower()
    return c in _SELF_COLLECTORS or c == service.strip().lower()


def _check_flow(flow: Any, index: int) -> Dict[str, str]:
    if not isinstance(flow, dict):
        raise FlowError(
            "flow #%d: must be a mapping, got %r" % (index, type(flow).__name__)
        )
    for key in REQUIRED_KEYS:
        if key not in flow:
            raise FlowError("flow #%d: missing required key %r" % (index, key))
        if not isinstance(flow[key], str):
            raise FlowError("flow #%d: %r must be a string" % (index, key))
    for key in ("collector", "data"):
        if not flow[key].strip():
            raise FlowError("flow #%d: %r must be non-empty" % (index, key))
    return {k: flow[k].strip() for k in REQUIRED_KEYS}


def declare_flows(service: str, flows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Build a validated flow declaration. Raises FlowError if malformed."""
    if not isinstance(service, str) or not service.strip():
        raise FlowError("service name is required")
    if not isinstance(flows, list):
        raise FlowError("flows must be a list of flow mappings")
    checked = [_check_flow(f, i) for i, f in enumerate(flows)]
    return {
        "levi_flow_declaration": FLOW_FORMAT,
        "service": service.strip(),
        "flows": checked,
    }


def audit_flows(declaration: Dict[str, Any]) -> Dict[str, Any]:
    """Score a flow declaration 0-100. Deny-closed on malformed input."""
    if not isinstance(declaration, dict):
        raise FlowError("declaration must be a mapping")
    service = declaration.get("service")
    flows = declaration.get("flows")
    if not isinstance(service, str) or not service.strip():
        raise FlowError("declaration: service name is required")
    if not isinstance(flows, list):
        raise FlowError("declaration: flows must be a list")
    flows = [_check_flow(f, i) for i, f in enumerate(flows)]

    service = service.strip()
    deductions: List[Dict[str, Any]] = []
    findings: List[Dict[str, Any]] = []

    # -- the symmetry rule: the rule-maker must declare its own collection --
    self_flows = [f for f in flows if _is_self_flow(f["collector"], service)]
    if flows and not self_flows:
        deductions.append({"points": 40, "reason": "asymmetric: no self-declared flow"})
        findings.append(
            {
                "check": "symmetry",
                "passed": False,
                "detail": (
                    "%s declares %d flow(s) but none for its own collection — "
                    "the rule binds everyone except the rule-maker."
                    % (service, len(flows))
                ),
            }
        )
    else:
        findings.append(
            {
                "check": "symmetry",
                "passed": True,
                "detail": "own collection declared (%d self flow(s))" % len(self_flows),
            }
        )

    # -- per-flow completeness --
    for i, flow in enumerate(flows):
        if not flow["purpose"]:
            deductions.append(
                {"points": 10, "reason": "flow #%d: no stated purpose" % i}
            )
        if not flow["user_control"] or flow["user_control"].lower() in ("none", "n/a"):
            # "n/a" is only honest when the flow collects nothing actionable;
            # a real collection with no control still costs.
            if flow["user_control"].lower() not in ("n/a",):
                deductions.append(
                    {"points": 10, "reason": "flow #%d: no user control" % i}
                )
            else:
                findings.append(
                    {
                        "check": "user_control",
                        "passed": True,
                        "detail": "flow #%d: n/a claimed — verify nothing actionable is collected"
                        % i,
                    }
                )
        if not flow["retention"]:
            deductions.append(
                {"points": 5, "reason": "flow #%d: retention unstated" % i}
            )
        coll = flow["collector"].lower()
        if coll.startswith("third-party") and coll.strip() in (
            "third-party",
            "third party",
        ):
            deductions.append(
                {"points": 5, "reason": "flow #%d: unnamed third-party collector" % i}
            )

    total_deducted = sum(d["points"] for d in deductions)
    score = max(0, 100 - total_deducted)
    if score >= 80:
        verdict = "transparent"
    elif score >= 50:
        verdict = "murky"
    else:
        verdict = "opaque"

    return {
        "service": service,
        "score": score,
        "verdict": verdict,
        "flow_count": len(flows),
        "self_flows": len(self_flows),
        "deductions": deductions,
        "findings": findings,
    }


def levi_declaration() -> Dict[str, Any]:
    """LEVI's own flow declaration — the rule-maker obeys the rule.

    Every flow LEVI itself collects is declared here, in the same format
    demanded of anyone else. Audit it with audit_flows; it must score
    transparent, or the module is lying.
    """
    return declare_flows(
        "LEVI",
        [
            {
                "collector": "us",
                "data": "growth journal entries (learnings, corrections, provenance)",
                "purpose": "offline self-improvement via the growth loop",
                "retention": "append-only local journal; user-deletable",
                "user_control": "inspect, export, delete via the forget command",
            },
            {
                "collector": "us",
                "data": "chat sessions harvested for growth (watermarked, idempotent)",
                "purpose": "growth-loop reflection",
                "retention": "local only; never transmitted anywhere",
                "user_control": "opt out of harvest; delete via forget",
            },
            {
                "collector": "us",
                "data": "native-brain training corpus (LEVI's own documents)",
                "purpose": "train LEVI's own brain from scratch",
                "retention": "versioned local weights; corpus manifest inspectable",
                "user_control": "never includes user data without explicit revocable consent",
            },
            {
                "collector": "us",
                "data": "usage telemetry",
                "purpose": "none — LEVI collects no telemetry",
                "retention": "n/a",
                "user_control": "n/a (nothing to control)",
            },
        ],
    )
