"""Alpha's build-planning deliberation: multi-step deliberation over an honest substrate.

``Reasoner.reason(task)`` runs propose -> critique -> verdict (see
``levi.alpha.si.deliberation``) and returns::

    {"answer", "substrate", "limits", "proposals", "critiques", "verdict",
     "brain"}

This is the deliberation behind build decisions. Plan-first is the
builder's law: Alpha proposes build approaches, critiques them, and
renders a verdict on the plan — and the verdict always states which
substrate reasoned.

HONESTY LAW — this is the whole point of the module:

- The verdict always states which substrate reasoned. The deliberation
  itself always runs on the rules engine, so the decider is always the
  rules engine — ``substrate`` says so.
- The native-brain weights are *exercised*, never assumed:
  ``core/levi/brain/weights/tiny-gpt.pt`` is loaded through
  ``levi.brain.inference`` and asked to continue the task text. That raw
  continuation joins the deliberation as the ``brain-voice`` proposal —
  verbatim, labeled, critiqued — and the substrate becomes
  ``"rules-engine + native-brain"``. The brain-voice can never win the
  verdict (its score is capped below every rules stance), so Alpha never
  claims brain reasoning it didn't do.
- When the native-brain weights are usable, the brain-voice's raw
  continuation is computed first and handed to ``propose``: the skeptical
  stance quotes the brain's distinctive drift words as evidence that the
  task's phrasing is loose (labeled as garbled proof-of-learning output —
  never as reasoning, never obeyed). The brain-voice proposal itself is
  still appended separately, scored, critiqued, and capped below every
  rules stance.
- If no weights are usable, ``limits`` says so plainly and the rules
  engine still delivers the deliberation. Alpha never claims brain
  reasoning it didn't do.

Stdlib only at import time: torch (if installed) is imported lazily
inside the brain loader, and brain failures degrade to an honest report —
never an exception.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .si import deliberation

ORIGIN = "levi-alpha/reason"
SUBSTRATE_RULES = "rules-engine"
SUBSTRATE_HYBRID = "rules-engine + native-brain"

BRAIN_STANCE = "brain-voice"
# The brain-voice can never win the verdict: confidence minus the default
# penalty lands below every rules stance (direct 0.45, skeptical 0.40,
# minimal 0.60). It is heard, never obeyed.
BRAIN_CONFIDENCE = 0.35
BRAIN_SEED = 1337
BRAIN_TEMPERATURE = 0.8

# The proof-of-learning brain is garbled — said verbatim wherever the
# brain-voice appears, so no reader mistakes it for reasoning.
BRAIN_GARBLED_CAVEAT = (
    "the brain's samples are garbled proof-of-learning output "
    "(see weights/eval.json and weights/samples.md) — not reasoning"
)


def _default_brain_root() -> Path:
    # core/levi/alpha/reason.py -> parents[1] is core/levi
    return Path(__file__).resolve().parents[1] / "brain"


class Reasoner:
    """Multi-step deliberator with an honest substrate report."""

    def __init__(
        self,
        brain_dir: Optional[str] = None,
        brain_chars: int = 160,
    ) -> None:
        self.brain_root = Path(brain_dir) if brain_dir else _default_brain_root()
        self.brain_chars = max(0, int(brain_chars))
        # Cached (BrainInference | None, detail): the weights load once.
        self._brain: Optional[Any] = None
        self._brain_detail: str = ""
        self._brain_loaded: bool = False

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
            "inference_wired": False,
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
        brain, detail = self._load_brain_inference()
        report["weights_loadable"] = True
        report["inference_wired"] = brain is not None
        if brain is not None:
            report["detail"] = (
                "weights file loads under torch and the offline inference "
                "path (levi.brain.inference) is wired: the brain continues "
                "the task text as a labeled brain-voice proposal. The "
                "decider stays the rules engine."
            )
        else:
            report["detail"] = f"weights load, but inference cannot run: {detail}"
        return report

    # -- brain inference ---------------------------------------------------

    def _load_brain_inference(self) -> Tuple[Optional[Any], str]:
        """Load the brain once; return (BrainInference | None, detail)."""
        if self._brain_loaded:
            return self._brain, self._brain_detail
        self._brain_loaded = True
        if self.brain_chars <= 0:
            self._brain_detail = "brain disabled for this reasoner (brain_chars=0)"
            return None, self._brain_detail
        try:
            from levi.brain import inference as brain_inference
        except ImportError as exc:
            self._brain_detail = (
                f"brain inference module unavailable: {exc.__class__.__name__}: {exc}"
            )
            return None, self._brain_detail
        weights = self.brain_root / "weights" / "tiny-gpt.pt"
        try:
            self._brain = brain_inference.load_brain(str(weights))
        except brain_inference.BrainError as exc:
            self._brain_detail = str(exc)
            return None, self._brain_detail
        except Exception as exc:  # noqa: BLE001 - defensive; reason IS the report
            self._brain_detail = (
                f"unexpected brain load failure "
                f"({exc.__class__.__name__}: {exc}) — reported, not raised"
            )
            return None, self._brain_detail
        desc = self._brain.describe()
        self._brain_detail = (
            f"brain loaded: {desc['params']} params, "
            f"{desc['training_steps']} training steps, "
            f"{desc['vocab_chars']}-char vocab, sha256 match: "
            f"{desc['sha256_match']}"
        )
        return self._brain, self._brain_detail

    def _brain_voice(self, task: str) -> Optional[Dict[str, Any]]:
        """Ask the brain to continue the task text; return a labeled
        proposal, or None when the brain cannot run (honesty lives in
        ``limits``, not here)."""
        brain, _ = self._load_brain_inference()
        if brain is None:
            return None
        try:
            gen = brain.generate(
                task,
                max_new_chars=self.brain_chars,
                temperature=BRAIN_TEMPERATURE,
                seed=BRAIN_SEED,
            )
        except Exception:  # noqa: BLE001 - generation failures degrade silently;
            return None  # the honest reason is already in the substrate report
        return {
            "stance": BRAIN_STANCE,
            "text": gen["continuation"],
            "confidence": BRAIN_CONFIDENCE,
            "label": "raw brain continuation — not reasoning",
            "generation": {
                "unmapped_chars": gen["unmapped_chars"],
                "max_new_chars": gen["max_new_chars"],
                "temperature": gen["temperature"],
                "seed": gen["seed"],
                "params": gen["params"],
            },
        }

    def substrate_report(self) -> Dict[str, Any]:
        """Full substrate picture: what reasoned, and the brain's status."""
        brain_probe = self.probe_brain()
        brain, detail = self._load_brain_inference()
        if brain is not None:
            limits = (
                "Propose -> critique -> verdict deliberation on the "
                "rules-engine + native-brain substrate. The native-brain "
                "weights continue the task text as a labeled brain-voice "
                "proposal (verbatim, critiqued like any stance); the rules "
                "engine still decides the verdict. Caveat: "
                + BRAIN_GARBLED_CAVEAT
                + ". "
                + detail
            )
            substrate = SUBSTRATE_HYBRID
        elif brain_probe["weights_present"]:
            limits = (
                "Rules-based deliberation (propose -> critique -> verdict) on "
                "the rules-engine substrate. Native-brain weights exist but "
                f"are not usable: {detail or brain_probe['detail']}."
            )
            substrate = SUBSTRATE_RULES
        else:
            limits = (
                "Rules-based deliberation (propose -> critique -> verdict) on "
                "the rules-engine substrate. No usable native-brain weights "
                "were found — Alpha reasoned with the rules engine, not the "
                "brain."
            )
            substrate = SUBSTRATE_RULES
        return {
            "substrate": substrate,
            "limits": limits,
            "brain": brain_probe,
        }

    # -- the deliberation ---------------------------------------------------

    def reason(self, task: str) -> Dict[str, Any]:
        """Deliberate over ``task``; refuse empty tasks outright."""
        if not isinstance(task, str) or not task.strip():
            raise ValueError(
                "empty task: nothing to reason about — give Alpha something to chew on"
            )
        report = self.substrate_report()
        # The brain-voice is computed first so the skeptical stance can
        # quote the brain's raw continuation as evidence of loose phrasing
        # (heard in deliberation, never obeyed in the verdict).
        brain_proposal = self._brain_voice(task)
        brain_continuation = (
            brain_proposal["text"] if brain_proposal is not None else None
        )
        proposals = deliberation.propose(task, brain_continuation=brain_continuation)
        if brain_proposal is not None:
            proposals.append(brain_proposal)
        critiques = deliberation.critique(proposals)
        verdict = deliberation.verdict(proposals, critiques, report["substrate"])
        if report["substrate"] == SUBSTRATE_HYBRID:
            # The decider is still the rules engine; the note must say what
            # the brain actually did — a raw continuation, not reasoning.
            verdict["note"] = (
                f"Reasoned on the {SUBSTRATE_HYBRID} substrate: the "
                "propose/critique/verdict deliberation ran on the rules "
                "engine, which chose the verdict above. The native-brain "
                "weights contributed one raw text continuation, included "
                "verbatim as the brain-voice proposal and critiqued with "
                "the rest. Caveat: " + BRAIN_GARBLED_CAVEAT + "."
            )
        return {
            "answer": verdict["answer"],
            "substrate": report["substrate"],
            "limits": report["limits"],
            "proposals": proposals,
            "critiques": critiques,
            "verdict": verdict,
            "brain": report["brain"],
        }


__all__ = [
    "ORIGIN",
    "SUBSTRATE_RULES",
    "SUBSTRATE_HYBRID",
    "BRAIN_STANCE",
    "Reasoner",
]
