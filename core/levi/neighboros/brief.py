"""NeighborOS founder's daily operations brief.

Reads the live Jobs project (see tracker.py) and produces the brief
the Taskade automation used to send: dispatch bottlenecks, urgent
work, supply gaps, and the single highest-leverage action for the day.

Deterministic selection rules (documented so the brief is auditable):

1. **Dispatch bottlenecks** — requested jobs with no worker assigned;
   requested jobs older than 24h; dispatched/in_progress jobs with no
   update in 48h (stalled).
2. **Urgent work** — open jobs with emergency priority, or with a due
   date that has passed or falls within the next 24h.
3. **Supply gaps** — categories with open jobs and zero active workers
   covering them.
4. **Highest-leverage action** — first match wins:
   a. oldest emergency/overdue open job → resolve it;
   b. oldest unassigned requested job → dispatch it;
   c. largest supply gap → recruit workers for that category;
   d. oldest stalled dispatched/in_progress job → follow up;
   e. empty queue → founder recruiting day (per the blueprint's
      founder scorecard: worker and customer leads first);
   f. otherwise → queue is flowing, name the oldest open job as next.

``generate_brief`` is pure given the tracker and ``now``; ``write_brief``
persists the dated markdown file (idempotent per date) and is the
cron-friendly entry point.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .tracker import NeighborTracker, ServiceJob, default_briefs_dir

UNASSIGNED_AGING = timedelta(hours=24)
STALLED_AFTER = timedelta(hours=48)
DUE_SOON = timedelta(hours=24)


def _parse_ts(ts: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _open_jobs(tracker: NeighborTracker) -> List[ServiceJob]:
    return sorted(
        (j for j in tracker.list_jobs() if j.is_open()),
        key=lambda j: (j.created_at, j.id),
    )


def dispatch_bottlenecks(
    tracker: NeighborTracker, now: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Jobs blocking the dispatch flow, oldest first."""
    now = now or datetime.now(timezone.utc)
    found: List[Dict[str, Any]] = []
    for job in _open_jobs(tracker):
        created = _parse_ts(job.created_at)
        updated = _parse_ts(job.updated_at)
        if job.status == "requested" and not job.worker:
            reason = "unassigned — no worker dispatched"
            if created and now - created > UNASSIGNED_AGING:
                reason = "unassigned and aging (>24h) — no worker dispatched"
            found.append({"job": job, "reason": reason})
        elif job.status in ("dispatched", "in_progress"):
            if updated and now - updated > STALLED_AFTER:
                who = f" ({job.worker})" if job.worker else ""
                found.append(
                    {
                        "job": job,
                        "reason": f"stalled — no update in 48h{who}",
                    }
                )
    return found


def urgent_work(
    tracker: NeighborTracker, now: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Open jobs needing action today: emergency priority or due soon/overdue."""
    now = now or datetime.now(timezone.utc)
    found: List[Dict[str, Any]] = []
    for job in _open_jobs(tracker):
        reasons = []
        if job.priority == "emergency":
            reasons.append("emergency priority")
        if job.due:
            try:
                due_day = date.fromisoformat(job.due)
            except ValueError:
                due_day = None
            if due_day is not None:
                today = now.date()
                if due_day < today:
                    reasons.append(f"overdue (due {job.due})")
                elif due_day - today <= DUE_SOON:
                    reasons.append(f"due {job.due}")
        if reasons:
            found.append({"job": job, "reason": "; ".join(reasons)})

    # Emergencies and overdue first, then oldest.
    def _rank(item: Dict[str, Any]) -> Tuple[int, str, int]:
        job = item["job"]
        urgent_flag = (
            0 if ("emergency" in item["reason"] or "overdue" in item["reason"]) else 1
        )
        return (urgent_flag, job.created_at, job.id)

    return sorted(found, key=_rank)


def supply_gaps(tracker: NeighborTracker) -> List[Dict[str, Any]]:
    """Categories with open demand and zero active workers, by demand desc."""
    demand: Dict[str, List[ServiceJob]] = {}
    for job in _open_jobs(tracker):
        if job.category:
            demand.setdefault(job.category, []).append(job)
    gaps = []
    for category, jobs in demand.items():
        workers = tracker.active_workers_for(category)
        if not workers:
            gaps.append(
                {
                    "category": category,
                    "open_jobs": len(jobs),
                    "jobs": sorted(jobs, key=lambda j: (j.created_at, j.id)),
                }
            )
    return sorted(gaps, key=lambda g: (-g["open_jobs"], g["category"]))


def highest_leverage_action(
    tracker: NeighborTracker, now: Optional[datetime] = None
) -> str:
    """The single highest-leverage action for the day (rule order in docstring)."""
    now = now or datetime.now(timezone.utc)
    urgent = urgent_work(tracker, now)
    if urgent:
        job = urgent[0]["job"]
        return (
            f"Resolve job #{job.id} '{job.title}' "
            f"({urgent[0]['reason']}) — it is the most time-critical open item."
        )
    bottlenecks = dispatch_bottlenecks(tracker, now)
    unassigned = [b for b in bottlenecks if "unassigned" in b["reason"]]
    if unassigned:
        job = unassigned[0]["job"]
        return (
            f"Dispatch job #{job.id} '{job.title}' "
            f"({unassigned[0]['reason']}) — assign a worker and move it forward."
        )
    gaps = supply_gaps(tracker)
    if gaps:
        gap = gaps[0]
        return (
            f"Recruit workers for '{gap['category']}' — "
            f"{gap['open_jobs']} open job(s) with 0 active workers. "
            "Supply is the hardest marketplace side; post in local groups today."
        )
    stalled = [b for b in bottlenecks if "stalled" in b["reason"]]
    if stalled:
        job = stalled[0]["job"]
        who = f" with {job.worker}" if job.worker else ""
        return (
            f"Follow up on job #{job.id} '{job.title}'{who} "
            f"({stalled[0]['reason']}) — unstick it or reassign."
        )
    open_jobs = _open_jobs(tracker)
    if not open_jobs:
        return (
            "Queue is empty — run a founder recruiting day. Per the blueprint's "
            "founder scorecard: 5–10 worker leads, 10–20 customer leads, and "
            "referrals from every interaction."
        )
    job = open_jobs[0]
    return (
        f"Queue is flowing — keep dispatch tight. Next: job #{job.id} "
        f"'{job.title}' ({job.status})."
    )


def _fmt_job_line(job: ServiceJob, suffix: str = "") -> str:
    bits = [f"#{job.id} {job.title}"]
    if job.category:
        bits.append(f"[{job.category}]")
    if job.priority != "normal":
        bits.append(f"({job.priority})")
    bits.append(f"— {job.status}")
    if job.worker:
        bits.append(f"· worker: {job.worker}")
    if job.customer:
        bits.append(f"· customer: {job.customer}")
    if job.due:
        bits.append(f"· due {job.due}")
    if suffix:
        bits.append(f"· {suffix}")
    return " ".join(bits)


def render_brief(
    tracker: NeighborTracker,
    brief_date: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    """Render the founder's daily operations brief as markdown."""
    now = now or datetime.now(timezone.utc)
    day = brief_date or now.date().isoformat()
    stats = tracker.stats()
    bottlenecks = dispatch_bottlenecks(tracker, now)
    urgent = urgent_work(tracker, now)
    gaps = supply_gaps(tracker)
    action = highest_leverage_action(tracker, now)

    lines = [
        f"# NeighborOS Daily Operations Brief — {day}",
        "",
        f"_Generated {now.isoformat(timespec='seconds')} · "
        "LEVI-native, local-first (replaces the Taskade automation)._",
        "",
        "## Pipeline snapshot",
        "",
        f"- Open jobs: {stats['jobs_open']} of {stats['jobs_total']} tracked",
    ]
    for status in ("requested", "dispatched", "in_progress", "completed", "cancelled"):
        count = stats["jobs_by_status"][status]
        if count:
            lines.append(f"  - {status}: {count}")
    lines += [
        f"- Workers: {stats['workers_active']} active of {stats['workers_total']}",
        "",
        "## Dispatch bottlenecks",
        "",
    ]
    if bottlenecks:
        lines += [f"- {_fmt_job_line(b['job'], b['reason'])}" for b in bottlenecks]
    else:
        lines.append("- None — nothing is stuck waiting on dispatch.")
    lines += ["", "## Urgent work", ""]
    if urgent:
        lines += [f"- {_fmt_job_line(u['job'], u['reason'])}" for u in urgent]
    else:
        lines.append("- None — no emergencies, overdue, or due-soon jobs.")
    lines += ["", "## Supply gaps", ""]
    if gaps:
        for g in gaps:
            lines.append(
                f"- '{g['category']}': {g['open_jobs']} open job(s), "
                "0 active workers covering it"
            )
    else:
        lines.append("- None — every demanded category has worker coverage.")
    lines += [
        "",
        "## Highest-leverage action",
        "",
        f"**{action}**",
        "",
        "---",
        "_NeighborOS Product Line 01 · built and operated by LEVI · "
        "free to start, earn-first._",
        "",
    ]
    return "\n".join(lines)


def brief_path_for(brief_date: str, briefs_dir: Optional[Path] = None) -> Path:
    base = Path(briefs_dir) if briefs_dir is not None else default_briefs_dir()
    return base / f"brief-{brief_date}.md"


def write_brief(
    tracker: NeighborTracker,
    brief_date: Optional[str] = None,
    now: Optional[datetime] = None,
    briefs_dir: Optional[Path] = None,
) -> Path:
    """Generate the brief and persist it to the dated file (idempotent)."""
    now = now or datetime.now(timezone.utc)
    day = brief_date or now.date().isoformat()
    text = render_brief(tracker, brief_date=day, now=now)
    path = brief_path_for(day, briefs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import os

        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    path.write_text(text, encoding="utf-8")
    try:
        import os

        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def generate_brief(
    tracker: Optional[NeighborTracker] = None,
    brief_date: Optional[str] = None,
    now: Optional[datetime] = None,
    briefs_dir: Optional[Path] = None,
) -> Tuple[str, Path]:
    """Cron-friendly entry: render + persist the brief, return (text, path)."""
    tracker = tracker or NeighborTracker()
    path = write_brief(tracker, brief_date=brief_date, now=now, briefs_dir=briefs_dir)
    return path.read_text(encoding="utf-8"), path
