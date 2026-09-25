"""Configuration for the mind runner. Local JSON store, stdlib only.

Config lives at ``<mind-home>/mind.json`` where mind-home defaults to
``~/.levi/mind/`` and can be overridden with the ``LEVI_MIND_HOME``
environment variable (used by tests to stay hermetic).

The schema is deliberately small and explicit. Anything the guard does not
understand refuses to classify — see :mod:`levi.mind.guard`.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

CONFIG_FILE = "mind.json"
PID_FILE = "mind.pid"
STATE_FILE = "mind.state.json"
LOG_FILE = "mind.log"

#: Canonical defaults. ``server.enabled`` stays False in milestone 1.1 —
#: the local server face arrives in milestone 1.3.
DEFAULT_CONFIG: dict = {
    "version": 1,
    "inference": {
        "mode": "local",  # "local" is the only permitted value
        "engine": "levi-brain",
        "explicit_only": True,
    },
    "network": {
        "remote_inference": False,
        "api_url": "",
        "telemetry": False,
    },
    "server": {
        "enabled": False,
        "host": "127.0.0.1",
        "port": 11434,
    },
    "weights": {
        "bundle": "",
        "explicit_load": True,
    },
}


def mind_home() -> Path:
    """Return the mind home directory, creating it on demand."""
    override = os.environ.get("LEVI_MIND_HOME")
    home = Path(override).expanduser() if override else Path.home() / ".levi" / "mind"
    home.mkdir(parents=True, exist_ok=True)
    return home


def config_path(home: Path | None = None) -> Path:
    return (home or mind_home()) / CONFIG_FILE


def _deep_merge(base: dict, over: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load(home: Path | None = None) -> dict:
    """Load the config, deep-merged over defaults.

    Missing file → defaults. Corrupt file → ValueError, so the caller can
    treat it as *uncertain* (fail closed) rather than guessing.
    """
    path = config_path(home)
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"cannot read mind config at {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"mind config at {path} is not a JSON object")
    return _deep_merge(DEFAULT_CONFIG, raw)


def save(config: dict, home: Path | None = None) -> Path:
    """Write the config atomically (tmp file + rename)."""
    path = config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)
    return path


def ensure(home: Path | None = None) -> dict:
    """Make sure a config exists; return the effective config."""
    home = home or mind_home()
    path = config_path(home)
    if not path.exists():
        save(copy.deepcopy(DEFAULT_CONFIG), home)
    return load(home)
