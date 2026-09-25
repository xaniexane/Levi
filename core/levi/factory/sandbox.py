"""
Factory Sandbox — constrained local checks (symbiosis with builder + factory pipeline).

Does not grant host-wide power. No network/package install.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import py_compile
import re
import subprocess
import sys


DEFAULT_ROOT = Path.home() / ".levi" / "factory_sandbox"

# Project ids and relative paths may never escape the sandbox root.
_SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


def _validate_project_id(project_id: str) -> str:
    if not isinstance(project_id, str) or not _SAFE_ID_RE.match(project_id):
        raise ValueError(
            "project_id must be 1-64 chars of [A-Za-z0-9_.-] (no path separators)"
        )
    return project_id


def _safe_join(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root``; raise ValueError on escape attempts."""
    if not isinstance(rel, str) or not rel:
        raise ValueError("relative path must be a non-empty string")
    path = (root / rel).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        raise ValueError("path escapes the sandbox root: %r" % (rel,)) from None
    return path


@dataclass
class ScaffoldResult:
    """Outcome of :meth:`Sandbox.scaffold_python_cli`."""

    ok: bool
    summary: str = ""
    artifacts: List[str] = field(default_factory=list)
    error: Optional[str] = None


class Sandbox:
    """Per-project sandbox directory used by SoftwareFactory pipeline."""

    def __init__(self, project_id: str, root: Optional[Path] = None):
        self.project_id = _validate_project_id(project_id)
        self.root = Path(root) if root else DEFAULT_ROOT / self.project_id
        self.root.mkdir(parents=True, exist_ok=True)

    def write_file(self, rel: str, content: str) -> Path:
        """Write ``content`` to a path inside the sandbox (escape-proof)."""
        if not isinstance(content, str):
            raise ValueError("content must be str, got %s" % type(content).__name__)
        path = _safe_join(self.root, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def scaffold_python_cli(self, name: str, idea: str) -> "ScaffoldResult":
        """Write a minimal stdlib-only CLI scaffold (main.py + README).

        Called by :meth:`levi.factory.pipeline.SoftwareFactory.advance`
        when leaving the architecture stage. Never touches the network;
        no shell beyond what :meth:`run_smoke` later executes inside this dir.
        """
        safe = _validate_project_id(name)
        idea_text = idea if isinstance(idea, str) else ""
        readme = self.write_file(
            "README.md",
            "# %s\n\n%s\n\nScaffolded by LEVI Software Factory (sandbox).\n"
            % (safe, idea_text[:500]),
        )
        main = self.write_file(
            "main.py",
            '"""%s — sandbox scaffold (stdlib only, no network)."""\n'
            "from __future__ import annotations\n\n"
            "import sys\n\n"
            "STATUS = %r\n\n"
            "def main(argv: list | None = None) -> int:\n"
            "    args = list(argv if argv is not None else sys.argv[1:])\n"
            '    if args and args[0] in ("status", "--status"):\n'
            "        print(STATUS)\n"
            "        return 0\n"
            "    print(STATUS)\n"
            '    print("usage: python main.py status")\n'
            "    return 0\n\n"
            'if __name__ == "__main__":\n'
            "    raise SystemExit(main())\n" % (safe, "%s scaffold OK" % safe),
        )
        return ScaffoldResult(
            ok=True,
            summary="scaffolded %s (main.py + README.md)" % safe,
            artifacts=[str(readme), str(main)],
        )

    def run_smoke(self, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run main.py if present; else syntax-check all .py under sandbox."""
        if args is None:
            args = []
        elif not isinstance(args, (list, tuple)) or any(
            not isinstance(a, str) for a in args
        ):
            raise ValueError("args must be a list/tuple of str (or None)")
        args = list(args)
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
    """Syntax-check (+ pytest if present) a builder project root."""
    root = Path(project_root)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        raise ValueError("timeout must be a positive integer number of seconds")
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
