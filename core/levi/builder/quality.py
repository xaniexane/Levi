"""Quality gates for generated code.

Every generated Python artifact passes through gates before it ships:

1. **Static gates** (always, unless ``quality="off"``): ``py_compile``,
   stdlib-``ast`` complexity caps (function length, branching), and an
   advisory ``ruff`` pass (skipped gracefully when ruff is absent).
2. **Council gate** (``quality="auto"`` or ``"council"``): the artifact
   is submitted to the code council through its CLI contract
   (``levi council build --json --write <tmp> --confirm``); when the
   council selects a winner, the winner's code replaces the draft.

If the council package is missing or errors, the gate degrades
gracefully to static-only and records the seam in the result notes —
never a silent pass, never a hard failure.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import py_compile
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

MAX_FUNCTION_LINES = 120
MAX_BRANCH_POINTS = 15  # rough cyclomatic cap


@dataclass
class GateResult:
    passed: bool
    method: str  # "council" | "static" | "off"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "method": self.method, "notes": list(self.notes)}


class _Complexity(ast.NodeVisitor):
    def __init__(self) -> None:
        self.worst = ("", 0, 0)  # name, max lines, max branch points

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        branches = sum(
            isinstance(
                n,
                (
                    ast.If,
                    ast.For,
                    ast.While,
                    ast.ExceptHandler,
                    ast.With,
                    ast.Assert,
                    ast.BoolOp,
                    ast.IfExp,
                    ast.comprehension,
                ),
            )
            for n in ast.walk(node)
        )
        lines = (node.end_lineno or node.lineno) - node.lineno + 1
        wname, wlines, wbranches = self.worst
        if lines > wlines:
            wname, wlines = node.name, lines
        if branches > wbranches:
            wname, wbranches = node.name, branches
        self.worst = (wname, wlines, wbranches)
        self.generic_visit(node)


def static_gate(relpath: str, code: str) -> GateResult:
    """py_compile + complexity caps + advisory ruff. Returns a GateResult."""
    notes: List[str] = []

    with tempfile.TemporaryDirectory(prefix="levi-build-gate-") as tmp:
        probe = Path(tmp) / "probe.py"
        probe.write_text(code, encoding="utf-8")
        try:
            py_compile.compile(str(probe), doraise=True)
        except py_compile.PyCompileError as exc:
            return GateResult(False, "static", [f"py_compile failed: {exc}"])

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return GateResult(False, "static", [f"ast parse failed: {exc}"])
    checker = _Complexity()
    checker.visit(tree)
    name, lines, branches = checker.worst
    if lines > MAX_FUNCTION_LINES:
        return GateResult(
            False,
            "static",
            [f"function {name!r} too long: {lines} lines (cap {MAX_FUNCTION_LINES})"],
        )
    if branches > MAX_BRANCH_POINTS:
        return GateResult(
            False,
            "static",
            [
                f"function {name!r} too complex: {branches} branch points "
                f"(cap {MAX_BRANCH_POINTS})"
            ],
        )
    notes.append(
        f"complexity ok (worst: {name or '<none>'} {lines} lines, {branches} branches)"
    )

    # Advisory ruff: never fails the build, skipped when unavailable.
    try:
        with tempfile.TemporaryDirectory(prefix="levi-build-ruff-") as tmp:
            probe = Path(tmp) / "probe.py"
            probe.write_text(code, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "ruff", "check", str(probe)],
                capture_output=True,
                text=True,
                timeout=30,
            )
        if proc.returncode == 0:
            notes.append("ruff clean")
        else:
            notes.append(
                "ruff advisory: "
                + (
                    proc.stdout.strip().splitlines()[:3]
                    and "; ".join(proc.stdout.strip().splitlines()[:3])
                    or "issues found"
                )
            )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        notes.append(f"ruff skipped ({exc.__class__.__name__})")

    return GateResult(True, "static", notes)


def _council_test_for(relpath: str) -> str:
    """Auto-generated council test: structural contract for a code artifact."""
    return f'''"""Auto-generated council test for {relpath} (LEVI Builder gate)."""
import candidate


def test_routes_table_present():
    routes = getattr(candidate, "ROUTES", None)
    assert isinstance(routes, list) and routes, "ROUTES must be a non-empty list"


def test_handlers_are_callable():
    for method, pattern, name in candidate.ROUTES:
        fn = getattr(candidate, name, None)
        assert callable(fn), f"handler {{name!r}} is not callable"


def test_module_has_docstring_or_comment():
    src = open(candidate.__file__, encoding="utf-8").read()
    assert len(src.strip()) > 50, "module looks empty"
'''


def council_gate(
    relpath: str, code: str, *, task_hint: str = ""
) -> Tuple[str, GateResult]:
    """Submit ``code`` to the council via its CLI contract.

    Returns ``(code_to_use, GateResult)``. Any failure — missing
    council package, no seats, no winner, exceptions — degrades to the
    submitted code with the seam recorded in ``notes``.
    """
    try:
        from levi.council.cli import cmd_council
    except ImportError as exc:
        return code, GateResult(
            True, "static", [f"council unavailable ({exc}); static gates only"]
        )

    task = (
        task_hint
        or f"Improve this Python module ({relpath}) while preserving its "
        f"behavior and public names. It must pass the provided tests. "
        f"Output only the improved module source."
    )
    tests_code = _council_test_for(relpath)

    with tempfile.TemporaryDirectory(prefix="levi-build-council-") as tmp:
        tests_path = Path(tmp) / "council_tests.py"
        tests_path.write_text(tests_code, encoding="utf-8")
        winner_path = Path(tmp) / "winner.py"
        args = argparse.Namespace(
            council_cmd="build",
            task=task,
            tests=str(tests_path),
            seats="",
            review_rounds=1,
            timeout=60.0,
            write=str(winner_path),
            confirm=True,
            json=True,
        )
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = cmd_council(args)
        except Exception as exc:  # council must never break a build
            return code, GateResult(
                True,
                "static",
                [
                    f"council error ({exc.__class__.__name__}: {exc}); "
                    f"kept draft, static gates only"
                ],
            )
        if rc != 0 or not winner_path.is_file():
            return code, GateResult(
                True,
                "static",
                [
                    f"council returned rc={rc} with no winner; "
                    f"kept draft, static gates only"
                ],
            )
        improved = winner_path.read_text(encoding="utf-8")
        receipt_note = f"council selected a winner (rc={rc})"
    # Re-verify the winner through the static gates before accepting it.
    static = static_gate(relpath, improved)
    if not static.passed:
        return code, GateResult(
            True,
            "static",
            [
                receipt_note + "; winner failed static re-check "
                f"({'; '.join(static.notes)}); kept draft"
            ],
        )
    notes = [receipt_note] + static.notes
    return improved, GateResult(True, "council", notes)


def gate_python_file(
    relpath: str, code: str, *, quality: str = "auto", task_hint: str = ""
) -> Tuple[str, GateResult]:
    """Run the full gate chain for one generated Python file.

    Returns ``(code_to_ship, GateResult)``. ``quality`` is one of
    ``"auto"`` (council when available, else static), ``"council"``,
    ``"static"``, ``"off"``.
    """
    if quality == "off":
        return code, GateResult(True, "off", ["quality gates disabled by request"])
    static = static_gate(relpath, code)
    if not static.passed:
        return code, static
    if quality in ("auto", "council"):
        improved, result = council_gate(relpath, code, task_hint=task_hint)
        if result.method == "council":
            return improved, result
        # Council degraded: merge its seam note into the static result.
        return code, GateResult(True, "static", static.notes + result.notes)
    return code, static
