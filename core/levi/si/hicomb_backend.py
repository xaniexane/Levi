"""Hicomb wiring for the SI layer (additive — no core files touched).

``BrainBackend`` structurally implements the ``ModelBackend`` protocol
in ``levi.hicomb.ai`` (name / available / complete / chat) so the
existing ``PairProgrammer`` can seat his own tiny-gpt brain without any
Hicomb core rewrite:

    from levi.si.hicomb_backend import BrainBackend
    from levi.hicomb.ai import PairProgrammer
    prog = PairProgrammer(backend=BrainBackend())

Honest provenance is preserved: completions come back with
source="model", label="model · brain-draft (not reasoning)", and low
confidence. If the brain cannot load, ``available()`` is False and
PairProgrammer keeps its local engine, labeled local-only — exactly as
before. L1, L3, L4.
"""

from __future__ import annotations

from typing import List, Optional

from .engine import SIEngine
from .laws import LAWS  # noqa: F401

_BRAIN_LABEL = "model · brain-draft (not reasoning)"


class BrainBackend:
    """ModelBackend over the SI layer's brain tier.

    - complete(): raw brain continuation of the buffer prefix, cut to a
      single candidate, labeled not-reasoning, confidence 0.25.
    - chat(): brain continuation prefixed with an honest header; never
      presented as explanation or advice.
    - available(): lazy load + tiny self-test, cached; any failure ->
      False (PairProgrammer then reports local-only, per its own code).
    """

    def __init__(self, engine: Optional[SIEngine] = None) -> None:
        self._engine = engine or SIEngine()
        self._available: Optional[bool] = None

    def name(self) -> str:
        return "levi-brain-tiny-gpt"

    def available(self) -> bool:
        if self._available is not None:
            return self._available
        self._available = self._self_test()
        return self._available

    def _self_test(self) -> bool:
        try:
            brain = self._engine._brain_or_none()  # noqa: SLF001 (same layer)
            if brain is None:
                return False
            out = brain.generate("def ", max_new_chars=8, temperature=0.5, seed=1)
            return bool(str(out.get("continuation", "")).strip())
        except Exception:
            return False

    def complete(
        self, prefix: str, context: str, language: str
    ) -> List["Completion"]:
        from levi.hicomb.ai import Completion

        brain = self._engine._brain_or_none()  # noqa: SLF001
        if brain is None:
            return []
        try:
            out = brain.generate(
                (prefix or "")[-200:], max_new_chars=60, temperature=0.6, seed=7
            )
            cont = str(out.get("continuation", ""))
            # one candidate: first line, whitespace-normalized, bounded
            cand = " ".join(cont.splitlines()[0].split())[:80] if cont.strip() else ""
            if not cand:
                return []
            return [
                Completion(
                    text=cand,
                    source="model",
                    label=_BRAIN_LABEL,
                    confidence=0.25,
                )
            ]
        except Exception:
            return []

    def chat(self, prompt: str, context: str, language: str) -> str:
        res = self._engine.generate_draft(
            f"{prompt}\n---\n{(context or '')[-400:]}", seed=7
        )
        return (
            f"[{res.tier} · not reasoning]\n{res.text}\n"
            f"(limits: {'; '.join(res.limits)})"
        )


__all__ = ["BrainBackend"]
