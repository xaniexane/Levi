"""BT — Bent Intelligence. Brilliant because it is intentionally narrow.

The honest version of the pitch: take a small local model (Phi-3-mini,
Gemma 2 2B — one-time download, then offline forever), lock it to ONE
domain with a strict system prompt + your FR corrections as few-shot
context, and it becomes fast, tiny, and weirdly good at that one thing
because it has no other options.

What this module does NOT claim: "2-bit QLoRA in 15 minutes" is not a
real pipeline — you fine-tune at higher precision, *then* quantize down
(see train_bt.py for the honest script). This harness runs inference
against a local runner if one exists and says so plainly if not.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


DOMAIN_PROMPTS = {
    "journal": (
        "You are a private emotional-journal intuition. You only reflect, "
        "never advise, never diagnose. Short, plain, warm. You know nothing "
        "outside this journal."
    ),
    "code-errors": (
        "You are a code-error intuition. You only explain this error and the "
        "smallest fix. No lectures, no general tutoring. You know nothing "
        "outside debugging."
    ),
}


@dataclass
class BentResult:
    text: str
    backend: str   # "ollama" | "stub"
    domain: str


class BentMind:
    """Domain-locked small-model harness. Local runners only, never cloud."""

    def __init__(self, domain: str = "journal", model: str = "phi3:mini"):
        if domain not in DOMAIN_PROMPTS:
            raise ValueError(f"unknown BT domain: {domain}")
        self.domain = domain
        self.model = model
        self.system = DOMAIN_PROMPTS[domain]

    def _ollama(self, prompt: str, few_shot: str = "") -> str | None:
        if not shutil.which("ollama"):
            return None
        full = f"{self.system}\n{few_shot}\nUser: {prompt}\nBent:"
        try:
            out = subprocess.run(
                ["ollama", "run", self.model, full],
                capture_output=True, text=True, timeout=120,
            )
            return out.stdout.strip() or None
        except (subprocess.SubprocessError, OSError):
            return None

    def generate(self, prompt: str, few_shot: str = "") -> BentResult:
        """Try the local model; fall back to an honest stub, never the cloud."""
        text = self._ollama(prompt, few_shot)
        if text is None:
            text = (
                f"[BT/{self.domain} offline stub — no local model installed. "
                f"One-time: `ollama pull {self.model}`, then this answers "
                "locally in <1s. Nothing was sent anywhere.]"
            )
            return BentResult(text=text, backend="stub", domain=self.domain)
        return BentResult(text=text, backend="ollama", domain=self.domain)
