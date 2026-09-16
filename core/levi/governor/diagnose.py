"""Diagnostics: "why did usage spike?" answered in plain language.

Top token contributors over any window, grouped by tool / task / agent /
provider, correlated with active cool-downs and budget state, rendered as
a summary a human can read without a dashboard.
"""

from __future__ import annotations

import time

from levi.governor.meter import Meter

GROUP_FIELDS = ("tool", "task", "agent", "provider")


def _group_key(record, group_by: str) -> str:
    return {
        "tool": record.tool_name or "(no tool)",
        "task": record.task_id or "(no task)",
        "agent": record.agent_id or "(no agent)",
        "provider": record.provider or "(no provider)",
    }[group_by]


def top_contributors(
    meter: Meter,
    window_seconds: int = 3600,
    group_by: str = "tool",
    limit: int = 10,
    clock=time.time,
) -> list[dict]:
    """Rank token contributors over the window. Shares sum to ~1."""
    if group_by not in GROUP_FIELDS:
        raise ValueError(f"group_by must be one of {GROUP_FIELDS}")
    now = clock()
    records = meter.query(since=now - window_seconds)
    buckets: dict[str, dict] = {}
    for r in records:
        key = _group_key(r, group_by)
        b = buckets.setdefault(key, {"key": key, "tokens": 0, "calls": 0})
        b["tokens"] += r.total
        b["calls"] += 1
    total = sum(b["tokens"] for b in buckets.values()) or 1
    ranked = sorted(buckets.values(), key=lambda b: b["tokens"], reverse=True)
    for b in ranked:
        b["share"] = b["tokens"] / total
    return ranked[:limit]


def summarize(
    meter: Meter,
    window_seconds: int = 3600,
    cooldowns=None,
    budgets=None,
    wallet=None,
    clock=time.time,
) -> str:
    """Plain-language answer to 'why did usage spike?'"""
    now = clock()
    cur = meter.totals(since=now - window_seconds)
    prev = meter.totals(since=now - 2 * window_seconds, until=now - window_seconds)
    lines = [
        f"Usage in the last {_fmt_dur(window_seconds)}: "
        f"{cur['total_tokens']:,} tokens across {cur['calls']} calls "
        f"({cur['prompt_tokens']:,} in / {cur['completion_tokens']:,} out)."
    ]
    if prev["total_tokens"]:
        ratio = cur["total_tokens"] / prev["total_tokens"]
        if ratio >= 2:
            lines.append(
                f"That is {ratio:.1f}× the previous window "
                f"({prev['total_tokens']:,} tokens) — elevated."
            )
        elif ratio <= 0.5:
            lines.append(
                f"That is {ratio:.1f}× the previous window "
                f"({prev['total_tokens']:,} tokens) — quieter than usual."
            )
        else:
            lines.append(
                f"Roughly flat vs the previous window "
                f"({prev['total_tokens']:,} tokens)."
            )
    else:
        lines.append("No usage in the previous window to compare against.")

    tops = top_contributors(meter, window_seconds, group_by="tool", clock=clock)
    if tops and cur["total_tokens"]:
        lead = tops[0]
        lines.append(
            f"Top cause: tool '{lead['key']}' spent {lead['tokens']:,} tokens "
            f"({lead['share']:.0%} of the window) in {lead['calls']} calls."
        )
        for b in tops[1:3]:
            lines.append(
                f"  then '{b['key']}': {b['tokens']:,} tokens ({b['share']:.0%})."
            )
    else:
        lines.append("No metered calls in the window — nothing to attribute.")

    if cooldowns is not None:
        states = cooldowns.status()
        open_now = [s for s, st in states.items() if st.get("state") == "open"]
        if open_now:
            lines.append("Cooling down now: " + ", ".join(sorted(open_now)) + ".")
        elif "_state_file" in states:
            lines.append("Cool-down state file is unreadable; all calls refused.")

    if budgets is not None:
        rem = budgets.remaining()
        lines.append(
            f"Budgets: session {rem['session_tokens']['remaining']:,} of "
            f"{rem['session_tokens']['budget']:,} left; day "
            f"{rem['day_tokens']['remaining']:,} of {rem['day_tokens']['budget']:,} left."
        )

    window_recs = meter.query(since=now - window_seconds)
    pass_calls = [r for r in window_recs if r.priority_pass_id]
    if pass_calls:
        pass_tokens = sum(r.total for r in pass_calls)
        lines.append(
            f"Priority lane: {len(pass_calls)} call(s) ran on burst passes "
            f"({pass_tokens:,} tokens) during genuine contention — labeled, "
            f"never manufactured."
        )
    if wallet is not None:
        active = wallet.list_active()
        if active:
            uses = sum(p.uses_remaining for p in active)
            lines.append(
                f"Burst passes active: {len(active)} pass(es) with "
                f"{uses} use(s) remaining."
            )
    return "\n".join(lines)


def _fmt_dur(seconds: int) -> str:
    if seconds < 3600:
        return f"{seconds // 60}min"
    return f"{seconds // 3600}h"
