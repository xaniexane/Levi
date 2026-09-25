"""Offline-first, proved — not promised.

``OfflineGuard`` disables socket creation for a block of code: any attempt
to open a network connection raises ``OfflineViolation`` instead of hanging
or phoning home. The synthesis front door (status + ask) must complete inside
the guard — ``levi synthesis prove-offline`` runs exactly that, and
``tests/test_synthesis_offline.py`` pins it.

``assert_no_network_imports`` statically scans this package's own sources
for network-library imports. The one legitimate ``import socket`` is this
module's own — it needs the name to disable it — and is allow-listed with
a comment saying why. Deeper organs keep their own offline contracts (e.g.
the L.W.P. press console never touches a network) and the suite's hermetic
conftest; this scan covers the new code this build controls.
"""

from __future__ import annotations

import re
import socket
from pathlib import Path
from typing import List, Optional

ORIGIN = "levi-synthesis/offline"

# import/from lines naming network libraries. offline.py's own
# `import socket` (needed to disable sockets) is allow-listed below.
_NETWORK_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(socket|urllib|requests|http\.client|http\.server|ssl|websockets)\b",
    re.MULTILINE,
)


class OfflineViolation(RuntimeError):
    """Raised when guarded code tries to touch the network."""


def _blocked(*args, **kwargs):
    raise OfflineViolation(
        "network blocked: synthesis runs offline-first — "
        "no sockets, no connections, no DNS"
    )


class OfflineGuard:
    """Context manager: creating a socket raises ``OfflineViolation``.

    Saves and restores ``socket.socket``, ``socket.create_connection`` and
    ``socket.getaddrinfo``. Restoration is unconditional — even when the
    guarded block raises.

    ``socket.socket`` is replaced with a *subclass* of the real socket whose
    constructor raises: stdlib import machinery that subclasses
    ``socket.socket`` (e.g. ``ssl``) keeps importing fine, while any actual
    socket creation is blocked. ``create_connection``/``getaddrinfo`` are
    plain functions, so a raising function suffices for them.
    """

    def __init__(self) -> None:
        self._saved = {}

    def __enter__(self) -> "OfflineGuard":
        real_socket = socket.socket

        class _BlockedSocket(real_socket):  # type: ignore[valid-type,misc]
            def __init__(self, *args, **kwargs):
                raise OfflineViolation(
                    "network blocked: synthesis runs offline-first — "
                    "no sockets, no connections, no DNS"
                )

        self._saved = {
            "socket": real_socket,
            "create_connection": socket.create_connection,
            "getaddrinfo": socket.getaddrinfo,
        }
        # This module imports socket for exactly one reason: to take it away.
        socket.socket = _BlockedSocket  # type: ignore[assignment]
        socket.create_connection = _blocked  # type: ignore[assignment]
        socket.getaddrinfo = _blocked  # type: ignore[assignment]
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        socket.socket = self._saved["socket"]
        socket.create_connection = self._saved["create_connection"]
        socket.getaddrinfo = self._saved["getaddrinfo"]
        self._saved = {}
        return False


def assert_no_network_imports(package_dir: Optional[str] = None) -> List[str]:
    """Scan this package's ``*.py`` for network imports.

    Returns the (empty) hit list; raises ``AssertionError`` naming every hit.
    """
    root = Path(package_dir) if package_dir else Path(__file__).resolve().parent
    hits: List[str] = []
    for path in sorted(root.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in _NETWORK_IMPORT_RE.finditer(text):
            # offline.py imports socket to disable it — the one allow-listed use.
            if path.name == "offline.py" and match.group(1) == "socket":
                continue
            hits.append(f"{path.name}: {match.group(0).strip()}")
    if hits:
        raise AssertionError(
            "network imports found in the synthesis package:\n" + "\n".join(hits)
        )
    return hits


__all__ = [
    "ORIGIN",
    "OfflineViolation",
    "OfflineGuard",
    "assert_no_network_imports",
]
