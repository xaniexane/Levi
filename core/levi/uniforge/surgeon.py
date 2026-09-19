"""UniForge code-surgeon instruments.

The Code Surgeon division: forensics, cyber security, emergency error
response and code refinement. These instruments are a faithful Python
port of the Omega Triple Threat Elite Acode plugin's surgeon and
converter logic — Chauncey's phone-side field instrument (the plugin
files themselves are untouched; see docs/UNIFORGE.md). The Acode plugin
is the hand; this module is the deep instrument: diagnose -> fix ->
verify.

Ported rules (behavioral parity with the plugin's ``surgeonCleanup`` /
``addClosedHeader``; parity is asserted in tests/test_uniforge_surgeon.py):

1. strip trailing whitespace on every line (each changed line = 1 fix)
2. tabs -> 4 spaces (1 fix if any tab was present)
3. collapse 4+ consecutive newlines to 3 (1 fix)
4. ``<name> == None`` -> ``<name> is None`` (each occurrence = 1 fix)
5. ``<name> != None`` -> ``<name> is not None`` (each occurrence = 1 fix)
6. preserve the original's trailing-newline state

stdlib only.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Tuple

_EQ_NONE = re.compile(r"(\b\w+)\s*==\s*None\b")
_NE_NONE = re.compile(r"(\b\w+)\s*!=\s*None\b")
_HEADER_STRIP = re.compile(
    r"^(#.*(?:Copyright|SPDX|All Rights Reserved|CLOSED|Proprietary).*\n)+",
    re.IGNORECASE,
)

# NOTE: the en dash (–) below is copied verbatim from the plugin's header.
CLOSED_HEADER_TEMPLATE = (
    "# CLOSED SOURCE – All Rights Reserved\n"
    "# Copyright (c) {year} {author}\n"
    "# Confidential property.\n\n"
)


def quick_cleanup(text: str) -> Tuple[str, Dict[str, int]]:
    """Apply the plugin's quick-cleanup rules. Returns (new_text, fix_counts)."""
    fixes: Dict[str, int] = {
        "trailing_whitespace": 0,
        "tabs": 0,
        "blank_lines": 0,
        "eq_none": 0,
        "ne_none": 0,
    }
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = re.sub(r"\s+$", "", line)
        if stripped != line:
            fixes["trailing_whitespace"] += 1
        cleaned_lines.append(stripped)
    src = "\n".join(cleaned_lines)
    if "\t" in src:
        src = src.replace("\t", "    ")
        fixes["tabs"] += 1
    collapsed = re.sub(r"\n{4,}", "\n\n\n", src)
    if collapsed != src:
        fixes["blank_lines"] += 1
        src = collapsed
    src, n = _EQ_NONE.subn(r"\1 is None", src)
    fixes["eq_none"] += n
    src, n = _NE_NONE.subn(r"\1 is not None", src)
    fixes["ne_none"] += n
    # Preserve the original's trailing-newline state (verbatim port of the
    # plugin guard; with the rules above it is defensive — none of them can
    # remove a trailing newline — but parity means keeping it).
    if not src.endswith("\n") and text.endswith("\n"):
        src += "\n"
    return src, fixes


def stamp_header(text: str, author: str) -> str:
    """Stamp the plugin's closed-source header, replacing any existing one."""
    year = datetime.date.today().year
    header = CLOSED_HEADER_TEMPLATE.format(year=year, author=author or "Author")
    body = _HEADER_STRIP.sub("", text)
    body = re.sub(r"^\s+", "", body, count=1)
    return header + body


@dataclass
class Finding:
    kind: str  # "syntax" | "cleanup"
    line: int  # 1-based; 0 when not line-specific
    detail: str


def diagnose(path: str) -> List[Finding]:
    """Forensic pass: syntax wounds plus everything quick_cleanup would fix."""
    findings: List[Finding] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if path.endswith(".py"):
        try:
            compile(text, path, "exec")
        except SyntaxError as exc:
            findings.append(
                Finding(
                    kind="syntax",
                    line=exc.lineno or 0,
                    detail="SyntaxError: %s" % (exc.msg,),
                )
            )
    _cleaned, fixes = quick_cleanup(text)
    total = sum(fixes.values())
    if total:
        parts = ", ".join(
            "%s=%d" % (name, count)
            for name, count in sorted(fixes.items())
            if count
        )
        findings.append(
            Finding(
                kind="cleanup",
                line=0,
                detail="%d quick-cleanup fix(es) available: %s" % (total, parts),
            )
        )
    return findings


def surgeon_file(path: str, apply: bool = False) -> Dict[str, Any]:
    """Quick cleanup on one file. Dry-run unless apply=True."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    cleaned, fixes = quick_cleanup(text)
    total = sum(fixes.values())
    receipt: Dict[str, Any] = {
        "instrument": "uniforge.surgeon",
        "path": os.path.abspath(path),
        "decision": "dry-run",
        "fixes": fixes,
        "total_fixes": total,
    }
    if apply and total:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(cleaned)
        receipt["decision"] = "executed"
    elif apply:
        receipt["decision"] = "executed"
    return receipt


def operate(path: str, apply: bool = False) -> Dict[str, Any]:
    """Full surgery: diagnose -> fix -> verify. Dry-run unless apply=True.

    Verify re-runs diagnose after the fix; ``verified`` is True only when
    no findings remain.
    """
    before = [asdict(f) for f in diagnose(path)]
    receipt: Dict[str, Any] = {
        "instrument": "uniforge.operate",
        "path": os.path.abspath(path),
        "decision": "dry-run",
        "findings_before": before,
        "fixes_applied": {},
        "findings_after": [],
        "verified": False,
    }
    if not apply:
        return receipt
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    cleaned, fixes = quick_cleanup(text)
    receipt["fixes_applied"] = fixes
    if sum(fixes.values()):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(cleaned)
    after = [asdict(f) for f in diagnose(path)]
    receipt["findings_after"] = after
    receipt["verified"] = not after
    receipt["decision"] = "executed" if not after else "executed-with-findings"
    return receipt


def receipt_json(receipt: Dict[str, Any]) -> str:
    return json.dumps(receipt, indent=2, sort_keys=True)
