"""Strictest-risk-ceiling composition for interpenetration.

Binding law: when modules compose into one action, the composition inherits
the *highest* risk level among its participants. The organism is wired
together; a low-risk module composed with a high-risk module does not dilute
the risk — it inherits it.

:class:`~levi.policy.gates.RiskLevel` is reused, never redefined. It is
imported lazily so this module stays importable even when the policy package
is unavailable (fail-closed: the functions raise rather than guess).

Deny-closed discipline:

- Empty input → :class:`ValueError` (no ceiling can be computed).
- Unknown / unparseable level → :class:`ValueError` (never silently dropped).
- ``compose_risk`` requires every participant to carry a resolvable risk.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Tuple

_RISK_MODULE = "levi.policy.gates"
_RISK_ATTR = "RiskLevel"


def _risk_level():
    """Lazily resolve ``levi.policy.gates.RiskLevel``.

    Raises RuntimeError when the policy package is unavailable — the
    ceiling cannot be computed honestly without the canonical enum, and
    no substitute is acceptable.
    """
    try:
        module = __import__(_RISK_MODULE, fromlist=[_RISK_ATTR])
        return getattr(module, _RISK_ATTR)
    except Exception as exc:
        raise RuntimeError(
            "interop.risks: policy gates unavailable (%s); "
            "risk ceiling cannot be computed" % exc
        ) from exc


def _parse_level(value: Any):
    """Coerce *value* to the canonical ``RiskLevel``.

    Accepts ``RiskLevel`` instances, ints (via the enum), and case-insensitive
    names (``"high"`` / ``"HIGH"``). Anything else → ``ValueError``.
    """
    RiskLevel = _risk_level()
    if isinstance(value, RiskLevel):
        return value
    if isinstance(value, bool):
        raise ValueError("risk level must not be a bool, got %r" % (value,))
    if isinstance(value, int):
        try:
            return RiskLevel(value)
        except ValueError:
            pass
        raise ValueError(
            "unknown risk level %r (valid ints: %s)"
            % (value, sorted(m.value for m in RiskLevel))
        )
    if isinstance(value, str):
        key = value.strip().upper()
        try:
            return RiskLevel[key]
        except KeyError:
            raise ValueError(
                "unknown risk level %r (valid names: %s)"
                % (value, sorted(m.name for m in RiskLevel))
            ) from None
    raise ValueError(
        "unparseable risk level %r (expected RiskLevel, int, or name str)" % (value,)
    )


def parse_level(value: Any):
    """Coerce *value* to the canonical ``RiskLevel``.

    This is the public face of :func:`_parse_level` — the single source of
    the ceiling ordering. Accepts ``RiskLevel`` instances, ints (via the
    enum), and case-insensitive names (``"high"`` / ``"HIGH"``).
    Anything else → :class:`ValueError` (deny-closed).
    """
    return _parse_level(value)


def highest_caution():
    """Return the highest caution level (``RiskLevel.CRITICAL``).

    This is the deny-closed default: an unknown or unrated component does
    not dilute a composition's ceiling — it raises it to the maximum.
    """
    return max(_risk_level())


def ceiling(levels: Iterable[Any]):
    """Return the strictest (maximum) risk level in *levels*.

    Deny-closed: raises :class:`ValueError` on an empty iterable or on any
    unknown/unparseable level — a ceiling with a hole in it is not a ceiling.
    """
    levels = list(levels)
    if not levels:
        raise ValueError("ceiling: no levels supplied (deny-closed)")
    parsed = [_parse_level(v) for v in levels]
    return max(parsed)


def _participant_risk(participant: Any) -> Tuple[str, Any]:
    """Extract ``(name, risk_level)`` from one participant.

    A participant is either a bare level (named ``"<anonymous>"``) or a
    mapping with ``"risk"`` (and optional ``"name"``/``"module"``) keys.
    """
    if isinstance(participant, Mapping):
        name = str(participant.get("name", participant.get("module", "<anonymous>")))
        if "risk" not in participant:
            raise ValueError(
                "compose_risk: participant %r carries no 'risk' key" % (name,)
            )
        return name, participant["risk"]
    return "<anonymous>", participant


def compose_risk(*module_risks: Any) -> Dict[str, Any]:
    """Compose the risk of several modules into one strictest-risk ceiling.

    Each argument is either a bare risk level (``RiskLevel`` / int / name)
    or a mapping like ``{"name": "rag", "risk": RiskLevel.MODERATE}``.

    Returns ``{"ceiling": RiskLevel, "contributions": {name: RiskLevel}}`` —
    the ceiling plus the per-module evidence that produced it, so callers
    (and receipts) can audit *why* the composition is risky. Deny-closed:
    raises :class:`ValueError` when any participant is unparseable.
    """
    if not module_risks:
        raise ValueError("compose_risk: no participants (deny-closed)")
    contributions: Dict[str, Any] = {}
    for participant in module_risks:
        name, raw = _participant_risk(participant)
        level = _parse_level(raw)
        key = name
        suffix = 2
        while key in contributions:  # two anonymous participants stay distinct
            key = "%s#%d" % (name, suffix)
            suffix += 1
        contributions[key] = level
    return {"ceiling": max(contributions.values()), "contributions": contributions}
