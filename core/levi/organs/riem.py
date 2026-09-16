"""RIEM — compost to genome (kernel organ).

RIEM takes REIM compost records and promotes the worthy ones into GENOME
PROPOSALS. A proposal is data, not a write: RIEM never modifies memory,
never applies policy, never mutates configuration. Applying a proposal is
always a human (or higher-organ) decision — RIEM only argues that the
failure was common enough and clear enough to deserve one.

Promotion rule (deterministic):
    reusable compost records promote when
    corroboration >= 2  OR  severity is "high".

Proposal kinds:
    - "procedural-memory": durable "how we do X" knowledge
    - "checklist-item":   a verification step to add to a review/checklist
    - "guard-rule":        a runtime guard to enforce

Compost class -> proposal kind is a fixed mapping; an unrecognized
compost_class raises ValueError (fail-closed) rather than silently
producing a mushy default.
"""

from __future__ import annotations

from typing import Dict, List
import hashlib

ORGAN = "riem"

KIND_BY_CLASS = {
    "flaky-input": "guard-rule",
    "missing-guard": "guard-rule",
    "resource-exhaustion": "guard-rule",
    "wrong-assumption": "checklist-item",
    "unknown": "procedural-memory",
}

REQUIRED_KEYS = (
    "organ", "source", "what", "context", "ts", "severity",
    "compost_class", "lesson", "inverse_map", "reusable",
    "corroboration", "fingerprint", "provenance",
)

PROMOTE_SEVERITY = "high"


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _validate_compost(compost: Dict) -> Dict:
    if not isinstance(compost, dict):
        raise ValueError(
            "promote: compost record must be a dict, got %s"
            % type(compost).__name__
        )
    missing = [k for k in REQUIRED_KEYS if k not in compost]
    if missing:
        raise ValueError(
            "promote: compost record is missing keys: %s" % ", ".join(missing)
        )
    if compost["organ"] != "reim":
        raise ValueError(
            "promote: not a REIM compost record (organ=%r)"
            % (compost.get("organ"),)
        )
    if compost["compost_class"] not in KIND_BY_CLASS:
        raise ValueError(
            "promote: unknown compost_class %r (known: %s)"
            % (compost["compost_class"], ", ".join(sorted(KIND_BY_CLASS)))
        )
    if not isinstance(compost["corroboration"], int) or compost["corroboration"] < 1:
        raise ValueError(
            "promote: corroboration must be a positive int, got %r"
            % (compost.get("corroboration"),)
        )
    return compost


def _eligible(compost: Dict) -> bool:
    return bool(compost["reusable"]) and (
        compost["corroboration"] >= 2 or compost["severity"] == PROMOTE_SEVERITY
    )


def _confidence(compost: Dict) -> str:
    if compost["severity"] == PROMOTE_SEVERITY and compost["corroboration"] >= 2:
        return "high"
    if compost["severity"] == PROMOTE_SEVERITY or compost["corroboration"] >= 3:
        return "medium"
    return "low"


def _content(kind: str, compost: Dict) -> str:
    if kind == "guard-rule":
        return (
            "Guard: before %s, enforce the precondition from this failure: %s"
            % (compost["source"], compost["lesson"])
        )
    if kind == "checklist-item":
        return (
            "Checklist: when doing work like %r, verify: %s"
            % (compost["what"][:80], compost["lesson"])
        )
    # procedural-memory
    return (
        "Procedural memory: %s. Inverse map: %s"
        % (compost["lesson"], compost["inverse_map"])
    )


def promote(compost_records: List[Dict]) -> List[Dict]:
    """Promote eligible REIM compost records into genome proposals.

    ``compost_records`` must be a list of :func:`levi.organs.reim.compost_failure`
    results (same-shape dicts are accepted as long as they carry all required
    keys and a recognized compost_class). Malformed input raises ValueError.

    Returns a list of proposal dicts::

        {
            "kind": "procedural-memory" | "checklist-item" | "guard-rule",
            "content": ...,
            "confidence": "high" | "medium" | "low",
            "fingerprint": stable id derived from the source compost,
            "provenance": {"organ": "riem", "compost_fingerprint": ...,
                          "source": ..., "ts": ..., "corroboration": ...},
            "applied": False,   # proposals are data, never writes
        }

    Records that fail the promotion rule (not reusable, corroboration < 2
    and severity not high) are skipped, not raised — ineligibility is
    routine, not an error. This function performs zero writes.
    """
    if not isinstance(compost_records, list):
        raise ValueError(
            "promote: compost_records must be a list, got %s"
            % type(compost_records).__name__
        )
    proposals: List[Dict] = []
    for compost in [_validate_compost(c) for c in compost_records]:
        if not _eligible(compost):
            continue
        kind = KIND_BY_CLASS[compost["compost_class"]]
        proposals.append(
            {
                "kind": kind,
                "content": _content(kind, compost),
                "confidence": _confidence(compost),
                "fingerprint": _fingerprint(compost["fingerprint"] + "|riem"),
                "provenance": {
                    "organ": ORGAN,
                    "compost_fingerprint": compost["fingerprint"],
                    "source": compost["source"],
                    "ts": compost["ts"],
                    "corroboration": compost["corroboration"],
                },
                "applied": False,
            }
        )
    return proposals


def format_proposals(proposals: List[Dict]) -> str:
    """Render :func:`promote` results. Raises ValueError on malformed input."""
    if not isinstance(proposals, list):
        raise ValueError("format_proposals: proposals must be a list")
    for p in proposals:
        if not isinstance(p, dict):
            raise ValueError("format_proposals: each proposal must be a dict")
        for key in ("kind", "content", "confidence"):
            if key not in p:
                raise ValueError(
                    "format_proposals: proposal is missing key %r" % key
                )
    lines = ["=== RIEM genome proposals (%d) ===" % len(proposals), ""]
    for i, p in enumerate(proposals, 1):
        lines.append(
            "%d. [%s] confidence=%s applied=%s"
            % (i, p["kind"], p["confidence"], p["applied"])
        )
        lines.append("   %s" % p["content"])
    lines.append("")
    lines.append(
        "Proposals are data, not writes. Nothing was applied."
    )
    return "\n".join(lines)
