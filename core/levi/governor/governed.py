"""The integration seam: wrap any provider so calls are governed.

:class:`GovernedProvider` decorates a :class:`levi.agent.providers.ChatProvider`
without changing its interface:

1. Pre-call: budget check, then cool-down check. A burst pass (see
   :mod:`levi.governor.priority`) may reserve the next probe slot during
   genuine contention — transparently labeled, never manufactured.
   Refusals come back as a ``ChatResponse`` with ``error`` set and a
   clear reason — never a silent drop, never an exception the loop
   cannot report.
2. The inner provider is called.
3. Post-call: the call is metered (attribution intact, including any
   priority pass used), the spike detector observes it, and any breach
   opens the cool-down circuit for the provider.

``governed_call()`` is the one-shot version for ad-hoc use.
"""

from __future__ import annotations

import time

from levi.agent.providers import ChatProvider, ChatResponse
from levi.governor.budgets import BudgetEnforcer
from levi.governor.cooldown import CooldownManager
from levi.governor.meter import Meter, fingerprint_messages
from levi.governor.priority import PassWallet


class GovernedProvider(ChatProvider):
    """A ChatProvider with metering, spike detection, and cool-downs."""

    def __init__(
        self,
        inner: ChatProvider,
        *,
        task_id: str = "",
        agent_id: str = "",
        tool_name: str = "",
        home=None,
        clock=time.time,
        meter: Meter | None = None,
        detector=None,
        cooldowns: CooldownManager | None = None,
        budgets: BudgetEnforcer | None = None,
        wallet: PassWallet | None = None,
        pass_id: str | None = None,
    ) -> None:
        if not isinstance(inner, ChatProvider):
            raise ValueError("GovernedProvider wraps a ChatProvider instance")
        self.inner = inner
        self.task_id = task_id
        self.agent_id = agent_id
        self.tool_name = tool_name
        # Burst pass for the honest priority lane (see priority.py). Only
        # meaningful during genuine contention; otherwise ignored.
        self.pass_id = pass_id
        self._clock = clock
        self._meter = meter if meter is not None else Meter(home=home, clock=clock)
        if detector is None:
            from levi.governor.spikes import SpikeDetector

            detector = SpikeDetector(clock=clock)
        self._detector = detector
        self._wallet = (
            wallet if wallet is not None else PassWallet(home=home, clock=clock)
        )
        self._cooldowns = (
            cooldowns
            if cooldowns is not None
            else CooldownManager(home=home, clock=clock, wallet=self._wallet)
        )
        if self._cooldowns._wallet is None:
            # A caller-supplied manager without a wallet still needs one
            # for the priority lane to function.
            self._cooldowns._wallet = self._wallet
        self._budgets = (
            budgets
            if budgets is not None
            else BudgetEnforcer(self._meter, home=home, clock=clock)
        )

    @property
    def name(self) -> str:
        return getattr(self.inner, "name", None) or self.inner.__class__.__name__

    def is_available(self) -> bool:
        return self.inner.is_available()

    @property
    def scope(self) -> str:
        # A spike in one provider must not kill the local rules engine.
        return f"provider:{self.name}"

    def _refuse(self, reason: str) -> ChatResponse:
        return ChatResponse(
            text="",
            provider=self.name,
            error=f"[governor] call refused: {reason}",
        )

    def chat(self, messages: list, tools: list[dict]) -> ChatResponse:
        # 1. Pre-call gates (deny-closed).
        ok, reason = self._budgets.authorize()
        if not ok:
            return self._refuse(f"budget — {reason}")
        grant = self._cooldowns.acquire(self.scope, pass_id=self.pass_id)
        if not grant.allowed:
            return self._refuse(f"cool-down — {grant.reason}")

        # 2. The real call.
        fp = fingerprint_messages(messages)
        try:
            resp = self.inner.chat(messages, tools)
        except Exception as exc:  # provider blew up: meter the attempt, re-raise never
            self._meter.record(
                provider=self.name,
                task_id=self.task_id,
                agent_id=self.agent_id,
                tool_name=self.tool_name,
                prompt_fingerprint=fp,
                priority_pass_id=grant.pass_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            if grant.probe:
                self._cooldowns.probe_failure(
                    self.scope, f"probe raised {type(exc).__name__}"
                )
            return self._refuse(f"provider raised {type(exc).__name__}: {exc}")

        # 3. Meter, detect, cool down.
        rec = self._meter.record(
            provider=self.name,
            model=resp.model or "",
            task_id=self.task_id,
            agent_id=self.agent_id,
            tool_name=self.tool_name,
            prompt_fingerprint=fp,
            prompt_tokens=resp.prompt_tokens or 0,
            completion_tokens=resp.completion_tokens or 0,
            priority_pass_id=grant.pass_id,
            error=resp.error,
        )
        self._budgets.note_spend(rec.total)
        alerts = self._detector.observe(rec)
        if grant.probe:
            if resp.error:
                self._cooldowns.probe_failure(self.scope, resp.error)
            else:
                self._cooldowns.probe_success(self.scope)
        # One breach per offending call (not one per attribution key):
        # collapse the alerts into a single breach carrying every reason.
        if alerts:
            self._cooldowns.breach(self.scope, "; ".join(str(a) for a in alerts))
        # No silent passes: attach the alerts to the response for the caller.
        if alerts:
            resp.governor_alerts = [str(a) for a in alerts]  # type: ignore[attr-defined]
        return resp

    def chat_with_pass(
        self, messages: list, tools: list[dict], pass_id: str
    ) -> ChatResponse:
        """One call with a burst pass attached (honest priority lane).

        The pass is only meaningful during genuine contention; otherwise
        the call proceeds normally and the pass is untouched.
        """
        old, self.pass_id = self.pass_id, pass_id
        try:
            return self.chat(messages, tools)
        finally:
            self.pass_id = old


def governed_call(
    provider: ChatProvider,
    messages: list,
    tools: list[dict],
    *,
    task_id: str = "",
    agent_id: str = "",
    tool_name: str = "",
    home=None,
    **kwargs,
) -> ChatResponse:
    """One-shot governed call: wrap, call once, return the response."""
    gov = GovernedProvider(
        provider,
        task_id=task_id,
        agent_id=agent_id,
        tool_name=tool_name,
        home=home,
        **kwargs,
    )
    return gov.chat(messages, tools)
