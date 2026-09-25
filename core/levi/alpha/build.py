"""alpha.build: the builder seat's engine — natural-language intent in, E3-E6 plan out.

Shape follows Chauncey's original alphaEngine (``alpha_engine_fragment.py``):
natural-language routing -> route -> build engine/module/service. Here the
"route" step resolves the intent into an E3-E6 tiered build plan, and the
"build" step runs the EmergencyBuilder under its tier gates (plan-first,
HITL where the tier demands it, never silent production).

Canon: "Omega powered by Alpha" — the daemon's build requests are powered
by this seat. "Alpha echoes Omega; the builder is the daemon's echo."

Stdlib only. The EmergencyBuilder is imported lazily so ``levi.alpha``
stays import-light for the substrate prober.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

TIERS = ("E3", "E4", "E5", "E6")

# The original fragment's command forms: "build engine|module|service <name>".
_BUILD_FORM_RE = re.compile(
    r"^build\s+(engine|module|service)\s+([A-Za-z0-9_.\-]+)\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_BUILD_BARE_RE = re.compile(r"^build\s+(.+)$", re.IGNORECASE | re.DOTALL)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return slug[:40] or "alpha_build"


def parse_build_intent(text: str) -> Dict[str, str]:
    """Parse natural-language build intent into a routing dict.

    Returns ``{"kind", "name", "goal"}`` where kind is one of
    engine/module/service/project. Honors the original alphaEngine forms::

        build engine <name> [rest]   -> kind=engine
        build module <name> [rest]   -> kind=module
        build service <name> [rest]   -> kind=service
        build <anything else>         -> kind=project, goal=<anything else>
        <anything else>               -> kind=project, goal=<text>

    Raises ValueError on empty intent.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty build intent: nothing to build — say what to build")
    t = text.strip()
    m = _BUILD_FORM_RE.match(t)
    if m:
        kind, name, rest = m.group(1).lower(), m.group(2), m.group(3).strip()
        goal = rest or f"build {kind} {name}"
        return {"kind": kind, "name": name, "goal": goal}
    m = _BUILD_BARE_RE.match(t)
    if m:
        return {"kind": "project", "name": "", "goal": m.group(1).strip()}
    return {"kind": "project", "name": "", "goal": t}


def _builder(workspace: Optional[Path] = None):
    from levi.builder.emergency import EmergencyBuilder

    return (
        EmergencyBuilder(workspace=Path(workspace))
        if workspace is not None
        else EmergencyBuilder()
    )


def plan_build(
    intent: str,
    tier: str = "E4",
    target: str = "independent",
    name: Optional[str] = None,
    workspace: Optional[Path] = None,
):
    """Route a natural-language build intent into an E3-E6 plan.

    Returns the ``BuildJob`` (status planned, or awaiting_hitl for
    E5/E6). Raises ValueError on empty intent or unknown tier — never
    silently coerces.
    """
    if not isinstance(tier, str) or tier.strip().upper() not in TIERS:
        raise ValueError(f"tier must be one of {', '.join(TIERS)} (got {tier!r})")
    parsed = parse_build_intent(intent)
    project_name = (name or "").strip() or parsed["name"] or _slugify(parsed["goal"])
    builder = _builder(workspace)
    return builder.plan(
        goal=parsed["goal"],
        tier=tier.strip().upper(),
        target=target,
        project_name=project_name,
    )


def apply_build(
    job_id: str,
    workspace: Optional[Path] = None,
    force: bool = False,
) -> str:
    """Apply a planned job under the E3-E6 tier gates.

    E5/E6 refuse without an approved HITL request unless ``force`` is
    explicitly passed (fail-closed). Returns the human-readable report.
    """
    return _builder(workspace).apply(job_id, force=force)


def format_plan(job: Any, workspace: Optional[Path] = None) -> str:
    """Render the plan receipt for a job."""
    return _builder(workspace).format_job(job)


def route_summary(parsed: Dict[str, str], tier: str) -> str:
    """One-line routing summary: what the NL intent resolved to."""
    return (
        f"alpha route: kind={parsed['kind']} name={parsed['name'] or '—'} "
        f"tier={tier} goal={parsed['goal'][:80]}"
    )


__all__ = [
    "TIERS",
    "parse_build_intent",
    "plan_build",
    "apply_build",
    "format_plan",
    "route_summary",
]
