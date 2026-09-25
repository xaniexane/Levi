"""Connector substrate: types, registry, and the polling contract.

A *connector* is LEVI's ear on the outside world: a small, local,
stdlib-only poller that turns an external source into a stream of plain
data events. Connectors observe; they never act — no writes, no sends,
no mutations beyond the read required to see what changed.

Every connector follows the same contract::

    events, state = poll(**inputs) -> (list of event dicts, new state dict)

The caller holds the ``state`` between polls (it is the connector's
memory of what it last saw); the connector itself keeps nothing. Poll
inputs are validated deny-closed: a malformed or out-of-policy poll is
refused with a named error, never half-run.

Ships with four native connectors:

- ``directory`` — polls a local directory for added / modified /
  removed files. Paths are deny-closed: must resolve under an allowed
  root, symlinks are followed then re-checked, and nothing outside the
  allowed roots is ever read.
- ``clock`` — pure tick math: given ``since``, ``now``, and
  ``period_seconds``, emits the ticks that fell due. It reads no wall
  clock itself — the caller passes ``now`` — so ticks are deterministic
  and testable.
- ``logtail`` — one event per new line appended to a local log file;
  rotation is reported honestly and re-baselined. Paths are deny-closed
  under the allowed roots, and floods are refused, never half-read.
- ``diskwatch`` — polls ``shutil.disk_usage`` for a path and emits one
  event per usage-band change (ok/warn/crit), including recovery. The
  first poll emits an honest ``baseline`` event; a steady band emits
  nothing. Thresholds are deny-closed (0 < warn < crit < 100).

Use::

    from levi.connectors import registry
    events, state = registry.poll("directory", path="~/notes", state={})
"""

from __future__ import annotations

from levi.connectors.base import (
    Connector,
    ConnectorError,
    ConnectorRegistry,
    registry,
)

__all__ = [
    "Connector",
    "ConnectorError",
    "ConnectorRegistry",
    "registry",
]

# Builtin connectors self-register on import.
from levi.connectors import clock as _clock  # noqa: E402,F401
from levi.connectors import directory as _directory  # noqa: E402,F401
from levi.connectors import diskwatch as _diskwatch  # noqa: E402,F401
from levi.connectors import logtail as _logtail  # noqa: E402,F401
