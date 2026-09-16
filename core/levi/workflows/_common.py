"""Shared helpers for flagship cross-module workflows.

Home resolution (binding): every workflow takes an explicit ``home`` path.
When the caller passes ``None`` the workflow falls back to the
``LEVI_HOME`` environment variable, and only then to ``~/.levi``.
Explicit always wins; implicit is a last resort.

Bloodstream bus events are emitted defensively: if ``levi.bloodstream.bus``
is not importable (it lands from another Megazord axis worker in parallel),
events are simply skipped — workflows never fail because the bus is absent.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


def resolve_home(home: Optional[os.PathLike | str] = None) -> Path:
    """Resolve the LEVI home dir: explicit param > LEVI_HOME env > ~/.levi."""
    if home is not None:
        return Path(home).expanduser()
    env = os.environ.get("LEVI_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".levi"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Bloodstream bus (defensive — the bus worker lands in parallel)
# ---------------------------------------------------------------------------

def _bus():
    """Return the bus module, or None when it is not importable yet."""
    try:
        from levi.bloodstream import bus as _bus_mod
    except Exception:
        return None
    return _bus_mod


def emit(event: str, payload: Optional[Dict[str, Any]] = None) -> bool:
    """Emit a bus event if the bloodstream bus exists. Never raises."""
    mod = _bus()
    if mod is None:
        return False
    for attr in ("emit", "publish", "record"):
        fn = getattr(mod, attr, None)
        if callable(fn):
            try:
                fn(event, dict(payload or {}))
            except Exception:
                return False
            return True
    return False


# ---------------------------------------------------------------------------
# Step logging (steps logged as data, never as side chatter)
# ---------------------------------------------------------------------------

def new_step(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "ok": True,
        "started_at": utc_now(),
        "finished_at": None,
        "detail": {},
    }


def finish_step(step: Dict[str, Any], ok: bool, detail: Optional[Dict] = None,
                reason: Optional[str] = None) -> Dict[str, Any]:
    step["ok"] = ok
    step["finished_at"] = utc_now()
    if detail:
        step["detail"] = detail
    if reason is not None:
        step["reason"] = reason
    return step


def workflow_result(name: str, steps: List[Dict[str, Any]],
                    artifacts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ok = all(s.get("ok") for s in steps)
    return {
        "workflow": name,
        "ok": ok,
        "started_at": steps[0]["started_at"] if steps else utc_now(),
        "finished_at": utc_now(),
        "steps": steps,
        "artifacts": artifacts or {},
    }


@contextmanager
def workflow_env(home: Path, growth: bool = True) -> Iterator[Path]:
    """Point growth/journal/session paths at ``home`` for a bounded run.

    The growth journal honors ``LEVI_GROWTH_DIR`` natively; the session
    harvester honors ``LEVI_AGENT_SESSIONS_DIR``; affect signals honor
    ``LEVI_HOME``. All three are set here and restored afterwards so a
    workflow run never touches the user's real ``~/.levi``.
    """
    saved = {
        "LEVI_HOME": os.environ.get("LEVI_HOME"),
        "LEVI_GROWTH_DIR": os.environ.get("LEVI_GROWTH_DIR"),
        "LEVI_AGENT_SESSIONS_DIR": os.environ.get("LEVI_AGENT_SESSIONS_DIR"),
    }
    os.environ["LEVI_HOME"] = str(home)
    if growth:
        os.environ["LEVI_GROWTH_DIR"] = str(home / "growth")
        os.environ["LEVI_AGENT_SESSIONS_DIR"] = str(home / "agent" / "sessions")
    try:
        yield home
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
