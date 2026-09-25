"""The AI seat: Chauncey's own trained brain behind the Operator contract.

Ruling (Chauncey, 2026-09-22): "None — I'm fully training it." NO
external AI provider is seated — no provider integrations, no API
keys, no key plumbing. The ``ai`` operator seat is filled by HIS OWN
trained models: the native training path (tiny-gpt lineage and future
runs), trained on his machines off his own records. Self-sufficiency
from the big providers: learn off them now, need them never.

So AI here does NOT mean a foreign model. :class:`AiBrainOperator`
is first-class LEVI (``is_foreign = False``), kind ``"ai"`` — the
trained-network mind, distinct from the synthetic/structural (SI)
and nano-bit (XI) minds. Served local now; servable over his own
cloud when that is stood up (declared direction, not built yet).

Present-but-honest about training state, per the honest-boundary law
(Chauncey, 2026-09-22): the operator declares what the current brain
can honestly do now versus what needs more training — and never fakes
a trained-brain result. When the brain cannot run here (no torch, no
weights), the seat degrades honestly instead of pretending.
"""

from __future__ import annotations

import glob
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.agent.providers import ChatMessage

from .contract import (
    AI,
    Operator,
    OperatorCapabilities,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
)

__all__ = ["AiBrainOperator", "AI_SEAT_NAME"]

#: Config/registry name of the AI seat.
AI_SEAT_NAME = "ai"


def _weights_dir(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    try:
        from levi.agent.brain_provider import weights_path

        return weights_path().parent
    except Exception:
        return Path("~/.levi/brain/weights").expanduser()


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


class AiBrainOperator(Operator):
    """The AI seat: his own trained brain, honestly governed.

    ``AiBrainOperator(provider=None, weights_dir=None)``. The provider
    override is a test/wiring seam — when omitted, the native brain
    provider (tiny-gpt lineage) is resolved lazily at call time, so
    importing this module never needs torch or weights.
    """

    name = AI_SEAT_NAME
    kind = AI
    version = "0.1.0"
    lineage = "levi:ai:trained-brain"
    is_foreign = False

    def __init__(
        self,
        *,
        provider: Any = None,
        weights_dir: Optional[str] = None,
    ) -> None:
        self._provider_override = provider
        self._weights_dir = _weights_dir(weights_dir)

    # -- training state ----------------------------------------------------

    def _resolve_provider(self) -> Any:
        if self._provider_override is not None:
            return self._provider_override
        from levi.agent.brain_provider import NativeBrainProvider

        return NativeBrainProvider()

    def training_state(self) -> Dict[str, Any]:
        """Honest training state: what the brain is and what it can do.

        Reads the repo's own training records defensively (eval.json,
        retrain logs — both gitignored build artifacts that may or may
        not be present in a given checkout). Nothing is invented: a
        missing record is reported as missing.
        """
        state: Dict[str, Any] = {
            "seat": self.name,
            "kind": self.kind,
            "architecture": "tiny-gpt",
            "live_checkpoint": "tiny-gpt.pt",
            "runnable": False,
            "why_not_runnable": "",
            "params": None,
            "train_steps": None,
            "held_out_loss": None,
            "records": {},
            "envelope_now": "",
            "needs_more_training": "",
        }
        try:
            provider = self._resolve_provider()
            runnable = bool(provider.is_available())
        except Exception as exc:
            runnable = False
            state["why_not_runnable"] = f"provider unavailable: {exc}"
        state["runnable"] = runnable
        if not runnable and not state["why_not_runnable"]:
            reasons = []
            try:
                from levi.agent.brain_provider import (
                    torch_available,
                    weights_path,
                )

                if not weights_path().is_file():
                    reasons.append("weights file missing")
                if not torch_available():
                    reasons.append("torch not installed in this environment")
            except Exception:
                reasons.append("brain provider could not be inspected")
            state["why_not_runnable"] = "; ".join(reasons) or "unknown"

        eval_rec = _read_json(self._weights_dir / "eval.json")
        if eval_rec:
            state["records"]["eval.json"] = True
            for key, field in (
                ("params", "params"),
                ("steps", "train_steps"),
                ("held_out_loss", "held_out_loss"),
            ):
                if isinstance(eval_rec.get(key), (int, float)):
                    state[field] = eval_rec[key]
        logs = sorted(glob.glob(str(self._weights_dir / "retrain_log_*.json")))
        if logs:
            latest = _read_json(Path(logs[-1]))
            if latest:
                state["records"]["latest_retrain_log"] = Path(logs[-1]).name
                train = latest.get("train") or {}
                if state["params"] is None and isinstance(
                    train.get("params"), (int, float)
                ):
                    state["params"] = train["params"]
                if state["train_steps"] is None and isinstance(
                    train.get("steps"), (int, float)
                ):
                    state["train_steps"] = train["steps"]
                ckpt = latest.get("checkpoint")
                if isinstance(ckpt, str) and ckpt:
                    state["live_checkpoint"] = Path(ckpt).name
                fb = latest.get("fallback_kept")
                if isinstance(fb, str) and fb:
                    state["standing_checkpoint"] = Path(fb).name

        params = state["params"]
        state["envelope_now"] = (
            "Narrow envelope: short continuations and tiny pattern "
            "completions inside its training distribution. "
            + (
                f"({int(params):,} params"
                + (
                    f", {int(state['train_steps'])} training steps"
                    if state["train_steps"]
                    else ""
                )
                + (
                    f", held-out loss {state['held_out_loss']:.2f}"
                    if isinstance(state["held_out_loss"], (int, float))
                    else ""
                )
                + ")"
                if isinstance(params, (int, float))
                else "(training records not present in this checkout)"
            )
        )
        state["needs_more_training"] = (
            "Fluent long-form generation, broad knowledge Q&A, nuanced "
            "reasoning and analysis, reliable instruction-following — "
            "all need more training. The seat says so instead of faking it."
        )
        return state

    def _state_note(self) -> str:
        st = self.training_state()
        bit = (
            "runnable"
            if st["runnable"]
            else f"not runnable here ({st['why_not_runnable']})"
        )
        return (
            f"AI seat: his own trained brain ({st['architecture']}, "
            f"checkpoint {st['live_checkpoint']}) — {bit}. "
            f"{st['envelope_now']} {st['needs_more_training']}"
        )

    # -- contract surface --------------------------------------------------

    def capabilities(self) -> OperatorCapabilities:
        return OperatorCapabilities(
            tools=(),
            streaming=False,
            memory_access=False,
            context_window=256,
            tool_use_loop=False,
            notes=(
                "The AI seat: Chauncey's own trained brain (tiny-gpt "
                "lineage), served local. No external providers, no API "
                "keys — self-sufficiency direction. Honest envelope: "
                "short continuations inside its training distribution; "
                "fluent long-form generation, broad knowledge, and "
                "nuanced reasoning need more training and are declared "
                "as such, never faked."
            ),
        )

    def health(self) -> OperatorHealth:
        st = self.training_state()
        if st["runnable"]:
            return OperatorHealth(
                ok=True, note=f"AI seat runnable. {self._state_note()}"
            )
        return OperatorHealth(ok=False, note=self._state_note())

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        t0 = time.perf_counter()
        st = self.training_state()
        if not st["runnable"]:
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                finish_reason="degraded",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=(
                    "ai seat: trained brain not runnable here "
                    f"({st['why_not_runnable']}) — this needs more "
                    "training/infra; not faked"
                ),
                note=self._state_note(),
            )
        chat_messages = [
            ChatMessage(
                role=m.role,
                content=m.content or "",
                name=m.name,
                tool_call_id=m.tool_call_id,
            )
            for m in messages
        ]
        try:
            resp = self._resolve_provider().chat(chat_messages, [])
        except Exception as exc:  # contract: never raise
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                finish_reason="degraded",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=f"ai seat: trained brain raised {exc!r} — not faked",
                note=self._state_note(),
            )
        text = getattr(resp, "text", "") or ""
        err = getattr(resp, "error", None)
        if err:
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                finish_reason="degraded",
                latency_ms=(time.perf_counter() - t0) * 1000.0,
                error=f"ai seat: trained brain errored ({err}) — not faked",
                note=self._state_note(),
            )
        return OperatorResult(
            text=text,
            operator=self.name,
            kind=self.kind,
            finish_reason="stop",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
            note=(
                "trained-brain result (his own model, served local). "
                f"{st['envelope_now']} {st['needs_more_training']}"
            ),
        )

    def cost(self) -> Dict[str, Any]:
        return {
            "metered": False,
            "unit": "local-compute",
            "note": (
                "his own trained brain, served local — no provider "
                "billing, no API keys; cost is his own compute"
            ),
        }
