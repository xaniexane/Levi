"""Cybrus broker operator channels — who performs the machine steps.

The founder broker (:mod:`levi.cybrus.broker_founder`) orchestrates a signup
plan step by step but never touches a browser itself. The *doing* belongs to
an operator channel: an object with
``perform(public_plan, step, context) -> {"ok": bool, "note": str}``.

LAW FL6 — OPERATOR-CHANNEL-BINDING
----------------------------------
The production channel, :class:`BrowserTaskChannel`, performs steps only
through an explicitly bound browser-task executor. An unbound channel
**fails closed** — ``perform`` raises instead of silently faking a signup.
There is no default executor and no silent fallback: a plan cannot advance
on pretend browser work.

Production binding
------------------
The executor is bound at runtime by the operator that *can* drive a
browser (the parent/root agent's browser-task capability)::

    channel = BrowserTaskChannel()
    channel.bind_executor(my_browser_task_driver)  # (plan, step, ctx) -> {"ok","note"}
    broker.run_to_checkpoint(plan_id, channel, session=session)

The executor receives the public plan (metadata only), the current step
descriptor, and the ``context`` dict the caller built — which may carry
exactly-once issued secrets (contact, password, verification code) obtained
from the broker's issuance methods. Secrets travel in-memory only: the
channel never logs, stores, or audits step notes, and the broker's audit
records carry step ids, never values (L1/L7).

:class:`ScriptedChannel` is the honest fake for tests and dry runs: every
step outcome is declared up front, and an undeclared step fails the plan
instead of being improvised.

HONEST BOUNDARIES
-----------------
- This module performs no network calls and drives no browser. The real
  browser-task executor lives outside this codebase (the agent runtime's
  browser-task capability); this module is the binding point, not the
  driver. Locally, without a bound executor, plans pause at
  ``credential-minted`` and the CLI says so plainly.
- Human checkpoints are never performed by any channel — the broker pauses
  to ``awaiting-human`` and only the human resumes.
- stdlib-only, like the rest of Cybrus.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional


class OperatorChannelError(Exception):
    """The operator channel cannot perform the step (unbound, malformed)."""


#: The executor contract: (public_plan, step, context) -> {"ok": bool, "note": str}.
Executor = Callable[[Dict, Dict, Dict], Dict]


class BrowserTaskChannel:
    """Production operator channel: drives steps via a bound executor.

    Construct empty and bind the real browser-task driver with
    :meth:`bind_executor`. Until bound, :meth:`perform` raises
    :class:`OperatorChannelError` (FL6 — fail closed, never fake).
    """

    def __init__(self, executor: Optional[Executor] = None):
        self._executor = executor

    def bind_executor(self, executor: Executor) -> "BrowserTaskChannel":
        """Bind the browser-task driver. Returns self for chaining."""
        if not callable(executor):
            raise OperatorChannelError("executor must be callable")
        self._executor = executor
        return self

    @property
    def bound(self) -> bool:
        """Whether a browser-task executor is bound."""
        return self._executor is not None

    def perform(
        self, public_plan: Dict, step: Dict, context: Dict
    ) -> Dict:
        """Perform one machine step through the bound executor.

        The executor's outcome is validated to the ``{"ok": bool,
        "note": str}`` contract; anything else fails the plan rather than
        being trusted. Step notes are never logged or stored here.
        """
        if self._executor is None:
            raise OperatorChannelError(
                "no browser-task executor bound: the production driver must "
                "be bound by the operator via bind_executor() before a plan "
                "can advance past credential-minted. Refusing to fake the "
                f"signup (plan step {step.get('id')!r} not performed)."
            )
        if not isinstance(step, dict) or "id" not in step:
            raise OperatorChannelError("malformed step descriptor")
        outcome = self._executor(public_plan, step, context)
        if not isinstance(outcome, dict) or "ok" not in outcome:
            raise OperatorChannelError(
                "operator channel must return {'ok': bool, 'note': str}"
            )
        return {"ok": bool(outcome["ok"]), "note": str(outcome.get("note", ""))}


class ScriptedChannel:
    """Honest fake channel: every step outcome is declared up front.

    ``script`` maps step id -> ``{"ok": bool, "note": str}``. A step with
    no declared outcome fails the plan instead of being improvised — the
    fake cannot silently invent browser work either.
    """

    def __init__(self, script: Dict[str, Dict]):
        self._script = dict(script)
        self.performed = []

    def perform(
        self, public_plan: Dict, step: Dict, context: Dict
    ) -> Dict:
        step_id = step.get("id")
        self.performed.append(step_id)
        outcome = self._script.get(step_id)
        if outcome is None:
            return {
                "ok": False,
                "note": f"no scripted outcome for step {step_id!r}: refusing to improvise",
            }
        return {"ok": bool(outcome["ok"]), "note": str(outcome.get("note", ""))}
