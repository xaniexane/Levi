"""Native SI core base — shared rules-kernel driver for all crew roles."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


class SiCore:
    """A native SI core for one crew role."""

    role: str = ""
    rules: list = []  # type: ignore[assignment]
    corpus_note_text: str = ""

    def weights_dir(self) -> Path:
        """~/.levi/si_team/weights/<role>/, LEVI_HOME-overridable."""
        home = Path(os.environ.get("LEVI_HOME", Path.home() / ".levi"))
        return home / "si_team" / "weights" / self.role

    def corpus_note(self) -> str:
        return self.corpus_note_text

    def weights_present(self) -> bool:
        d = self.weights_dir()
        return d.is_dir() and any(d.iterdir())

    def substrate_name(self) -> str:
        return "rules-engine"

    def reason(self, task: str) -> Dict[str, object]:
        from levi.si_team.si import kernel

        answer, rule_tag = kernel.reason(self.rules, task, self._fallback)
        limits = [
            "rules-engine reasoning only — trainable SI weights are not finished yet",
            "no persistent memory of past consults (per-consult reasoning)",
        ]
        if not self.weights_present():
            limits.append(
                f"no SI weights yet at {self.weights_dir()} — native-brain probe is not wired"
            )
        return {
            "answer": answer,
            "substrate_used": self.substrate_name(),
            "rule_tag": rule_tag,
            "limits": limits,
        }

    def _fallback(self, task: str) -> str:  # noqa: ARG002
        return (
            f"[{self.role.upper()}] No rule matched your task yet, so here is "
            "the honest default: I can only reason from my current rule set. "
            "Give me more detail and I'll work what I have harder."
        )
