"""simplicity — the complexity-budget auditor.

Studied from: retired-software-revival-research-20260916-0004/report.md (Section 22)
and revival-50-more-20260916-0009/report-part1.md (Section 6), MERGED.

The load-bearing idea (both sources agree): whole-system
comprehensibility is a *discipline*, not an accident. Small modules,
few moving parts, a surface one team can hold in its head — enforced
by budgets, not wishes.

LEVI's take: ``audit_source`` measures one Python module — lines of
code, function count, max nesting depth, import count — and checks it
against a ``Budget``. ``audit_paths`` runs it over real files, so LEVI
can turn the lens on itself (``levi.revival`` modules included). The
"one-team API surface" check counts public names: if the surface is
too wide for one team to hold, the module fails. Runnable, honest,
stdlib-only (``ast`` does the measuring).

This is an original, from-scratch reimplementation for LEVI.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Union

ORIGIN = "levi-revival/simplicity"


@dataclass
class Budget:
    """The discipline, in numbers. Defaults are LEVI's house rules."""

    max_lines: int = 400
    max_functions: int = 25
    max_nesting: int = 4
    max_imports: int = 15
    max_public_names: int = 30  # the one-team API surface


@dataclass
class ModuleReport:
    """What the auditor measured for one module."""

    name: str
    lines: int
    functions: int
    max_nesting: int
    imports: int
    public_names: int
    failures: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures

    def check(self, budget: Budget) -> "ModuleReport":
        fails: List[str] = []
        if self.lines > budget.max_lines:
            fails.append(f"lines {self.lines} > {budget.max_lines}")
        if self.functions > budget.max_functions:
            fails.append(f"functions {self.functions} > {budget.max_functions}")
        if self.max_nesting > budget.max_nesting:
            fails.append(f"max_nesting {self.max_nesting} > {budget.max_nesting}")
        if self.imports > budget.max_imports:
            fails.append(f"imports {self.imports} > {budget.max_imports}")
        if self.public_names > budget.max_public_names:
            fails.append(
                f"public_names {self.public_names} > {budget.max_public_names} "
                "(surface wider than one team can hold)"
            )
        self.failures = fails
        return self


class _NestingVisitor(ast.NodeVisitor):
    """Deepest nesting of control-flow / def / class blocks."""

    def __init__(self) -> None:
        self.depth = 0
        self.max_depth = 0

    def _nested(self, node: ast.AST) -> None:
        self.depth += 1
        self.max_depth = max(self.max_depth, self.depth)
        self.generic_visit(node)
        self.depth -= 1

    # every block-introducing statement nests one level
    visit_FunctionDef = _nested
    visit_AsyncFunctionDef = _nested
    visit_ClassDef = _nested
    visit_For = _nested
    visit_AsyncFor = _nested
    visit_While = _nested
    visit_If = _nested
    visit_With = _nested
    visit_AsyncWith = _nested
    visit_Try = _nested
    visit_TryStar = _nested


def audit_source(name: str, source: str, budget: Budget | None = None) -> ModuleReport:
    """Measure one module's source text and check it against the budget."""
    budget = budget or Budget()
    tree = ast.parse(source, filename=name)
    lines = len([line for line in source.splitlines() if line.strip()])

    functions = sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in ast.walk(tree)
    )
    visitor = _NestingVisitor()
    visitor.visit(tree)
    imports = sum(
        isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)
    )
    public_names = sum(
        1
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
        or isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and not t.id.startswith("_") and t.id.isupper()
            for t in node.targets
        )
    )

    return ModuleReport(
        name=name,
        lines=lines,
        functions=functions,
        max_nesting=visitor.max_depth,
        imports=imports,
        public_names=public_names,
    ).check(budget)


def audit_paths(
    paths: List[Union[str, Path]], budget: Budget | None = None
) -> Dict[str, ModuleReport]:
    """Audit real files — point this at LEVI's own modules to keep honest."""
    budget = budget or Budget()
    reports: Dict[str, ModuleReport] = {}
    for path in paths:
        path = Path(path)
        source = path.read_text(encoding="utf-8")
        reports[str(path)] = audit_source(path.name, source, budget)
    return reports


def summarize(reports: Dict[str, ModuleReport]) -> Dict[str, int]:
    """One honest tally: how many modules passed, how many broke budget."""
    passed = sum(1 for r in reports.values() if r.passed)
    return {"modules": len(reports), "passed": passed, "failed": len(reports) - passed}
