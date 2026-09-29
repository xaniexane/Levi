"""Keel engine — hold the line unless the shift is real.

A verdict without ballast tacks at every gust. The keel watches one named
line (the current course verdict) against a chronological stream of new
readings and decides, for the whole run, whether the line holds or the
ship tacks. A tack is never declared on a single loud reading: the
challenger must clear the hysteresis band above the line's own score for
``persistence`` consecutive readings. Readings that challenge but fall
short are counted as shudders — honest evidence, never a tack.

A reading is a dict with ``id``, ``verdict`` (a named course), and
``score`` in [0, 1]::

    {"line": "steady", "line_score": 0.62,
     "readings": [{"id": "r1", "verdict": "surge", "score": 0.80},
                  {"id": "r2", "verdict": "surge", "score": 0.81},
                  {"id": "r3", "verdict": "surge", "score": 0.79}],
     "band": 0.10, "persistence": 3}

Here the challenger clears 0.62 + 0.10 = 0.72 three times running, so the
keel tacks to ``surge``. The same readings with ``band`` 0.20 would hold:
a gust, not a shift.

Laws (declared up front, proved by the test suite)
--------------------------------------------------
1. **Line law** — ``line`` is a non-empty string and ``line_score`` is a
   number in [0, 1]; a keel without a real line is refused, never run.
2. **Reading law** — every reading carries a non-empty ``id``, a
   non-empty ``verdict``, and a ``score`` in [0, 1]; ids are unique. A
   reading missing any of these is refused, never scored.
3. **Band law** — ``band`` is a number >= 0; a negative band would let a
   weaker reading tack the ship, so it is refused.
4. **Persistence law** — ``persistence`` is an int >= 1; one loud reading
   is never a shift.
5. **Streak law** — only *consecutive* challenger readings count; a
   reading that agrees with the line or falls short of the band resets
   the streak to zero. Tacks are earned in a row, never accumulated.
6. **Determinism law** — same inputs → byte-identical verdict (sans
   ``ran_at``).
7. **Deny-closed law** — malformed inputs (unknown keys are fine, bad
   shapes are not) are refused with a named error, never coerced.
8. **Bound law** — runs are capped at ``max_readings`` (default 4096);
   a bigger run is refused rather than half-run.
9. **Evidence law** — every reading's disposition carries the margin it
   cleared or missed, the streak after it, and the line it was measured
   against; a bare decision is refused by design.

Pure computation — no actions, no side effects.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

_DEFAULT_BAND = 0.10
_DEFAULT_PERSISTENCE = 3
_DEFAULT_MAX_READINGS = 4096


def _check_score(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EngineInputError(
            f"engine 'keel': {where} must be a number in [0, 1], got "
            + type(value).__name__
        )
    score = float(value)
    if not 0.0 <= score <= 1.0:
        raise EngineInputError(
            f"engine 'keel': {where} must be in [0, 1], got {score!r}"
        )
    return score


def _keel(inputs: Dict[str, Any]) -> EngineResult:
    line = inputs.get("line")
    if not isinstance(line, str) or not line.strip():
        raise EngineInputError("engine 'keel': line must be a non-empty string")
    line_score = _check_score(inputs.get("line_score"), "line_score")

    band = inputs.get("band", _DEFAULT_BAND)
    if isinstance(band, bool) or not isinstance(band, (int, float)):
        raise EngineInputError(
            "engine 'keel': band must be a number >= 0, got " + type(band).__name__
        )
    band = float(band)
    if band < 0:
        raise EngineInputError(f"engine 'keel': band must be >= 0, got {band!r}")

    persistence = inputs.get("persistence", _DEFAULT_PERSISTENCE)
    if isinstance(persistence, bool) or not isinstance(persistence, int):
        raise EngineInputError(
            "engine 'keel': persistence must be an int >= 1, got "
            + type(persistence).__name__
        )
    if persistence < 1:
        raise EngineInputError(
            f"engine 'keel': persistence must be >= 1, got {persistence!r}"
        )

    readings = inputs.get("readings")
    if not isinstance(readings, list):
        raise EngineInputError(
            "engine 'keel': readings must be a list, got " + type(readings).__name__
        )
    max_readings = inputs.get("max_readings", _DEFAULT_MAX_READINGS)
    if isinstance(max_readings, bool) or not isinstance(max_readings, int):
        raise EngineInputError("engine 'keel': max_readings must be a positive int")
    if max_readings < 1:
        raise EngineInputError("engine 'keel': max_readings must be a positive int")
    if len(readings) > max_readings:
        raise EngineInputError(
            f"engine 'keel': {len(readings)} readings exceed max_readings "
            f"{max_readings} — refusing rather than half-running"
        )

    seen_ids: Dict[Any, None] = {}
    current_line = line
    current_score = line_score
    streak = 0
    tacks = 0
    shudders = 0
    dispositions: List[Dict[str, Any]] = []
    trace: List[str] = []

    for reading in readings:
        if not isinstance(reading, dict):
            raise EngineInputError(
                "engine 'keel': every reading must be a dict, got "
                + type(reading).__name__
            )
        rid = reading.get("id")
        if not isinstance(rid, str) or not rid.strip():
            raise EngineInputError("engine 'keel': every reading needs a non-empty id")
        if rid in seen_ids:
            raise EngineInputError(f"engine 'keel': duplicate reading id {rid!r}")
        seen_ids[rid] = None
        verdict = reading.get("verdict")
        if not isinstance(verdict, str) or not verdict.strip():
            raise EngineInputError(
                f"engine 'keel': reading {rid!r} needs a non-empty verdict"
            )
        score = _check_score(reading.get("score"), f"reading {rid!r} score")

        line_before = current_line
        threshold = current_score + band
        margin = round(score - threshold, 6)
        if verdict != current_line and score >= threshold:
            streak += 1
            disposition = "challenging"
        else:
            if verdict != current_line:
                shudders += 1
                disposition = "shudder"
            else:
                disposition = "agrees"
            streak = 0

        tacked_to: Any = None
        if streak >= persistence:
            tacked_to = verdict
            tacks += 1
            trace.append(
                f"{rid}: TACK — {verdict!r} cleared {threshold:.3f} "
                f"{persistence} readings running; line was {current_line!r}"
            )
            current_line = verdict
            current_score = score
            streak = 0
        else:
            trace.append(
                f"{rid}: {disposition} (score {score:.3f} vs band line "
                f"{threshold:.3f}, margin {margin:+.3f}, streak {streak})"
            )

        dispositions.append(
            {
                "id": rid,
                "verdict": verdict,
                "score": score,
                "disposition": disposition,
                "margin": margin,
                "streak_after": streak,
                "measured_against_line": line_before,
                "tacked_to": tacked_to,
                "band": band,
                "persistence": persistence,
            }
        )

    decision = "tack" if tacks else "hold"
    verdict = {
        "decision": decision,
        "line_in": line,
        "line_out": current_line,
        "tacks": tacks,
        "shudders": shudders,
        "readings": dispositions,
        "band": band,
        "persistence": persistence,
        "total": len(dispositions),
    }
    return EngineResult(
        engine_id="keel",
        verdict=verdict,
        confidence=round(current_score, 6),
        trace=trace,
    )


KEEL_ENGINE = Engine(
    id="keel",
    name="Keel",
    description=(
        "Verdict-stability engine: holds the named line unless a challenger "
        "clears the hysteresis band for `persistence` consecutive readings; "
        "a gust is never a shift."
    ),
    version="1.0.0",
    required=("line", "line_score", "readings"),
    schema={
        "line": "non-empty string, the current course verdict",
        "line_score": "number in [0, 1], the score that set the line",
        "readings": "chronological list of {id, verdict, score}",
        "band": "number >= 0, default 0.10 (hysteresis margin)",
        "persistence": "int >= 1, default 3 (consecutive readings to tack)",
        "max_readings": "int >= 1, default 4096 (run guard)",
    },
    risk="info",
    handler=_keel,
)

registry.register(KEEL_ENGINE)


def _declare_to_interop() -> None:
    try:
        from levi.interop.registry import register
    except Exception:  # pragma: no cover - registry substrate mid-edit
        return
    try:
        register(
            "engines-keel",
            provides=("engines.keel.decide",),
            requires=(),
        )
    except Exception:  # deny-closed: duplicate / malformed never half-runs
        pass


_declare_to_interop()
