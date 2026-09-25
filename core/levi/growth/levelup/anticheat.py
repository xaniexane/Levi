"""Anti-cheat detection + proportional penalties (L10–L14).

Chauncey's law (2026-09-22): "Trying to edit system instead of user
skills -> you lose abilities and super tokens, knocked back levels
depending on how much was done in the ahead-of-time edits — and [for]
trying to speed up progress of leveling up / achieving abilities and
skills."

Detection (four channels):
  (a) Ledger tampering — the EXP chain already fail-closes (L2); here
      the tampered span is *located* so penalties target exactly it.
  (b) EXP velocity anomaly — per-event and per-day gains exceeding
      what the scoring math can legitimately produce.
  (c) System edits — receipts that never came through the legitimate
      award path: unknown kinds, or receipts missing the provenance
      meta the award path always writes.
  (d) Unlock acceleration — abilities unlocked outside the level path
      (requirements unmet), blocked fail-closed at unlock time and
      revoked when found in the record.

Penalty math (explicit, per the proportional rule):
  illicit_exp      = sum of flagged receipt deltas + per-day excess
  confiscated_exp  = min(illicit_exp, current entity total)
  effective_exp    = entity_total - confiscated_exp (over active penalties)
  levels_lost      = level_for(total) - level_for(effective_exp)

The knockback is exactly the levels the illicit work bought — it
scales with how much was done. Abilities are revoked newest-first
(unlocks newest-first, then any whose level requirement the effective
EXP no longer meets). Super tokens are confiscated from the EARNED
pool only, up to what was granted during the illicit span; base
weekly tokens are never touched.

Every penalty: one hash-chained adjudication receipt + one journal
entry (kind="penalty") carrying review_flag="chauncey-review".
Penalties are automatic per the law; reversal is Chauncey's alone,
via reverse_penalty(..., approved_by="chauncey"), and is itself
receipted — revoked abilities/tokens are restored as records, never
vaporized (nothing-thrown-away law).
"""

from __future__ import annotations

import re
from typing import Any

from .adjudication import (
    active_abilities,
    active_penalties,
    append_adj,
    confiscated_exp,
    earned_tokens,
    verify_adj,
)
from .levels import level_for
from .receipts import entity_total, read_receipts, verify_chain

# ---------------------------------------------------------------------------
# Legitimacy bounds (derived from the scoring math, L5/L8 + goal constants)
# ---------------------------------------------------------------------------

MAX_REPLY_EXP = 50 * 3.0  # 2*10+3*10 base, x3.0 Supernova = 150
MAX_QUESTION_STEPS = 5    # policy: questions longer than this are not legitimate
MAX_QUESTION_EXP = MAX_QUESTION_STEPS * 10 * 3.0 * 1.20  # 180
MAX_REPLIES_PER_DAY = 20  # policy cap on scored replies per entity-day
MAX_DAILY_QUOTA = 22      # policy cap on question quota per day
DAILY_COMPLETE_BONUS = 50

KIND_MAX = {
    "reply": int(MAX_REPLY_EXP),
    "question": int(MAX_QUESTION_EXP),
    "daily-complete": DAILY_COMPLETE_BONUS,
}

# Provenance meta the legitimate award path always writes (L11).
REQUIRED_META = {
    "reply": ("attention", "interaction", "intensity"),
    "question": ("qid", "steps", "intensity"),
    "daily-complete": ("date", "quota"),
}

_ERROR_INDEX_RE = re.compile(r"receipt (\d+):")


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def locate_tamper(path=None) -> tuple[bool, tuple[int, int] | None, list[str]]:
    """Verify the EXP chain and locate the tampered span (L10).

    Returns (ok, span, errors). `span` is the (first_seq, last_seq) of
    the broken region, or None when the chain is clean. In-place body
    edits ("hash mismatch") taint exactly those receipts; a broken
    linkage taints from the break to the end of the ledger (a forged
    tail), since nothing after a forged link can be trusted. This
    keeps penalties targeted at the illicit work (L10), never at
    legitimate receipts sitting after an in-place edit.
    """
    receipts = read_receipts(path)
    ok, errors = verify_chain(path)
    if ok:
        return True, None, []
    bad_exact: set[int] = set()
    tail_start: int | None = None
    for e in errors:
        m = _ERROR_INDEX_RE.search(e)
        if not m:
            continue
        i = int(m.group(1))
        if "linkage broken" in e:
            tail_start = i if tail_start is None else min(tail_start, i)
        else:
            bad_exact.add(i)
    seqs = {i + 1 for i in bad_exact}  # 0-based index -> 1-based seq
    if tail_start is not None:
        seqs.update(range(tail_start + 1, len(receipts) + 1))
    if not seqs:
        seqs = set(range(1, len(receipts) + 1))
    return False, (min(seqs), max(seqs)), errors


def _day_of(rec: dict) -> str:
    ts = str(rec.get("ts", ""))
    return ts[:10] if len(ts) >= 10 else "unknown"


def daily_cap(date_iso: str) -> int:
    """Max legitimate EXP one entity can earn on one date (L11).

    quota * MAX_QUESTION_EXP + daily bonus + MAX_REPLIES_PER_DAY * 150.
    Uses the day's actual goal quota when one exists, else the policy cap.
    """
    from .goals import get_goal

    quota = MAX_DAILY_QUOTA
    goal = get_goal(date_iso)
    if goal and isinstance(goal.get("quota"), int):
        quota = min(goal["quota"], MAX_DAILY_QUOTA)
    return int(quota * MAX_QUESTION_EXP + DAILY_COMPLETE_BONUS
               + MAX_REPLIES_PER_DAY * MAX_REPLY_EXP)


def detect(entity: str, path=None) -> dict[str, Any]:
    """Run all four detection channels for one entity.

    Returns findings; illicit_exp is the total illegitimate EXP.
    Never raises on a broken chain — tamper is a finding, not a crash.
    """
    receipts = [
        r for r in read_receipts(path) if r.get("entity") == entity
    ]
    findings: dict[str, Any] = {
        "entity": entity,
        "chain_ok": True,
        "chain_errors": [],
        "tampered_span": None,
        "flags": [],          # {seq, kind, reason, illicit_exp}
        "velocity_days": [],  # {date, day_total, cap, excess}
        "acceleration": [],   # abilities unlocked without meeting requirements
        "illicit_exp": 0,
    }

    ok, span, errors = locate_tamper(path)
    findings["chain_ok"] = ok
    findings["chain_errors"] = errors
    findings["tampered_span"] = span
    illicit = 0

    if not ok:
        # Tampered span: every receipt in it is illegitimate (L10).
        tainted = {
            r["seq"] for r in receipts
            if span and span[0] <= int(r.get("seq", 0)) <= span[1]
        }
        for r in receipts:
            if r.get("seq") in tainted:
                d = int(r.get("exp_delta", 0))
                findings["flags"].append(
                    {"seq": r["seq"], "kind": "tamper",
                     "reason": "receipt inside tampered ledger span",
                     "illicit_exp": d}
                )
                illicit += d
    else:
        # Per-event bounds + provenance (L11). A receipt already flagged
        # by an earlier check is never double-counted.
        flagged_seqs: set = set()
        for r in receipts:
            seq = r.get("seq")
            kind = r.get("kind")
            d = int(r.get("exp_delta", 0))
            meta = r.get("meta") or {}
            if kind not in KIND_MAX:
                flagged_seqs.add(seq)
                findings["flags"].append(
                    {"seq": seq, "kind": "system-edit",
                     "reason": "unknown kind %r — not from the award path" % (kind,),
                     "illicit_exp": d}
                )
                illicit += d
                continue
            if d > KIND_MAX[kind]:
                flagged_seqs.add(seq)
                findings["flags"].append(
                    {"seq": seq, "kind": "velocity-event",
                     "reason": "%s award %d exceeds max legitimate %d"
                               % (kind, d, KIND_MAX[kind]),
                     "illicit_exp": d}
                )
                illicit += d
                continue
            missing = [k for k in REQUIRED_META[kind] if k not in meta]
            if missing:
                flagged_seqs.add(seq)
                findings["flags"].append(
                    {"seq": seq, "kind": "system-edit",
                     "reason": "missing provenance meta %s — not from the award path"
                               % (missing,),
                     "illicit_exp": d}
                )
                illicit += d

        # Per-day velocity (L11): excess over the cap, newest receipts first.
        # Receipts already flagged above don't count toward the day total —
        # the excess must come from unflagged receipts only.
        by_day: dict[str, list[dict]] = {}
        for r in receipts:
            if r.get("seq") not in flagged_seqs:
                by_day.setdefault(_day_of(r), []).append(r)
        for day, recs in sorted(by_day.items()):
            day_total = sum(int(r.get("exp_delta", 0)) for r in recs)
            cap = daily_cap(day)
            if day_total > cap:
                excess = day_total - cap
                findings["velocity_days"].append(
                    {"date": day, "day_total": day_total,
                     "cap": cap, "excess": excess}
                )
                # newest receipts carry the excess (skips already-flagged)
                for r in sorted(recs, key=lambda x: -int(x.get("seq", 0))):
                    if excess <= 0:
                        break
                    if r.get("seq") in flagged_seqs:
                        continue
                    take = min(int(r.get("exp_delta", 0)), excess)
                    flagged_seqs.add(r.get("seq"))
                    findings["flags"].append(
                        {"seq": r.get("seq"), "kind": "velocity-day",
                         "reason": "day %s total %d exceeds cap %d"
                                   % (day, day_total, cap),
                         "illicit_exp": take}
                    )
                    illicit += take
                    excess -= take

    # Unlock acceleration (channel d): ability active whose requirement
    # the effective EXP never met — i.e. unlocked outside the level path.
    from . import unlocks as _unlocks

    effective = effective_exp(entity, path)
    for aid in active_abilities(entity):
        req = _unlocks.get_ability(aid)["level_required"]
        if level_for(effective) < req:
            findings["acceleration"].append(
                {"ability_id": aid, "level_required": req,
                 "reason": "unlocked outside the level path"}
            )

    findings["illicit_exp"] = illicit
    return findings


# ---------------------------------------------------------------------------
# Effective state (ledger totals minus active penalties)
# ---------------------------------------------------------------------------


def effective_exp(entity: str, exp_path=None, adj_path=None) -> int:
    """EXP the entity legitimately holds: ledger total minus active
    penalty confiscations. Level is computed from this (L12)."""
    return max(entity_total(entity, exp_path) - confiscated_exp(entity, adj_path), 0)


def levels_after_penalty(entity: str, illicit_exp: int,
                         exp_path=None, adj_path=None) -> tuple[int, int, int]:
    """(levels_before, levels_after, levels_lost) if `illicit_exp` were
    confiscated — the proportional knockback, computed before acting."""
    total = entity_total(entity, exp_path)
    already = confiscated_exp(entity, adj_path)
    before = level_for(max(total - already, 0))
    take = min(illicit_exp, max(total - already, 0))
    after = level_for(max(total - already - take, 0))
    return before, after, before - after


# ---------------------------------------------------------------------------
# Penalties (L12, L13, L14)
# ---------------------------------------------------------------------------


def _journal_penalty(entry: dict) -> None:
    from levi.growth import journal as _journal
    from levi.growth.guards import check_no_sentience_claim

    blurb = entry.get("blurb", "")
    hits = check_no_sentience_claim(blurb)
    if hits:
        raise ValueError("penalty blurb tripped the sentience rail: %s" % hits)
    _journal.append_entry(entry)


def apply_penalty(entity: str, findings: dict[str, Any],
                  note: str = "") -> dict[str, Any]:
    """Enforce Chauncey's law for one entity from detector findings.

    Writes: one chained penalty receipt (+ token-confiscate and
    unlock-revoke receipts as needed) and one journal entry with
    review_flag="chauncey-review". Returns the penalty record.
    Idempotent-ish: calling twice with the same findings confiscates
    once — the second call finds nothing new to take.
    """
    from . import unlocks as _unlocks

    # Idempotency: findings already covered by an active penalty's
    # flagged_seqs are not confiscated twice.
    already_flagged: set = set()
    for p in active_penalties(entity):
        already_flagged.update(p["data"].get("flagged_seqs", []))
    fresh_flags = [f for f in findings.get("flags", [])
                   if f.get("seq") not in already_flagged]
    illicit = sum(int(f.get("illicit_exp", 0)) for f in fresh_flags)
    total = entity_total(entity)
    already = confiscated_exp(entity)
    remaining = max(total - already, 0)
    take = min(illicit, remaining)

    level_before = level_for(max(total - already, 0))
    effective = max(total - already - take, 0)
    level_after = level_for(effective)

    # Abilities: revoke newest-first among unlocks that no longer qualify
    # (level requirement unmet by effective EXP), plus acceleration flags.
    accel = {a["ability_id"] for a in findings.get("acceleration", [])}
    # unlock order: sequence in the adjudication ledger (newest first)
    from .adjudication import read_adj

    unlock_order: list[str] = []
    for r in read_adj():
        if r.get("entity") == entity and r.get("kind") == "unlock":
            unlock_order.append(r["data"].get("ability_id"))
    candidates = [
        aid for aid in reversed(unlock_order)
        if aid in active_abilities(entity)
        and (aid in accel
             or _unlocks.get_ability(aid)["level_required"] > level_after)
    ]

    # Super tokens: confiscate earned tokens granted during the illicit
    # span, capped at the earned balance. Base weekly pool untouched.
    # The span anchors on the earliest flagged EXP receipt; when the
    # cheat is unlock acceleration, it anchors on the forged unlock
    # receipts instead — honestly earned tokens granted before the
    # cheat are never swept in.
    anchor_tss: list[str] = []
    flagged_seqs = [f.get("seq") for f in fresh_flags]
    for r in read_receipts():
        if r.get("entity") == entity and r.get("seq") in flagged_seqs:
            anchor_tss.append(str(r.get("ts", "")))
    accel_aids = {a["ability_id"] for a in findings.get("acceleration", [])}
    for r in read_adj():
        if (r.get("entity") == entity and r.get("kind") == "unlock"
                and r["data"].get("ability_id") in accel_aids):
            anchor_tss.append(str(r.get("ts", "")))
    span_start = min(anchor_tss) if anchor_tss else None
    granted_in_span = 0
    for r in read_adj():
        if (r.get("entity") == entity and r.get("kind") == "token-grant"
                and (span_start is None or str(r.get("ts", "")) >= span_start)):
            granted_in_span += int(r["data"].get("tokens", 0))
    tokens_to_take = min(granted_in_span, earned_tokens(entity))

    reasons = sorted({f["kind"] for f in fresh_flags})
    if findings.get("tampered_span"):
        reasons.append("ledger-tamper")

    penalty = append_adj(
        "penalty",
        entity,
        {
            "illicit_exp": illicit,
            "confiscated_exp": take,
            "level_before": level_before,
            "level_after": level_after,
            "levels_lost": level_before - level_after,
            "abilities_revoked": candidates,
            "tokens_confiscated": tokens_to_take,
            "reasons": reasons,
            "tampered_span": findings.get("tampered_span"),
            "flagged_seqs": flagged_seqs,
            "acceleration": findings.get("acceleration", []),
            "note": note,
            "review_flag": "chauncey-review",
            "reversible": True,
        },
    )

    for aid in candidates:
        append_adj("unlock-revoke", entity,
                   {"ability_id": aid, "penalty_seq": penalty["seq"],
                    "reason": "penalty: requirement no longer met / unearned"})
    if tokens_to_take > 0:
        append_adj("token-confiscate", entity,
                   {"tokens": tokens_to_take, "penalty_seq": penalty["seq"],
                    "pool": "earned"})

    _journal_penalty(
        {
            "kind": "penalty",
            "entity": entity,
            "penalty_seq": penalty["seq"],
            "illicit_exp": illicit,
            "confiscated_exp": take,
            "level_before": level_before,
            "level_after": level_after,
            "levels_lost": level_before - level_after,
            "abilities_revoked": candidates,
            "tokens_confiscated": tokens_to_take,
            "reasons": reasons,
            "review_flag": "chauncey-review",
            "reversible": True,
            "blurb": (
                "%s penalized under the anti-cheat law: %d illicit EXP "
                "confiscated, level %d -> %d, %d abilit%s revoked, %d "
                "super tokens confiscated from the earned pool. "
                "Flagged for Chauncey's review; fully reversible."
                % (entity, take, level_before, level_after, len(candidates),
                   "y" if len(candidates) == 1 else "ies", tokens_to_take)
            ),
        }
    )
    return penalty


def reverse_penalty(entity: str, penalty_seq: int,
                    approved_by: str) -> dict[str, Any]:
    """Chauncey's reversal: restores confiscated EXP eligibility, revoked
    abilities, and confiscated tokens as new receipts. Only
    approved_by="chauncey" is accepted — anyone else raises."""
    if approved_by != "chauncey":
        raise ValueError(
            "reverse_penalty: only Chauncey can reverse a penalty "
            "(approved_by=%r)" % (approved_by,)
        )
    from .adjudication import read_adj

    target = None
    for r in read_adj():
        if (r.get("entity") == entity and r.get("kind") == "penalty"
                and r.get("seq") == penalty_seq):
            target = r
            break
    if target is None:
        raise ValueError("reverse_penalty: no penalty seq %s for %s"
                         % (penalty_seq, entity))
    if target not in active_penalties(entity):
        raise ValueError("reverse_penalty: penalty %s already reversed"
                         % (penalty_seq,))

    data = target["data"]
    rev = append_adj(
        "penalty-reversal",
        entity,
        {
            "penalty_seq": penalty_seq,
            "restored_exp": int(data.get("confiscated_exp", 0)),
            "approved_by": "chauncey",
        },
    )
    for aid in data.get("abilities_revoked", []):
        append_adj("unlock-restore", entity,
                   {"ability_id": aid, "penalty_seq": penalty_seq,
                    "restored_by": "chauncey"})
    if int(data.get("tokens_confiscated", 0)) > 0:
        append_adj("token-grant", entity,
                   {"tokens": int(data["tokens_confiscated"]),
                    "reason": "penalty-reversal:%s" % penalty_seq})

    _journal_penalty(
        {
            "kind": "penalty-reversal",
            "entity": entity,
            "penalty_seq": penalty_seq,
            "reversal_seq": rev["seq"],
            "approved_by": "chauncey",
            "review_flag": "chauncey-review",
            "blurb": (
                "Chauncey reversed penalty %d for %s: confiscated EXP "
                "eligibility, %d abilit%s, and %d super tokens restored "
                "as new receipts. Original penalty record preserved."
                % (penalty_seq, entity, len(data.get("abilities_revoked", [])),
                   "y" if len(data.get("abilities_revoked", [])) == 1 else "ies",
                   int(data.get("tokens_confiscated", 0)))
            ),
        }
    )
    return rev
