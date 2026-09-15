"""
Phase runner for capability-discovery / service-delivery projects — pre-MVP.

P0–P15 are executable workflow phases (state machine + HITL + capability log).
Not to be confused with the product stage map A/B/C (levi.cloud.stages):
those are maturity stages, not a runner.

LEVI can run these phases before the full product exists:
  - Autonomous on low-risk execution
  - HITL before consequences
  - Capability log after each phase step

Does not claim production deploy or invented business facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json
import os

from levi.project.capability_log import CapabilityLog
from levi.project.hitl import HITLGate


DEFAULT_STATE = Path.home() / ".levi" / "project_phases.json"


# Generic service workflow (any client site/business — not one brand)
# Alias SERVICE_PHASES kept for backward compatibility
SERVICE_PHASES: List[Dict[str, Any]] = [
    {
        "id": "P0",
        "name": "Capability audit",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "What this environment can actually do (web, browser, fs, terminal, connectors).",
        "future_skill": "CAPABILITY_AUDIT",
    },
    {
        "id": "P1",
        "name": "Site archaeology",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "Public site inspection: pages, nav, services, booking, visual hierarchy. OBSERVED vs INFERENCE.",
        "future_skill": "WEBSITE_ARCHEOLOGY",
        "needs": ["public_url"],
    },
    {
        "id": "P2",
        "name": "Baseline reconstruction",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "Preview reconstruction of observed experience. No invented prices/reviews. OWNER VERIFICATION for unknowns.",
        "future_skill": "BASELINE_RECONSTRUCT",
    },
    {
        "id": "P3",
        "name": "Ten premium UI experiments",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "Warm Spa, Mobile Booking Machine, Boutique Studio, … Hybrid Growth. Functional previews.",
        "future_skill": "UI_DESIGN_LAB",
    },
    {
        "id": "P4",
        "name": "$0 premium craft",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "Typography, spacing, CTAs, a11y, metadata, sitemap — reversible preview only.",
        "future_skill": "ZERO_COST_PREMIUM",
    },
    {
        "id": "P5",
        "name": "UX journey simulation",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "First-time, returning, gift-card, mobile booking. Label PRE-LAUNCH UX RESULTS.",
        "future_skill": "UX_JOURNEY_SIM",
    },
    {
        "id": "P6",
        "name": "Synthesis / hybrid",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "Winning pattern map + premium hybrid from strongest verified patterns.",
        "future_skill": "DESIGN_SYNTHESIS",
    },
    {
        "id": "P7",
        "name": "Savings analysis",
        "autonomy": "partial",
        "risk": "MEDIUM",
        "desc": "Document possible $0 alternatives. Never cancel until dependencies verified. HITL before action.",
        "future_skill": "COST_AUDIT",
        "hitl_domain": "subscription",
    },
    {
        "id": "P8",
        "name": "Revenue opportunities",
        "autonomy": "partial",
        "risk": "MEDIUM",
        "desc": "Booking, gift cards, rebooking, referrals — estimates not guarantees. HITL before live changes.",
        "future_skill": "REVENUE_EXPERIMENT",
        "hitl_domain": "pricing",
    },
    {
        "id": "P9",
        "name": "Package 2 reinvestment",
        "autonomy": "hitl",
        "risk": "HIGH",
        "desc": "Optional spend recommendations only after verified savings. No auto-purchase.",
        "future_skill": "REINVEST_ADVISOR",
        "hitl_domain": "money",
    },
    {
        "id": "P10",
        "name": "HITL gate practice",
        "autonomy": "hitl",
        "risk": "LOW",
        "desc": "Format approval cards; silence ≠ approval.",
        "future_skill": "HITL_GATE",
    },
    {
        "id": "P11",
        "name": "Capability log maintenance",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "Record every meaningful task for future skill extraction.",
        "future_skill": "AUDIT_LOGGING",
    },
    {
        "id": "P12",
        "name": "Future skill candidates",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "Propose LEVI skills from evidence only.",
        "future_skill": "SKILL_EXTRACTION",
    },
    {
        "id": "P15",
        "name": "Levi requirements doc (design only)",
        "autonomy": "full",
        "risk": "LOW",
        "desc": "LEVI_FUTURE_REQUIREMENTS.md from observed capabilities — do not claim Levi is complete.",
        "future_skill": "REPORT_GENERATION",
    },
]

EASY_TOUCH_PHASES = SERVICE_PHASES  # alias only


@dataclass
class ProjectState:
    project_id: str = "service_client"
    public_url: str = ""
    current_phase: str = "P0"
    completed: List[str] = field(default_factory=list)
    notes: Dict[str, str] = field(default_factory=dict)
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProjectState":
        return cls(
            project_id=d.get("project_id") or "service_client",
            public_url=d.get("public_url") or "",
            current_phase=d.get("current_phase") or "P0",
            completed=list(d.get("completed") or []),
            notes=dict(d.get("notes") or {}),
            updated_at=d.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        )


class PhaseRunner:
    """Pre-MVP orchestrator for service capability discovery + delivery workflows."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_STATE
        self.state = ProjectState()
        self.log = CapabilityLog()
        self.hitl = HITLGate()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = ProjectState.from_dict(raw)
        except Exception:
            pass

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state.updated_at = datetime.now(timezone.utc).isoformat()
        # Atomic + owner-only: project state may reference client work.
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.state.to_dict(), fh, indent=2)
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        os.replace(tmp, self.path)

    def set_url(self, url: str) -> None:
        """Set the public site URL. Empty clears; non-empty must be http(s)."""
        cleaned = url.strip() if isinstance(url, str) else ""
        if cleaned and not (
            cleaned.startswith("http://") or cleaned.startswith("https://")
        ):
            raise ValueError(
                "url must start with http:// or https:// (public sites only)"
            )
        self.state.public_url = cleaned
        self._persist()

    def status(self) -> str:
        lines = [
            f"=== Project: {self.state.project_id} (pre-MVP usable) ===",
            f"URL: {self.state.public_url or '(set with: levi project --url https://...)'}",
            f"Current phase: {self.state.current_phase}",
            f"Completed: {', '.join(self.state.completed) or '—'}",
            "",
            "Phases:",
        ]
        for p in SERVICE_PHASES:
            mark = (
                "✓"
                if p["id"] in self.state.completed
                else ("→" if p["id"] == self.state.current_phase else "·")
            )
            lines.append(
                f"  {mark} {p['id']} {p['name']}  [{p['autonomy']}/{p['risk']}]"
            )
        lines.append("")
        lines.append(
            "Principle: AUTONOMOUS ON EXECUTION · HUMAN-CONTROLLED ON CONSEQUENCES"
        )
        lines.append("Silence is not approval. Production/money/customer data = HITL.")
        return "\n".join(lines)

    def phase_info(self, phase_id: str) -> Optional[Dict[str, Any]]:
        for p in SERVICE_PHASES:
            if p["id"].upper() == phase_id.upper():
                return p
        return None

    def run_phase(self, phase_id: Optional[str] = None) -> str:
        """
        Execute what can be done safely for a phase.
        Pre-MVP: produces guidance + logs + HITL cards; does not invent facts or deploy.
        """
        pid = (phase_id or self.state.current_phase).upper()
        meta = self.phase_info(pid)
        if not meta:
            return f"Unknown phase {pid}. Known: " + ", ".join(
                p["id"] for p in SERVICE_PHASES
            )

        lines = [
            f"══ Phase {meta['id']}: {meta['name']} ══",
            f"Autonomy: {meta['autonomy']}  Risk: {meta['risk']}",
            meta["desc"],
            "",
        ]

        # HITL path for consequential phases
        if meta.get("autonomy") in ("hitl", "partial") and meta.get("hitl_domain"):
            req = self.hitl.propose(
                what=f"Proceed with phase {meta['id']} ({meta['name']}) beyond documentation",
                why="Phase may touch business cost, pricing, or commitments",
                changes="No automatic spend/cancel/production change — documentation + recommendations only until approved",
                cost="$0 unless owner approves later",
                risk=meta["risk"],
                benefit="Clear options without silent side effects",
                if_approved="Continue analysis and draft recommendations",
                if_denied="Stay at documentation-only; no external changes",
                domain=meta["hitl_domain"],
            )
            lines.append(req.format_card())
            lines.append("")
            lines.append("Phase continues in DOCUMENTATION-ONLY mode until APPROVE.")
            self.log.log(
                task=f"Phase {meta['id']} HITL gate",
                result="blocked",
                tools=["hitl"],
                human_required=True,
                future_skill="HITL_GATE",
                phase=meta["id"],
                output_summary=f"Pending {req.id}",
            )
            return "\n".join(lines)

        # Safe autonomous / guided execution
        if meta["id"] == "P0":
            lines.extend(self._run_p0())
        elif meta["id"] == "P1":
            lines.extend(self._run_p1())
        elif meta["id"] == "P11":
            lines.append(self.log.format(limit=10))
        elif meta["id"] == "P12":
            cands = self.log.skill_candidates()
            lines.append("Skill candidates from log:")
            lines.append(
                ", ".join(cands) if cands else "(none yet — run earlier phases)"
            )
            for p in SERVICE_PHASES:
                lines.append(f"  · {p['future_skill']} — {p['name']}")
        else:
            lines.append("PRE-MVP guided mode:")
            lines.append(f"  1) Perform: {meta['desc']}")
            lines.append(
                "  2) Separate OBSERVED FACT / INFERENCE / HYPOTHESIS / UNKNOWN"
            )
            lines.append('  3) Log results: levi project --log "..."')
            lines.append("  4) Mark complete: levi project --complete " + meta["id"])
            if meta.get("needs"):
                lines.append(f"  Needs: {meta['needs']}")
            if not self.state.public_url and meta["id"] in ("P1", "P2", "P3"):
                lines.append("  Set URL first: levi project --url https://example.com")

        self.log.log(
            task=f"Phase {meta['id']} {meta['name']}",
            result="partial" if meta["id"] not in ("P0",) else "completed",
            tools=["phase_runner"],
            automatable="partial" if meta["autonomy"] != "full" else "yes",
            human_required=meta["autonomy"] != "full",
            future_skill=meta.get("future_skill") or "",
            phase=meta["id"],
            output_summary="pre-MVP phase guidance emitted",
            safety="no production mutation",
        )
        return "\n".join(lines)

    def _run_p0(self) -> List[str]:
        # Honest audit of what *this* LEVI core + host can do
        rows = [
            ("WEB ACCESS", "DOABLE NOW", "fetch public pages when URL given"),
            ("BROWSER CONTROL", "PARTIAL", "depends on host tools"),
            ("FILESYSTEM", "DOABLE NOW", "local ~/.levi + project artifacts"),
            ("TERMINAL", "DOABLE NOW", "local shell in sandbox/host"),
            ("CODE EXECUTION", "DOABLE NOW", "Python kernel + tests"),
            ("GITHUB", "DOABLE WITH ADDITIONAL ACCESS", "needs auth"),
            ("CLOUDFLARE / DNS", "HITL + ACCESS", "never auto"),
            ("CONNECTORS", "PARTIAL", "user-connected only"),
            ("AUTHENTICATED SITES", "HUMAN TAKEOVER", "credentials not assumed"),
            ("PREVIEW DEPLOYMENTS", "DOABLE WITH ACCESS", "no production"),
            ("HITL GATES", "DOABLE NOW", "levi project hitl"),
            ("CAPABILITY LOG", "DOABLE NOW", "levi project log"),
            ("MULTI-AGENT", "PARTIAL", "specialists exist; full swarm later"),
        ]
        lines = ["Capability audit (honest, not exaggerated):", ""]
        for name, cls, note in rows:
            lines.append(f"  {name:22} {cls:28} {note}")
        lines.append("")
        lines.append(
            "Mark P0 complete when you accept this audit: levi project --complete P0"
        )
        return lines

    def _run_p1(self) -> List[str]:
        lines = ["Site archaeology checklist:", ""]
        if not self.state.public_url:
            lines.append(
                "NO URL SET — cannot fetch. Set: levi project --url https://..."
            )
            lines.append("Until then, document only what the owner provides.")
            return lines
        lines.append(f"Target: {self.state.public_url}")
        lines.append("Capture (OBSERVED only):")
        for item in [
            "pages & navigation",
            "services listed",
            "prices if shown (else UNKNOWN)",
            "booking path",
            "gift-card path",
            "contact / social",
            "visual hierarchy, type, color",
            "mobile vs desktop notes",
            "SEO basics (title, meta if visible)",
        ]:
            lines.append(f"  · {item}")
        lines.append("")
        lines.append("Separate: OBSERVED FACT | INFERENCE | HYPOTHESIS | UNKNOWN")
        lines.append("Do not invent reviews, awards, or medical claims.")
        lines.append('Log findings: levi project --log "archaeology: ..."')
        return lines

    def complete(self, phase_id: str) -> str:
        """Mark a phase complete. Unknown phase ids are rejected, not logged."""
        known = [p["id"] for p in SERVICE_PHASES]
        pid = phase_id.upper() if isinstance(phase_id, str) else ""
        if pid not in known:
            raise ValueError(
                "unknown phase %r — known phases: %s" % (phase_id, ", ".join(known))
            )
        if pid not in self.state.completed:
            self.state.completed.append(pid)
        # advance current to next incomplete
        for p in SERVICE_PHASES:
            if p["id"] not in self.state.completed:
                self.state.current_phase = p["id"]
                break
        self._persist()
        self.log.log(
            task=f"Mark complete {pid}",
            result="completed",
            future_skill="PHASE_TRACKING",
            phase=pid,
        )
        return f"Completed {pid}. Current → {self.state.current_phase}"

    def add_log_note(self, text: str, phase: str = "", skill: str = "") -> str:
        """Append a free-text note to the capability log."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("log note text must be a non-empty string")
        e = self.log.log(
            task=text[:200],
            result="completed",
            phase=phase or self.state.current_phase,
            future_skill=skill,
            output_summary=text[:300],
        )
        return f"Logged [{e.id}]"
