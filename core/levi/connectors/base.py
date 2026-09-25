"""Connector registry: the only legal way to run a connector.

Registration is additive and idempotent; ``poll`` validates that the
connector exists and that the poll callable returned the contract
shape ``(events, state)`` — a connector that returns anything else is
treated as a failure, never as partial data. Connectors observe only:
a poll must not mutate anything outside the read it needs to see.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple


class ConnectorError(ValueError):
    """Raised when a poll is refused or a connector misbehaves."""


# poll(**inputs) -> (events, new_state)
PollFn = Callable[..., Tuple[List[Dict[str, Any]], Dict[str, Any]]]


@dataclass
class Connector:
    """A registered external-source poller."""

    id: str
    name: str
    description: str
    version: str = "1.0.0"
    # Documented input names; the poll validates its own inputs.
    inputs: Tuple[str, ...] = ()
    risk: str = "info"  # connectors observe; they never act
    poll: PollFn | None = None


class ConnectorRegistry:
    """Additive, idempotent registry of connectors."""

    def __init__(self) -> None:
        self._connectors: Dict[str, Connector] = {}

    def register(self, connector: Connector) -> Connector:
        if not connector.id or not isinstance(connector.id, str):
            raise ConnectorError("connector needs a non-empty string id")
        self._connectors[connector.id] = connector
        return connector

    def get(self, connector_id: str) -> Connector:
        try:
            return self._connectors[connector_id]
        except KeyError:
            raise ConnectorError(f"unknown connector '{connector_id}'") from None

    def list(self) -> List[Connector]:
        return [self._connectors[k] for k in sorted(self._connectors)]

    def poll(
        self, connector_id: str, **inputs: Any
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        connector = self.get(connector_id)
        if connector.poll is None:
            raise ConnectorError(f"connector '{connector_id}' has no poll function")
        result = connector.poll(**inputs)
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or not isinstance(result[0], list)
            or not isinstance(result[1], dict)
        ):
            raise ConnectorError(
                f"connector '{connector_id}' broke the poll contract: "
                "expected (events: list, state: dict)"
            )
        return result


registry = ConnectorRegistry()


def describe(connector_id: str) -> Dict[str, Any]:
    """Public descriptor for a connector (no callables)."""
    c = registry.get(connector_id)
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "version": c.version,
        "inputs": list(c.inputs),
        "risk": c.risk,
    }
