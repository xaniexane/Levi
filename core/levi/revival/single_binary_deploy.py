"""single_binary_deploy — one binary, one service unit, atomic rollbacks.

Studied from: hybrid-cost-cutting-combos-20260916-0006 report.md (section 4,
old-school techniques: static binaries run directly under the init system
instead of containers/orchestration — deletes the daemon, registry bills,
and orchestration complexity).

Functional pattern studied: the deployable unit is a single static binary;
the service manager supervises it; releases are atomic symlink swaps
between versioned slots with instant rollback to the previous slot.

What this module is: a real local mechanism for the *release* half —
``ReleaseManager`` keeps versioned binary slots under a releases directory,
``promote()`` atomically swaps the ``current`` symlink, ``rollback()``
swaps back to the previous slot, and history is append-only. ``unit_file()``
renders an init-system service unit (systemd dialect) for the binary with
restart policy, resource limits, and a health-check stanza. Writing the unit
to the system location and reloading the init system stays the operator's
step — this module never touches /etc or runs systemctl.

Honest limits: the health check is configuration, not an executor — no HTTP
probing happens here. Atomicity of the swap relies on the OS symlink
rename, which is atomic on POSIX.

This is an original, from-scratch implementation for LEVI. Not artificial.
Synthetic.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

ORIGIN = "levi-revival/single-binary-deploy"


@dataclass
class ServiceSpec:
    """Everything the init system needs to supervise one binary."""

    name: str
    binary_name: str = "app"  # filename inside the release slot
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    user: str = "app"
    working_dir: str = "/srv/app"
    restart: str = "always"  # no | on-failure | always
    restart_sec: int = 5
    memory_max: str = "512M"  # systemd MemoryMax= value
    cpu_quota: str = "100%"  # systemd CPUQuota= value
    health_path: str = "/healthz"
    health_port: int = 8080
    health_interval_s: int = 30

    def validate(self) -> None:
        if self.restart not in ("no", "on-failure", "always"):
            raise ValueError(f"bad restart policy: {self.restart}")
        if not self.name or any(c in self.name for c in " /\\"):
            raise ValueError(f"bad service name: {self.name!r}")


def unit_file(spec: ServiceSpec, releases_dir: Path) -> str:
    """Render the service unit. Pure text; the operator installs it."""
    spec.validate()
    exe = releases_dir / "current" / spec.binary_name
    env_lines = "".join(f'Environment="{k}={v}"\n' for k, v in spec.env.items())
    args = " ".join(spec.args)
    return (
        f"[Unit]\n"
        f"Description={spec.name} (single-binary release)\n"
        f"After=network.target\n"
        f"\n"
        f"[Service]\n"
        f"Type=simple\n"
        f"User={spec.user}\n"
        f"WorkingDirectory={spec.working_dir}\n"
        f"ExecStart={exe} {args}\n".rstrip()
        + "\n"
        f"{env_lines}"
        f"Restart={spec.restart}\n"
        f"RestartSec={spec.restart_sec}\n"
        f"MemoryMax={spec.memory_max}\n"
        f"CPUQuota={spec.cpu_quota}\n"
        f"# health: GET http://127.0.0.1:{spec.health_port}{spec.health_path} "
        f"every {spec.health_interval_s}s (operator's prober)\n"
        f"\n"
        f"[Install]\n"
        f"WantedBy=multi-user.target\n"
    )


@dataclass
class ReleaseRecord:
    version: str
    slot: str
    installed_at: float
    size_bytes: int


class ReleaseManager:
    """Versioned release slots with atomic promote/rollback.

    Layout under ``root``:
        releases/<version>/app      the binary (any executable file)
        current -> releases/<version>   atomic symlink
        history.jsonl               append-only record of promotes/rollbacks
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.releases = self.root / "releases"
        self.current_link = self.root / "current"
        self.history_path = self.root / "history.jsonl"
        self.releases.mkdir(parents=True, exist_ok=True)

    # -- install ---------------------------------------------------------------
    def install(
        self, version: str, binary_src: Path, binary_name: str = "app"
    ) -> ReleaseRecord:
        """Stage a new release slot from a binary file. Not yet live."""
        if not version or "/" in version or version in (".", ".."):
            raise ValueError(f"bad version: {version!r}")
        slot = self.releases / version
        if slot.exists():
            raise ValueError(f"version already installed: {version}")
        slot.mkdir(parents=True)
        dest = slot / binary_name
        shutil.copy2(binary_src, dest)
        os.chmod(dest, 0o755)
        return ReleaseRecord(
            version=version,
            slot=str(slot),
            installed_at=time.time(),
            size_bytes=dest.stat().st_size,
        )

    def installed(self) -> List[str]:
        return sorted(p.name for p in self.releases.iterdir() if p.is_dir())

    # -- promote / rollback ------------------------------------------------------
    def current_version(self) -> Optional[str]:
        if not self.current_link.is_symlink():
            return None
        return os.readlink(self.current_link).split("/")[-1]

    def promote(self, version: str) -> str:
        """Atomically point ``current`` at a staged version. Returns the
        previous version (or None)."""
        target = self.releases / version
        if not target.is_dir():
            raise ValueError(f"version not installed: {version}")
        previous = self.current_version()
        tmp = self.root / f".current.tmp.{os.getpid()}"
        try:
            if tmp.is_symlink() or tmp.exists():
                tmp.unlink()
            os.symlink(target, tmp)
            os.replace(tmp, self.current_link)  # atomic on POSIX
        finally:
            if tmp.is_symlink():
                tmp.unlink()
        self._record("promote", version, previous)
        return previous

    def rollback(self) -> str:
        """Swap back to the most recent previous version. Raises when there
        is no previous version on record."""
        previous = self._last_previous()
        if previous is None:
            raise RuntimeError("no previous version to roll back to")
        self.promote(previous)
        return previous

    def _last_previous(self) -> Optional[str]:
        current = self.current_version()
        for line in reversed(self._history_lines()):
            rec = json.loads(line)
            if rec["action"] == "promote" and rec["version"] != current:
                if (self.releases / rec["version"]).is_dir():
                    return rec["version"]
        return None

    # -- history -----------------------------------------------------------------
    def _record(self, action: str, version: str, previous: Optional[str]) -> None:
        rec = {
            "ts": time.time(),
            "action": action,
            "version": version,
            "previous": previous,
        }
        with open(self.history_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    def _history_lines(self) -> List[str]:
        if not self.history_path.exists():
            return []
        return self.history_path.read_text(encoding="utf-8").splitlines()

    def history(self) -> List[dict]:
        return [json.loads(line) for line in self._history_lines() if line.strip()]

    def prune(self, keep: int = 5) -> List[str]:
        """Remove oldest installed versions, keeping ``keep`` plus whatever
        is currently live. Returns removed version names."""
        live = self.current_version()
        keep_set = set(sorted(self.installed())[-keep:])
        if live:
            keep_set.add(live)
        removed = []
        for version in self.installed():
            if version not in keep_set:
                shutil.rmtree(self.releases / version)
                removed.append(version)
        return sorted(removed)
