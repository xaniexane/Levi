"""Substrate router for the SI team.

Contract (shared with the Alpha worker):
  - register_substrate(role_name, probe_fn): register an explicit substrate
    for a role. The probe returns an answer string or None.
  - At import, try `from levi.alpha import probe_alpha` inside
    try/except ImportError. If it yields a reasoner, Alpha routes through
    it; otherwise the rules fallback answers.
  - This module never hard-depends on levi.alpha.

Resolution order for consult(): registered probe > levi.alpha (Alpha only)
> native rules-engine SI core. Every answer reports which substrate
actually answered.
"""

from __future__ import annotations

import importlib
from typing import Callable, Dict, Optional, Tuple

ProbeFn = Callable[[str], Optional[str]]

_substrates: Dict[str, ProbeFn] = {}


def register_substrate(role_name: str, probe_fn: ProbeFn) -> None:
    """Register an explicit substrate probe for *role_name*."""
    if not callable(probe_fn):
        raise TypeError("probe_fn must be callable")
    _substrates[(role_name or "").strip().lower()] = probe_fn


def unregister_substrate(role_name: str) -> None:
    _substrates.pop((role_name or "").strip().lower(), None)


def registered_roles() -> list:
    return sorted(_substrates)


def _safe_probe(probe: ProbeFn, task: str) -> Optional[str]:
    try:
        result = probe(task)
    except Exception:
        return None
    if isinstance(result, str) and result.strip():
        return result
    return None


def _normalize_alpha_result(result: object) -> Optional[str]:
    """The sibling alpha Reasoner returns a receipt dict, not a bare string."""
    if isinstance(result, str) and result.strip():
        return result
    if isinstance(result, dict):
        answer = result.get("answer")
        if isinstance(answer, str) and answer.strip():
            return answer
    return None


def _alpha_probe_fn(task: str) -> Optional[str]:
    reasoner_probe = _alpha_reasoner_from_module()
    if reasoner_probe is None:
        return None
    try:
        return _normalize_alpha_result(reasoner_probe(task))
    except Exception:
        return None


def _alpha_reasoner_from_module() -> Optional[ProbeFn]:
    """Best-effort probe of the sibling Alpha substrate — never required."""
    try:
        module = importlib.import_module("levi.alpha")
    except ImportError:
        return None
    probe_alpha = getattr(module, "probe_alpha", None)
    if not callable(probe_alpha):
        return None
    try:
        reasoner = probe_alpha()
    except Exception:
        return None
    if callable(reasoner):
        return reasoner
    reason = getattr(reasoner, "reason", None)
    if callable(reason):
        return reason
    return None


def _brain_probe() -> Optional[ProbeFn]:
    """Optional hook for the native brain — wired when a probe API lands.

    Today levi.brain exposes no inference entry point, so this returns
    None honestly. Kept so capability_report() can name the hook.
    """
    return None


def reason(
    role: str, task: str, fallback: Callable[[str], Tuple[str, str]]
) -> Tuple[str, str]:
    """Route *task* to the best available substrate for *role*.

    Returns (substrate_name, answer). *fallback* is the SI core's own
    rules engine: (task) -> (answer, rule_tag).
    """
    name = (role or "").strip().lower()

    probe = _substrates.get(name)
    if probe is not None:
        answer = _safe_probe(probe, task)
        if answer is not None:
            return f"registered:{name}", answer

    if name == "alpha":
        answer = _alpha_probe_fn(task)
        if answer is not None:
            return "levi.alpha", answer
        brain_probe = _brain_probe()
        if brain_probe is not None:
            answer = _safe_probe(brain_probe, task)
            if answer is not None:
                return "native-brain", answer

    answer, _rule_tag = fallback(task)
    return "rules-engine", answer
