"""LEVI's mini-kernel — small core, restartable everything else.

Studied from: systems-internals survey (QNX Neutrino microkernel,
resource-manager section).

The mechanism, functionally: a tiny kernel moves messages between
servers and clients. Servers are user-space services with a request
handler and private state; sending is synchronous — the caller blocks
until the server replies. When a high-priority client blocks on a
low-priority server, the server *inherits* the client's priority for
the duration of the request (priority inheritance, no inversion).
Servers are named through one transparent registry: the client calls
``send(name, request)`` the same way whether the server is "local" or
"remote-in-model". If a server's handler crashes, the kernel restarts
just that server — fresh state, same name — without restarting the
kernel or any other server.

Honesty: in-process model of microkernel IPC. Synchronous send is a
direct handler call; priority inheritance is tracked on the server's
effective priority; "remote" servers run in the same process but go
through the identical naming path. Crashes are Python exceptions;
restart is state re-initialization.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

ORIGIN = "levi-revival/minikern"


class KernelError(Exception):
    """Base failure for mini-kernel operations."""


class Server:
    """A restartable user-space service behind the kernel."""

    def __init__(
        self,
        name: str,
        handler: Callable[[Dict[str, Any], Any], Any],
        priority: int = 0,
        remote: bool = False,
    ):
        self.name = name
        self.handler = handler
        self.base_priority = priority
        self.effective_priority = priority
        self.remote = remote
        self.state: Dict[str, Any] = {}
        self.restarts = 0
        self.crashes = 0
        self.served = 0

    def reset(self) -> None:
        """Re-initialize after a crash: fresh state, identity kept."""
        self.state = {}
        self.effective_priority = self.base_priority
        self.restarts += 1


class Kernel:
    """The microkernel: naming, synchronous IPC, restart supervision."""

    def __init__(self) -> None:
        self._servers: Dict[str, Server] = {}
        self.log: List[str] = []

    # -- naming (transparent: local and remote look identical) --------
    def register(self, server: Server) -> None:
        if server.name in self._servers:
            raise KernelError(f"server {server.name!r} already registered")
        self._servers[server.name] = server
        self.log.append(f"registered {server.name}")

    def lookup(self, name: str) -> Server:
        try:
            return self._servers[name]
        except KeyError:
            raise KernelError(f"unknown server {name!r}") from None

    def names(self) -> List[str]:
        return sorted(self._servers)

    # -- synchronous message-passing IPC ------------------------------
    def send(self, name: str, request: Any, client_priority: int = 0) -> Any:
        """Blocking send: the caller waits for the server's reply."""
        server = self.lookup(name)
        # Priority inheritance: the server borrows the client's
        # priority while it works on this request.
        boosted = max(client_priority, server.base_priority)
        server.effective_priority = boosted
        try:
            reply = server.handler(server.state, request)
        except Exception as exc:
            server.crashes += 1
            self.log.append(f"{name} crashed: {exc!r}; restarting")
            server.reset()
            raise KernelError(f"server {name!r} crashed and was restarted") from exc
        finally:
            server.effective_priority = server.base_priority
        server.served += 1
        return reply

    def restart_server(self, name: str) -> None:
        """Restart a server on demand — the kernel keeps running."""
        server = self.lookup(name)
        server.reset()
        self.log.append(f"{name} restarted on demand")

    def stats(self, name: str) -> Dict[str, Any]:
        server = self.lookup(name)
        return {
            "name": server.name,
            "priority": server.base_priority,
            "remote": server.remote,
            "restarts": server.restarts,
            "crashes": server.crashes,
            "served": server.served,
        }
