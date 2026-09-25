"""Bletchley Park: the human+machine intelligence pipeline with hard isolation.

Origin: 1939-45, GC&CS Bletchley Park — ~10,000 staff (majority women; ~75%
of Bombes operated by WRNS "Wrens") processing 2,000-6,000 intercepted
messages a day through intercept -> cribs (Hut 8) -> Bombe menus (Hut 6) ->
machine runs (outstations) -> checking -> translation -> Ultra. An explicit
human+machine staging system with hard isolation: cryptanalysts produced
"menus" (guessed plaintext + machine settings); Wrens wired and ran the
Turing-Welchman Bombes in 8-hour shifts; when a machine "stopped," one Wren
recorded settings while a second re-ran and a third tested the stop on a
checking machine. Compartmentalization was itself a mechanism — Bombe
operators never knew Enigma's name, so a captured operator revealed
nothing. Humans did judgment (cribs, menus, interpretation); machines did
enumeration.

What it is in LEVI: a staged attack pipeline with hard isolation. Four
stages — collect -> hypothesize -> machine-run -> verify — where each
stage's output is the next stage's ONLY input, stages run strictly forward
(never re-run, never skipped), and every machine run is recorded in a shift
log. A finding can only be reached through the full chain; a planted "stop"
is found only by walking it.

Honesty label: LOAD-BEARING — forward-only staged flow with per-stage input
isolation and a shift log is a concrete, transferable mechanism.

Deny-closed inputs: empty or duplicate intercept ids, unknown intercept
ids, out-of-order stages, re-running a completed stage, menus without an
expected stop, empty shift names or stop lists, duplicate stops in a run,
and verifying a stop the machines never produced are all rejected with
ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["StagedAttackPipeline", "Verification"]

STAGE_COLLECTED = "collected"
STAGE_HYPOTHESIZED = "hypothesized"
STAGE_MACHINE_RUN = "machine_run"
STAGE_VERIFIED = "verified"


def _clean(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a non-empty string")
    return value.strip()


@dataclass
class Verification:
    intercept_id: str
    stop: str
    found: bool
    expected_stop: str = ""


class StagedAttackPipeline:
    """Intercept -> hypothesize (menus) -> machine-run (shifts) -> verify.

    Each stage consumes only the previous stage's output. There is no
    shortcut: a stop can only be verified if the machines produced it and
    the cryptanalysts predicted it.
    """

    def __init__(self) -> None:
        self._stage: dict[str, str] = {}
        self._payloads: dict[str, str] = {}
        self._expected: dict[str, str] = {}  # intercept -> expected stop
        self._stops: dict[str, list[str]] = {}  # intercept -> machine stops
        self._shift_log: list[dict] = []
        self._verified: dict[str, list[Verification]] = {}

    # -- stage 1: intercept --------------------------------------------------
    def collect(self, intercept_id: str, payload: str) -> str:
        """Interception stations bring in the raw material."""
        intercept_id = _clean(intercept_id, "intercept id")
        payload = _clean(payload, "payload")
        if intercept_id in self._stage:
            raise ValueError(f"duplicate intercept: {intercept_id!r}")
        self._stage[intercept_id] = STAGE_COLLECTED
        self._payloads[intercept_id] = payload
        return intercept_id

    # -- stage 2: the cryptanalyst's menu --------------------------------------
    def hypothesize(self, intercept_id: str, menu: dict) -> dict:
        """Hut 6 writes a menu: guessed plaintext + settings, and the stop
        they expect the machines to find. Consumes ONLY the intercept."""
        self._require_stage(intercept_id, STAGE_COLLECTED, "hypothesize")
        if not isinstance(menu, dict) or not menu:
            raise ValueError("menu must be a non-empty dict")
        expected = menu.get("expected_stop")
        expected = _clean(expected, "menu['expected_stop']") if expected else None
        if not expected:
            raise ValueError("menu must include a non-empty 'expected_stop'")
        self._expected[intercept_id] = expected
        self._stage[intercept_id] = STAGE_HYPOTHESIZED
        return {"intercept_id": intercept_id, "expected_stop": expected}

    # -- stage 3: the machine run ----------------------------------------------
    def machine_run(self, intercept_id: str, shift: str, stops: list[str]) -> list[str]:
        """The Wrens' shift: wire the machine, run it, record every stop.
        Consumes ONLY the menu. Logged per shift."""
        self._require_stage(intercept_id, STAGE_HYPOTHESIZED, "machine_run")
        shift = _clean(shift, "shift")
        if not isinstance(stops, list) or not stops:
            raise ValueError("stops must be a non-empty list of strings")
        cleaned = [_clean(s, f"stop {i}") for i, s in enumerate(stops)]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError(f"duplicate stops in machine run: {stops!r}")
        self._stops[intercept_id] = cleaned
        self._shift_log.append(
            {"intercept_id": intercept_id, "shift": shift, "stops": len(cleaned)}
        )
        self._stage[intercept_id] = STAGE_MACHINE_RUN
        return list(cleaned)

    # -- stage 4: check the stop -------------------------------------------------
    def verify(self, intercept_id: str, stop: str) -> Verification:
        """Test a stop on the checking machine: it counts as found only if
        the machines produced it AND the menu predicted it."""
        self._require_stage(intercept_id, STAGE_MACHINE_RUN, "verify")
        stop = _clean(stop, "stop")
        produced = self._stops[intercept_id]
        if stop not in produced:
            raise ValueError(
                f"stop {stop!r} was never produced by the machine run for "
                f"{intercept_id!r} — cannot verify what the machines "
                "never found"
            )
        expected = self._expected[intercept_id]
        result = Verification(
            intercept_id=intercept_id,
            stop=stop,
            found=(stop == expected),
            expected_stop=expected,
        )
        self._verified.setdefault(intercept_id, []).append(result)
        if all(v.found for v in self._verified[intercept_id]):
            self._stage[intercept_id] = STAGE_VERIFIED
        return result

    def shift_log(self) -> list[dict]:
        """Every machine shift, in order — who ran what, how many stops."""
        return [dict(entry) for entry in self._shift_log]

    # -- internals ---------------------------------------------------------------
    def _require_stage(self, intercept_id: str, want: str, action: str) -> None:
        stage = self._stage.get(intercept_id)
        if stage is None:
            raise ValueError(f"unknown intercept: {intercept_id!r}")
        if stage == want:
            return
        order = [STAGE_COLLECTED, STAGE_HYPOTHESIZED, STAGE_MACHINE_RUN, STAGE_VERIFIED]
        if order.index(stage) > order.index(want):
            raise ValueError(
                f"cannot {action} {intercept_id!r}: stage {stage!r} already "
                "complete — stages run forward only, never re-run"
            )
        raise ValueError(
            f"cannot {action} {intercept_id!r}: requires stage {want!r} "
            f"first (currently {stage!r}) — stages never skip"
        )
