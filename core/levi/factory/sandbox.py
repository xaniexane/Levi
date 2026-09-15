"""
Factory Sandbox — constrained local checks (symbiosis with builder + factory pipeline).

Does not grant host-wide power. No network/package install.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import py_compile
import subprocess
import sys


DEFAULT_ROOT = Path.home() / ".levi" / "factory_sandbox"


class Sandbox:
    """Per-project sandbox directory used by SoftwareFactory pipeline."""

    def __init__(self, project_id: str, root: Optional[Path] = None):
        self.project_id = project_id
        self.root = Path(root) if root else DEFAULT_ROOT / project_id
        self.root.mkdir(parents=True, exist_ok=True)

    def write_file(self, rel: str, content: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_smoke(self, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run main.py if present; else syntax-check all .py under sandbox."""
        args = args or []
        main = self.root / "main.py"
        py_files = list(self.root.rglob("*.py"))
        syn_ok = True
        errors = []
        for p in py_files[:40]:
            try:
                py_compile.compile(str(p), doraise=True)
            except Exception as e:
                syn_ok = False
                errors.append(f"{p}: {e}")
        if not syn_ok:
            return {
                "ok": False,
                "returncode": 1,
                "error": "; ".join(errors),
                "stdout": "",
            }
        if main.exists():
            try:
                r = subprocess.run(
                    [sys.executable, str(main)] + list(args),
                    cwd=str(self.root),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                return {
                    "ok": r.returncode == 0,
                    "returncode": r.returncode,
                    "stdout": r.stdout or "",
                    "stderr": r.stderr or "",
                    "error": None
                    if r.returncode == 0
                    else (r.stderr or "nonzero exit"),
                }
            except Exception as e:
                return {"ok": False, "returncode": 1, "error": str(e), "stdout": ""}
        return {
            "ok": True,
            "returncode": 0,
            "stdout": f"syntax ok ({len(py_files)} files); no main.py",
            "error": None,
        }


def syntax_check(paths: List[Path]) -> Dict[str, str]:
    results = {}
    for p in paths:
        p = Path(p)
        if not p.exists() or p.suffix != ".py":
            results[str(p)] = "skip"
            continue
        try:
            py_compile.compile(str(p), doraise=True)
            results[str(p)] = "ok"
        except Exception as e:
            results[str(p)] = f"fail: {e}"
    return results


def run_smoke(project_root: Path, timeout: int = 30) -> str:
    root = Path(project_root)
    test = root / "tests" / "test_smoke.py"
    lines = ["=== Sandbox smoke ===", f"root={root}"]
    py_files = (
        list((root / "src").rglob("*.py"))
        if (root / "src").exists()
        else list(root.rglob("*.py"))
    )
    syn = syntax_check(py_files[:40])
    lines.append("syntax:")
    for k, v in syn.items():
        lines.append(f"  {v:4} {k}")
    if any(str(v).startswith("fail") for v in syn.values()):
        lines.append("ABORT: syntax failures")
        return "\n".join(lines)
    if test.exists():
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", str(test), "-q", "--tb=no"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            lines.append(f"pytest exit={r.returncode}")
            lines.append((r.stdout or "")[-400:])
        except Exception as e:
            lines.append(f"pytest error: {e}")
    else:
        lines.append("No tests/test_smoke.py — syntax-only check done")
    lines.append("Sandbox does not install packages or open network.")
    return "\n".join(lines)
