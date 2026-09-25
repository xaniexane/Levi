"""ExitPlan builder: the departure drill giants never give you.

The law of the drill: archive first, migrate second, delete last.
A dependency with no named runway is a no-runway risk. Parse's one-year
runway is the minimum-notice standard; Apollo's 30 days is the disaster
that proves the rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

MINIMUM_RUNWAY_DAYS = 365  # the Parse standard: anything shorter is flagged


@dataclass
class Dependency:
    """One thing you depend on a giant for."""

    name: str  # e.g. "scheduled posts bot"
    platform: str  # must match a catalog platform for hostility lookup
    kind: str  # api | app | data | community | login
    runway_days: Optional[int]  # announced notice before kill; None = unknown
    local_substitute: str  # what replaces it locally
    notes: str = ""


def lock_in_score(dep: Dependency) -> int:
    """1 (loose) to 5 (trapped). Honest inputs in, honest number out."""
    score = 1
    if dep.kind in ("data", "community"):
        score += 2  # your history and your people are the hardest to move
    elif dep.kind == "api":
        score += 1
    if dep.runway_days is None:
        score += 1  # no announced notice: they can evict you tomorrow
    elif dep.runway_days < 60:
        score += 1  # Apollo-scale notice
    if not dep.local_substitute.strip():
        score += 1  # no substitute named: you haven't planned at all
    return min(score, 5)


@dataclass
class ExitPlan:
    platform: str
    generated_at: str
    steps: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def build_plan(platform: str, deps: List[Dependency]) -> ExitPlan:
    """Build the departure drill. Archive -> migrate -> delete, always."""
    from .catalog import hostility_by_platform

    entry = hostility_by_platform(platform)
    plan = ExitPlan(
        platform=platform,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    if entry is None:
        plan.warnings.append(
            "Platform %r is not in the hostility catalog — treat it as "
            "unknown-hostility and plan a drill anyway." % platform
        )
    elif entry.pattern == "acquired-kill":
        plan.warnings.append(
            "ACQUIRED-KILL pattern (%s, %d): a giant's developer platform is a "
            "loan. Assume a 1-year runway and mirror everything now."
            % (entry.platform, entry.year)
        )
    elif entry.pattern == "api-enclosure":
        plan.warnings.append(
            "API-ENCLOSURE pattern (%s, %d): the free tier is bait. Archive your "
            "data before the price sheet arrives." % (entry.platform, entry.year)
        )
    elif entry.pattern == "deletion-refusal":
        plan.warnings.append(
            "DELETION-REFUSAL pattern (%s): the delete button deletes the "
            "account, not the history. Archive your own ledger first — nobody "
            "else will." % entry.platform
        )

    ranked = sorted(deps, key=lambda d: (lock_in_score(d), d.kind in ("data", "community")), reverse=True)

    # Phase 1: archive everything the giant holds
    data_deps = [d for d in ranked if d.kind == "data"]
    for d in data_deps:
        plan.steps.append({
            "phase": "1-archive",
            "action": "Request and download your full data export for %r; "
                      "verify it with the takeout auditor before trusting it."
                      % d.name,
        })
    # Phase 2: replace integrations with local substitutes
    for d in ranked:
        if d.kind in ("api", "app", "login"):
            plan.steps.append({
                "phase": "2-migrate",
                "action": "Replace %r with local substitute: %s."
                          % (d.name, d.local_substitute or "(none named — name one now)"),
            })
            if d.runway_days is None:
                plan.warnings.append(
                    "%r has no announced runway — it could be revoked without "
                    "notice. Migrate first, sleep later." % d.name
                )
            elif d.runway_days < MINIMUM_RUNWAY_DAYS:
                plan.warnings.append(
                    "%r runway is %d days (below the %d-day Parse standard)."
                    % (d.name, d.runway_days, MINIMUM_RUNWAY_DAYS)
                )
    # Phase 3: move the community (people are the hardest lock-in)
    for d in ranked:
        if d.kind == "community":
            plan.steps.append({
                "phase": "3-community",
                "action": "Move %r: announce the new home, run both in parallel "
                          "for a transition window, then freeze the old one."
                          % d.name,
            })
    # Phase 4: delete — last, never first
    if deps:
        plan.steps.append({
            "phase": "4-delete",
            "action": "Only now: delete the account. Confirm every phase above "
                      "completed first — deletion is irreversible and (on "
                      "deletion-refusal platforms) does not remove your history "
                      "anyway.",
        })
    return plan


def plan_to_markdown(plan: ExitPlan) -> str:
    """Render the drill as a human-readable checklist."""
    lines = ["# Exit plan: %s" % plan.platform,
             "generated %s" % plan.generated_at, ""]
    if plan.warnings:
        lines.append("## Warnings")
        for w in plan.warnings:
            lines.append("- %s" % w)
        lines.append("")
    lines.append("## The drill (archive -> migrate -> community -> delete)")
    phase = ""
    for s in plan.steps:
        if s["phase"] != phase:
            phase = s["phase"]
            lines.append("")
            lines.append("### %s" % phase)
        lines.append("- [ ] %s" % s["action"])
    return "\n".join(lines) + "\n"
