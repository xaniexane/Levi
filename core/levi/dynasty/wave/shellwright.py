# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Shellwright — keeper of the LEVI Shell.

Jack of all trades; shell 10. Owns the clean-room terminal: sessions
that survive, commands under guard, automation hooks for the legion.

Its unreplicable attribute is **pulse-chain liveness**: Shellwright
never reads a clock to judge a session alive. Every session breathes
on a forward-only pulse bound to the receipt chain at creation, and
aliveness is proven by pulse advance between seals. Replayed or forged
pulses are refused with a typed error; wall-clock skew cannot move the
verdict, because no timestamp is ever consulted.
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, WareError
from levi.dynasty.shell.runner import RefusedCommand
from levi.dynasty.shell.sessions import SessionError

__all__ = ["PulseError", "Shellwright"]


class PulseError(AgentError):
    """A session pulse was replayed, skipped, or forged."""


def _chain_len(home: Path) -> int:
    """Count of sealed receipts under ``home`` — the chain's length,
    without re-verifying every seal (cheap enough to call per beat)."""
    receipts_dir = home / "dynasty" / "receipts"
    if not receipts_dir.is_dir():
        return 0
    return sum(1 for p in receipts_dir.iterdir() if p.suffix == ".json")


class Shellwright(DynastyAgent):
    """Builds the LEVI Shell: sessions, guarded runs, automation hooks."""

    agent_id = "shellwright"
    display_name = "Shellwright"
    owns = "LEVI Shell"
    first_milestone = "CLI prototype → Android body"
    proficiency = {"shell": 10, "runtime": 8, "automation": 8, "general": 6}
    specialties = [
        "clean-room terminal sessions that survive process killing",
        "guarded command execution under a hard deny-list",
        "automation hooks: agents and scripts driving sessions",
        "pulse-chain liveness — aliveness without clocks",
    ]
    attributes = [
        {
            "name": "pulse-chain liveness",
            "assertion": (
                "Shellwright never reads a clock to judge a session alive: "
                "every session breathes on a forward-only pulse bound to the "
                "receipt chain at creation, and aliveness is proven by pulse "
                "advance between seals — replayed or forged pulses are "
                "refused with a typed error, and wall-clock skew cannot move "
                "the verdict because no timestamp is ever consulted."
            ),
        }
    ]

    def __init__(self, home: Optional[Path] = None) -> None:
        # Locks BEFORE super().__init__: the seal lane must exist when
        # the default wares are registered, because sign_milestone is
        # bound then — and the keeper key it touches has a thread-race
        # in its first-boot creation (partial reads fork the key view
        # and break the chain permanently; proven in the purge).
        self._seal_lock = threading.Lock()
        # Seal queue: receipts mint read-then-write (seq = len+1, O_EXCL).
        # Two threads minting in the same second collide on the file name
        # and the loser eats a raw OSError. The agent serializes its own
        # seals — a FIFO lane, gapless per-agent sequences under storms.
        # Session lane: the session registry dumps its whole dict on
        # every mutation while other threads may be mutating it. Every
        # session-touching op goes through this lock.
        self._session_lock = threading.Lock()
        # name -> {"next": int, "last": int, "origin": int}
        # "next" is the pulse the next heartbeat must present/advance to;
        # "last" is the most recently issued pulse; "origin" is the
        # receipt-chain length at creation — the pulse's birthmark.
        self._pulses: Dict[str, Dict[str, int]] = {}
        super().__init__(home)
        # Warm the keeper key once, single-threaded, through the locked
        # ware — first-boot key creation must never happen mid-storm.
        self.wares.invoke("sign_milestone", f"{self.agent_id}:key-warmup")

    # -- seals ------------------------------------------------------
    def _sign_milestone(self, milestone: str) -> Dict[str, str]:
        """Corroboration signature, through the seal lane — the keeper
        key's first-boot creation is thread-racy, so it never happens
        outside this lock."""
        with self._seal_lock:
            return super()._sign_milestone(milestone)

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Any = None,
    ) -> Dict[str, Any]:
        """Plan→execute→verify→receipt, through the per-agent seal lane."""
        with self._seal_lock:
            return super().do_task(kind, payload, task=task, verify=verify)

    # -- pulse-chain sessions ----------------------------------------
    def shell_session_create(self, name: str) -> Dict[str, Any]:
        """Create a session and bind its pulse to the receipt chain."""
        if not isinstance(name, str) or not name.strip():
            raise AgentError("session name must be a non-empty string")
        with self._session_lock:
            if name in self._pulses:
                raise PulseError(
                    f"pulse already bound for session {name!r} "
                    f"({'retired' if self._pulses[name].get('retired') else 'active'})"
                )
            # Refresh from disk first: another process may have written
            # sessions since this instance loaded — never clobber them.
            self.sessions._load()
            try:
                record = self.sessions.create(name)
            except SessionError as exc:
                raise PulseError(str(exc)) from exc
            origin = _chain_len(self._home)
            self._pulses[name] = {"next": origin + 1, "last": origin, "origin": origin}
            record = dict(record)
            record["pulse_origin"] = origin
            return record

    def pulse_heartbeat(
        self, name: str, present: Optional[int] = None
    ) -> Dict[str, Any]:
        """Advance (or present) a session's pulse.

        ``present=None`` advances the pulse by exactly one and returns
        it. ``present=<int>`` is a presented token: it must equal the
        next expected pulse, or the beat is refused — a replayed or
        forged pulse never lands. Either way the session record's
        heartbeat is stamped (DNA compatibility), but liveness is never
        derived from that stamp.
        """
        if not isinstance(name, str) or not name.strip():
            raise AgentError("session name must be a non-empty string")
        with self._session_lock:
            state = self._pulses.get(name)
            if state is None:
                raise PulseError(f"no pulse bound for session {name!r}")
            if state.get("retired"):
                raise PulseError(f"pulse for {name!r} is retired — session is dead")
            expected = state["next"]
            if present is not None:
                if not isinstance(present, int) or isinstance(present, bool):
                    raise PulseError(f"pulse token for {name!r} must be an int")
                if present != expected:
                    raise PulseError(
                        f"pulse {present} refused for {name!r}: "
                        f"expected {expected} — replay or forgery"
                    )
            pulse = expected
            state["next"] = expected + 1
            state["last"] = pulse
            try:
                record = self.sessions.heartbeat(name)
            except SessionError as exc:
                raise PulseError(str(exc)) from exc
            record = dict(record)
            record["pulse"] = pulse
            return record

    def session_liveness(self, name: str) -> Dict[str, Any]:
        """Verdict on a session, derived from pulse advance — no clocks.

        "alive" iff the registry holds the session open AND its pulse
        has advanced past its chain-bound origin. "dead" iff the
        session was killed. "unknown" iff no pulse was ever bound.
        """
        if not isinstance(name, str) or not name.strip():
            raise AgentError("session name must be a non-empty string")
        with self._session_lock:
            state = self._pulses.get(name)
            if state is None:
                return {"name": name, "liveness": "unknown"}
            try:
                record = self.sessions.get(name)
            except SessionError:
                return {"name": name, "liveness": "unknown"}
            if record.get("status") == "dead" or state.get("retired"):
                return {
                    "name": name,
                    "liveness": "dead",
                    "pulse": state["last"],
                    "pulse_origin": state["origin"],
                }
            alive = state["last"] > state["origin"]
            return {
                "name": name,
                "liveness": "alive" if alive else "dormant",
                "pulse": state["last"],
                "pulse_origin": state["origin"],
            }

    def shell_session_kill(self, name: str) -> Dict[str, Any]:
        """Kill a session and retire its pulse — the tombstone stays, so
        liveness reads "dead", never "unknown", and the pulse is never
        re-issued to a recycled name."""
        if not isinstance(name, str) or not name.strip():
            raise AgentError("session name must be a non-empty string")
        with self._session_lock:
            try:
                record = self.sessions.kill(name)
            except SessionError as exc:
                raise PulseError(str(exc)) from exc
            state = self._pulses.get(name)
            if state is not None:
                state["retired"] = True
            return dict(record)

    # -- guarded runs -------------------------------------------------
    def guarded_run(self, argv: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run a command through the guarded runner ware.

        The deny-list refusal is translated into the agent's typed
        error contract — :class:`AgentError`, never a bare leak.
        """
        if not isinstance(argv, list):
            raise AgentError("guarded_run argv must be a list of strings")
        try:
            return self.wares.invoke("run_command", argv, timeout=timeout)
        except (WareError, RefusedCommand) as exc:
            raise AgentError(f"guarded run refused: {exc}") from exc

    # -- dispatch -----------------------------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Shell-domain shapes; everything else rides the shared DNA."""
        if not isinstance(task, dict):
            raise AgentError("handle requires a task dict")
        shape = task.get("shape")
        if shape == "shell_session_create":
            return self.shell_session_create(str(task.get("name", "")))
        if shape == "pulse_heartbeat":
            return self.pulse_heartbeat(str(task.get("name", "")), task.get("present"))
        if shape == "session_liveness":
            return self.session_liveness(str(task.get("name", "")))
        if shape == "shell_session_kill":
            return self.shell_session_kill(str(task.get("name", "")))
        if shape == "guarded_run":
            argv = task.get("argv")
            if not isinstance(argv, list):
                raise AgentError("guarded_run task needs argv as a list")
            return self.guarded_run(argv, int(task.get("timeout", 30)))
        return super().handle(task)

    # -- first green task ---------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        """Create a session, run echo under guard, beat the pulse once,
        seal the receipt. Green only if the guarded run truly ran."""
        name = f"shellwright-first-{uuid.uuid4().hex[:8]}"
        session = self.shell_session_create(name)
        try:
            run = self.wares.invoke("run_command", ["echo", "shellwright-alive"])
        except (WareError, RefusedCommand) as exc:
            raise AgentError(f"first task echo refused: {exc}") from exc
        beat = self.pulse_heartbeat(name)

        def _verify(payload: Dict[str, Any]) -> None:
            if run.get("returncode") != 0:
                raise AgentError(
                    f"echo exited {run.get('returncode')}: {run.get('stderr')}"
                )
            if "shellwright-alive" not in str(run.get("stdout", "")):
                raise AgentError("echo output did not carry the witness word")

        return self.do_task(
            "wave.first_task",
            {
                "session": name,
                "pulse_origin": session["pulse_origin"],
                "pulse": beat["pulse"],
                "echo": str(run.get("stdout", "")).strip(),
                "returncode": run.get("returncode"),
            },
            task="shellwright:first",
            verify=_verify,
        )
