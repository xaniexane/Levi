"""eli: intelligence-layer mind alongside echo (LEVI-native).

Canon role (ORGANISM_FORMS): "intelligence-layer mind alongside echo".

Canon evidence (founder corpus: copilot-sweep/ser13-18-21-master-conversation.md):
  - "ELI (Orchestrator) — global task scheduler + router
    (eli_orchestrator.py)."
  - SER-13 (Logic Engine): "ELI orchestrates which state to use."
  - Hierarchy: ELI sits in the Intelligence Layer with Echo, Alpha,
    HyperCube, Oracle, OmniPulse, DemandPulse.

This is a LEVI-native recreation with LEVI's own twist — never a copy of
the original code. ELI is a deterministic, rules-based task router:

  - :class:`ELIRouter`: register named engines (callables); ``route(task)``
    picks an engine by explicit routing rules and returns a receipt.
    Unregistered engines can never be chosen (fail-closed).
  - Routing rules are plain keyword policies — inspectable, deterministic,
    no model calls. ELI never executes the task itself; it returns the
    routing decision as DATA. Execution belongs to the caller (or to
    ``levi.orchestration``).
  - Dry-run purity: ``route(..., dry_run=True)`` computes the routing
    without invoking any handler — and even on a live route, the handler
    is NOT invoked by ELI; the receipt carries the handler for the caller
    to invoke under its own gates.
  - Hostile input as data: a task that is not a non-empty string, or that
    matches no rule, is routed to ``"unrouted"`` with a reason — never to
    an engine by accident, never executed.
  - ``route_logic_state``: the SER-13 duty — pick a logic state for a task
    from the canonical 13 (requires the name tables seated via
    ``levi.ser18.seat()``); unseated tables -> ``"undecided"`` with an
    honest reason, never an invented state.

ELI is a mind alongside Echo, not above it: Echo reflects, ELI routes.
Neither overrides the other's verdict.

Ready-for-review by the keeper. Never claims his review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from levi.cybrus import qid

FORM_NAME = "eli"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# Default routing policy: keyword -> engine. Deterministic, inspectable,
# and deliberately coarse — ELI routes to organs, it does not decide tasks.
_DEFAULT_RULES: List[Dict[str, Any]] = [
    {"keywords": ("blueprint", "design", "architect"), "engine": "echo"},
    {"keywords": ("repair", "fix", "heal", "upgrade", "evolve"), "engine": "uniforge"},
    {"keywords": ("build", "generate", "scaffold", "compile"), "engine": "alpha"},
    {"keywords": ("run", "execute", "automate", "apply"), "engine": "omega"},
    {
        "keywords": ("market", "job", "opportunity", "demand", "scout"),
        "engine": "demandpulse",
    },
    {"keywords": ("identity", "key", "secret", "vault", "encrypt"), "engine": "cybrus"},
    {"keywords": ("reflect", "mirror", "diagnose", "fracture"), "engine": "echo"},
    {"keywords": ("sandbox", "simulate", "safe", "experiment"), "engine": "vector"},
    {
        "keywords": ("strategy", "goal", "weight", "long-term", "plan"),
        "engine": "oracle",
    },
    {"keywords": ("telemetry", "health", "metrics", "alert"), "engine": "cyberpulse"},
    {"keywords": ("message", "send", "coordinate", "sync"), "engine": "nexus"},
    {"keywords": ("how-to", "teach", "learn", "document"), "engine": "cortex"},
]


class ELIRouter:
    """Deterministic task router. Returns routing decisions as data."""

    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None) -> None:
        self._engines: Dict[str, Callable[..., Any]] = {}
        self._rules: List[Dict[str, Any]] = list(
            rules if rules is not None else _DEFAULT_RULES
        )
        self._history: List[Dict[str, Any]] = []

    def register_engine(self, name: Any, handler: Any) -> Dict[str, Any]:
        """Register an engine handler. Fail-closed on bad input."""
        if not isinstance(name, str) or not name.strip():
            return self._receipt(
                "rejected",
                f"engine name must be a non-empty string, got {name!r}",
                engine=None,
                task=None,
            )
        if not callable(handler):
            return self._receipt(
                "rejected",
                f"handler for engine {name!r} must be callable, got "
                f"{type(handler).__name__}",
                engine=name.strip(),
                task=None,
            )
        key = name.strip()
        self._engines[key] = handler
        return self._receipt(
            "registered", f"engine '{key}' registered", engine=key, task=None
        )

    def route(self, task: Any, *, dry_run: bool = False) -> Dict[str, Any]:
        """Pick an engine for ``task``. Returns a receipt; never executes."""
        if not isinstance(task, str) or not task.strip():
            return self._receipt(
                "unrouted",
                f"task must be a non-empty string, got {type(task).__name__}: "
                "treated as data, routed nowhere",
                engine=None,
                task=task if isinstance(task, str) else None,
                dry_run=dry_run,
            )
        lowered = task.lower()
        chosen: Optional[str] = None
        matched_rule: Optional[str] = None
        for rule in self._rules:
            for kw in rule["keywords"]:
                if kw in lowered:
                    chosen = rule["engine"]
                    matched_rule = kw
                    break
            if chosen:
                break
        if chosen is None:
            return self._receipt(
                "unrouted",
                "no routing rule matched: task held as data, routed nowhere",
                engine=None,
                task=task,
                dry_run=dry_run,
            )
        if chosen not in self._engines:
            return self._receipt(
                "unrouted",
                f"rule matched engine '{chosen}' via keyword '{matched_rule}', "
                "but that engine is not registered: fail-closed, routed nowhere",
                engine=chosen,
                task=task,
                dry_run=dry_run,
            )
        receipt = self._receipt(
            "routed",
            (
                f"routed to '{chosen}' via keyword '{matched_rule}'"
                + (
                    " (dry run — no handler invoked, none ever is by ELI)"
                    if dry_run
                    else " (handler returned as data for the caller)"
                )
            ),
            engine=chosen,
            task=task,
            dry_run=dry_run,
        )
        receipt["handler"] = self._engines[chosen]
        if not dry_run:
            self._history.append(
                {"at": receipt["at"], "engine": chosen, "rule": matched_rule}
            )
        return receipt

    def route_logic_state(self, task: Any) -> Dict[str, Any]:
        """SER-13 duty: pick a logic state for a task from the canon 13.

        Deterministic keyword mapping; unseated name tables -> 'undecided'
        with an honest reason, never an invented state.
        """
        if not qid.STATE_NAMES:
            return {
                "form": FORM_NAME,
                "status": "undecided",
                "reason": "SER-13 name tables not seated (see levi.ser18.seat()); "
                "refusing to invent a logic state",
                "state": None,
                "at": _utcnow(),
            }
        lowered = task.lower() if isinstance(task, str) else ""
        mapping = [
            (("undo", "reverse", "invert"), "Inverse"),
            (("reflect", "mirror"), "Echo"),
            (("fail", "crash", "break"), "Collapse"),
            (("retry", "restart", "again"), "Rebirth"),
            (("forecast", "predict", "project"), "Projection"),
            (("review", "think", "consider"), "Reflection"),
            (("split", "branch", "fork"), "Divergence"),
            (("merge", "join", "unite"), "Convergence"),
            (("meta", "about"), "Meta"),
        ]
        state = "Forward"  # the default logic state
        for keywords, name in mapping:
            if any(k in lowered for k in keywords):
                state = name
                break
        if state not in qid.STATE_NAMES:
            state = qid.STATE_NAMES[0]
        return {
            "form": FORM_NAME,
            "status": "decided",
            "reason": f"logic state '{state}' selected from the seated SER-13 canon",
            "state": state,
            "at": _utcnow(),
        }

    def history(self) -> List[Dict[str, Any]]:
        return [dict(h) for h in self._history]

    def _receipt(
        self,
        status: str,
        reason: str,
        *,
        engine: Optional[str],
        task: Optional[Any],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        return {
            "form": FORM_NAME,
            "status": status,
            "reason": reason,
            "engine": engine,
            "task": task,
            "dry_run": dry_run,
            "at": _utcnow(),
        }
