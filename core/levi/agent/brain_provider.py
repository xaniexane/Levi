"""LEVI's native brain provider (``levi-brain``).

This is LEVI's OWN model: a transformer trained from scratch on LEVI's
own corpus (see ``core/levi/brain/train/`` and ``docs/BRAIN_TRAINING.md``).
No LLaMA weights, no llama.cpp, no third-party model — the weights are
LEVI's, the architecture is LEVI's, the training data is LEVI's. The
next version of llama is not llama at all.

Honest design notes:

* The brain is currently a tiny char-level GPT (~2-4M params). It
  produces fluent-ish continuations with corpus flavor; it does NOT
  emit tool calls. Inside the agentic loop it answers in prose — the
  loop treats "no tool calls" as a final answer.
* ``torch`` is imported lazily; the core stays stdlib-only. Without
  torch, or without trained weights, :meth:`is_available` is False and
  provider selection falls back honestly (the loop always reports the
  provider it actually used).
* This provider is EXPLICIT-ONLY for now (``--provider levi-brain`` or
  ``LEVI_PROVIDER=levi-brain``). A 2-4M char model has not earned the
  default slot of the tool-using loop — it gets it when the native
  brain becomes tool-capable. See ``docs/BRAIN_TRAINING.md`` §4 for the
  native scaling roadmap. The old llama-server path (``levi-local``) is
  likewise explicit-only and legacy.
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Any

from levi.agent.providers import ChatMessage, ChatProvider, ChatResponse


def weights_path() -> Path:
    """Trained native-brain weights (``LEVI_BRAIN_WEIGHTS`` overrides)."""
    override = os.environ.get("LEVI_BRAIN_WEIGHTS", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent.parent / "brain" / "weights" / "tiny-gpt.pt"


def train_log() -> dict[str, Any]:
    """Training metadata (params, steps, loss) when present, else {}."""
    try:
        import json

        p = weights_path().parent / "train_log.json"
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def torch_available() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except Exception:
        return False


class NativeBrainProvider(ChatProvider):
    """Chat provider backed by LEVI's own trained brain."""

    name = "levi-brain"

    def __init__(self) -> None:
        self._model: Any = None
        self._chars: list[str] = []
        self._stoi: dict[str, int] = {}
        self._block_size = 256
        self._load_error: str | None = None

    # -- availability ----------------------------------------------------

    def is_available(self) -> bool:
        return weights_path().is_file() and torch_available()

    def status(self) -> dict[str, Any]:
        log = train_log()
        return {
            "provider": self.name,
            "available": self.is_available(),
            "weights": str(weights_path()),
            "weights_present": weights_path().is_file(),
            "torch_available": torch_available(),
            "params": log.get("params"),
            "steps": log.get("steps"),
            "loss_first": log.get("loss_first"),
            "loss_last": log.get("loss_last"),
        }

    # -- model loading (lazy, cached) ------------------------------------

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        try:
            import torch
            import torch.nn.functional as F  # noqa: F401  (kept for symmetry with train.py)
            from levi.brain.train.train import TinyGPT
        except Exception as exc:
            self._load_error = f"cannot load native brain: {exc}"
            return False
        try:
            # weights_only=True: the checkpoint must be plain tensors +
            # containers. A full pickle load would execute arbitrary code
            # from the file (LEVI_BRAIN_WEIGHTS can point anywhere), so a
            # checkpoint needing object reconstruction is refused outright.
            ckpt = torch.load(
                str(weights_path()), map_location="cpu", weights_only=True
            )
            if (
                not isinstance(ckpt, dict)
                or not isinstance(ckpt.get("chars"), list)
                or not isinstance(ckpt.get("model_state"), dict)
            ):
                raise ValueError(
                    "not a LEVI brain checkpoint: expected a mapping with "
                    "'chars' (list), 'config' (dict), 'model_state' (dict)"
                )
            chars = ckpt["chars"]
            cfg = ckpt.get("config", {})
            model = TinyGPT(
                len(chars),
                n_layer=int(cfg.get("n_layer", 4)),
                n_head=int(cfg.get("n_head", 4)),
                n_embd=int(cfg.get("n_embd", 128)),
                block_size=int(cfg.get("block_size", 256)),
            )
            model.load_state_dict(ckpt["model_state"])
            model.eval()
            self._model = model
            self._chars = list(chars)
            self._stoi = {c: i for i, c in enumerate(chars)}
            self._block_size = int(cfg.get("block_size", 256))
            return True
        except Exception as exc:
            self._load_error = f"cannot load native brain weights: {exc}"
            return False

    # -- generation ------------------------------------------------------

    def _prompt(self, messages: list[ChatMessage]) -> str:
        parts: list[str] = []
        for m in messages:
            role = (m.role or "").strip().lower()
            content = (m.content or "").strip()
            if not content:
                continue
            if role == "system":
                parts.append(content)
            elif role == "user":
                parts.append(f"user: {content}")
            elif role == "assistant":
                parts.append(f"assistant: {content}")
            elif role == "tool":
                parts.append(f"[{m.name or 'tool'} result] {content}")
        prompt = "\n".join(parts).strip()
        if not prompt:
            prompt = "Levi:"
        else:
            prompt += "\nassistant:"
        # the brain only sees the tail it was built for
        return prompt[-self._block_size :]

    def _generate(
        self, prompt: str, n_chars: int = 280, temperature: float = 0.9
    ) -> str:
        # Validate before importing torch: these are caller errors, and
        # torch may not even be installed.
        if not isinstance(n_chars, int) or isinstance(n_chars, bool) or n_chars < 1:
            raise ValueError(
                f"_generate: 'n_chars' must be an integer >= 1, got {n_chars!r}"
            )
        try:
            temperature = float(temperature)
        except (TypeError, ValueError):
            raise ValueError(
                f"_generate: 'temperature' must be a number, got {temperature!r}"
            ) from None
        if not (temperature > 0) or not math.isfinite(temperature):
            raise ValueError(
                f"_generate: 'temperature' must be a finite positive number, "
                f"got {temperature!r}"
            )
        import torch
        import torch.nn.functional as F

        model = self._model
        idx = torch.tensor([[self._stoi.get(c, 0) for c in prompt]], dtype=torch.long)
        with torch.no_grad():
            for _ in range(n_chars):
                logits = model(idx[:, -self._block_size :])
                probs = F.softmax(logits[:, -1, :] / temperature, dim=-1)
                nxt = torch.multinomial(probs, 1)
                idx = torch.cat([idx, nxt], dim=1)
                # stop at a clean-ish boundary past the minimum
                if idx.shape[1] - len(prompt) > 60 and int(nxt) == self._stoi.get(
                    "\n", -1
                ):
                    if idx.shape[1] - len(prompt) > 120:
                        break
        text = "".join(self._chars[i] for i in idx[0].tolist())
        return text[len(prompt) :].strip()

    # -- ChatProvider contract -------------------------------------------

    def chat(self, messages: list[ChatMessage], tools: list[dict]) -> ChatResponse:
        t0 = time.time()
        if not isinstance(messages, list) or not messages:
            raise ValueError(
                "chat: 'messages' must be a non-empty list of ChatMessage"
            )
        if not self._ensure_model():
            return ChatResponse(
                error=self._load_error or "native brain unavailable",
                provider=self.name,
                latency_ms=int((time.time() - t0) * 1000),
            )
        try:
            prompt = self._prompt(messages)
            continuation = self._generate(prompt)
        except Exception as exc:
            return ChatResponse(
                error=f"native brain generation failed: {exc}",
                provider=self.name,
                latency_ms=int((time.time() - t0) * 1000),
            )
        if not continuation:
            continuation = "(the native brain is still learning to speak — no continuation generated)"
        return ChatResponse(
            text=continuation,
            model="tiny-gpt",
            provider=self.name,
            latency_ms=int((time.time() - t0) * 1000),
        )
