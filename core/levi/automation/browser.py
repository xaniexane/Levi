"""LEVI browser automation — plans + helper emission. PLANS ONLY.

Original LEVI-native implementation. Concept adapted from the Levi-ai
Stage-1 lineage (source-sync entry ``levi-ai``); no source text copied.

Binding boundary: this module builds structured automation *plans* and
emits helper scripts the user runs themselves (Termux/CDP/device). It
never opens a URL, never drives a browser, never executes anything.
Steps that would touch login/captcha/2FA/payments are marked HITL and
must stay manual (see docs/AUTOMATION_SAFETY.md).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_PLAN_STEPS = (
    (
        "ensure_runtime",
        "Termux + chromium/firefox or a CDP endpoint on 127.0.0.1:9222",
        False,
    ),
    ("open_url", "Open the target URL", False),
    ("wait_ready", "Wait for document-ready or a ready selector", False),
    (
        "optional_login_gate",
        "HITL if login/captcha/2FA is detected — stays manual",
        True,
    ),
    ("extract_or_fill", "Perform the goal's extract/fill actions", False),
    ("snapshot", "Save HTML/text snapshot under the output dir", False),
    ("report", "Return a summary JSON to the LEVI companion", False),
)


@dataclass
class BrowserPlan:
    id: str
    goal: str
    url: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    runtime: str = "termux-cdp"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "url": self.url,
            "steps": [dict(s) for s in self.steps],
            "runtime": self.runtime,
            "created_at": self.created_at,
        }


def plan_browser_job(
    goal: str,
    url: str = "about:blank",
    fields: Optional[List[str]] = None,
    ready_selector: str = "body",
    runtime: str = "termux-cdp",
) -> BrowserPlan:
    """Build a structured browser-automation plan. No execution.

    ``goal`` is truncated to 500 chars. Returns a :class:`BrowserPlan`
    the user (or a HITL-gated runner) can carry out.
    """
    goal = str(goal or "")[:500]
    if not goal.strip():
        raise ValueError("plan_browser_job: goal must not be empty")
    steps: List[Dict[str, Any]] = []
    for i, (action, detail, hitl) in enumerate(_PLAN_STEPS, start=1):
        step: Dict[str, Any] = {
            "id": i,
            "action": action,
            "detail": detail,
            "hitl": hitl,
        }
        if action == "open_url":
            step["detail"] = url
        elif action == "wait_ready":
            step["detail"] = f"document ready or selector {ready_selector!r}"
        elif action == "extract_or_fill":
            step["detail"] = goal
            step["fields"] = list(fields or [])
        steps.append(step)
    return BrowserPlan(
        id=f"BR-{int(time.time() * 1000):x}",
        goal=goal,
        url=url,
        steps=steps,
        runtime=runtime,
    )


def emit_termux_helper(
    plan: BrowserPlan, out_dir: str = "$HOME/levi_browser_out"
) -> str:
    """Emit a bash helper the user pastes into Termux. Script text only."""
    if not isinstance(plan, BrowserPlan):
        raise ValueError("emit_termux_helper: expected a BrowserPlan")
    goal_line = plan.goal.replace("\n", " ")
    return "\n".join(
        [
            "#!/data/data/com.termux/files/usr/bin/bash",
            "# LEVI browser helper — generated plan, user-executed",
            f"# Goal: {goal_line}",
            "# This script only fetches static content. Interactive steps",
            "# (login/captcha/2FA) stay manual — see docs/AUTOMATION_SAFETY.md.",
            "set -e",
            f'OUT="{out_dir}"',
            'mkdir -p "$OUT"',
            f"URL={json.dumps(plan.url)}",
            'echo "[LEVI] Fetching $URL (static only)"',
            'curl -sL --max-time 60 "$URL" -o "$OUT/page.html" || true',
            'wc -c "$OUT/page.html"',
            'echo "[LEVI] Plan id: ' + plan.id + '"',
            'echo "[LEVI] HITL: complete login/captcha in a real browser if needed"',
        ]
    )


def format_plan(plan: BrowserPlan) -> str:
    """Render a plan as Markdown for chat/CLI display."""
    lines = [
        "## Browser Automation Plan",
        f"**Job** `{plan.id}`",
        f"**Goal:** {plan.goal}",
        f"**URL:** {plan.url}",
        "",
    ]
    for s in plan.steps:
        hitl = " _(HITL)_" if s.get("hitl") else ""
        lines.append(f"{s['id']}. **{s['action']}**{hitl} — {s['detail']}")
    lines += [
        "",
        "_Plans only. Execution is the user's action on Termux/CDP/device — "
        "never silent in-app browsing._",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Skill registration
# ---------------------------------------------------------------------------

try:  # pragma: no cover — import-time fallback keeps module import light
    from levi.skill.registry import Skill, SkillRisk

    _PLANS: List[BrowserPlan] = []

    def _skill_browser_plan(args):
        args = args or {}
        plan = plan_browser_job(
            str(args.get("goal") or ""),
            url=str(args.get("url") or "about:blank"),
            fields=list(args.get("fields") or []),
        )
        _PLANS.insert(0, plan)
        del _PLANS[30:]
        return format_plan(plan)

    def _skill_browser_emit(args):
        plan = _PLANS[0] if _PLANS else None
        if plan is None:
            return "no browser plan yet — build one first"
        return emit_termux_helper(plan)

    BROWSER_SKILLS = [
        Skill(
            id="automation_browser_plan",
            name="Browser Plan",
            description="Build a structured browser-automation plan (plans only, no execution)",
            category="automation",
            risk_level=SkillRisk.INFO,
            handler=_skill_browser_plan,
            tags=["automation", "browser", "plan"],
        ),
        Skill(
            id="automation_browser_emit",
            name="Browser Termux Helper",
            description="Emit the Termux helper script for the latest browser plan",
            category="automation",
            risk_level=SkillRisk.INFO,
            handler=_skill_browser_emit,
            tags=["automation", "browser", "termux"],
        ),
    ]
except ImportError:  # pragma: no cover
    BROWSER_SKILLS = []  # type: ignore[assignment]
    Skill = object  # type: ignore[assignment,misc]
    SkillRisk = None  # type: ignore[assignment]
