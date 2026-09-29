"""Chauncey's own model as a chat provider: the BPE TinyGPT brain.

This is the link between his published/training model and his personal
agent: the agent pulls HIS model, not a rented provider. Local-first —
the checkpoint loads from his own disk; nothing is fetched at chat
time.

Honest capability boundary (measured, not claimed):
* The model generates text continuations from the conversation. At its
  current size/training (1.8M params, loss ~2.4 and falling) it is NOT
  a reliable tool-caller: this provider never fabricates tool calls.
  When the model emits no valid tool call, the loop ends with its
  text — exactly what the weights actually said.
* Tool-use through the model becomes real when evals say it is; until
  then the SI face (deterministic planner) carries the tools and the
  AI face carries the voice. That is the twin.

Weights resolution: ``LEVI_BRAIN_BPE`` env var, else the newest
``tiny-gpt-bpe-ckpt-*.pt`` in the staging dir, else the packaged
``weights/tiny-gpt-bpe.pt``. Missing weights or torch → not available
(never an exception at import).

Stdlib + torch only. No network.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from levi.agent.providers import (ChatMessage, ChatProvider, ChatResponse,
                                  ProviderToolCall)

HERE = Path(__file__).resolve().parent
BRAIN_DIR = HERE.parent / "brain"
TRAIN_DIR = BRAIN_DIR / "train"
STAGING_DIR = BRAIN_DIR / "weights" / "staging_bpe"
PACKAGED = BRAIN_DIR / "weights" / "tiny-gpt-bpe.pt"

GENERATE_TOKENS = 120
TEMPERATURE = 0.8


def resolve_bpe_checkpoint() -> Path | None:
    """Newest usable BPE checkpoint, or None."""
    override = os.environ.get("LEVI_BRAIN_BPE", "").strip()
    if override:
        p = Path(override)
        return p if p.is_file() else None
    if STAGING_DIR.is_dir():
        ckpts = sorted(STAGING_DIR.glob("tiny-gpt-bpe-ckpt-*.pt"))
        if ckpts:
            return ckpts[-1]
    if PACKAGED.is_file():
        return PACKAGED
    return None


def torch_available() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except Exception:
        return False


class BpeBrainProvider(ChatProvider):
    """Chauncey's BPE brain behind the ChatProvider contract."""

    name = "levi-bpe-brain"

    def __init__(self) -> None:
        self._model: Any = None
        self._tok: Any = None
        self._cfg: dict = {}
        self._load_error: str | None = None
        self._ckpt_path: Path | None = None

    # -- availability ----------------------------------------------------

    def is_available(self) -> bool:
        if self._model is not None:
            return True
        if not torch_available():
            self._load_error = "torch not installed"
            return False
        ckpt = resolve_bpe_checkpoint()
        if ckpt is None:
            self._load_error = "no BPE checkpoint found"
            return False
        return self._ensure_model()

    def status(self) -> dict:
        avail = self.is_available()
        return {
            "provider": self.name,
            "available": avail,
            "checkpoint": str(self._ckpt_path) if self._ckpt_path else None,
            "config": self._cfg,
            "load_error": self._load_error,
            "capability": (
                "text generation from his own weights; "
                "model tool-calling not yet capable — never fabricated"
            ),
        }

    # -- loading ----------------------------------------------------------

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        try:
            import torch

            sys_path_added = False
            import sys

            if str(TRAIN_DIR) not in sys.path:
                sys.path.insert(0, str(TRAIN_DIR))
                sys_path_added = True
            try:
                from tok import ByteBPETokenizer
                from train import TinyGPT
            finally:
                if sys_path_added:
                    sys.path.remove(str(TRAIN_DIR))

            ckpt_path = resolve_bpe_checkpoint()
            if ckpt_path is None:
                self._load_error = "no BPE checkpoint found"
                return False
            ckpt = torch.load(ckpt_path, map_location="cpu",
                              weights_only=False)
            cfg = dict(ckpt.get("config", {}))
            arch = ckpt.get("arch", {}) or {}
            n_layer = int(arch.get("n_layer", cfg.get("n_layer", 2)))
            n_head = int(arch.get("n_head", cfg.get("n_head", 2)))
            n_embd = int(arch.get("n_embd", cfg.get("n_embd", 96)))
            block_size = int(arch.get("block_size", cfg.get("block_size", 48)))
            vocab_size = int(cfg.get("vocab_size", 8192))

            model = TinyGPT(vocab_size=vocab_size, n_layer=n_layer,
                            n_head=n_head, n_embd=n_embd,
                            block_size=block_size)
            model.load_state_dict(ckpt["model_state"])
            model.eval()

            tok_path = TRAIN_DIR / "tokenizer.json"
            if not tok_path.is_file():
                self._load_error = f"tokenizer missing: {tok_path}"
                return False
            tok = ByteBPETokenizer.load(str(tok_path))

            self._model = model
            self._tok = tok
            self._cfg = {
                "vocab_size": vocab_size, "n_layer": n_layer,
                "n_head": n_head, "n_embd": n_embd,
                "block_size": block_size,
                "step": ckpt.get("step"), "round": ckpt.get("round"),
            }
            self._ckpt_path = ckpt_path
            self._load_error = None
            return True
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            return False

    # -- generation -------------------------------------------------------

    def _generate(self, prompt: str, max_tokens: int = GENERATE_TOKENS) -> str:
        import torch
        import torch.nn.functional as F

        bs = self._cfg["block_size"]
        ids = self._tok.encode(prompt)[-bs:] or [0]
        x = torch.tensor([ids])
        with torch.no_grad():
            for _ in range(max_tokens):
                logits, _ = self._model(x[:, -bs:])
                probs = F.softmax(logits[0, -1] / TEMPERATURE, dim=-1)
                nxt = torch.multinomial(probs, 1).item()
                ids.append(nxt)
                x = torch.tensor([ids])
                # stop at a clean end when the model emits one
                if self._tok.decode([nxt]).strip().endswith(("<|end|>",)):
                    break
        return self._tok.decode(ids)

    def chat(self, messages: list[ChatMessage], tools: list[dict]) -> ChatResponse:
        t0 = time.perf_counter()
        if not self._ensure_model():
            return ChatResponse(
                error=f"bpe brain unavailable: {self._load_error}")
        # Conversation → one prompt: last user message drives generation,
        # with a short rolling tail for context.
        tail = []
        for m in messages[-6:]:
            if m.role in ("system", "user", "assistant") and m.content:
                tail.append(f"{m.role}: {m.content[:800]}")
        tail.append("assistant:")
        prompt = "\n".join(tail)[-2000:]
        try:
            full = self._generate(prompt)
            # The model's own continuation is everything after our prompt.
            text = full[len(prompt):].strip() or full.strip()
        except Exception as exc:
            return ChatResponse(error=f"generation failed: {exc}")
        ms = int((time.perf_counter() - t0) * 1000)
        # No tool calls are fabricated: at this training stage the model
        # cannot reliably emit them, so none are claimed.
        _ = ProviderToolCall  # (kept import honest — reserved for eval-gated future)
        return ChatResponse(text=text, tool_calls=[], model="levi-bpe-brain",
                            provider=self.name, latency_ms=ms)
