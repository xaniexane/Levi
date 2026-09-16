"""Unified foreground supervisor for every LEVI service.

AXIS 4 of MEGAZORD¹⁰ — one supervisor for all services.

The catalog is static data: every LEVI long-running service as one dict with
``name``, ``module``, ``summary``, ``start_hint`` and a zero-arg ``health``
callable returning ``(ok: bool, detail: str)``.  The health callables never
raise — any exception becomes ``(False, "<error>")`` — and never start a
server, a thread, or a background process; they only instantiate the service's
core object against the LEVI home and ask it whether it is coherent.

Foreground-only operation
--------------------------
LEVI never installs itself behind the user's back: no systemd units, no
launchd plists, no cron jobs, no OS daemons.  The user owns their machine.
A "pulse" is a single foreground pass of :meth:`Supervisor.supervise_once`
run by the user (or by a foreground process they started), e.g.::

    python -m levi.daemon pulse

Health checks resolve the LEVI home at call time from ``$LEVI_HOME``
(hermetic tests) falling back to ``~/.levi``.  Passing ``home=`` to
:class:`Supervisor` binds every health check to that directory instead.
"""

from __future__ import annotations

import datetime as _dt
import functools
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

# A health check takes no arguments and reports (ok, detail).
HealthCheck = Callable[[], Tuple[bool, str]]

__all__ = [
    "HealthCheck",
    "Supervisor",
    "levi_home",
    "list_services",
    "service_status",
    "all_status",
    "supervise_once",
]


def levi_home() -> Path:
    """LEVI state home: ``$LEVI_HOME`` when set (hermetic tests), else ``~/.levi``."""
    raw = os.environ.get("LEVI_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".levi"


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Health checks (module-level; each takes an optional home for binding)
# ---------------------------------------------------------------------------


def _check_control_daemon(home: Path | None = None) -> Tuple[bool, str]:
    from levi.daemon.control import ControlDaemon

    daemon = ControlDaemon(path=(home or levi_home()) / "control_daemon.json")
    return True, f"{len(daemon.directives)} directives, stances loaded"


def _check_automation_engine(home: Path | None = None) -> Tuple[bool, str]:
    from levi.daemon.automation import AutomationRegistry

    reg = AutomationRegistry(data_dir=(home or levi_home()) / "automations")
    return True, f"{len(reg.list())} automations registered"


def _check_daemon_kernel(home: Path | None = None) -> Tuple[bool, str]:
    from levi.daemon.kernel import DaemonKernel

    kernel = DaemonKernel(path=(home or levi_home()) / "daemon_kernel.json")
    state_keys = len(kernel.state.to_dict())
    return True, f"kernel state loaded ({state_keys} state fields)"


def _check_heartbeat(home: Path | None = None) -> Tuple[bool, str]:
    from levi.daemon.heartbeat import run_heartbeat

    result = run_heartbeat(home=(home or levi_home()), force=False)
    if result.silent:
        return True, f"heartbeat silent: {result.reason}"
    return True, f"heartbeat flags {len(result.attention)} attention item(s)"


def _check_perpetual(home: Path | None = None) -> Tuple[bool, str]:
    from levi.perpetual.supervise import service_overview

    view = service_overview(home=(home or levi_home()))
    return True, (
        f"{len(view['services'])} child adapters, "
        f"{view['crashes_total']} crash(es) recorded"
    )


def _check_galaxy_services(home: Path | None = None) -> Tuple[bool, str]:
    from levi.galaxy.service import GalaxyServices

    svc = GalaxyServices(home=(home or levi_home()))
    pkgs = svc.list_services()
    return True, f"{len(pkgs)} package(s) in the service directory"


def _check_oath_trust(home: Path | None = None) -> Tuple[bool, str]:
    import levi.oath as oath

    # Oath resolves its own home from $LEVI_OATH_HOME; bind it to the
    # supervisor's home for the check (restored afterwards) so the check
    # never touches the real ~/.levi when tests point elsewhere.
    env_key = "LEVI_OATH_HOME"
    sentinel = object()
    previous = os.environ.get(env_key, sentinel)
    try:
        if previous is sentinel:
            os.environ[env_key] = str((home or levi_home()) / "oath")
        audit = oath.AUDIT_FILE()
    finally:
        if previous is sentinel:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = previous
    return True, f"oath trust module live; audit ledger at {audit}"


def _check_agent_server(home: Path | None = None) -> Tuple[bool, str]:  # noqa: ARG001
    from levi.agent import server

    if not callable(getattr(server, "serve", None)):
        return False, "levi.agent.server.serve is not callable"
    handler = getattr(server, "_AgentHandler", None)
    handler_name = getattr(handler, "__name__", "?")
    return True, f"agent HTTP server module live (handler {handler_name})"


def _guarded(check: HealthCheck) -> HealthCheck:
    """Wrap a health check so it can never raise."""

    @functools.wraps(check)
    def wrapper() -> Tuple[bool, str]:
        try:
            ok, detail = check()
            return bool(ok), str(detail)
        except Exception as exc:  # noqa: BLE001 - health must never raise
            return False, f"{type(exc).__name__}: {exc}"

    return wrapper


def _bind(check: Callable[[Path | None], Tuple[bool, str]], home: Path) -> HealthCheck:
    return _guarded(functools.partial(check, home))


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


class Supervisor:
    """One foreground supervisor for every LEVI service.

    ``SERVICE_CATALOG`` is static data; ``health`` in each entry is a
    zero-arg callable returning ``(ok, detail)``.  Constructing with an
    explicit ``home`` rebinds every health check to that directory (used by
    hermetic tests); otherwise checks resolve ``$LEVI_HOME`` / ``~/.levi``
    at call time.
    """

    SERVICE_CATALOG: List[Dict[str, Any]] = [
        {
            "name": "control-daemon",
            "module": "levi.daemon.control",
            "summary": (
                "Steers personas, wit styles and alchemy stances; the "
                "no-pure-negative control plane. Composable via UnifiedDaemon."
            ),
            "start_hint": "levi daemon status  (foreground: python -m levi.daemon pulse)",
            "health": _guarded(functools.partial(_check_control_daemon)),
            "_check_fn": _check_control_daemon,
        },
        {
            "name": "automation-engine",
            "module": "levi.daemon.automation",
            "summary": (
                "Scheduled automations registry: triggers, actions, "
                "persistence, due-run evaluation."
            ),
            "start_hint": "levi automations  (foreground: python -m levi.daemon pulse)",
            "health": _guarded(functools.partial(_check_automation_engine)),
            "_check_fn": _check_automation_engine,
        },
        {
            "name": "daemon-kernel",
            "module": "levi.daemon.kernel",
            "summary": (
                "Event bus, tool registry and audit trail underneath every "
                "daemon turn; safety-level enforcement."
            ),
            "start_hint": "python -m levi.daemon pulse  (kernel is inspected, never forked)",
            "health": _guarded(functools.partial(_check_daemon_kernel)),
            "_check_fn": _check_daemon_kernel,
        },
        {
            "name": "heartbeat",
            "module": "levi.daemon.heartbeat",
            "summary": (
                "Periodic self-check: growth learnings, tracked items, recent "
                "errors. Idempotent and silent when nothing needs attention."
            ),
            "start_hint": "levi heartbeat  (foreground: python -m levi.daemon pulse)",
            "health": _guarded(functools.partial(_check_heartbeat)),
            "_check_fn": _check_heartbeat,
        },
        {
            "name": "perpetual",
            "module": "levi.perpetual.supervise",
            "summary": (
                "Perpetual supervision loops: heartbeat, growth and automation "
                "child threads, crash reports, alive markers, hunt waves."
            ),
            "start_hint": "levi perpetual services  (foreground only)",
            "health": _guarded(functools.partial(_check_perpetual)),
            "_check_fn": _check_perpetual,
        },
        {
            "name": "galaxy-services",
            "module": "levi.galaxy.service",
            "summary": (
                "Galaxy package service directory: installed packages, ports, "
                "verb resolution for third-party services."
            ),
            "start_hint": "levi galaxy list  (foreground: python -m levi.daemon pulse)",
            "health": _guarded(functools.partial(_check_galaxy_services)),
            "_check_fn": _check_galaxy_services,
        },
        {
            "name": "oath-trust",
            "module": "levi.oath",
            "summary": (
                "Oath trust daemon: contacts, commands, audit ledger, inbox; "
                "cryptographic trust between LEVI instances."
            ),
            "start_hint": "python -m levi.oath doctor  (foreground only)",
            "health": _guarded(functools.partial(_check_oath_trust)),
            "_check_fn": _check_oath_trust,
        },
        {
            "name": "agent-server",
            "module": "levi.agent.server",
            "summary": (
                "Agentic loop HTTP server (POST /v1/agent/chat, bearer auth). "
                "Health verifies the module and handler; it never binds a port."
            ),
            "start_hint": "levi agent serve  (foreground only; binds 127.0.0.1)",
            "health": _guarded(functools.partial(_check_agent_server)),
            "_check_fn": _check_agent_server,
        },
    ]

    def __init__(self, home: str | os.PathLike[str] | None = None) -> None:
        self.home = Path(home).expanduser() if home is not None else levi_home()
        # Rebind each static health check to this supervisor's home.
        self._entries: List[Dict[str, Any]] = []
        for entry in self.SERVICE_CATALOG:
            bound = dict(entry)
            bound["health"] = _bind(entry["_check_fn"], self.home)
            self._entries.append(bound)

    # -- stable contract ----------------------------------------------------

    def list_services(self) -> List[Dict[str, Any]]:
        """Catalog entries as data (name, module, summary, start_hint, health)."""
        return [{k: v for k, v in e.items() if k != "_check_fn"} for e in self._entries]

    def service_status(self, name: str) -> Dict[str, Any]:
        """Health status for one service; never raises on unknown names."""
        entry = next((e for e in self._entries if e["name"] == name), None)
        checked_at = _utc_now()
        if entry is None:
            known = ", ".join(e["name"] for e in self._entries)
            return {
                "name": name,
                "module": None,
                "summary": None,
                "status": "unknown",
                "ok": False,
                "detail": f"unknown service '{name}'; known: {known}",
                "checked_at": checked_at,
            }
        ok, detail = entry["health"]()
        return {
            "name": entry["name"],
            "module": entry["module"],
            "summary": entry["summary"],
            "status": "up" if ok else "down",
            "ok": ok,
            "detail": detail,
            "checked_at": checked_at,
        }

    def all_status(self) -> Dict[str, Dict[str, Any]]:
        """Health status for every service, keyed by service name."""
        return {e["name"]: self.service_status(e["name"]) for e in self._entries}

    def supervise_once(self) -> Dict[str, Any]:
        """Run every health check once — the foreground 'pulse'."""
        statuses = self.all_status()
        up = sum(1 for s in statuses.values() if s["ok"])
        return {
            "ran_at": _utc_now(),
            "home": str(self.home),
            "total": len(statuses),
            "up": up,
            "down": len(statuses) - up,
            "services": statuses,
        }


# ---------------------------------------------------------------------------
# Module-level convenience API (default supervisor, default home)
# ---------------------------------------------------------------------------


def list_services() -> List[Dict[str, Any]]:
    """Catalog of every LEVI service."""
    return Supervisor().list_services()


def service_status(name: str) -> Dict[str, Any]:
    """Health status for one service."""
    return Supervisor().service_status(name)


def all_status() -> Dict[str, Dict[str, Any]]:
    """Health status for every service."""
    return Supervisor().all_status()


def supervise_once() -> Dict[str, Any]:
    """Run every health check once — the foreground 'pulse'."""
    return Supervisor().supervise_once()
