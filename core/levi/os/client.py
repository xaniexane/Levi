"""Chat as a client of the daemon — the chat window submits outcomes,
the OS layer does the work and keeps the receipts.

This is the canon direction made concrete: the daemon is the always-on
OS layer; chat is one client among possible many (voice, schedule, API).
The client holds no state beyond what the OS layer returns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from levi.os.outcome import Plan, state_outcome
from levi.os.receipts import os_dir, read_receipts
from levi.os.runner import RunReport, default_home, execute

__all__ = ["ChatClient"]


class ChatClient:
    """Thin client over the OS runner."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self._home = Path(home) if home is not None else default_home()

    def run_outcome(self, text: str, member: Any = None) -> str:
        """State an outcome; plan it; execute it; report back in prose."""
        plan = state_outcome(text, member=member)
        report = execute(plan, home=self._home)
        return self._render(plan, report)

    def _render(self, plan: Plan, report: RunReport) -> str:
        lines = [f'Outcome: "{plan.outcome_text}"', ""]
        for step, result in zip(plan.steps, report.results, strict=True):
            lines.append(
                f"- {step.clause} -> {result.skill_id} "
                f"(rank {result.rank}, {result.status})"
            )
        lines.append("")
        lines.append(
            f"{len(report.results)} step(s), receipts verified: {report.chain_ok}"
        )
        return "\n".join(lines)

    def recent_receipts(self, limit: int = 10) -> List[dict]:
        """Read back the OS layer's receipts (newest last, capped)."""
        all_receipts = list(read_receipts(os_dir(self._home)))
        return [r.to_dict() for r in all_receipts[-limit:]]
