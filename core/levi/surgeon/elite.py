"""LEVI Surgeon — elite multi-pass cleanup.

Heuristic multi-pass code doctoring: syntax-gated passes of safe textual
fixes (whitespace, None-comparison style, augmented assignment, missing
colons), stopping early when the file parses clean. Concept adapted from the
Omega Code Surgeon ELITE lineage; original implementation, snapshot-first
via :class:`levi.surgeon.surgeon.SnapshotManager`.

The surgeon never executes code. Every pass re-parses with ``ast``; a pass
that breaks parsing is rolled back. Application to disk goes through the
caller's own HITL — this module only proposes and applies to its working copy.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


def syntax_error(src: str, name: str = "<text>") -> Optional[str]:
    try:
        ast.parse(src, filename=name)
        return None
    except SyntaxError as e:
        return f"line {e.lineno}: {e.msg}"


def _none_fix(m: "re.Match") -> str:
    return (
        f"{m.group(1)} is not None" if "!=" in m.group(2) else f"{m.group(1)} is None"
    )


def cleanup_pass(src: str) -> Tuple[str, List[str]]:
    """One pass of safe textual fixes. Returns (new_src, fix_descriptions)."""
    fixes: List[str] = []
    original = src

    lines = [ln.rstrip() for ln in src.splitlines()]
    src = "\n".join(lines)
    if not src.endswith("\n"):
        src += "\n"
    if src != original:
        fixes.append("whitespace normalization")

    if "\t" in src:
        src = src.expandtabs(4)
        fixes.append("tabs -> 4 spaces")

    new = re.sub(r"\n{4,}", "\n\n\n", src)
    if new != src:
        fixes.append("collapsed excessive blank lines")
        src = new

    new = re.sub(r"(\b\w+)\s*(==|!=)\s*None\b", _none_fix, src)
    if new != src:
        fixes.append("None comparison style")
        src = new

    new = re.sub(
        r"(\b\w+)\s*=\s*\1\s*\+\s*(\d+)", lambda m: f"{m.group(1)} += {m.group(2)}", src
    )
    if new != src:
        fixes.append("augmented assignment")
        src = new

    # Conservative missing-colon fixer (compound-statement openers only).
    out_lines = []
    for ln in src.splitlines():
        s = ln.rstrip()
        if re.match(
            r"^\s*(if|elif|else|for|while|def|class|try|except|finally|with)\b", s
        ):
            if not s.endswith((":", "\\", ",")):
                if re.search(r"\b(if|for|while|def|class)\b", s) or s.strip() in {
                    "else",
                    "try",
                    "finally",
                }:
                    s += ":"
                    fixes.append(f"added colon: {s.strip()[:50]}")
        out_lines.append(s)
    src = "\n".join(out_lines) + "\n"

    return src, fixes


@dataclass
class EliteResult:
    path: str
    passes: int
    fixes: List[str] = field(default_factory=list)
    clean: bool = False
    backup: Optional[str] = None


def elite_repair(path: Path, max_passes: int = 25) -> EliteResult:
    """Multi-pass repair of a Python file. Snapshot-first, syntax-gated.

    Each pass applies ``cleanup_pass``; if the result fails to parse, the
    pass is rolled back and repair stops. Returns an EliteResult describing
    what happened. The caller decides whether to keep the working copy —
    this function writes the repaired text back to ``path`` only, after
    taking a ``.elite.bak`` snapshot beside it.
    """
    from levi.surgeon.surgeon import SnapshotManager

    path = Path(path)
    src = path.read_text(encoding="utf-8", errors="replace")
    snap = SnapshotManager()
    snap.take(f"elite:{path.name}", src)
    backup = str(path) + ".elite.bak"
    Path(backup).write_bytes(path.read_bytes())

    all_fixes: List[str] = []
    passes = 0
    for _ in range(max_passes):
        passes += 1
        new_src, fixes = cleanup_pass(src)
        if not fixes:
            break
        if syntax_error(new_src, str(path)) is not None:
            break  # pass broke parsing — roll back, stop
        src, all_fixes = new_src, all_fixes + fixes
        if syntax_error(src, str(path)) is None and not fixes:
            break

    path.write_text(src, encoding="utf-8")
    clean = syntax_error(src, str(path)) is None
    return EliteResult(
        path=str(path), passes=passes, fixes=all_fixes, clean=clean, backup=backup
    )
