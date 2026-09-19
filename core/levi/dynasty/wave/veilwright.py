# SECTION 0 — Hybrid IP Protection Block
# Date of Invention: mid-March 2026.
# This work is the exclusive property of Chauncey Logan. All rights reserved.
# Protections are retroactive to the date of invention and extend to all versions, expansions, and derivatives.
# Reproduction, distribution, modification, reverse-engineering, or imitation is prohibited — including training AI systems on this content or embedding its structures into other platforms.
# This work is closed and owner-controlled: not open-source, not licensed for reuse. Unauthorized use triggers immediate legal action.
# SPDX-License-Identifier: LicenseRef-LEVI-Proprietary
"""Veilwright — overlays+VR: the layer above the app, experimental.

Two experiments, one thesis: the interface is a layer, not an app.
An overlay experiment is registered with a sealed device-hostility
note and is OFF by default — nothing runs unless the keeper turns it
on.

Unreplicable attribute — **hostility-fold**: every documented device
hostility is folded into an append-only ledger that pins the overlay
off for that device — the failure record IS the gate. There is no
separate allow-list to bypass, and the fold is never unfolded: a
sealed hostility record cannot be cleared, rewritten, or expired.
Summoning consults the fold first; a folded-hostile device is refused
before any session is created.

Honest limits: EXPERIMENTAL. Device-dependent, costs battery, off by
default. Some devices will be hostile to overlays; those failures get
documented into the fold, not hidden. This is the farthest-flung of
the Phase 0 builds and it acts like it. No money shape at MVP —
experiments don't charge.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

from levi.dynasty.dna import AgentError, DynastyAgent, scrub_text
from levi.dynasty.wave.threadweaver import (
    _chain_locked,
    _checked_payload,
    _refuse_root_wipe,
)


class Veilwright(DynastyAgent):
    """Raises the veil — overlays over any app, off until summoned."""

    agent_id = "veilwright"
    display_name = "Veilwright"
    owns = "overlays+VR"
    first_milestone = "overlay launcher prototype"
    proficiency = {"overlays": 10, "vr": 9, "general": 5}
    specialties = [
        "experimental overlay launcher",
        "device-hostility documentation",
        "VR hub first-room prototype",
    ]
    attributes = [
        {
            "name": "hostility-fold",
            "assertion": (
                "every documented device hostility is folded into an "
                "append-only ledger that pins the overlay off for that "
                "device — the failure record IS the gate; the fold is never "
                "unfolded, cleared, or expired"
            ),
        },
    ]

    def __init__(self, home: Optional[object] = None) -> None:
        super().__init__(home)
        self._task_lock = threading.RLock()
        self._experiments: Dict[str, Dict[str, Any]] = {}
        self._hostility: Dict[str, Dict[str, Any]] = {}
        self._summoned: Dict[str, str] = {}  # session name -> experiment

    # -- guarded entry points (see threadweaver: same chain race) ------
    def act(self, task: Dict[str, Any]) -> Dict[str, Any]:
        with self._task_lock:
            return super().act(task)

    def do_task(
        self,
        kind: str,
        payload: Dict[str, Any],
        task: str = "",
        verify: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        with self._task_lock:
            _checked_payload(payload)
            with _chain_locked(self._home):
                return super().do_task(kind, payload, task, verify)

    def _ware_run_command(
        self, argv: List[str], timeout: int = 30
    ) -> Dict[str, object]:
        _refuse_root_wipe(argv)
        return super()._ware_run_command(argv, timeout)

    # -- experiments ---------------------------------------------------
    def register_experiment(self, name: str, hostility_note: str) -> Dict[str, Any]:
        """Register an overlay experiment. OFF by default; a
        device-hostility note is REQUIRED — an experiment with no
        documented hostility stance is refused."""
        name = scrub_text(str(name or "")).strip()
        note = scrub_text(str(hostility_note or "")).strip()
        if not name:
            raise AgentError("register_experiment needs a name")
        if not note:
            raise AgentError(
                "register_experiment refused: a device-hostility note is "
                "required — untested assumptions don't ship"
            )
        with self._task_lock:
            if name in self._experiments:
                raise AgentError(f"experiment {name!r} already registered")
            receipt = self.do_task(
                "wave.overlay_experiment",
                {
                    "experiment": name,
                    "default": "off",
                    "hostility_note": note,
                },
                task=f"veilwright:experiment/{name}",
            )
            self._experiments[name] = {
                "receipt_hash": receipt["receipt_hash"],
                "hostility_note": note,
                "state": "off",
            }
            self.note(f"registered overlay experiment {name} (off by default)")
            return receipt

    def record_hostility(self, device: str, note: str) -> Dict[str, Any]:
        """Fold a device hostility finding into the ledger. Append-only:
        a device already in the fold is refused a second record — the
        first fold stands."""
        device = scrub_text(str(device or "")).strip()
        note = scrub_text(str(note or "")).strip()
        if not device:
            raise AgentError("record_hostility needs a device")
        if not note:
            raise AgentError("record_hostility needs a hostility note")
        with self._task_lock:
            if device in self._hostility:
                raise AgentError(
                    f"device {device!r} is already folded hostile — "
                    "the fold is append-only, first record stands"
                )
            receipt = self.do_task(
                "wave.hostility_record",
                {"device": device, "note": note},
                task=f"veilwright:hostility/{device}",
            )
            self._hostility[device] = {
                "note": note,
                "receipt_hash": receipt["receipt_hash"],
            }
            self.note(f"folded hostility for device {device}")
            return receipt

    def clear_hostility(self, device: str) -> Dict[str, Any]:
        """There is no unfolding. This always raises."""
        device = scrub_text(str(device or "")).strip()
        with self._task_lock:
            if device not in self._hostility:
                raise AgentError(f"unknown device {device!r} — nothing to clear")
            raise AgentError(
                f"device {device!r} stays folded hostile — the fold is "
                "append-only: sealed hostility is never cleared, rewritten, "
                "or expired"
            )

    def hostility_fold(self) -> List[Dict[str, str]]:
        """The fold, read-only: every device pinned off, with its note."""
        with self._task_lock:
            return [
                {"device": d, "note": h["note"]}
                for d, h in sorted(self._hostility.items())
            ]

    # -- summoning ------------------------------------------------------
    def summon(self, experiment: str, device: str) -> Dict[str, Any]:
        """Summon an overlay experiment on a device.

        The fold is consulted first: a folded-hostile device is refused
        before any session exists. Summoning an unknown experiment, or
        one already summoned on that device, is refused.
        """
        experiment = scrub_text(str(experiment or "")).strip()
        device = scrub_text(str(device or "")).strip()
        if not experiment:
            raise AgentError("summon needs an experiment")
        if not device:
            raise AgentError("summon needs a device")
        with self._task_lock:
            if experiment not in self._experiments:
                raise AgentError(f"unknown experiment {experiment!r}")
            if device in self._hostility:
                raise AgentError(
                    f"device {device!r} is folded hostile — overlay pinned off"
                )
            session = f"veil:{experiment}:{device}"
            if session in self._summoned:
                raise AgentError(
                    f"experiment {experiment!r} already summoned on {device!r}"
                )
            self.sessions.create(session, command="overlay")
            receipt = self.do_task(
                "wave.overlay_summon",
                {"experiment": experiment, "device": device, "state": "on"},
                task=f"veilwright:summon/{experiment}/{device}",
            )
            self._summoned[session] = experiment
            self._experiments[experiment]["state"] = "on"
            self.note(f"summoned {experiment} on {device}")
            return {
                "experiment": experiment,
                "device": device,
                "state": "on",
                "session": session,
                "receipt_hash": receipt["receipt_hash"],
            }

    def dismiss(self, experiment: str, device: str) -> Dict[str, Any]:
        """Dismiss a summoned overlay. Dismissing what was never
        summoned is refused."""
        experiment = scrub_text(str(experiment or "")).strip()
        device = scrub_text(str(device or "")).strip()
        session = f"veil:{experiment}:{device}"
        with self._task_lock:
            if session not in self._summoned:
                raise AgentError(
                    f"nothing summoned for {experiment!r} on {device!r} — "
                    "dismissal refused"
                )
            self.sessions.kill(session)
            receipt = self.do_task(
                "wave.overlay_dismiss",
                {"experiment": experiment, "device": device, "state": "off"},
                task=f"veilwright:dismiss/{experiment}/{device}",
            )
            del self._summoned[session]
            if experiment in self._experiments:
                self._experiments[experiment]["state"] = "off"
            self.note(f"dismissed {experiment} on {device}")
            return {
                "experiment": experiment,
                "device": device,
                "state": "off",
                "receipt_hash": receipt["receipt_hash"],
            }

    # -- jack-of-all-trades dispatch ----------------------------------
    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        shape = task.get("shape", "echo")
        if shape == "experiment_register":
            return self.register_experiment(
                str(task.get("name", "")), str(task.get("hostility_note", ""))
            )
        if shape == "record_hostility":
            return self.record_hostility(
                str(task.get("device", "")), str(task.get("note", ""))
            )
        if shape == "clear_hostility":
            return self.clear_hostility(str(task.get("device", "")))
        if shape == "hostility_fold":
            return {"fold": self.hostility_fold()}
        if shape == "summon":
            return self.summon(
                str(task.get("experiment", "")), str(task.get("device", ""))
            )
        if shape == "dismiss":
            return self.dismiss(
                str(task.get("experiment", "")), str(task.get("device", ""))
            )
        return super().handle(task)

    # -- first green task ----------------------------------------------
    def first_task(self) -> Dict[str, Any]:
        note = (
            "off by default; untested devices are presumed hostile until a "
            "clean run is sealed — hostility findings fold into the ledger"
        )
        experiment = self.register_experiment("overlay-launcher-proto", note)
        return self.do_task(
            "wave.first_task",
            {
                "experiment": "overlay-launcher-proto",
                "experiment_receipt": experiment["receipt_hash"],
                "default": "off",
                "hostility_note": note,
                "vr_scene": "hub-room-1 (prototype planned)",
                "milestone": self.first_milestone,
            },
            task="veilwright:first",
        )
