"""Cybrus policy engine — default-deny authorization with deny-wins.

Rules are ``(subject, resource, action, effect, risk_level)`` tuples.
Patterns support exact match, ``"*"`` (match anything), and a trailing
``".*"`` prefix wildcard (``"vault.*"`` matches ``"vault.tokens"``).

Semantics (binding):
- **Default-deny**: no matching rule → the action is denied (fail closed).
- **Deny wins**: any matching ``deny`` rule beats every matching ``allow``.
- **Strictest risk ceiling**: the decision's risk level is the HIGHEST
  (strictest) risk among the matched rules — and ``risk_of()`` gives the
  same ceiling for any composite/inherited capability: every composite
  takes the strictest risk of its components.
- There is **no bypass path**: nothing in this module (or anywhere in
  cybrus governance) can skip evaluation. High-risk ``allow`` decisions
  still require a human approval (see ``levi.cybrus.approval``).

Rules persist as JSON under ``~/.levi/cybrus/policy.json`` (``LEVI_HOME``
override honored) via the shared ``_paths`` helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


# --- standalone-safe import of the sibling _paths helper -------------------
# The sibling builder owns _paths.py; it is already landed, but this module
# must also work if the package __init__ is mid-flight (it imports sibling
# engines that may not have landed yet). So: try the package import, fall
# back to loading _paths.py by file path. Stdlib only.
def _paths():  # noqa: D103 - private helper
    try:
        from levi.cybrus import _paths as _p

        return _p
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "levi.cybrus._paths.standalone",
            Path(__file__).resolve().parent / "_paths.py",
        )
        if spec is None or spec.loader is None:  # pragma: no cover
            raise ImportError("cybrus _paths helper unavailable") from None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


RISK_LEVELS = ("low", "medium", "high", "critical")
_RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

EFFECTS = ("allow", "deny")

#: Risks at or above this level require a human approval even when allowed.
APPROVAL_RISK_FLOOR = "high"

_STORE_NAME = "policy"


def risk_of(*levels: str) -> str:
    """Strictest (highest) risk level among *levels*.

    This is the risk-ceiling rule: every composite or inherited capability
    takes the strictest risk of its components — risk can only escalate,
    never dilute. Empty input → ``"low"`` (no components, no risk).
    Raises :class:`ValueError` on an unknown level.
    """
    if not levels:
        return "low"
    for level in levels:
        if level not in _RISK_RANK:
            raise ValueError(
                f"unknown risk level {level!r}; valid: {list(RISK_LEVELS)}"
            )
    return max(levels, key=lambda level: _RISK_RANK[level])


def _matches(pattern: str, value: str) -> bool:
    if pattern == "*" or pattern == value:
        return True
    if pattern.endswith(".*") and value.startswith(pattern[:-1]):
        return True
    return False


@dataclass
class Decision:
    """The outcome of :meth:`PolicyEngine.evaluate`."""

    decision: str  #: "allow" or "deny"
    risk: str  #: strictest risk among matched rules (or "critical" on default-deny)
    matched_rule: Optional[Dict]  #: the decisive rule, None on default-deny
    reason: str

    @property
    def allowed(self) -> bool:
        return self.decision == "allow"


def _seed_rules() -> List[Dict]:
    """Conservative starting policy. Vault/token work is high-risk by
    default (allowed for the owner, but gated on human approval);
    executing system commands is hard-denied at critical."""
    return [
        {
            "subject": "owner",
            "resource": "*",
            "action": "read",
            "effect": "allow",
            "risk": "low",
        },
        {
            "subject": "owner",
            "resource": "identity.*",
            "action": "*",
            "effect": "allow",
            "risk": "medium",
        },
        {
            "subject": "owner",
            "resource": "device.*",
            "action": "*",
            "effect": "allow",
            "risk": "medium",
        },
        {
            "subject": "owner",
            "resource": "vault.*",
            "action": "*",
            "effect": "allow",
            "risk": "high",
        },
        {
            "subject": "owner",
            "resource": "token.*",
            "action": "*",
            "effect": "allow",
            "risk": "high",
        },
        {
            "subject": "*",
            "resource": "system.*",
            "action": "execute",
            "effect": "deny",
            "risk": "critical",
        },
    ]


class PolicyEngine:
    """Default-deny, deny-wins policy evaluation over persisted JSON rules."""

    def __init__(self) -> None:
        p = _paths()
        self._path: Path = p.store_path(_STORE_NAME)
        data = p.load_json_store(self._path)
        if data is None:
            self._rules: List[Dict] = _seed_rules()
            self._save()
        elif isinstance(data, list):
            self._rules = data
        else:  # pragma: no cover - corrupt shapes are quarantined by _paths
            raise ValueError(f"policy store has unexpected shape at {self._path}")

    # -- persistence -----------------------------------------------------

    def _reload(self) -> None:
        """Reload rules from disk. Call with the store lock held."""
        data = _paths().load_json_store(self._path)
        if data is None:
            self._rules = _seed_rules()
        elif isinstance(data, list):
            self._rules = data
        else:  # pragma: no cover - corrupt shapes are quarantined by _paths
            raise ValueError(f"policy store has unexpected shape at {self._path}")

    def _save(self) -> None:
        _paths().save_json_store(self._path, self._rules)

    # -- rules -----------------------------------------------------------

    def list_rules(self) -> List[Dict]:
        return [dict(rule) for rule in self._rules]

    def add_rule(
        self,
        subject: str,
        resource: str,
        action: str,
        effect: str,
        risk_level: str,
    ) -> Dict:
        """Append a rule and persist. Validates effect and risk level."""
        if effect not in EFFECTS:
            raise ValueError(f"effect must be one of {EFFECTS}, got {effect!r}")
        if risk_level not in _RISK_RANK:
            raise ValueError(
                f"unknown risk level {risk_level!r}; valid: {list(RISK_LEVELS)}"
            )
        rule = {
            "subject": subject,
            "resource": resource,
            "action": action,
            "effect": effect,
            "risk": risk_level,
        }
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            self._rules.append(rule)
            self._save()
        return dict(rule)

    def remove_rule(self, index: int) -> Dict:
        """Remove the rule at *index*. Raises :class:`IndexError` when out
        of range. Runs under the store lock so a concurrent mutation cannot
        shift the index between read and write."""
        p = _paths()
        with p.store_lock(self._path):
            self._reload()
            removed = self._rules.pop(index)
            self._save()
            return dict(removed)

    # -- evaluation ------------------------------------------------------

    def evaluate(self, subject: str, resource: str, action: str) -> Decision:
        """Evaluate ``(subject, resource, action)`` against the rules.

        Deny wins over allow. The decision risk is the strictest risk among
        the matched rules on the winning side. No matching rule → deny at
        ``critical`` risk (default-deny, fail closed and loud).
        """
        matched = [
            rule
            for rule in self._rules
            if _matches(rule["subject"], subject)
            and _matches(rule["resource"], resource)
            and _matches(rule["action"], action)
        ]
        denies = [rule for rule in matched if rule["effect"] == "deny"]
        allows = [rule for rule in matched if rule["effect"] == "allow"]
        if denies:
            risk = risk_of(*(rule["risk"] for rule in denies))
            decisive = max(denies, key=lambda r: _RISK_RANK[r["risk"]])
            return Decision(
                decision="deny",
                risk=risk,
                matched_rule=dict(decisive),
                reason=f"denied by rule {decisive} (deny wins over allow)",
            )
        if allows:
            risk = risk_of(*(rule["risk"] for rule in allows))
            decisive = max(allows, key=lambda r: _RISK_RANK[r["risk"]])
            return Decision(
                decision="allow",
                risk=risk,
                matched_rule=dict(decisive),
                reason=f"allowed by rule {decisive}",
            )
        return Decision(
            decision="deny",
            risk="critical",
            matched_rule=None,
            reason="default-deny: no rule matches (fail closed)",
        )

    def needs_approval(self, decision: Decision) -> bool:
        """True when *decision* is an allow at high risk or above — the
        human-in-the-loop gate (see ``levi.cybrus.approval``). Denied
        decisions never need approval: they are simply blocked."""
        return (
            decision.decision == "allow"
            and _RISK_RANK[decision.risk] >= _RISK_RANK[APPROVAL_RISK_FLOOR]
        )
