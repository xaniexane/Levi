"""Alpha's reasoner: multi-step deliberation over an honest substrate.

``Reasoner.reason(task)`` runs propose -> critique -> verdict (see
``levi.alpha.si.deliberation``) and returns::

    {"answer", "substrate", "limits", "proposals", "critiques", "verdict",
     "brain"}

HONESTY LAW — this is the whole point of the module:

- The verdict always states which substrate reasoned. In this build the
  deliberation itself is always the rules engine, so ``substrate`` is
  always ``"rules-engine"``.
- The native-brain weights are *probed*, never assumed:
  ``core/levi/brain/weights/tiny-gpt.pt`` plus any
  ``runs/tiny-gpt-v2-*/checkpoints``. The probe reports present /
  loadable / why-not, and that report lands verbatim in ``limits``.
- If no weights are usable, ``limits`` says so plainly and the rules
  engine still delivers the deliberation. Alpha never claims brain
  reasoning it didn't do.

Stdlib only at import time: torch (if installed) is imported lazily
inside the probe, and probe failures degrade to an honest report —
never an exception.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .si import deliberation

ORIGIN = "levi-alpha/reason"
SUBSTRATE_RULES = "rules-engine"


def _default_brain_root() -> Path:
    # core/levi/alpha/reason.py -> parents[1] is core/levi
    return Path(__file__).resolve().parents[1] / "brain"


class Reasoner:
    """Multi-step deliberator with an honest substrate report."""

    def __init__(self, brain_dir: Optional[str] = None) -> None:
        self.brain_root = Path(brain_dir) if brain_dir else _default_brain_root()

    # -- substrate probing -------------------------------------------------

    def probe_brain(self) -> Dict[str, Any]:
        """Probe the native-brain weights; report, never assume."""
        weights = self.brain_root / "weights" / "tiny-gpt.pt"
        runs = self.brain_root / "runs"
        checkpoints: List[str] = []
        if runs.is_dir():
            checkpoints = sorted(
                str(p) for p in runs.glob("tiny-gpt-v2-*/checkpoints") if p.is_dir()
            )
        report: Dict[str, Any] = {
            "weights_path": str(weights),
            "weights_present": weights.is_file(),
            "weights_loadable": False,
            "detail": "",
            "checkpoints": checkpoints,
        }
        if not weights.is_file():
            report["detail"] = (
                f"no native-brain weights found at {weights} — nothing to route over"
            )
            return report
        try:
            import torch  # noqa: F401
        except ImportError:
            report["detail"] = (
                "weights file present but torch is not installed in this "
                "environment — the weights cannot be exercised"
            )
            return report
        import torch

        try:
            torch.load(str(weights), map_location="cpu", weights_only=True)
        except Exception as exc:  # noqa: BLE001 - the reason IS the report
            report["detail"] = (
                f"weights file present but unreadable ({exc.__class__.__name__}: {exc})"
            )
            return report
        report["weights_loadable"] = True
        report["detail"] = (
            "weights file loads under torch, but this build has no live "
            "brain-inference path wired — deliberation stays rules-engine "
            "and is reported as such"
        )
        return report

    def substrate_report(self) -> Dict[str, Any]:
        """Full substrate picture: what reasoned, and the brain's status."""
        brain = self.probe_brain()
        if brain["weights_loadable"]:
            limits = (
                "Rules-based deliberation (propose -> critique -> verdict) on "
                "the rules-engine substrate. Native-brain weights are present "
                "and loadable, but this build wires no live inference path — "
                "Alpha reasons with the rules engine and says so."
            )
        elif brain["weights_present"]:
            limits = (
                "Rules-based deliberation (propose -> critique -> verdict) on "
                "the rules-engine substrate. Native-brain weights exist but "
                f"are not usable: {brain['detail']}."
            )
        else:
            limits = (
                "Rules-based deliberation (propose -> critique -> verdict) on "
                "the rules-engine substrate. No usable native-brain weights "
                "were found — Alpha reasoned with the rules engine, not the "
                "brain."
            )
        return {
            "substrate": SUBSTRATE_RULES,
            "limits": limits,
            "brain": brain,
        }

    # -- the deliberation ---------------------------------------------------

    def reason(self, task: str) -> Dict[str, Any]:
        """Deliberate over ``task``; refuse empty tasks outright."""
        if not isinstance(task, str) or not task.strip():
            raise ValueError(
                "empty task: nothing to reason about — give Alpha something to chew on"
            )
        report = self.substrate_report()
        proposals = deliberation.propose(task)
        critiques = deliberation.critique(proposals)
        verdict = deliberation.verdict(proposals, critiques, report["substrate"])
        return {
            "answer": verdict["answer"],
            "substrate": report["substrate"],
            "limits": report["limits"],
            "proposals": proposals,
            "critiques": critiques,
            "verdict": verdict,
            "brain": report["brain"],
        }


__all__ = ["ORIGIN", "SUBSTRATE_RULES", "Reasoner"]
