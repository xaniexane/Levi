"""The offline-first answer chain.

Local-first, always: the chain asks the local backend first. If its
confidence falls below the policy threshold, an optional cloud backend
may answer — but only when the dual gate passes (see :mod:`levi.offline.gates`).

Every run returns a :class:`ChainResult` carrying a :class:`ChainReceipt`:
which backend answered, the confidence, whether escalation was
considered/granted/denied and why, and whether redaction changed the
prompt. Receipts are the honest audit trail; the answer text alone is
never the whole story.

Honest limits, stated up front:

- ``RuleBackend`` is a *policy stub*, not intelligence: it answers from
  supplied context with a template and reports a modest, deterministic
  confidence. It makes no sentience claims and no knowledge claims
  beyond the context it was given.
- Confidence here is heuristic (context coverage + answer length), the
  same class of estimate the studied MVP used. It gates escalation; it
  is not a truth meter.
- Redaction is best-effort regex scrubbing via LEVI's own growth gate.
  It reduces exposure; it is not a proof of absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Tuple

from .gates import GatePolicy, default_policy

try:  # reuse LEVI's own redaction gate; never a second copy of the patterns
    from levi.growth.redact import redact_text as _redact_text
except Exception:  # hermetic fallback: coarse but safe
    import re as _re

    _FALLBACK = _re.compile(
        r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"
        r"|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
        r"|\b\d{3}-\d{2}-\d{4}\b"
    )

    def _redact_text(text: str) -> str:  # type: ignore[misc]
        return _FALLBACK.sub("[redacted]", text or "")


def scrub(text: str) -> str:
    """Scrub secrets/PII from text before it touches disk or a wire."""
    return _redact_text(text or "")


@dataclass
class Answer:
    text: str
    confidence: float  # 0.0 .. 1.0, heuristic
    backend: str
    citations: List[str] = field(default_factory=list)


class Backend(Protocol):
    name: str

    def generate(self, prompt: str, context: str = "") -> Answer: ...


class RuleBackend:
    """Honest local policy stub: answers from given context, modest confidence.

    This is the last resort in the chain, not a mind. When no context is
    supplied it says so plainly and reports low confidence so a better
    local backend — or a gated cloud one — can take the turn.
    """

    name = "local:rule"

    def generate(self, prompt: str, context: str = "") -> Answer:
        prompt = (prompt or "").strip()
        context = (context or "").strip()
        if context:
            words = context.split()
            excerpt = " ".join(words[:60])
            text = (
                "From local context: %s%s\n\n"
                "(answered locally by rule stub; confidence is heuristic)"
                % (excerpt, "…" if len(words) > 60 else "")
            )
            confidence = 0.55 + min(0.2, len(words) / 1000.0)
        else:
            text = (
                "I have no local context for that, and I will not guess. "
                "Supply local notes or enable a better local backend."
            )
            confidence = 0.2
        return Answer(
            text=text, confidence=round(confidence, 3), backend=self.name, citations=[]
        )


@dataclass
class ChainReceipt:
    backend: str
    confidence: float
    escalated: bool
    escalation_considered: bool
    escalation_reason: str
    redaction_applied: bool
    prompt_chars: int
    context_chars: int


@dataclass
class ChainResult:
    answer: Answer
    receipt: ChainReceipt


class Offliner:
    """The offline-first chain. ``policy`` is the keeper's standing law."""

    def __init__(
        self,
        local: Backend,
        cloud: Optional[Backend] = None,
        policy: Optional[GatePolicy] = None,
    ) -> None:
        self.local = local
        self.cloud = cloud
        self.policy = policy or default_policy()

    def answer(
        self,
        prompt: str,
        context: str = "",
        allow_cloud: bool = False,
    ) -> ChainResult:
        safe_prompt = scrub(prompt)
        safe_context = scrub(context)
        redaction_applied = (safe_prompt != prompt) or (safe_context != context)

        local_answer = self.local.generate(safe_prompt, context=safe_context)
        considered = local_answer.confidence < self.policy.confidence_threshold

        final = local_answer
        escalated = False
        if considered and self.cloud is not None:
            permitted, reason = self.policy.escalation_permitted(allow_cloud)
            if permitted:
                final = self.cloud.generate(safe_prompt, context=safe_context)
                escalated = True
                escalation_reason = "escalated: " + reason
            else:
                escalation_reason = "escalation denied: " + reason
        elif considered:
            escalation_reason = "escalation denied: no cloud backend configured"
        else:
            escalation_reason = (
                "not considered: local confidence %.3f >= threshold %.2f"
                % (local_answer.confidence, self.policy.confidence_threshold)
            )

        receipt = ChainReceipt(
            backend=final.backend,
            confidence=final.confidence,
            escalated=escalated,
            escalation_considered=considered,
            escalation_reason=escalation_reason,
            redaction_applied=redaction_applied,
            prompt_chars=len(safe_prompt),
            context_chars=len(safe_context),
        )
        return ChainResult(answer=final, receipt=receipt)
