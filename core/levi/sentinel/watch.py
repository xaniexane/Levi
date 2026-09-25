"""Sentinel watch — read-only defensive detection sensors.

Purely read-only: failed-login detection from auth logs, suspicious
process patterns, and a listening-ports inventory. Detection never
mutates anything; containment lives in :mod:`levi.sentinel.contain`
and requires explicit human confirmation.

Stdlib-only: ``re``, ``subprocess``, ``os``.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

__all__ = [
    "ScanResult",
    "scan_failed_logins",
    "scan_processes",
    "listening_ports",
    "run_watch",
    "FAILED_LOGIN_PATTERNS",
    "SUSPICIOUS_PROCESS_PATTERNS",
    "FAILED_LOGIN_THRESHOLD",
    "find_auth_log",
]

#: Auth-log lines that indicate a failed authentication attempt.
FAILED_LOGIN_PATTERNS = (
    re.compile(r"Failed password", re.IGNORECASE),
    re.compile(r"Invalid user", re.IGNORECASE),
    re.compile(r"authentication failure", re.IGNORECASE),
)

#: Heuristic markers of compromise in a process listing. These are
#: *detection* patterns for the operator's own hosts — bind shells,
#: reverse-shell idioms, and common miner/loader tokens.
SUSPICIOUS_PROCESS_PATTERNS = (
    re.compile(r"\bnc(\.exe)?\s+(-l|-[a-z]*l)", re.IGNORECASE),
    re.compile(r"/dev/tcp/\d", re.IGNORECASE),
    re.compile(r"bash\s+-i\s+>&", re.IGNORECASE),
    re.compile(r"\bmeterpreter\b", re.IGNORECASE),
    re.compile(r"\bxmrig\b", re.IGNORECASE),
    re.compile(r"\bminerd\b", re.IGNORECASE),
    re.compile(r"\bstratum\+tcp\b", re.IGNORECASE),
)

#: Failed-login count that trips an alert (tune to your environment).
FAILED_LOGIN_THRESHOLD = 20

#: Max auth-log lines sampled per scan (bounded, never the whole file).
_MAX_LOG_SAMPLE = 2000

#: Max recent lines reported for an alert (forensics, not exfiltration —
#: this is the operator's own host data).
_MAX_RECENT_LINES = 5


@dataclass
class ScanResult:
    """Outcome of one sensor scan."""

    sensor: str
    ok: bool  # True when nothing alarming was found
    alerts: List[str] = field(default_factory=list)
    detail: Dict[str, object] = field(default_factory=dict)

    def merge_into(self, alerts: List[str]) -> None:
        alerts.extend(self.alerts)


def find_auth_log() -> Optional[str]:
    """Return the first readable auth log, or None."""
    for candidate in ("/var/log/auth.log", "/var/log/secure"):
        try:
            if os.path.isfile(candidate) and os.access(candidate, os.R_OK):
                return candidate
        except OSError:
            continue
    return None


def _tail_lines(path: str, limit: int) -> List[str]:
    """Read at most ``limit`` trailing lines of a text file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            # Bounded: walk from the end in chunks.
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            chunk = 8192
            data = ""
            while size > 0 and data.count("\n") <= limit:
                step = min(chunk, size)
                size -= step
                fh.seek(size)
                data = fh.read(step) + data
            return data.splitlines()[-limit:]
    except OSError:
        return []


def scan_failed_logins(log_path: Optional[str] = None) -> ScanResult:
    """Count failed authentication attempts in the auth log.

    Read-only. Returns an alert when the count exceeds
    ``FAILED_LOGIN_THRESHOLD``.
    """
    path = log_path or find_auth_log()
    if path is None:
        return ScanResult(
            sensor="failed_logins",
            ok=True,
            detail={"note": "no readable auth log on this host"},
        )
    lines = _tail_lines(path, _MAX_LOG_SAMPLE)
    fails = [ln for ln in lines if any(p.search(ln) for p in FAILED_LOGIN_PATTERNS)]
    count = len(fails)
    result = ScanResult(
        sensor="failed_logins",
        ok=count <= FAILED_LOGIN_THRESHOLD,
        detail={
            "log": path,
            "sampled_lines": len(lines),
            "failed_attempts": count,
            "threshold": FAILED_LOGIN_THRESHOLD,
        },
    )
    if count > FAILED_LOGIN_THRESHOLD:
        result.alerts.append(
            f"elevated failed logins in {path}: {count} in sampled window "
            f"(threshold {FAILED_LOGIN_THRESHOLD})"
        )
        result.detail["recent"] = fails[-_MAX_RECENT_LINES:]
    return result


def _ps_output() -> str:
    try:
        proc = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.stdout if proc.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def scan_processes(ps_text: Optional[str] = None) -> ScanResult:
    """Flag suspicious process markers on this host. Read-only.

    ``ps_text`` injects a synthetic listing for tests; otherwise the
    real ``ps aux`` output is used.
    """
    text = ps_text if ps_text is not None else _ps_output()
    hits: List[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if "grep" in lowered and "sentinel" not in lowered:
            # Skip our own inspection pipeline; not a verdict.
            pass
        for pattern in SUSPICIOUS_PROCESS_PATTERNS:
            if pattern.search(line):
                hits.append(line.strip()[:200])
                break
    result = ScanResult(
        sensor="suspicious_processes",
        ok=not hits,
        detail={"suspicious": len(hits)},
    )
    if hits:
        result.alerts.append(
            f"{len(hits)} suspicious process marker(s) detected — triage before acting"
        )
        result.detail["markers"] = hits[:10]
    return result


def listening_ports() -> ScanResult:
    """Inventory listening sockets via ``ss``. Read-only, informational.

    No alert semantics — the operator reviews the inventory manually.
    """
    lines: List[str] = []
    tool = None
    for candidate in (["ss", "-tuln"], ["netstat", "-tuln"]):
        try:
            proc = subprocess.run(candidate, capture_output=True, text=True, timeout=15)
            if proc.returncode == 0 and proc.stdout.strip():
                tool = candidate[0]
                lines = proc.stdout.strip().splitlines()[:25]
                break
        except (OSError, subprocess.SubprocessError):
            continue
    return ScanResult(
        sensor="listening_ports",
        ok=True,
        detail={"tool": tool or "unavailable", "inventory": lines},
    )


def run_watch(log_path: Optional[str] = None) -> Dict[str, object]:
    """Run all watch sensors. Read-only. Returns a report dict."""
    results = [
        scan_failed_logins(log_path),
        scan_processes(),
        listening_ports(),
    ]
    alerts: List[str] = []
    for result in results:
        result.merge_into(alerts)
    return {
        "sensors": [
            {
                "sensor": r.sensor,
                "ok": r.ok,
                "alerts": r.alerts,
                "detail": r.detail,
            }
            for r in results
        ],
        "alerts": alerts,
        "alert_count": len(alerts),
    }
