"""Code-quality techniques applied to every council candidate.

All stdlib-only, all hermetic (no network). Techniques:

1. test-first      — the tests file must define test_* functions; a
                     candidate with no tests is flagged, not accepted.
2. static-gates    — syntax + ruff (when installed) + ast-based
                     cyclomatic-complexity cap + max function length.
                     A failing candidate never reaches review.
3. property-checks — stdlib randomized property tester: prop_*(rng)
                     functions, N seeded trials each; candidates must
                     survive. Skipped (not failed) when no properties
                     file is supplied.
4. mutation        — lightweight mutation testing: flip comparison
                     operators, boolean ops/negations, off-by-one on
                     ints; the test suite must kill the mutants.
                     Bounded and deterministic; kill rate is reported
                     (advisory — a low rate indicts the tests, not the
                     candidate, so it never blocks review on its own).
5. review-checklist — each review scores SECURITY / ERROR_HANDLING /
                     EDGE_CASES explicitly; parsed into the receipt.

Pipeline order: generate → static gates → tests → property checks →
mutation sample → review round → synthesize. Only static-gate and
test/property failures block review; everything is recorded in the
receipt with evidence.
"""

from __future__ import annotations

import ast
import copy
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from .sandbox import _scrubbed_env, council_root, run_candidate

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_SKIP = "skip"


@dataclass
class TechniqueResult:
    name: str
    status: str  # pass | fail | skip
    evidence: str = ""
    details: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "evidence": self.evidence,
            "details": self.details,
        }


# -- 1. test-first -------------------------------------------------------

_TEST_RE = re.compile(r"^test_")


def test_first_check(tests_code: str) -> TechniqueResult:
    """Require the tests file to actually define test_* functions."""
    try:
        tree = ast.parse(tests_code)
    except SyntaxError as exc:
        return TechniqueResult(
            "test-first", STATUS_FAIL, f"tests file has a syntax error: {exc}"
        )
    found = [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _TEST_RE.match(n.name)
    ]
    if not found:
        return TechniqueResult(
            "test-first",
            STATUS_FAIL,
            "no test_* functions found in tests file — "
            "a candidate with no tests is flagged, not silently accepted",
            {"found": []},
        )
    return TechniqueResult(
        "test-first",
        STATUS_PASS,
        f"{len(found)} test_* function(s): {', '.join(sorted(found)[:8])}",
        {"found": sorted(found)},
    )


# -- 2. static gates ------------------------------------------------------

_RUFF_SELECT = "E4,E7,E9,F"


class _ComplexityVisitor(ast.NodeVisitor):
    """Cyclomatic complexity; does not descend into nested defs."""

    def __init__(self) -> None:
        self.score = 1

    def visit_If(self, node):  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_For(self, node):  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node):  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_While(self, node):  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_Assert(self, node):  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_IfExp(self, node):  # noqa: N802
        self.score += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):  # noqa: N802
        self.score += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node):  # noqa: N802
        self.score += 1 + len(node.ifs)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):  # noqa: N802
        pass  # nested defs are scored as their own entries

    def visit_AsyncFunctionDef(self, node):  # noqa: N802
        pass

    def visit_Lambda(self, node):  # noqa: N802
        pass

    def visit_ClassDef(self, node):  # noqa: N802
        pass


def _function_entries(tree: ast.AST) -> list[tuple[str, ast.FunctionDef]]:
    return [
        (n.name, n)
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def static_gates(
    code: str, max_complexity: int = 10, max_func_lines: int = 50
) -> TechniqueResult:
    """Syntax + ruff + complexity + length gates. Fails loudly."""
    lines: list[str] = []
    failed = False

    try:
        tree = ast.parse(code)
        lines.append("syntax: PASS — parses OK")
    except SyntaxError as exc:
        return TechniqueResult("static-gates", STATUS_FAIL, f"syntax: FAIL — {exc}")

    ruff = shutil.which("ruff")
    if ruff:
        try:
            proc = subprocess.run(
                [
                    ruff,
                    "check",
                    "--select",
                    _RUFF_SELECT,
                    "--output-format",
                    "concise",
                    "--stdin-filename",
                    "candidate.py",
                    "-",
                ],
                input=code,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode == 0:
                lines.append("ruff: PASS — clean")
            else:
                failed = True
                out = (proc.stdout or proc.stderr or "").strip()[:800]
                lines.append(f"ruff: FAIL — {out}")
        except Exception as exc:
            lines.append(f"ruff: SKIP — could not run ({exc})")
    else:
        lines.append("ruff: SKIP — not installed (syntax check above still applies)")

    for name, fn in _function_entries(tree):
        visitor = _ComplexityVisitor()
        for stmt in fn.body:
            visitor.visit(stmt)
        if visitor.score > max_complexity:
            failed = True
            lines.append(
                f"complexity: FAIL — {name}() scores {visitor.score} "
                f"(cap {max_complexity})"
            )
        length = (fn.end_lineno or 0) - (fn.lineno or 0) + 1
        if length > max_func_lines:
            failed = True
            lines.append(
                f"length: FAIL — {name}() is {length} lines (cap {max_func_lines})"
            )
    if not any(line.startswith(("complexity: FAIL", "length: FAIL")) for line in lines):
        lines.append(
            f"complexity/length: PASS — all functions ≤{max_complexity} "
            f"complexity, ≤{max_func_lines} lines"
        )

    return TechniqueResult(
        "static-gates",
        STATUS_FAIL if failed else STATUS_PASS,
        "\n".join(lines),
    )


# -- 3. property checks ----------------------------------------------------

_PROP_RUNNER_TEMPLATE = '''\
"""Council property runner: prop_*(rng), seeded trials, JSON report."""
import json
import random
import sys
import traceback

sys.path.insert(0, ".")

TRIALS = __TRIALS__
BASE_SEED = 20260916

results = {"properties": {}, "error": ""}

try:
    import candidate
except Exception:
    results["error"] = "candidate import failed:\\n" + traceback.format_exc(limit=5)
    print(json.dumps(results))
    raise SystemExit(0)

try:
    import properties as p
except Exception:
    results["error"] = "properties import failed:\\n" + traceback.format_exc(limit=5)
    print(json.dumps(results))
    raise SystemExit(0)

names = [n for n in sorted(dir(p)) if n.startswith("prop_")]
if not names:
    results["error"] = "no prop_* callables found in properties module"
    print(json.dumps(results))
    raise SystemExit(0)

for name in names:
    fn = getattr(p, name)
    if not callable(fn):
        continue
    ok = 0
    failure = None
    for trial in range(TRIALS):
        rng = random.Random(BASE_SEED + trial)
        try:
            fn(rng)
            ok += 1
        except Exception:
            failure = {"trial": trial, "error": traceback.format_exc(limit=4)}
            break
    results["properties"][name] = {
        "trials_passed": ok,
        "failed": failure is not None,
        "failure": failure,
    }

print(json.dumps(results))
'''


def _prop_names(properties_code: str) -> list[str] | None:
    """prop_* function names in the properties source, or None if unparsable."""
    try:
        tree = ast.parse(properties_code)
    except SyntaxError:
        return None
    return sorted(
        n.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name.startswith("prop_")
    )


def run_properties(
    code: str,
    properties_code: str | None,
    trials: int = 30,
    timeout: float = 60.0,
    run_id: str | None = None,
    seat: str = "unknown",
) -> TechniqueResult:
    """Run randomized property checks against the candidate in the sandbox."""
    if not properties_code or not properties_code.strip():
        return TechniqueResult(
            "property-checks", STATUS_SKIP, "no properties file supplied"
        )
    names = _prop_names(properties_code)
    if names is None:
        return TechniqueResult(
            "property-checks", STATUS_FAIL, "properties file has a syntax error"
        )
    if not names:
        return TechniqueResult(
            "property-checks", STATUS_SKIP, "no prop_* functions in properties file"
        )

    scratch = council_root() / (run_id or "noprop") / "props" / seat
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "candidate.py").write_text(code, encoding="utf-8")
    (scratch / "properties.py").write_text(properties_code, encoding="utf-8")
    runner = scratch / "_proprunner.py"
    runner.write_text(
        _PROP_RUNNER_TEMPLATE.replace("__TRIALS__", str(max(1, trials))),
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [sys.executable, str(runner)],
            cwd=str(scratch),
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=_scrubbed_env(),
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return TechniqueResult(
            "property-checks", STATUS_FAIL, f"timed out after {timeout}s"
        )
    except OSError as exc:
        return TechniqueResult("property-checks", STATUS_FAIL, f"failed to run: {exc}")

    payload = None
    for line in reversed((proc.stdout or "").strip().splitlines()):
        if line.strip().startswith("{"):
            try:
                payload = json.loads(line.strip())
                break
            except Exception:
                continue
    if payload is None:
        return TechniqueResult(
            "property-checks", STATUS_FAIL, "no JSON output from property runner"
        )
    if payload.get("error"):
        return TechniqueResult("property-checks", STATUS_FAIL, payload["error"][:500])
    failed = {
        name: info
        for name, info in payload.get("properties", {}).items()
        if info.get("failed")
    }
    total_trials = sum(
        info.get("trials_passed", 0) for info in payload.get("properties", {}).values()
    )
    if failed:
        ev_lines = [
            f"{name}: FAILED on trial {info['failure']['trial']}: "
            f"{info['failure']['error'].splitlines()[-1][:160]}"
            for name, info in failed.items()
        ]
        return TechniqueResult(
            "property-checks",
            STATUS_FAIL,
            f"{len(failed)}/{len(names)} properties failed:\n" + "\n".join(ev_lines),
            {"failed": list(failed)},
        )
    return TechniqueResult(
        "property-checks",
        STATUS_PASS,
        f"{len(names)} properties × {trials} seeded trials passed "
        f"({total_trials} assertions)",
        {"properties": list(payload.get("properties", {}))},
    )


# -- 4. mutation testing (lightweight) -------------------------------------

_CMP_FLIP = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
}


def _replace_node(node: ast.AST, new: ast.AST) -> None:
    node.__class__ = new.__class__
    node.__dict__.clear()
    node.__dict__.update(new.__dict__)


def _collect_mutants(tree: ast.AST) -> list[tuple[str, int, int, str]]:
    """Return (description, lineno, col, kind) for each mutable site."""
    found: list[tuple[str, int, int, str]] = []
    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", 0) or 0
        col = getattr(node, "col_offset", 0) or 0
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = type(node.ops[0])
            if op in _CMP_FLIP:
                found.append(
                    (
                        f"compare {op.__name__}→{_CMP_FLIP[op].__name__}",
                        lineno,
                        col,
                        "cmp",
                    )
                )
        elif isinstance(node, ast.BoolOp):
            other = "Or" if isinstance(node.op, ast.And) else "And"
            found.append(
                (f"boolop {type(node.op).__name__}→{other}", lineno, col, "boolop")
            )
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            found.append(("remove `not`", lineno, col, "not"))
        elif isinstance(node, ast.Constant) and type(node.value) is bool:
            found.append(
                (f"constant {node.value}→{not node.value}", lineno, col, "const-bool")
            )
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            found.append(
                (f"constant {node.value}→{node.value + 1}", lineno, col, "const-int")
            )
    # Deterministic order.
    found.sort(key=lambda m: (m[1], m[2], m[0]))
    return found


def _apply_mutant(tree: ast.AST, kind: str, lineno: int, col: int) -> ast.AST | None:
    new_tree = copy.deepcopy(tree)
    for node in ast.walk(new_tree):
        if (
            type(node).__name__ not in ("Compare", "BoolOp", "UnaryOp", "Constant")
            or getattr(node, "lineno", None) != lineno
            or getattr(node, "col_offset", None) != col
        ):
            continue
        if kind == "cmp" and isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = type(node.ops[0])
            if op in _CMP_FLIP:
                node.ops[0] = _CMP_FLIP[op]()
                break
        elif kind == "boolop" and isinstance(node, ast.BoolOp):
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            break
        elif (
            kind == "not"
            and isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.Not)
        ):
            _replace_node(node, node.operand)
            break
        elif (
            kind == "const-bool"
            and isinstance(node, ast.Constant)
            and type(node.value) is bool
        ):
            node.value = not node.value
            break
        elif (
            kind == "const-int"
            and isinstance(node, ast.Constant)
            and type(node.value) is int
        ):
            node.value = node.value + 1
            break
    else:
        return None
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree)
    except Exception:
        return None


def mutation_sample(
    code: str,
    tests_code: str,
    baseline_passed: list[str],
    timeout: float = 30.0,
    max_mutants: int = 12,
    run_id: str | None = None,
    seat: str = "unknown",
) -> TechniqueResult:
    """Flip operators/constants; the suite must kill the mutants.

    A mutant is *killed* when it errors, times out, or fails any test
    that passed on the unmutated baseline. Kill rate is reported; a low
    rate is advisory (it indicts the tests, not the candidate).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return TechniqueResult(
            "mutation", STATUS_FAIL, f"cannot mutate: syntax error: {exc}"
        )
    sites = _collect_mutants(tree)
    if not sites:
        return TechniqueResult("mutation", STATUS_SKIP, "no mutable sites found")
    sites = sites[: max(1, max_mutants)]

    baseline_set = set(baseline_passed)
    killed = 0
    survivors: list[str] = []
    ran = 0
    for desc, lineno, col, kind in sites:
        mutant = _apply_mutant(tree, kind, lineno, col)
        if mutant is None or mutant == code:
            continue
        ran += 1
        res = run_candidate(
            mutant,
            tests_code,
            timeout=timeout,
            run_id=f"{run_id or 'nomut'}-mut",
            seat=f"{seat}-m{ran}",
        )
        dead = (
            not res.ok
            or res.timed_out
            or bool(res.error)
            or bool(set(f["name"] for f in res.failed) & baseline_set)
            or (not res.passed and baseline_set)
        )
        if dead:
            killed += 1
        else:
            survivors.append(f"L{lineno}: {desc}")

    if ran == 0:
        return TechniqueResult("mutation", STATUS_SKIP, "no mutants produced")
    rate = killed / ran
    weak = rate < 0.5
    ev = (
        f"kill rate {killed}/{ran} ({rate:.0%})"
        + (" — WEAK suite: over half the mutants survived" if weak else "")
        + (f"; survived: {'; '.join(survivors[:5])}" if survivors else "")
    )
    return TechniqueResult(
        "mutation",
        STATUS_PASS,
        ev,
        {
            "mutants": ran,
            "killed": killed,
            "kill_rate": round(rate, 3),
            "weak_tests": weak,
            "survivors": survivors,
        },
    )


# -- 5. review checklist ----------------------------------------------------

_CHECKLIST_RE = re.compile(
    r"^(SECURITY|ERROR_HANDLING|EDGE_CASES)\s*:\s*(PASS|FAIL|UNKNOWN)\b\s*-?\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)

_CHECKLIST_DIMS = ("SECURITY", "ERROR_HANDLING", "EDGE_CASES")


def parse_checklist(text: str) -> dict:
    """Parse the review checklist block into per-dimension verdicts."""
    out: dict = {}
    for m in _CHECKLIST_RE.finditer(text or ""):
        dim = m.group(1).upper()
        if dim not in out:
            out[dim] = {
                "verdict": m.group(2).upper(),
                "note": m.group(3).strip()[:200],
            }
    for dim in _CHECKLIST_DIMS:
        out.setdefault(dim, {"verdict": "UNKNOWN", "note": "not scored by reviewer"})
    return out
