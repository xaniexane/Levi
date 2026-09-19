"""small_tool_ethos — the anti-bloat law, enforced by measurement.

Studied from: desktop-casualties-20260916/report.md (2. Winamp: one
small tool doing one thing better than anything else — 4.2 MB
installer vs iTunes's 170 MB).

The load-bearing idea: smallness is a design decision you can
measure. Declare a budget (bytes on disk, file count, dependency
count); measure the tool; fail loudly when it outgrows its brief.
The law is only real if something checks it.

LEVI's take: ``measure(path)`` walks a local directory and reports
bytes, file count, and a dependency census (stdlib vs third-party
imports, counted from ``import`` statements). ``check_budget``
compares a ``Budget`` against a measurement and returns explicit
violations; ``simplicity_score`` grades 0-100. This is an original,
from-scratch implementation for LEVI.

Honest limits: dependency counting is lexical (it reads import
statements; dynamic imports are invisible). Byte counts are source
bytes, not installed or runtime footprint. The score is a heuristic,
not a verdict.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

ORIGIN = "levi-revival/small-tool-ethos"

# Modules that ship with the interpreter: not dependencies.
_STDLIB = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()


@dataclass(frozen=True)
class Budget:
    """The anti-bloat law for one tool."""

    max_bytes: int
    max_files: int
    max_third_party_deps: int
    name: str = ""


@dataclass(frozen=True)
class Measurement:
    """What a tool actually costs, measured locally."""

    path: str
    total_bytes: int
    file_count: int
    stdlib_imports: tuple
    third_party_imports: tuple

    @property
    def third_party_count(self) -> int:
        return len(self.third_party_imports)


@dataclass(frozen=True)
class Violation:
    """One way the tool broke its budget."""

    field: str  # "bytes" | "files" | "third_party_deps"
    budget: int
    actual: int

    def describe(self) -> str:
        return f"{self.field}: budget {self.budget}, actual {self.actual}"


def _top_level_imports(source: str) -> List[str]:
    """Lexically collect imported top-level module names."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module.split(".")[0])
    return names


def measure(path: str | Path) -> Measurement:
    """Measure a local tool directory (recursive, source bytes)."""
    root = Path(path)
    if not root.is_dir():
        raise ValueError(f"not a directory: {path}")
    total_bytes = 0
    file_count = 0
    stdlib: set = set()
    third_party: set = set()
    for file in sorted(root.rglob("*.py")):
        if "__pycache__" in file.parts:
            continue
        file_count += 1
        total_bytes += file.stat().st_size
        for name in _top_level_imports(
            file.read_text(encoding="utf-8", errors="replace")
        ):
            if name in _STDLIB or name == "__future__":
                stdlib.add(name)
            else:
                third_party.add(name)
    return Measurement(
        path=str(root),
        total_bytes=total_bytes,
        file_count=file_count,
        stdlib_imports=tuple(sorted(stdlib)),
        third_party_imports=tuple(sorted(third_party)),
    )


def check_budget(budget: Budget, measurement: Measurement) -> List[Violation]:
    """Return one violation per exceeded budget line (empty = clean)."""
    violations: List[Violation] = []
    if measurement.total_bytes > budget.max_bytes:
        violations.append(Violation("bytes", budget.max_bytes, measurement.total_bytes))
    if measurement.file_count > budget.max_files:
        violations.append(Violation("files", budget.max_files, measurement.file_count))
    if measurement.third_party_count > budget.max_third_party_deps:
        violations.append(
            Violation(
                "third_party_deps",
                budget.max_third_party_deps,
                measurement.third_party_count,
            )
        )
    return violations


def simplicity_score(budget: Budget, measurement: Measurement) -> int:
    """Heuristic 0-100: headroom left in each budget line, averaged."""
    ratios = [
        max(0.0, 1.0 - measurement.total_bytes / max(1, budget.max_bytes)),
        max(0.0, 1.0 - measurement.file_count / max(1, budget.max_files)),
        max(
            0.0,
            1.0 - measurement.third_party_count / max(1, budget.max_third_party_deps),
        ),
    ]
    return int(round(sum(ratios) / len(ratios) * 100))


def demo() -> Dict:
    """Measure this module's own directory as the sample tool."""
    here = Path(__file__).resolve().parent
    single = here / "demo_tool_sample"
    single.mkdir(exist_ok=True)
    (single / "tiny.py").write_text(
        "import os\nimport sys\n\n\ndef main():\n    print(os.name, sys.version)\n",
        encoding="utf-8",
    )
    try:
        measurement = measure(single)
        budget = Budget(
            max_bytes=4096, max_files=5, max_third_party_deps=0, name="tiny"
        )
        violations = check_budget(budget, measurement)
        return {
            "bytes": measurement.total_bytes,
            "files": measurement.file_count,
            "third_party": list(measurement.third_party_imports),
            "violations": [v.describe() for v in violations],
            "simplicity_score": simplicity_score(budget, measurement),
        }
    finally:
        (single / "tiny.py").unlink()
        single.rmdir()
