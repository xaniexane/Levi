"""Confidence-based request router: answer locally first, escalate only when needed.

Plain speech: this is the traffic cop for LEVI's brain. Every request goes to
Chauncey's own local model first. It only escalates to a cloud teacher when the
local answer is too uncertain, when the request is flagged as novel, or when a
teacher's feature flag is on. Every escalation is written to a JSONL log that
the training loop can later consume — that loop is what makes the local model
need the teacher less over time. That is the self-sufficiency mechanism.

Fixes over the original router.pdf sketch (Chauncey, 2026-09-26):
  - The threshold env var typo ("LEVI_CONFIDENCE_THRES HOLD", with a space)
    is fixed: LEVI_CONFIDENCE_THRESHOLD is actually honored, default 0.62.
  - If the cloud teacher throws, the request falls back to the local answer
    instead of crashing; the failure is recorded on the result and in the log.
  - Cost tracking: when a client reports tokens/latency, they go into the log
    row; otherwise None — never fabricated.
  - Log hygiene: the escalation log file is created with 0600 permissions, and
    LEVI_ESCALATION_LOG_PROMPTS=0 switches the log to prompt/answer hashes
    instead of raw text.
  - The outcome loop can be closed: `record_outcome(request_id, outcome, note)`
    appends an outcome record keyed by request_id (the original row is never
    rewritten in place — history is append-only).
  - `make_router()` wires Chauncey's real local model: the BPE brain provider
    with a ModelClient adapter, falling back to a stub when weights/torch are
    missing. Cloud teachers are empty by default and opt-in via
    LEVI_CLOUD_<NAME> flags; no keys live in code.

Stdlib only in the module itself; the BPE adapter import is optional and
lazy so importing this module never pulls in torch.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Protocol


def _flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


def _teacher_enabled(name: str) -> bool:
    return _flag(f"LEVI_CLOUD_{name.upper()}")


CONFIDENCE_THRESHOLD = float(os.environ.get("LEVI_CONFIDENCE_THRESHOLD", "0.62"))
ESCALATION_LOG_PATH = Path(
    os.environ.get("LEVI_ESCALATION_LOG", "data/escalations.jsonl")
)
# When "0", the log records sha256 hashes of prompt/answer instead of raw text.
LOG_RAW_TEXT = _flag("LEVI_ESCALATION_LOG_PROMPTS", True)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ModelClient(Protocol):
    name: str

    def answer(self, prompt: str) -> str: ...
    def confidence(self, prompt: str, answer: str) -> float: ...


@dataclass
class RoutingResult:
    """Plain speech: the full receipt for one routed request."""

    request_id: str
    prompt: str
    local_answer: str
    local_confidence: float
    escalated: bool
    teacher_used: Optional[str] = None
    teacher_answer: Optional[str] = None
    final_answer: str = ""
    latency_ms: float = 0.0
    # Set when escalation was attempted but the teacher failed (then the
    # local answer stands in as the final answer).
    teacher_error: Optional[str] = None
    teacher_latency_ms: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


@dataclass
class StubLocal:
    """Fallback local client used when Chauncey's model is unavailable."""

    name: str = "local-stub"

    def answer(self, prompt: str) -> str:
        return f"[local] {prompt[::-1]}"

    def confidence(self, prompt: str, answer: str) -> float:
        return 0.9 if len(prompt) < 20 else 0.4


class BPEBrainClient:
    """ModelClient adapter over Chauncey's own BPE brain (ChatProvider API).

    Confidence is heuristic and honest about it: it measures fluency-ish
    proxies (answer length vs prompt length, repetition) rather than claiming
    the model knows its own uncertainty. The model is small and still
    training; this adapter prefers under-confidence (more escalation) over
    pretending.
    """

    name = "bpe-brain"

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    def _messages(self, prompt: str) -> list:
        from levi.agent.providers import ChatMessage

        return [ChatMessage(role="user", content=prompt)]

    def answer(self, prompt: str) -> str:
        resp = self._provider.chat(self._messages(prompt), tools=[])
        self._last_response = resp
        return resp.text

    def confidence(self, prompt: str, answer: str) -> float:
        if not answer.strip():
            return 0.0
        # Heuristic, deliberately conservative: longer coherent-looking
        # answers score higher, short or highly repetitive answers lower.
        words = answer.split()
        if not words:
            return 0.0
        repetition = 1.0 - len(set(words)) / max(len(words), 1)
        length_bonus = min(len(answer) / max(len(prompt), 1), 1.5) / 1.5
        conf = 0.55 * (1.0 - repetition) + 0.25 * length_bonus + 0.2
        return round(max(0.0, min(1.0, conf)), 3)

    @property
    def last_usage(self) -> tuple[Optional[int], Optional[int], float]:
        resp = getattr(self, "_last_response", None)
        if resp is None:
            return None, None, 0.0
        pt = resp.prompt_tokens or None
        ct = resp.completion_tokens or None
        return pt, ct, resp.latency_ms or 0.0


def make_router(
    local_model: Optional[ModelClient] = None,
    teachers: Optional[dict[str, ModelClient]] = None,
    threshold: Optional[float] = None,
    novelty_check: Optional[Callable[[str], bool]] = None,
    log_path: Optional[Path] = None,
) -> "Router":
    """Plain speech: build a router wired to Chauncey's real local model.

    Prefers the BPE brain provider; falls back to the stub when the weights
    or torch are missing. Cloud teachers are empty by default (opt-in via
    LEVI_CLOUD_<NAME> flags) — pass `teachers=` explicitly to wire any in.
    """
    if local_model is None:
        local_model = _default_local_model()
    if threshold is None:
        threshold = float(os.environ.get("LEVI_CONFIDENCE_THRESHOLD", "0.62"))
    return Router(
        local_model=local_model,
        cloud_teachers=teachers or {},
        threshold=threshold,
        novelty_check=novelty_check,
        log_path=log_path or Path(
            os.environ.get("LEVI_ESCALATION_LOG", "data/escalations.jsonl")
        ),
    )


def _default_local_model() -> ModelClient:
    """Try the BPE brain provider; fall back to the stub, never raise."""
    try:
        from levi.agent.bpe_brain_provider import BPEBrainProvider

        provider = BPEBrainProvider()
        if provider.is_available():
            return BPEBrainClient(provider)
    except Exception:
        pass
    return StubLocal()


class Router:
    """Answers locally by default; escalates on low confidence or novelty.

    Teacher failures never crash the request: the local answer stands in and
    the failure is recorded on the result and in the escalation log.
    """

    def __init__(
        self,
        local_model: ModelClient,
        cloud_teachers: Optional[dict[str, ModelClient]] = None,
        threshold: float = CONFIDENCE_THRESHOLD,
        novelty_check: Optional[Callable[[str], bool]] = None,
        log_path: Path = ESCALATION_LOG_PATH,
        log_raw_text: Optional[bool] = None,
    ):
        self.local_model = local_model
        self.cloud_teachers = cloud_teachers or {}
        self.threshold = threshold
        self.novelty_check = novelty_check
        self.log_path = log_path
        self.log_raw_text = (
            _flag("LEVI_ESCALATION_LOG_PROMPTS", True)
            if log_raw_text is None
            else log_raw_text
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def route(self, prompt: str) -> RoutingResult:
        start = time.time()
        local_answer = self.local_model.answer(prompt)
        local_confidence = self.local_model.confidence(prompt, local_answer)
        novel = bool(self.novelty_check(prompt)) if self.novelty_check else False

        result = RoutingResult(
            request_id=str(uuid.uuid4()),
            prompt=prompt,
            local_answer=local_answer,
            local_confidence=local_confidence,
            escalated=False,
            final_answer=local_answer,
        )

        if local_confidence < self.threshold or novel:
            teacher_name, teacher = self._pick_teacher()
            if teacher is not None:
                result.escalated = True
                result.teacher_used = teacher_name
                t0 = time.time()
                try:
                    result.teacher_answer = teacher.answer(prompt)
                    result.final_answer = result.teacher_answer
                    if hasattr(teacher, "last_usage"):
                        pt, ct, _ = teacher.last_usage
                        result.prompt_tokens, result.completion_tokens = pt, ct
                except Exception as exc:  # cloud outage must not kill the request
                    result.teacher_error = f"{type(exc).__name__}: {exc}"
                    result.final_answer = local_answer
                finally:
                    result.teacher_latency_ms = (time.time() - t0) * 1000

        result.latency_ms = (time.time() - start) * 1000
        self._log(result)
        return result

    def record_outcome(
        self, request_id: str, outcome: str, note: str = ""
    ) -> None:
        """Plain speech: close the training loop for one routed request.

        Appends an outcome record keyed by request_id (e.g. outcome="kept",
        "corrected", "rejected"). The original log row is never rewritten —
        history stays append-only, and the training pipeline joins on
        request_id when it distills the escalation log.
        """
        record = {
            "kind": "outcome",
            "request_id": request_id,
            "outcome": outcome,
            "note": note,
            "ts": time.time(),
        }
        self._append_line(record)

    def _pick_teacher(self) -> tuple[Optional[str], Optional[ModelClient]]:
        for name, client in self.cloud_teachers.items():
            if _teacher_enabled(name):
                return name, client
        return None, None

    def _log(self, result: RoutingResult) -> None:
        record = asdict(result)
        record["kind"] = "escalation"
        record["ts"] = time.time()
        record["outcome"] = None  # filled in later via record_outcome()
        if not self.log_raw_text:
            for field in ("prompt", "local_answer", "teacher_answer", "final_answer"):
                value = record.get(field)
                record[field] = _sha(value) if isinstance(value, str) else value
        self._append_line(record)

    def _append_line(self, record: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        try:
            os.chmod(self.log_path, 0o600)
        except OSError:
            pass


if __name__ == "__main__":  # demo only — inert on import
    class DemoLocal:
        name = "local-demo"

        def answer(self, prompt: str) -> str:
            return f"[local] {prompt[::-1]}"

        def confidence(self, prompt: str, answer: str) -> float:
            return 0.9 if len(prompt) < 20 else 0.4

    class DemoTeacher:
        name = "gemini"
        last_usage = (12, 30, 120.5)

        def answer(self, prompt: str) -> str:
            return f"[gemini] considered answer to: {prompt}"

        def confidence(self, prompt: str, answer: str) -> float:
            return 0.95

    os.environ["LEVI_CLOUD_GEMINI"] = "1"
    router = Router(
        local_model=DemoLocal(), cloud_teachers={"gemini": DemoTeacher()}
    )
    for p in ["hi", "explain quantum entanglement to a 5 year old in detail"]:
        r = router.route(p)
        print(r.escalated, "->", r.final_answer[:60])
    print("logged to", router.log_path.resolve())
