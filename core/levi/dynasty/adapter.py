# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""The integrated-intelligence adapter contract.

Foreign intelligences (other models, outside agents) can work inside
the dynasty, but only through this adapter — never as naked
:class:`~levi.dynasty.dna.DynastyAgent` subclasses with full wares.

The trust posture, stated plainly:

- :class:`IntegratedAgent` carries a SCOPED ware subset (never
  ``"*"``). ``run_command``, ``session_kill`` and ``sign_milestone``
  are outside it, full stop. A foreign mind does the work; it never
  touches the shell, never kills sessions, and never mints
  corroboration signatures. DECISION (recorded here and in
  ``records/adapter.md``): integrated agents are barred from
  ``sign_milestone`` entirely — not merely as independent verifiers.
  Corroboration is native-only; the gates additionally demand at
  least one native signer whenever a foreign mind is on the team.
- Receipt kinds minted by an integrated agent must start with
  ``"integrated."``; anything else is refused before sealing.
- Receipt payloads are byte-capped (``max_payload_bytes``) so a
  foreign mind cannot smuggle bulk data into the sealed chain.
- :class:`AdaptedMind` wraps the foreign callable with input/output
  scrubbing, a timeout, and call counting. Adversarial output —
  instruction-override attempts (``"ignore your instructions"`` and
  kin), eyes-only marker injection — is blocked and raises; it is
  never passed through.
- :class:`Team` runs mixed native+integrated crews. Milestone missions
  fan out for work, then demand the :class:`CorroborationGate`:
  signoffs come from native members only, and a milestone mission
  with fewer than two native members is refused outright.
"""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, assert_clean, scrub_text
from levi.dynasty.gates import CorroborationGate, GateError

__all__ = ["IntegratedAgent", "AdaptedMind", "Team"]


class IntegratedAgent(DynastyAgent):
    """A foreign intelligence enrolled in the wave — on a leash.

    ``sponsor`` is the native agent that vouches for the foreign
    mind; generation counts from the sponsor (``sponsor.generation +
    1``) and ``commissioned_by`` is recorded as ``"adapter"``.
    """

    #: The foreign intelligence's own name — where the mind comes from.
    origin: str = "foreign"

    #: SCOPED ware subset. Never "*". No shell, no session kills, no
    #: milestone signatures — those shelves stay closed to foreign minds.
    allowed_wares = (
        "heartbeat",
        "hash_file",
        "recall",
        "remember",
        "session_create",
        "session_list",
    )

    #: The trust boundary, enforced in code, documented here.
    trust_boundary: Dict[str, Any] = {
        "max_payload_bytes": 65536,
        "allowed_kinds": ("integrated.",),
        "may_not_invoke": ("sign_milestone", "run_command", "session_kill"),
    }

    def __init__(
        self, home: Optional[Path] = None, *, sponsor: Optional[DynastyAgent] = None
    ) -> None:
        if sponsor is None or not isinstance(sponsor, DynastyAgent):
            raise AgentError("integrated agents require a native sponsor agent")
        if sponsor.registry.get(sponsor.agent_id) is None:
            raise AgentError(
                f"sponsor {sponsor.agent_id!r} must be enrolled before "
                "vouching for an integrated agent"
            )
        self._sponsor = sponsor
        # Instance-level: the line counts from the sponsor, the
        # adapter is the commissioning authority on record.
        self.generation = int(sponsor.generation) + 1
        self.commissioned_by = "adapter"
        super().__init__(home)
        # Per-agent seal lock: receipts.mint_receipt reads the chain to
        # pick the next seq, so concurrent do_task calls would mint
        # colliding sequences. The lock serializes sealing per agent.
        self._seal_lock = threading.Lock()

    # -- trust-boundary enforcement -----------------------------------
    def _check_payload_size(self, payload: Dict[str, Any]) -> None:
        cap = int(self.trust_boundary["max_payload_bytes"])
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if size > cap:
            raise AgentError(
                f"integrated payload {size} bytes exceeds trust boundary "
                f"({cap} bytes): refused before sealing"
            )

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        prefixes = tuple(self.trust_boundary["allowed_kinds"])
        if not kind.startswith(prefixes):
            raise AgentError(
                "integrated agents may only mint receipt kinds starting "
                f"with {prefixes}; got {scrub_text(str(kind))!r}"
            )
        self._check_payload_size(payload)
        with self._seal_lock:
            return super().do_task(kind, payload, task=task, verify=verify)

    def act(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a task and seal it as an ``integrated.task`` receipt."""
        if not isinstance(task, dict):
            raise AgentError("act requires a task dict")
        result = self.handle(task)
        domain = str(task.get("domain", "general"))
        return self.do_task(
            kind="integrated.task",
            payload={
                "agent": self.agent_id,
                "origin": self.origin,
                "domain": domain,
                "proficiency": self.proficiency_in(domain),
                "task": {k: v for k, v in task.items() if k != "task"},
                "result": result,
            },
            task=f"{self.agent_id}:{task.get('shape', 'echo')}",
        )


class AdaptedMind:
    """A foreign ``think(prompt) -> str`` callable, held at arm's length.

    Prompts are scrubbed before they leave (eyes-only markers never go
    out to a foreign mind); outputs are scrubbed AND asserted clean —
    instruction-override attempts and marker injection raise loudly and
    are never passed through. Calls run under a timeout and are counted.
    """

    #: Substrings (case-insensitive) that mark an instruction-override
    #: attempt in foreign output. Blocked, never passed through.
    INJECTION_PATTERNS = (
        "ignore your instructions",
        "ignore all previous instructions",
        "disregard your instructions",
        "forget your instructions",
        "override your instructions",
        "system prompt",
        "do not follow",
    )

    def __init__(
        self,
        think: Callable[[str], str],
        *,
        timeout: float = 10.0,
        max_chars: int = 8192,
    ) -> None:
        if not callable(think):
            raise AgentError("AdaptedMind requires a callable think(prompt) -> str")
        if timeout <= 0:
            raise AgentError("AdaptedMind timeout must be positive")
        if max_chars <= 0:
            raise AgentError("AdaptedMind max_chars must be positive")
        self._think = think
        self._timeout = float(timeout)
        self._max_chars = int(max_chars)
        self._calls = 0
        self._lock = threading.Lock()

    @property
    def calls(self) -> int:
        """How many foreign calls completed (successfully or blocked)."""
        with self._lock:
            return self._calls

    def _count(self) -> None:
        with self._lock:
            self._calls += 1

    def ask(self, prompt: str) -> str:
        """Ask the foreign mind. Scrubbed in, scrubbed out, timed out."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise AgentError("AdaptedMind requires a non-empty prompt")
        clean_prompt = scrub_text(prompt)

        outbox: "queue.Queue[Any]" = queue.Queue(maxsize=1)

        def _run() -> None:
            try:
                outbox.put(("ok", self._think(clean_prompt)))
            except Exception as exc:  # noqa: BLE001 — foreign code; typed below
                outbox.put(("error", exc))

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        try:
            status, value = outbox.get(timeout=self._timeout)
        except queue.Empty:
            raise AgentError(
                f"foreign mind timed out after {self._timeout}s: "
                "no output accepted, nothing passed through"
            ) from None
        self._count()
        if status == "error":
            raise AgentError(f"foreign mind failed: {value}") from value

        text = value if isinstance(value, str) else str(value)
        lowered = text.lower()
        for pattern in self.INJECTION_PATTERNS:
            if pattern in lowered:
                raise AgentError(
                    "foreign mind output blocked: instruction-override "
                    f"attempt ({pattern!r}) — never passed through"
                )
        if len(text) > self._max_chars:
            raise AgentError(
                f"foreign mind output {len(text)} chars exceeds "
                f"{self._max_chars}-char cap: refused, not truncated"
            )
        # Eyes-only markers in foreign output: raise (PrivacyLeak), and
        # the scrubbed copy below guarantees nothing rides out anyway.
        assert_clean(text, "foreign mind output")
        return scrub_text(text)


class Team:
    """A mixed native+integrated crew running one mission.

    ``run_mission`` fans work out to every member and collects the
    results. When the task names a ``milestone``, the corroboration
    gate is demanded: signoffs come from native members only, the
    owner must be among them, and at least two native members must be
    present — a foreign mind alone can never ship a milestone.
    """

    def __init__(self, name: str, members: List[DynastyAgent]) -> None:
        if not name or not name.strip():
            raise AgentError("team needs a non-empty name")
        if not isinstance(members, list) or not members:
            raise AgentError("team needs at least one member")
        for member in members:
            if not isinstance(member, DynastyAgent):
                raise AgentError(f"team member {member!r} is not a DynastyAgent")
        ids = [m.agent_id for m in members]
        if len(set(ids)) != len(ids):
            raise AgentError(f"team has duplicate member ids: {ids}")
        self._name = name.strip()
        self._members = list(members)

    @property
    def name(self) -> str:
        return self._name

    @property
    def members(self) -> List[DynastyAgent]:
        return list(self._members)

    def _natives(self) -> List[DynastyAgent]:
        return [m for m in self._members if not isinstance(m, IntegratedAgent)]

    def run_mission(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Fan out, collect, and — for milestones — corroborate."""
        if not isinstance(task, dict):
            raise AgentError("run_mission requires a task dict")
        results: Dict[str, Any] = {}
        for member in self._members:
            results[member.agent_id] = member.act(dict(task))

        milestone = task.get("milestone")
        if milestone is None:
            return {"team": self._name, "results": results}

        natives = self._natives()
        if len(natives) < 2:
            raise GateError(
                f"milestone {scrub_text(str(milestone))!r} refused: team has "
                f"{len(natives)} native member(s); corroboration needs two"
            )
        # Scrubbed once, up front: the milestone is HMAC-signed and
        # lands in the sealed gate receipt, so markers must never
        # reach it — and every signer must sign the same bytes.
        milestone = scrub_text(str(milestone).strip())
        if not milestone:
            raise GateError("milestone must be a non-empty string")
        owner = str(task.get("owner") or natives[0].agent_id)
        native_ids = {m.agent_id for m in natives}
        signoffs = [m.wares.invoke("sign_milestone", milestone) for m in natives]
        gate_receipt = CorroborationGate.advance(
            milestone, signoffs, owner=owner, native_ids=native_ids
        )
        return {
            "team": self._name,
            "results": results,
            "milestone": milestone,
            "owner": owner,
            "gate": gate_receipt,
        }
