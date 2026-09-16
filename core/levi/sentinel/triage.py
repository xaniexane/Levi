"""Sentinel triage — defensive file triage scanner.

Read-only scan of a directory tree: every bounded file gets a SHA-256
"DNA" fingerprint plus MIME guess, and signature rules flag markers of
compromise — reverse-shell idioms, miner tokens, obfuscation markers.
Findings are *triage leads* for a human analyst, never verdicts.

Stdlib-only: ``hashlib``, ``os``, ``re``.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

__all__ = [
    "Finding",
    "TriageReport",
    "triage_scan",
    "SIGNATURE_RULES",
    "MAX_FILES",
    "MAX_FILE_BYTES",
]

#: Bounded traversal.
MAX_FILES = 500
#: Files larger than this are hashed but not content-scanned.
MAX_FILE_BYTES = 2_000_000

#: (rule_id, severity, compiled pattern, analyst note)
SIGNATURE_RULES = (
    (
        "reverse-shell",
        "high",
        re.compile(
            rb"nc\s+-[a-z]*e\s|/dev/tcp/\d|bash\s+-i\s+>&|socat\s+.*EXEC", re.IGNORECASE
        ),
        "reverse/bind-shell idiom — verify whether this is expected tooling",
    ),
    (
        "miner",
        "medium",
        re.compile(rb"xmrig|minerd|stratum\+tcp|cryptonight", re.IGNORECASE),
        "miner token — check whether mining is authorized on this host",
    ),
    (
        "obfuscation",
        "low",
        re.compile(
            rb"eval\s*\(\s*base64|exec\s*\(\s*base64|fromhex\s*\(|\\x[0-9a-f]{2}(\\x[0-9a-f]{2}){5,}",
            re.IGNORECASE,
        ),
        "possible obfuscation — inspect the surrounding code",
    ),
    (
        "credential-harvest",
        "medium",
        re.compile(rb"mimikatz|sekurlsa|lsass\s+dmp|procdump.*lsass", re.IGNORECASE),
        "credential-access tooling marker — confirm authorized use",
    ),
)


@dataclass
class Finding:
    path: str
    rule_id: str
    severity: str
    note: str
    sha256: str


@dataclass
class TriageReport:
    scanned: int
    hashed_only: int
    findings: List[Finding] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def by_severity(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts


def _sha256_file(path: Path) -> Optional[str]:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def triage_scan(root: str) -> TriageReport:
    """Read-only triage scan of ``root``. Never modifies, never quarantines."""
    root_p = Path(root)
    if not root_p.is_dir():
        raise ValueError(f"not a directory: {root}")
    report = TriageReport(scanned=0, hashed_only=0)
    count = 0
    for dirpath, _dirnames, filenames in os.walk(root_p):
        for name in sorted(filenames):
            if count >= MAX_FILES:
                break
            full = Path(dirpath) / name
            count += 1
            try:
                size = full.stat().st_size
            except OSError as exc:
                report.errors.append(f"{full}: {exc}")
                continue
            digest = _sha256_file(full)
            if digest is None:
                report.errors.append(f"{full}: unreadable")
                continue
            if size > MAX_FILE_BYTES:
                report.hashed_only += 1
                continue
            report.scanned += 1
            try:
                content = full.read_bytes()
            except OSError as exc:
                report.errors.append(f"{full}: {exc}")
                continue
            for rule_id, severity, pattern, note in SIGNATURE_RULES:
                if pattern.search(content):
                    report.findings.append(
                        Finding(
                            path=str(full),
                            rule_id=rule_id,
                            severity=severity,
                            note=note,
                            sha256=digest,
                        )
                    )
                    break  # one lead per file keeps triage readable
    return report
