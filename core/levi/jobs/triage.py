"""LEVI job organ — ENGINE 2 / TRIAGE. 1–10 match scoring, Review Buffer ->
Apply Queue.

The rubric is deterministic and explainable — every score ships with its
breakdown, so the human can see exactly what the number is made of.
Missing profile signals degrade the score honestly ("pay unknown: +1")
instead of inventing fit.

Rubric (max 10, min 1):
  role fit ......... +3  title/keywords hit the profile's target types
                      0   and a hard cap applies if it hits avoid types
  pay fit .......... +2  pay inside the profile's target range (+1 unknown)
  remote fit ....... +2  matches the profile's remote preference (+1 unknown)
  skills overlap ... +2  fraction of the profile's top skills found in text
  equipment ........ +1  equipment provided, or none needed
  felony screen .... hard cap at 2 when the record needs felony-friendly
                      and the listing is not

``triage_buffer`` scores every unscored buffer row and promotes rows at
or above the threshold into the Apply Queue with a priority rank.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from .profiles import Profile
from .store import Warehouse


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text_of(listing: Dict[str, Any]) -> str:
    return " ".join(
        str(listing.get(k) or "")
        for k in ("job_title", "company", "pay_range", "location_remote", "notes")
    ).lower()


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _parse_pay(pay_range: str) -> Tuple[Any, Any]:
    """Extract (low, high) hourly-ish numbers from a pay string, or (None, None)."""
    nums = [
        float(n.replace(",", ""))
        for n in re.findall(r"\$?\s*([\d,]+(?:\.\d+)?)", pay_range or "")
    ]
    if not nums:
        return None, None
    low = min(nums)
    high = max(nums)
    # yearly figures (>500) get a rough hourly conversion for comparison
    if low > 500:
        low, high = low / 2080.0, high / 2080.0
    return low, high


def score_listing(listing: Dict[str, Any], profile: Profile) -> Dict[str, Any]:
    """Score one listing 1–10 against a profile. Returns
    {score, breakdown, capped, flags}."""
    text = _text_of(listing)
    words = set(_words(text))
    breakdown: Dict[str, Any] = {}
    flags: List[str] = []
    capped = False

    # -- role fit (+3) --------------------------------------------------
    targets = [t.lower() for t in (profile.get("job_types_target") or [])]
    avoids = [t.lower() for t in (profile.get("job_types_avoid") or [])]
    role_points = 0
    if targets:
        hit = any(any(w in words for w in _words(t)) for t in targets if _words(t))
        if hit:
            role_points = 3
            breakdown["role_fit"] = "target type matched: +3"
        else:
            breakdown["role_fit"] = "no target type matched: +0"
    else:
        breakdown["role_fit"] = "no target types in profile: +0 (unknown)"
    if avoids and any(any(w in words for w in _words(a)) for a in avoids if _words(a)):
        role_points = 0
        capped = True
        flags.append("matches an avoided job type")
        breakdown["role_fit"] = "avoided type matched: +0, score capped"

    # -- pay fit (+2) ----------------------------------------------------
    pay_points = 0
    low, high = _parse_pay(str(listing.get("pay_range") or ""))
    tmin = profile.get("target_pay_min")
    tmax = profile.get("target_pay_max")
    if low is None:
        pay_points = 1
        breakdown["pay_fit"] = "pay unknown: +1"
    elif tmin or tmax:
        try:
            pmin = float(tmin) if tmin not in (None, "") else 0.0
            pmax = float(tmax) if tmax not in (None, "") else float("inf")
            if high >= pmin and low <= pmax:
                pay_points = 2
                breakdown["pay_fit"] = "pay overlaps target range: +2"
            else:
                breakdown["pay_fit"] = "pay outside target range: +0"
        except (TypeError, ValueError):
            pay_points = 1
            breakdown["pay_fit"] = "target pay unparseable: +1"
    else:
        pay_points = 1
        breakdown["pay_fit"] = "no target pay in profile: +1"

    # -- remote fit (+2) --------------------------------------------------
    remote_points = 0
    pref = str(profile.get("remote_preference") or "").lower()
    loc = str(listing.get("location_remote") or "").lower()
    if not pref:
        remote_points = 1
        breakdown["remote_fit"] = "no remote preference in profile: +1"
    elif not loc:
        remote_points = 1
        breakdown["remote_fit"] = "location unknown: +1"
    elif "remote" in pref and "remote" in loc:
        remote_points = 2
        breakdown["remote_fit"] = "remote matches: +2"
    elif "hybrid" in pref and "hybrid" in loc:
        remote_points = 2
        breakdown["remote_fit"] = "hybrid matches: +2"
    elif "on-site" in pref.replace("onsite", "on-site") and "remote" not in loc:
        remote_points = 2
        breakdown["remote_fit"] = "on-site matches: +2"
    else:
        breakdown["remote_fit"] = "preference/location mismatch: +0"

    # -- skills overlap (+2) -----------------------------------------------
    skills = [s.lower() for s in (profile.get("top_skills") or [])]
    skill_points = 0
    if skills:
        hits = sum(
            1 for s in skills if any(w in words for w in _words(s)) and _words(s)
        )
        skill_points = round(2 * hits / len(skills))
        breakdown["skills_overlap"] = (
            f"{hits}/{len(skills)} top skills found: +{skill_points}"
        )
    else:
        breakdown["skills_overlap"] = "no skills in profile: +0"

    # -- equipment (+1) ------------------------------------------------------
    equip = str(listing.get("equipment_provided") or "").strip().lower()
    equip_points = 1 if equip in ("y", "yes", "true", "1") else 0
    breakdown["equipment"] = f"equipment provided={equip or 'unknown'}: +{equip_points}"

    total = 1 + role_points + pay_points + remote_points + skill_points + equip_points

    # -- felony hard cap ------------------------------------------------------
    felony = str(profile.get("felony_on_record") or "").strip().lower()
    listing_ff = str(listing.get("felony_friendly") or "").strip().lower()
    if felony in ("y", "yes", "true", "1") and listing_ff in ("n", "no", "false", "0"):
        capped = True
        flags.append("record needs felony-friendly; listing is not")
        breakdown["felony_screen"] = "hard cap applied: score <= 2"

    score = max(1, min(10, total))
    if capped:
        score = min(score, 2)
    return {"score": score, "breakdown": breakdown, "capped": capped, "flags": flags}


def triage_buffer(
    warehouse: Warehouse,
    profile: Profile,
    threshold: int = 7,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Score unscored buffer rows; promote >= threshold to the Apply Queue.
    Dry-run default: scores and reports, writes nothing."""
    report: Dict[str, Any] = {
        "dry_run": dry_run,
        "threshold": threshold,
        "scored": 0,
        "promoted": 0,
        "parked": 0,
        "items": [],
    }
    buffer = warehouse.list_rows("review_buffer")
    queue = warehouse.list_rows("apply_queue")
    next_rank = max([int(r.get("priority_rank") or 0) for r in queue] + [0]) + 1

    for row in buffer:
        if row.get("match_score") not in (None, "", 0):
            continue
        scored = score_listing(row, profile)
        report["scored"] += 1
        action = "parked"
        if scored["score"] >= threshold and not scored["capped"]:
            action = "promoted"
            report["promoted"] += 1
            if not dry_run:
                warehouse.add_row(
                    "apply_queue",
                    {
                        "priority_rank": next_rank,
                        "job_title": row.get("job_title"),
                        "company": row.get("company"),
                        "url": row.get("url"),
                        "apply_method": "",
                        "resume_version": "",
                        "cover_letter": "N",
                        "deadline": "",
                        "assigned_to": "Human",
                        "estimated_time_min": "",
                        "status": "queued",
                        "completed": "N",
                        "notes": f"score {scored['score']}/10 via triage; flags: {', '.join(scored['flags']) or 'none'}",
                    },
                )
                warehouse.update_row(
                    "review_buffer",
                    row["id"],
                    {
                        "match_score": scored["score"],
                        "action_taken": f"promoted to apply queue (rank {next_rank})",
                    },
                )
                next_rank += 1
        else:
            report["parked"] += 1
            if not dry_run:
                warehouse.update_row(
                    "review_buffer",
                    row["id"],
                    {
                        "match_score": scored["score"],
                        "action_taken": f"parked (score {scored['score']}/10)",
                    },
                )
        report["items"].append(
            {
                "title": row.get("job_title"),
                "company": row.get("company"),
                "score": scored["score"],
                "action": action,
                "flags": scored["flags"],
            }
        )
    return report
