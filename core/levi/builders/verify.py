"""Bounded verify/retry loop (the verifier twin) — the honest-retry law.

Five gates, in order: compile, contracts, safety, packaging, smoke.
Generated code must clear all five before it is presented. Retries inside
the bound are free by construction: there is no meter in this package, so
there is nothing to charge a retry through. Builder-caused fixes cost the
owner nothing — as architecture, not policy.

The ternary (the giants sell binary pass/fail; we build the third states):

- VERIFIED: passed clean on the first attempt.
- SELF_HEALED: the builder broke it and fixed it inside the bound, free.
  Presented with the repair record — honesty, not a quiet rewrite.
- OWNER_DECISION_NEEDED: the bound is exhausted. The loop stops, reports
  the diagnostics bundle, and never claims the build is done. The owner
  decides; the builder does not fake it.

No network calls in any path here. Subprocess use is local-only
(`sys.executable` on generated files) with a hard timeout.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from levi.builders.actions import apply_actions, plan_actions
from levi.builders.packs import get_pack
from levi.builders.planner import BuildPlan
from levi.builders._text import _plural
from levi.builders.scaffold import ScaffoldEngine

# Total attempts = 1 initial + MAX_BUILDER_RETRIES repair passes.
MAX_BUILDER_RETRIES = 3
# Hard cap per check so a broken generation can never hang the loop.
CHECK_TIMEOUT_SECONDS = 60

# Never allowed in generated code, whatever the domain pack says.
_GLOBAL_FORBIDDEN = ("eval(", "exec(")


class BuildOutcome(Enum):
    VERIFIED = "verified"
    SELF_HEALED = "self_healed"
    OWNER_DECISION_NEEDED = "owner_decision_needed"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class VerifyReport:
    outcome: BuildOutcome
    attempts: int
    repairs: List[str] = field(default_factory=list)
    checks: List[CheckResult] = field(default_factory=list)
    diagnostics: str = ""
    target_dir: str = ""


def _check_compile(files: Dict[str, str]) -> CheckResult:
    for path, content in sorted(files.items()):
        if not path.endswith(".py"):
            continue
        try:
            compile(content, path, "exec")
        except SyntaxError as exc:
            return CheckResult(
                "compile", False, "%s: %s (line %s)" % (path, exc.msg, exc.lineno)
            )
    return CheckResult("compile", True, "all python files compile")


def _local_module_paths(files: Dict[str, str]) -> Dict[str, str]:
    """Map dotted module names to generated paths."""
    mapping: Dict[str, str] = {}
    for path in files:
        if not path.endswith(".py"):
            continue
        dotted = path[:-3].replace("/", ".")
        mapping[dotted] = path
        if dotted.endswith(".__init__"):
            mapping[dotted[: -len(".__init__")]] = path
    return mapping


_STDLIB_TOP_LEVELS = frozenset(
    "os sys json re argparse threading time socket subprocess tempfile urllib "
    "http dataclasses typing hmac pathlib decimal string hashlib enum traceback "
    "shutil importlib functools collections itertools datetime math random copy io "
    "secrets __future__".split()
)


def _plurals_keys(models_src: str) -> set:
    """The routable entity set: keys of the PLURALS dict in models.py."""
    try:
        tree = ast.parse(models_src)
    except SyntaxError:
        return set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PLURALS":
                    if isinstance(node.value, ast.Dict):
                        return {
                            k.value
                            for k in node.value.keys
                            if isinstance(k, ast.Constant) and isinstance(k.value, str)
                        }
    return set()


def _check_contracts(plan: BuildPlan, files: Dict[str, str]) -> CheckResult:
    # 1. Every planned module was emitted.
    for module in plan.modules:
        if module.path not in files:
            return CheckResult(
                "contracts", False, "planned module missing: %s" % module.path
            )
    # 2. Every local import resolves to a generated file.
    local = _local_module_paths(files)
    top_levels = {p.split("/")[0].rsplit(".", 1)[0] for p in files if p.endswith(".py")}
    for path, content in sorted(files.items()):
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue  # the compile gate reports this precisely
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mod = node.module
            elif isinstance(node, ast.Import):
                mod = node.names[0].name if node.names else ""
            else:
                continue
            first = mod.split(".")[0]
            if first in _STDLIB_TOP_LEVELS:
                continue
            if first in top_levels:
                if mod not in local:
                    return CheckResult(
                        "contracts",
                        False,
                        "%s imports unresolvable local module %r" % (path, mod),
                    )
                continue
            # Not stdlib, not generated: generated code is stdlib-only by law.
            return CheckResult(
                "contracts",
                False,
                "%s imports %r — not stdlib, not generated" % (path, mod),
            )
    # 3. Domain rules: the plan's entities must be served, not just named.
    if plan.domain == "web-api":
        models_src = files.get("api/models.py", "")
        for entity_model in plan.data_model:
            cls = "".join(p.capitalize() for p in entity_model.name.split("_"))
            if "class %s" % cls not in models_src:
                return CheckResult(
                    "contracts", False, "models.py missing class %s" % cls
                )
        # Routes dispatch through PLURALS, so routability = PLURALS coverage.
        served = _plurals_keys(models_src)
        for entity_model in plan.data_model:
            if _plural(entity_model.name) not in served:
                return CheckResult(
                    "contracts",
                    False,
                    "PLURALS never serves %r" % entity_model.name,
                )
    if plan.domain == "realtime":
        events_src = files.get("events.py", "")
        if "def publish" not in events_src or "def since" not in events_src:
            return CheckResult(
                "contracts", False, "events.py must expose publish and since"
            )
    return CheckResult(
        "contracts",
        True,
        "plan honored: %d modules, imports resolve" % len(plan.modules),
    )


def _tmp_discard_only(content: str) -> bool:
    """True iff every os.remove/os.unlink call lives inside _discard_tmp
    AND _discard_tmp guards on the .tmp suffix.

    The store's atomic-write temp cleanup is the one deletion the engine
    emits itself. The denylist still forbids the pattern everywhere else;
    this exception is verified by AST, not granted by trust.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return False
    state = {"guard": False, "stray": False}

    def visit(node, enclosing: str) -> None:
        name = enclosing
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "_discard_tmp":
                dumped = ast.dump(node)
                if ".tmp" in dumped and "endswith" in dumped:
                    state["guard"] = True
            name = node.name
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr in ("remove", "unlink")
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
            ):
                if name != "_discard_tmp":
                    state["stray"] = True
        for child in ast.iter_child_nodes(node):
            visit(child, name)

    visit(tree, "")
    return state["guard"] and not state["stray"]


# Deletion patterns with a single verified exception (see _tmp_discard_only).
_DELETION_PATTERNS = ("os.remove(", "os.unlink(")


def _check_safety(plan: BuildPlan, files: Dict[str, str]) -> CheckResult:
    forbidden = list(_GLOBAL_FORBIDDEN) + list(get_pack(plan.domain)["forbidden"])
    for path, content in sorted(files.items()):
        if not path.endswith(".py"):
            continue
        for pattern in forbidden:
            if pattern in content:
                if pattern in _DELETION_PATTERNS and _tmp_discard_only(content):
                    continue  # the store's guarded temp cleanup, AST-verified
                return CheckResult(
                    "safety",
                    False,
                    "%s contains forbidden pattern %r" % (path, pattern),
                )
    return CheckResult("safety", True, "no destructive or dynamic-exec patterns")


def _check_packaging(plan: BuildPlan, files: Dict[str, str]) -> CheckResult:
    readme = files.get("README.md", "")
    if len(readme) < 100:
        return CheckResult("packaging", False, "README.md missing or skeletal")
    entry = next((m.path for m in plan.modules if m.kind == "entry"), None)
    if not entry or entry not in files:
        return CheckResult("packaging", False, "entry point missing")
    tests = [p for p in files if p.startswith("tests/test_") and p.endswith(".py")]
    if not tests:
        return CheckResult("packaging", False, "no tests shipped")
    try:
        prov = json.loads(files.get(".provenance.json", ""))
        if prov.get("provenance") != "builder":
            raise ValueError("provenance marker wrong")
    except (ValueError, AttributeError):
        return CheckResult("packaging", False, ".provenance.json invalid")
    return CheckResult(
        "packaging",
        True,
        "readme, entry %s, %d test files, provenance ok" % (entry, len(tests)),
    )


def _run_one_test(target_dir: str, rel: str) -> Optional[str]:
    """Run one generated test file. Returns None on pass, detail on fail."""
    full = os.path.join(target_dir, rel)
    try:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"  # keep the product pristine
        proc = subprocess.run(
            [sys.executable, full],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return "%s timed out" % rel
    except OSError as exc:
        return "%s could not run: %s" % (rel, exc)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "")[-800:]
        return "%s exit %d: %s" % (rel, proc.returncode, tail)
    return None


def _check_smoke(
    plan: BuildPlan, files: Dict[str, str], target_dir: str
) -> CheckResult:
    # Test list comes from the verified file set, never from stale disk state.
    tests = sorted(
        p for p in files if p.startswith("tests/test_") and p.endswith(".py")
    )
    if not tests:
        return CheckResult("smoke", False, "no test files found")
    failures = []
    for rel in tests:
        detail = _run_one_test(target_dir, rel)
        if detail:
            failures.append(detail)
    if failures:
        return CheckResult("smoke", False, "; ".join(failures))
    return CheckResult("smoke", True, "%d test files passed" % len(tests))


def _repair_note(level: int) -> str:
    return {
        1: "sanitized identifiers and regenerated from the same plan",
        2: "regenerated from the same plan (transient-fault retry)",
        3: "final regeneration from the same plan before owner decision",
    }.get(level, "repair pass %d" % level)


def _gates(
    plan: BuildPlan, files: Dict[str, str], target_dir: str
) -> List[CheckResult]:
    # Short-circuit, never silently: a failed prerequisite skips the gates
    # that depend on it, and the skip is recorded in the report. The smoke
    # gate (live servers, real subprocesses) is the expensive one — it never
    # runs against code that failed a static gate.
    compile_r = _check_compile(files)
    if not compile_r.passed:
        skipped = "skipped: compile failed"
        return [
            compile_r,
            CheckResult("contracts", False, skipped),
            CheckResult("safety", False, skipped),
            CheckResult("packaging", False, skipped),
            CheckResult("smoke", False, skipped),
        ]
    contracts_r = _check_contracts(plan, files)
    safety_r = _check_safety(plan, files)
    packaging_r = _check_packaging(plan, files)
    if all(r.passed for r in (contracts_r, safety_r, packaging_r)):
        smoke_r = _check_smoke(plan, files, target_dir)
    else:
        smoke_r = CheckResult("smoke", False, "skipped: a static gate failed")
    return [compile_r, contracts_r, safety_r, packaging_r, smoke_r]


class VerifyLoop:
    """Verifier twin: proves the proposer's output before anyone sees it."""

    def __init__(self, max_retries: int = MAX_BUILDER_RETRIES) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self.max_retries = max_retries

    def run(
        self, engine: ScaffoldEngine, target_dir: Optional[str] = None
    ) -> VerifyReport:
        """Run the bounded verify loop. Retries are free by construction.

        Returns a VerifyReport; never raises for builder-caused failures —
        exhaustion becomes OWNER_DECISION_NEEDED, not an exception.
        """
        if target_dir is None:
            target_dir = tempfile.mkdtemp(prefix="levi-build-")
        os.makedirs(target_dir, exist_ok=True)

        attempts = 0
        repairs: List[str] = []
        last_checks: List[CheckResult] = []
        diagnostics = ""

        for attempt in range(self.max_retries + 1):
            attempts = attempt + 1
            repair_level = attempt  # 0 = fresh, >=1 = escalating repairs
            plan = engine._plan_for(repair_level)
            files = engine.generate(repair_level=repair_level)
            engine.apply_fault_hook(attempt, files)  # test-only; None in prod
            if repair_level:
                repairs.append(_repair_note(repair_level))
            # Retries never delete: every attempt regenerates the SAME domain
            # and file contract, so each attempt overwrites the same paths.
            # Pre-existing files in the target dir are the owner's, not ours.
            # The build's internal representation is the typed action stream:
            # ordered, deterministic, applied in dependency order.
            action_plan = plan_actions(plan, files)
            apply_actions(action_plan, target_dir, files)

            checks = _gates(plan, files, target_dir)
            last_checks = checks
            if all(c.passed for c in checks):
                outcome = (
                    BuildOutcome.VERIFIED if attempt == 0 else BuildOutcome.SELF_HEALED
                )
                return VerifyReport(
                    outcome=outcome,
                    attempts=attempts,
                    repairs=repairs,
                    checks=checks,
                    target_dir=target_dir,
                )
            diagnostics = "\n".join(
                "%s: %s" % (c.name, c.detail) for c in checks if not c.passed
            )

        return VerifyReport(
            outcome=BuildOutcome.OWNER_DECISION_NEEDED,
            attempts=attempts,
            repairs=repairs,
            checks=last_checks,
            diagnostics=(
                "Bound exhausted after %d attempts (%d retries). "
                "The builder stopped rather than ship a broken app.\n%s\n%s"
                % (
                    attempts,
                    self.max_retries,
                    diagnostics,
                    traceback.format_exc(limit=0),
                )
            ),
            target_dir=target_dir,
        )

    def verify_files(
        self, plan: BuildPlan, files: Dict[str, str], target_dir: str
    ) -> VerifyReport:
        """Single verification pass over an explicit file set (no regen).

        Used by refinement: the file set is the merged project on disk, and
        only the builder's own diff may change it — so there is nothing to
        retry against. Failure is reported, never hidden.
        """
        os.makedirs(target_dir, exist_ok=True)
        action_plan = plan_actions(plan, files)
        apply_actions(action_plan, target_dir, files)
        checks = _gates(plan, files, target_dir)
        if all(c.passed for c in checks):
            return VerifyReport(
                outcome=BuildOutcome.VERIFIED,
                attempts=1,
                checks=checks,
                target_dir=target_dir,
            )
        return VerifyReport(
            outcome=BuildOutcome.OWNER_DECISION_NEEDED,
            attempts=1,
            checks=checks,
            diagnostics="\n".join(
                "%s: %s" % (c.name, c.detail) for c in checks if not c.passed
            ),
            target_dir=target_dir,
        )
