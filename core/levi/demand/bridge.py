"""DemandPulse -> DDD bridge (greatness build, 2026-09-26).

A scored DemandPulse signal auto-drafts a DDD/DirectDepositDaemon outreach
draft in the approval ledger. Chauncey still approves every word before
anything sends — the ledger never sends on its own, and the money-lands
protocol stands: customer agreement alone never triggers performance.

LAWS (law -> guard -> prove; Chauncey 2026-09-26):
  B1 TRUTH NEVER UPGRADES. Signals stay HYPOTHESIS. The bridge reads
     signals and never rewrites them — kind/confidence are untouched.
     Guard: _assert_hypothesis() refuses to draft non-HYPOTHESIS signals,
     and the proof pins (signal snapshot before) == (signal snapshot after).
  B2 DRAFT-ONLY. The bridge creates held drafts. It never approves exact
     text, never marks anything sent, never touches the outreach gate.
     Guard: this module never calls approve_exact_text / mark_sent /
     set_outreach_gate — a test pins the source text. Drafts enter
     state="held" with approval=None and recipient=None, so the ledger's
     own gate makes sending impossible without his ruling.
  B3 DIRECTION-FIT BESIDE SIGNAL SCORES. opportunity = the signal's
     deterministic demand number / 100; fit = direction_fit() against the
     editable JSON profile; combined = 0.5*opportunity + 0.5*fit with the
     math shown. Deterministic, transparent, real signals only.
  B4 OUTCOME FEEDBACK. Approved / sent / paid events on bridged drafts are
     recorded back against the originating signal in the outcome ledger —
     explicit sync, idempotent, never inferred. (O2: approval is his
     explicit act; the sync only mirrors it.)

Advisory: auto-drafted text is a machine-written template awaiting his
accuracy ruling and exact-text approval. Drafts fail the ten-pass accuracy
check by construction (accuracy_ok=False), so they can never clear the
send gate until he assesses them.

stdlib-only. Nothing here publishes, spends, contacts anyone, or touches
alerts or the watcher's poll cadence.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

# ---------------------------------------------------------------------------
# Laws as importable constants (tests pin these, not just the docstring)

LAWS = (
    "B1 truth never upgrades (signals stay HYPOTHESIS; bridge never rewrites)",
    "B2 draft-only (no approve / send / gate touches — held drafts only)",
    "B3 direction-fit beside signal scores (deterministic, transparent)",
    "B4 outcome feedback (explicit idempotent sync back to the signal)",
)

BRIDGE_ID_PREFIX = "ddd-b"
OUTCOME_SIGHTING_NOTE = "auto: bridge drafted DDD outreach"
OUTCOME_SYNC_NOTES = {
    "approved": "bridge: draft approved (mirrored from ledger — explicit)",
    "send_ready": "bridge: draft send-ready (mirrored from ledger — explicit)",
    "sent": "bridge: draft sent (mirrored from ledger — explicit)",
    "paid": "bridge: payment received (explicit call)",
}

# Only "pursue" verdicts auto-draft. Watch/drop are surfaced, never drafted.
_DRAFT_VERDICTS = frozenset({"pursue"})


def default_ledger_path() -> Path:
    """DDD approval ledger store. DDD_LEDGER_PATH env wins (tests, alt)."""
    env = os.environ.get("DDD_LEDGER_PATH")
    if env:
        return Path(env)
    return Path(
        "/home/hatch/workspace/.jarvis/idea-executions/"
        "ef9dbe8a-360d-4bff-9925-fd596e7add95/scratch/ledger_store.json"
    )


_DDD_SCRATCH = Path(
    "/home/hatch/workspace/.jarvis/idea-executions/"
    "ef9dbe8a-360d-4bff-9925-fd596e7add95/scratch"
)


def _load_ledger(path: Optional[Path] = None):
    """Import the DDD Ledger class from its scratch tree (decoupled)."""
    scratch = str(_DDD_SCRATCH)
    if scratch not in sys.path:
        sys.path.insert(0, scratch)
    from ledger import Ledger  # noqa: E402  (local import: scratch tree, not repo)

    return Ledger(str(path or default_ledger_path()))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# B3 — scoring: opportunity + direction-fit, math shown


def _assert_hypothesis(signal: Any) -> None:
    """B1 guard: the bridge only moves HYPOTHESIS signals and never
    rewrites them. Anything else is refused, not converted."""
    kind = getattr(signal, "kind", None)
    if kind != "HYPOTHESIS":
        raise ValueError(
            f"B1: bridge drafts HYPOTHESIS signals only; got kind={kind!r} "
            f"on signal {getattr(signal, 'id', '?')!r} — refused, not converted"
        )


def score_for_bridge(signal: Any, profile: Any) -> Dict[str, Any]:
    """B3: score one signal for the bridge. Pure — reads, never writes.

    opportunity = signal.number / 100 (the deterministic demand number).
    A signal with no number cannot be scored honestly -> no draft.
    fit = direction_fit(signal, profile).score.
    combined = 0.5 * opportunity + 0.5 * fit; verdict via direction.verdict().
    """
    _assert_hypothesis(signal)
    from levi.demand import direction as direction_mod

    number = getattr(signal, "number", None)
    if number is None:
        return {
            "signal_id": getattr(signal, "id", ""),
            "scored": False,
            "reason": "no deterministic demand number — unscored, never drafted",
        }
    if (
        isinstance(number, bool)
        or not isinstance(number, (int, float))
        or not 0.0 <= float(number) <= 100.0
    ):
        raise ValueError(
            f"signal number must be a number in [0, 100], got {number!r}"
        )
    opportunity = round(float(number) / 100.0, 4)
    fit_result = direction_mod.direction_fit(signal, profile)
    fit = fit_result.score
    v = direction_mod.verdict(opportunity, fit)
    return {
        "signal_id": getattr(signal, "id", ""),
        "scored": True,
        "opportunity": opportunity,
        "direction_fit": fit,
        "combined": v["combined"],
        "math": v["math"],
        "verdict": v["verdict"],
        "fit_reasons": fit_result.to_dict()["reasons"],
        "signal_source": getattr(signal, "source", ""),
        "signal_confidence": getattr(signal, "confidence", None),
        "signal_kind": getattr(signal, "kind", ""),
    }


def should_draft(scored: Mapping[str, Any]) -> bool:
    """Only pursue-verdict signals auto-draft. Watch/drop surface only."""
    return bool(scored.get("scored")) and scored.get("verdict") in _DRAFT_VERDICTS


# ---------------------------------------------------------------------------
# B2 — drafting: held drafts only, provenance in flags


def draft_text_for(signal: Any, scored: Mapping[str, Any]) -> str:
    """Machine-written DDD outreach template from a scored signal.

    Grounded ONLY in the signal's need text and scores — no invented
    customer, no invented findings. The bracketed provenance block marks
    it as machine-written; it must be replaced by Chauncey's exact words
    (via his approval) before the draft can move anywhere.
    """
    need = str(getattr(signal, "need", "") or "").strip()
    source = scored.get("signal_source", "") or "unknown"
    return (
        "Hi — I'm Chauncey. I do one-page website audits for local businesses: "
        "$49, plain-English report back in two days, no jargon.\n"
        "\n"
        "[BRIDGE DRAFT — machine-written from a DemandPulse signal. "
        "NOT Chauncey's words. Awaiting his accuracy ruling and exact-text "
        "approval before it can move.]\n"
        f'Signal: "{need[:200]}" (sensed via {source}; HYPOTHESIS, '
        "not a verified customer. Scores: "
        f"opportunity={scored.get('opportunity')}, "
        f"direction-fit={scored.get('direction_fit')}, "
        f"combined={scored.get('combined')}.)\n"
        "\n"
        "Pay by Cash App: $DirectDepositDaemon. I respond within 48 hours, "
        "one revision included, and I'll make it right or refund you.\n"
        "\n"
        "— Chauncey"
    )


def _draft_id_for(signal_id: str) -> str:
    return f"{BRIDGE_ID_PREFIX}-{signal_id[:8]}"


def already_bridged(ledger: Any, signal_id: str) -> Optional[Dict[str, Any]]:
    """Return the existing bridge draft for this signal, if any."""
    for d in ledger.data.get("drafts", []):
        flags = d.get("flags") or {}
        if flags.get("bridge_signal_id") == signal_id:
            return d
    return None


def draft_for_signal(
    signal: Any,
    ledger: Any,
    profile: Any,
    outcomes_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """B1+B2: draft one signal into the DDD ledger.

    Returns {"drafted": bool, "draft_id"/"reason", "scored": {...}}.
    Never mutates the signal; never approves/sends; duplicate signals
    return the existing draft instead of drafting twice.
    """
    _assert_hypothesis(signal)
    signal_id = str(getattr(signal, "id", "") or "")
    if not signal_id:
        raise ValueError("signal must have a non-empty id")

    existing = already_bridged(ledger, signal_id)
    scored = score_for_bridge(signal, profile)
    if existing is not None:
        return {
            "drafted": False,
            "reason": "already bridged",
            "draft_id": existing["id"],
            "scored": scored,
        }
    if not should_draft(scored):
        return {
            "drafted": False,
            "reason": (
                f"verdict={scored.get('verdict')} — only 'pursue' auto-drafts; "
                "surfaced, not drafted"
            )
            if scored.get("scored")
            else scored.get("reason", "unscored"),
            "draft_id": None,
            "scored": scored,
        }

    draft_id = _draft_id_for(signal_id)
    # Collision-proof the id (two signals could share an 8-char prefix).
    suffix = 1
    base = draft_id
    try:
        while True:
            ledger.get(draft_id)
            suffix += 1
            draft_id = f"{base}-{suffix}"
    except KeyError:
        pass

    text = draft_text_for(signal, scored)
    flags = {
        "bridge_signal_id": signal_id,
        "auto_drafted": True,
        "bridge": "demandpulse->ddd",
        "signal_source": scored["signal_source"],
        "signal_kind": scored["signal_kind"],
        "signal_confidence": scored["signal_confidence"],
        "opportunity": scored["opportunity"],
        "direction_fit": scored["direction_fit"],
        "combined": scored["combined"],
        "verdict": scored["verdict"],
        "verdict_math": scored["math"],
        "fit_reasons": scored["fit_reasons"],
        # Ten-pass honesty: the machine cannot assess accuracy or
        # locality — both fail by construction until he rules.
        "accuracy_ok": False,
        "accuracy_note": (
            "auto-drafted by bridge — accuracy unassessed; "
            "needs Chauncey's ruling"
        ),
        "local_ok": False,
        "needs_target": True,
    }
    draft = ledger.add_draft(
        draft_id,
        business="open prospect (unattributed signal)",
        channel="outreach",
        draft_text=text,
        recipient=None,  # no recipient -> the gate blocks sending by itself
        flags=flags,
        state="held",  # B2: held drafts only
        hold_reason=(
            "auto-drafted by DemandPulse->DDD bridge — needs Chauncey's "
            "accuracy ruling, a real target, and exact-text approval"
        ),
    )

    # B4: sighting row against the signal (the machine noting its own draft).
    from levi.demand import outcomes as outcomes_mod

    outcomes_mod.record_event(
        signal_id,
        "sighting",
        title=f"bridge draft {draft_id}",
        composite=round(scored["combined"] * 100.0, 2),
        tier="bridge",
        segment=getattr(signal, "segment", "general"),
        markers=["bridge", "ddd-draft", f"verdict:{scored['verdict']}"],
        note=OUTCOME_SIGHTING_NOTE,
        path=outcomes_path,
    )
    return {"drafted": True, "draft_id": draft["id"], "scored": scored}


def scan_and_draft(
    dp: Any,
    ledger: Any,
    profile: Any,
    outcomes_path: Optional[Path] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Draft every unbridged pursue-verdict live signal. Receipted."""
    receipt: Dict[str, Any] = {
        "checked": 0,
        "drafted": 0,
        "skipped": 0,
        "draft_ids": [],
        "skipped_ids": [],
        "ts": _now_iso(),
    }
    signals = list(dp.live_signals())
    if limit is not None:
        signals = signals[: max(0, int(limit))]
    for sig in signals:
        receipt["checked"] += 1
        try:
            result = draft_for_signal(sig, ledger, profile,
                                      outcomes_path=outcomes_path)
        except ValueError as exc:
            receipt["skipped"] += 1
            receipt["skipped_ids"].append(
                {"signal_id": getattr(sig, "id", "?"), "reason": str(exc)}
            )
            continue
        if result["drafted"]:
            receipt["drafted"] += 1
            receipt["draft_ids"].append(result["draft_id"])
        else:
            receipt["skipped"] += 1
            receipt["skipped_ids"].append(
                {"signal_id": result["scored"].get("signal_id"),
                 "reason": result["reason"]}
            )
    return receipt


# ---------------------------------------------------------------------------
# B4 — outcome feedback: explicit idempotent sync back to the signal


def _existing_sync_notes(
    card_id: str, outcomes_path: Optional[Path]
) -> set:
    from levi.demand import outcomes as outcomes_mod

    notes = set()
    for row in outcomes_mod.read_rows(outcomes_path):
        if row.get("card_id") == card_id:
            note = row.get("note", "")
            for key, marker in OUTCOME_SYNC_NOTES.items():
                if marker in note:
                    notes.add(key)
    return notes


def sync_outcomes(
    ledger: Any, outcomes_path: Optional[Path] = None
) -> Dict[str, Any]:
    """B4: mirror bridged drafts' ledger states back onto their signals.

    approved / send_ready / sent -> "converted" rows (his explicit acts,
    mirrored — never inferred from silence). Idempotent: a state already
    mirrored is never recorded twice.
    """
    from levi.demand import outcomes as outcomes_mod

    receipt: Dict[str, Any] = {"mirrored": 0, "skipped": 0, "ts": _now_iso()}
    state_to_event = {
        "approved": "approved",
        "send_ready": "send_ready",
        "sent": "sent",
    }
    for d in ledger.data.get("drafts", []):
        flags = d.get("flags") or {}
        signal_id = flags.get("bridge_signal_id")
        if not signal_id:
            continue  # not a bridge draft — the sync never touches others
        state = d.get("state", "")
        if state not in state_to_event:
            receipt["skipped"] += 1
            continue
        key = state_to_event[state]
        if key in _existing_sync_notes(signal_id, outcomes_path):
            receipt["skipped"] += 1
            continue
        outcomes_mod.record_event(
            signal_id,
            "converted",
            title=f"bridge draft {d['id']}",
            note=OUTCOME_SYNC_NOTES[key],
            path=outcomes_path,
        )
        receipt["mirrored"] += 1
    return receipt


def record_bridge_payment(
    signal_id: str,
    note: str = "",
    outcomes_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Explicit call: money landed on a bridged draft's work.

    The money-lands protocol: only Chauncey's confirmation that a named
    customer paid triggers this. Never called by the machine on its own.
    """
    if not isinstance(signal_id, str) or not signal_id.strip():
        raise ValueError(f"signal_id must be a non-empty string, got {signal_id!r}")
    from levi.demand import outcomes as outcomes_mod

    marker = OUTCOME_SYNC_NOTES["paid"]
    if "paid" in _existing_sync_notes(signal_id.strip(), outcomes_path):
        return {"recorded": False, "reason": "payment already recorded"}
    return {
        "recorded": True,
        "row": outcomes_mod.record_event(
            signal_id.strip(),
            "converted",
            note=f"{marker}{': ' + note if note else ''}",
            path=outcomes_path,
        ),
    }


def render_status(
    dp: Any, ledger: Any, profile: Any
) -> str:
    """Plain-text bridge status for the CLI / chat."""
    live = list(dp.live_signals())
    scored = [s for s in (score_for_bridge(x, profile) for x in live)
              if s.get("scored")]
    pursue = [s for s in scored if s["verdict"] == "pursue"]
    watch = [s for s in scored if s["verdict"] == "watch"]
    drop = [s for s in scored if s["verdict"] == "drop"]
    bridged = sum(
        1 for d in ledger.data.get("drafts", [])
        if (d.get("flags") or {}).get("bridge_signal_id")
    )
    lines = [
        "=== DemandPulse -> DDD bridge ===",
        f"live signals={len(live)}  scored={len(scored)}",
        f"  pursue={len(pursue)}  watch={len(watch)}  drop={len(drop)}",
        f"bridge drafts in ledger={bridged}",
        "",
        "Laws: B1 truth never upgrades · B2 draft-only · "
        "B3 direction-fit beside scores · B4 outcome feedback",
        "Drafts are held templates awaiting his accuracy ruling and "
        "exact-text approval. Money-lands protocol stands.",
    ]
    return "\n".join(lines)
