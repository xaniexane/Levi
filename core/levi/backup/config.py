"""Backup configuration: paths, config/state files, rclone discovery.

Never stores secrets. The crypt passphrase lives only in rclone's own
obscured config (entered interactively by the user during setup); this
module only records *which* rclone remote to use.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

CONFIG_NAME = "backup.json"
STATE_NAME = "backup_state.json"
DEFAULT_KEEP_LOCAL = 14


def levi_home() -> Path:
    """LEVI state dir. LEVI_HOME env override exists for tests/isolation."""
    override = os.environ.get("LEVI_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".levi"


def backup_root() -> Path:
    return levi_home() / "backups"


def staging_root() -> Path:
    return levi_home() / "restore-staging"


def config_path() -> Path:
    return levi_home() / CONFIG_NAME


def state_path() -> Path:
    return levi_home() / STATE_NAME


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(cfg: dict) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def load_state() -> dict:
    p = state_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(state: dict) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def rclone_path() -> str | None:
    """Locate the rclone binary: PATH first, then ~/bin (our install spot)."""
    found = shutil.which("rclone")
    if found:
        return found
    cand = Path.home() / "bin" / "rclone"
    if cand.exists() and os.access(cand, os.X_OK):
        return str(cand)
    return None


def rclone_available() -> bool:
    return rclone_path() is not None
