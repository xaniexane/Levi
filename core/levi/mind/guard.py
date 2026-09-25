"""Offline-mandatory guard — the verifier half of the start pair.

Local is law: the mind runner refuses to start with any network inference
path enabled. The verdict is ternary, not boolean:

- ``LOCAL``     — every check says local; start is allowed.
- ``REFUSED``   — a network path was found; start is refused with explicit
                  reasons. Never silent, never vague.
- ``UNCERTAIN`` — the config could not be verified at all; treated as a
                  refusal (fail closed) but reported as its own state so a
                  corrupt or tampered config is not mistaken for a clean no.

The guard never grants on absence of evidence: it must positively find the
local-only posture before it says ``LOCAL``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verdict(Enum):
    LOCAL = "local"
    REFUSED = "refused"
    UNCERTAIN = "uncertain"


@dataclass
class GuardReport:
    verdict: Verdict
    reasons: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.verdict is Verdict.LOCAL

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
        }


#: Keys that, if truthy anywhere in the config, mean a network path exists.
_NETWORK_HINT_KEYS = {
    "remote_inference",
    "remote",
    "api_url",
    "endpoint",
    "cloud",
    "cloud_provider",
    "remote_api_key",
    "third_party_weights",
    "telemetry",
    "usage_ping",
    "crash_report",
}

#: Keys that, if truthy, mean weights came from outside our own machines.
_FOREIGN_WEIGHT_KEYS = {"url", "registry", "hub", "mirror"}

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _iter_paths(config: Any, prefix: str = ""):
    """Yield (dotted.path, value) for every leaf in a nested config."""
    if isinstance(config, dict):
        for key, value in config.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                yield from _iter_paths(value, path)
            else:
                yield path, value
    else:
        yield prefix, config


def check(config: Any) -> GuardReport:
    """Evaluate a config dict against the offline-mandatory rule."""
    if not isinstance(config, dict):
        return GuardReport(
            Verdict.UNCERTAIN,
            ["config is not a mapping; cannot verify local-only posture"],
        )

    reasons: list[str] = []
    leaves = list(_iter_paths(config))
    by_leaf = {leaf: leaf.split(".")[-1].lower() for leaf, _value in leaves}
    values = dict(leaves)

    # 1. Positive local-only posture must be present.
    mode = (
        config.get("inference", {}).get("mode")
        if isinstance(config.get("inference"), dict)
        else None
    )
    if mode != "local":
        reasons.append(f"inference.mode is {mode!r}, not 'local'")

    # 2. Any network hint key that is truthy is a refusal.
    for leaf, leaf_name in by_leaf.items():
        value = values[leaf]
        if leaf_name in _NETWORK_HINT_KEYS and value not in (
            False,
            "",
            None,
            0,
            [],
            {},
        ):
            reasons.append(f"network path enabled at {leaf}={value!r}")

    # 3. The local server face (milestone 1.3 shape) must stay loopback-only.
    server = config.get("server")
    if isinstance(server, dict) and server.get("enabled"):
        host = server.get("host", "")
        if host not in _LOOPBACK_HOSTS:
            reasons.append(f"server enabled on non-loopback host {host!r}")

    # 4. Only our own weights ever load — any foreign-weight source refuses.
    weights = config.get("weights")
    if isinstance(weights, dict):
        for leaf, leaf_name in by_leaf.items():
            if leaf.startswith("weights.") and leaf_name in _FOREIGN_WEIGHT_KEYS:
                value = values[leaf]
                if value not in (False, "", None, 0, [], {}):
                    reasons.append(f"foreign weight source at {leaf}={value!r}")

    if reasons:
        return GuardReport(Verdict.REFUSED, reasons)
    return GuardReport(
        Verdict.LOCAL, ["local-only posture verified; no network inference paths found"]
    )
