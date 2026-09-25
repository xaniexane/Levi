"""Redline engine — the spend-budget guard.

The standing law is no spending until the operation is self-sufficient
and profitable. This engine is the machine form of that line: given what
is already spent, the hard cap, and a proposed pending amount, it says
exactly where the line stands.

Inputs
------
``spent``: number ≥ 0 — already committed.
``cap``: number > 0 — the hard cap. Nothing crosses it.
``pending``: number ≥ 0, default 0 — the proposed spend under judgment.
``warn_ratio``: number in (0, 1), default 0.10 — the fraction of the cap
that counts as "running close" even when nothing is breached.
``label``: optional str — what the pending spend is for (reported back,
never judged).

The verdict is one of:

- ``"over"`` — ``spent`` already exceeds ``cap``. The line is crossed.
- ``"would-breach"`` — ``spent`` is fine but ``spent + pending`` crosses
  the cap; the exact overshoot is named.
- ``"at-risk"`` — inside the cap but the remaining headroom is below
  ``warn_ratio`` of the cap. Close is close; the engine says so.
- ``"clear"`` — inside the cap with comfortable headroom.

Laws (declared up front, proved by the test suite)
--------------------------------------------------
1. **Determinism law** — same inputs → byte-identical verdict.
2. **Deny-over law** — ``spent > cap`` is always ``"over"``. No
   rounding, no grace, no "close enough".
3. **Pending-counts law** — the pending amount is added *before*
   judgment. ``"would-breach"`` names the exact overshoot to the cent.
4. **Honest-math law** — ``remaining`` and ``overshoot`` are reported
   exactly (rounded to cents for money, never truncated toward comfort).
5. **No-negative law** — negative ``spent``/``pending``/``cap``, a zero
   cap, or a ``warn_ratio`` outside (0, 1) is refused outright, never
   coerced.

Confidence is 1.0 in every verdict — the math is exact, and exact math
does not hedge.

Pure computation — no actions, no side effects.
"""

from __future__ import annotations

from typing import Any, Dict, List

from levi.engines.base import Engine, EngineInputError, EngineResult, registry

_DEFAULT_WARN_RATIO = 0.10


def _money(value: float) -> float:
    """Cents-rounded, never truncated toward comfort."""
    return round(float(value) + 0.0, 2)


def _redline(inputs: Dict[str, Any]) -> EngineResult:
    spent = inputs.get("spent")
    cap = inputs.get("cap")
    pending = inputs.get("pending", 0)
    warn_ratio = inputs.get("warn_ratio", _DEFAULT_WARN_RATIO)
    label = inputs.get("label")

    for key, value in (("spent", spent), ("cap", cap), ("pending", pending)):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise EngineInputError(f"redline: '{key}' must be a number")
    if not isinstance(warn_ratio, (int, float)) or isinstance(warn_ratio, bool):
        raise EngineInputError("redline: 'warn_ratio' must be a number")
    if label is not None and not isinstance(label, str):
        raise EngineInputError("redline: 'label' must be a str when given")

    if spent < 0:
        raise EngineInputError("redline: 'spent' cannot be negative")
    if pending < 0:
        raise EngineInputError("redline: 'pending' cannot be negative")
    if cap <= 0:
        raise EngineInputError("redline: 'cap' must be > 0")
    if not 0.0 < warn_ratio < 1.0:
        raise EngineInputError("redline: 'warn_ratio' must be in (0, 1)")

    trace: List[str] = [
        f"spent={spent} cap={cap} pending={pending}"
        + (f" label={label!r}" if label else "")
    ]
    total = spent + pending
    remaining = _money(cap - spent)

    if spent > cap:
        overshoot = _money(spent - cap)
        trace.append(
            f"OVER: spent {spent} exceeds cap {cap} by {overshoot} — "
            "the line is crossed"
        )
        verdict = {
            "status": "over",
            "spent": _money(spent),
            "cap": _money(cap),
            "overshoot": overshoot,
        }
    elif total > cap:
        overshoot = _money(total - cap)
        trace.append(
            f"WOULD-BREACH: spent {spent} + pending {pending} = {total} "
            f"crosses cap {cap} by {overshoot}"
        )
        verdict = {
            "status": "would-breach",
            "spent": _money(spent),
            "cap": _money(cap),
            "pending": _money(pending),
            "overshoot": overshoot,
            "remaining": remaining,
        }
    elif remaining < _money(cap * warn_ratio):
        trace.append(
            f"AT-RISK: remaining {remaining} is below the warn band "
            f"({warn_ratio} of cap {cap}) — close is close"
        )
        verdict = {
            "status": "at-risk",
            "spent": _money(spent),
            "cap": _money(cap),
            "pending": _money(pending),
            "remaining": remaining,
        }
    else:
        trace.append(f"CLEAR: remaining {remaining} of cap {cap} — inside the line")
        verdict = {
            "status": "clear",
            "spent": _money(spent),
            "cap": _money(cap),
            "pending": _money(pending),
            "remaining": remaining,
        }
    if label:
        verdict["label"] = label
    return EngineResult(
        engine_id="redline", verdict=verdict, confidence=1.0, trace=trace
    )


REDLINE_ENGINE = Engine(
    id="redline",
    name="Redline",
    description=(
        "The spend-budget guard: judges a proposed pending spend against "
        "what is already spent and a hard cap — over, would-breach "
        "(exact overshoot), at-risk (warn band), or clear. Exact math, "
        "no grace."
    ),
    version="1.0.0",
    required=("spent", "cap"),
    schema={
        "spent": "number ≥ 0 — already committed",
        "cap": "number > 0 — the hard cap",
        "pending": "number ≥ 0, default 0 — the spend under judgment",
        "warn_ratio": "number in (0, 1), default 0.10 — the close-call band",
        "label": "optional str — what the pending spend is for",
    },
    risk="info",
    handler=_redline,
)

registry.register(REDLINE_ENGINE)
