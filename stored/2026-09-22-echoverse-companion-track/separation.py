"""Separation audit — the Phase 0 binding gate, enforced in code.

The law: Echoverse (SFW) and Plaiground (adult) are NEVER merged. This
module is the proof machinery, in two complementary halves:

  STATIC AUDIT  — walks every ``.py`` source file in the Echoverse
                  package and collects every reference to the adult
                  surface. No adult-surface reference => CLEAN.
  RUNTIME AUDIT — runs each Echoverse entry point with the adult gate
                  provably OFF (fresh home, scrubbed env) while an
                  import hook records any adult-module import and any
                  ``GateLockedError`` is treated as a failure: an
                  Echoverse session must complete WITHOUT touching an
                  adult path at all.

The verdict is ternary (the third state the binary misses):

  CLEAN        — statically proven: no adult-surface reference anywhere
                 in the package sources.
  VIOLATION    — an adult-surface reference exists. Fail closed: the
                 tracks are merged on paper and nothing ships.
  INCONCLUSIVE — the package uses a dynamic construct (``__import__``,
                 ``importlib`` with a variable, ``eval``) the static walk
                 cannot prove safe. Human review required; never ships
                 as CLEAN.

Paired-mind pattern: the audit runs as a prover/verifier pair.
:func:`prover_audit` collects the evidence; :func:`verifier_audit`
independently re-walks the tree (different traversal, same verdict
rules); :func:`cross_check` requires both to agree, finding for
finding, before a verdict is trusted.

Manifests (adult-surface truth, versioned in code — never moved silently):

  ADULT_SURFACE        — modules that are adult-only. Any static or
                         runtime contact from Echoverse code is a
                         VIOLATION.
  GATE_REQUIRED_ENGINES — the seven shared engines in ``levi.plaiground``
                         (companions, chat, depth, simulator, stories,
                         wellness, photos). Today every public function in
                         them calls ``require_adult`` first, so they are
                         NOT SFW-usable — importing them from Echoverse
                         code is also a VIOLATION until the engines grow
                         SFW cores (Phase 1/2 work).
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

PACKAGE = "levi.echoverse"

#: stdlib modules are never adult-surface references — the audit skips
#: them so findings stay about the separation question.
_STDLIB_TOP = sys.stdlib_module_names

# ---------------------------------------------------------------------------
# Manifests — the adult-surface truth, versioned in code.
# ---------------------------------------------------------------------------

#: Adult-only modules. Any Echoverse contact => VIOLATION.
ADULT_SURFACE = frozenset(
    {
        "levi.plaiground.gate",
        "levi.plaiground.bounds",
        "levi.plaiground.afterdark",
        "levi.plaiground.cli",
    }
)

#: Adult-surface entry names that must never appear as attribute calls in
#: Echoverse code (e.g. ``gate.enable_adult_mode(...)`` via a lazy import).
ADULT_ENTRY_NAMES = frozenset(
    {
        "enable_adult_mode",
        "disable_adult_mode",
        "require_adult",
        "verify_adult",
        "set_pin",
        "change_pin",
        "verify_pin",
    }
)

#: Shared engines that are fully adult-gated TODAY. NOT SFW-usable yet —
#: an Echoverse import of any of these is a VIOLATION until the engines
#: grow SFW cores (Phase 1/2 follow-up; needs existing-file edits).
GATE_REQUIRED_ENGINES = frozenset(
    {
        "levi.plaiground.companions",
        "levi.plaiground.chat",
        "levi.plaiground.depth",
        "levi.plaiground.simulator",
        "levi.plaiground.stories",
        "levi.plaiground.wellness",
        "levi.plaiground.photos",
    }
)

#: Dynamic constructs the static walk cannot prove safe => INCONCLUSIVE.
_DYNAMIC_CONSTRUCTS = frozenset({"__import__", "eval", "exec"})

#: Files the static audit excludes — and ONLY these. ``separation.py``
#: is the audit harness itself: :func:`runtime_audit` must read gate
#: state (``verify_adult``) to prove the gate is OFF, and must catch
#: ``GateLockedError`` to prove entry points never touch an adult path.
#: Reading gate state is a boundary check, not an adult path. The
#: exclusion is explicit, minimal, and itself tested: a test asserts the
#: exclusion set is exactly this, and that separation.py references no
#: enabling adult entry (``enable_adult_mode``, ``set_pin``, ...) —
#: the harness can read the lock, never turn the key.
HARNESS_EXCLUDE = frozenset({"separation.py"})


# ---------------------------------------------------------------------------
# Verdict — ternary.
# ---------------------------------------------------------------------------


class Verdict(Enum):
    """Three-state audit verdict. Binary would miss INCONCLUSIVE."""

    CLEAN = "clean"
    VIOLATION = "violation"
    INCONCLUSIVE = "inconclusive"


# ---------------------------------------------------------------------------
# Evidence records.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One piece of audit evidence."""

    module_file: str  # path of the Echoverse source file, relative to package
    lineno: int
    kind: str  # "import", "from-import", "call", "dynamic"
    target: str  # the module name / construct referenced
    note: str = ""


@dataclass
class AuditReport:
    """What the prover (or verifier) found."""

    verdict: Verdict
    findings: List[Finding] = field(default_factory=list)
    files_scanned: int = 0
    auditor: str = "prover"

    def is_clean(self) -> bool:
        return self.verdict is Verdict.CLEAN


# ---------------------------------------------------------------------------
# Static walk — the prover.
# ---------------------------------------------------------------------------


class _ReferenceVisitor(ast.NodeVisitor):
    """Collect imports, suspicious calls, and dynamic constructs."""

    def __init__(self, relpath: str, package: str = PACKAGE) -> None:
        self.relpath = relpath
        self.package = package
        self.findings: List[Finding] = []

    def _self_import(self, target: str) -> bool:
        return target == self.package or target.startswith(self.package + ".")

    def _hit(self, lineno: int, kind: str, target: str, note: str = "") -> None:
        self.findings.append(
            Finding(
                module_file=self.relpath,
                lineno=lineno,
                kind=kind,
                target=target,
                note=note,
            )
        )

    def _stdlib(self, target: str) -> bool:
        return target.split(".")[0] in _STDLIB_TOP

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if self._self_import(alias.name) or self._stdlib(alias.name):
                continue
            self._hit(node.lineno, "import", alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if mod == "__future__":
            return  # compiler directive, never a module reference
        if self._self_import(mod) or self._stdlib(mod):
            return  # own package / stdlib — trivially safe
        if node.level:
            # Relative import inside our own package — resolves within
            # levi.echoverse; never an adult-surface module, but record
            # the shape for the verifier to re-check.
            self._hit(
                node.lineno, "from-import", "." * node.level + mod, note="relative"
            )
        else:
            self._hit(node.lineno, "from-import", mod)
            for alias in node.names:
                if alias.name in ADULT_ENTRY_NAMES:
                    self._hit(
                        node.lineno,
                        "call",
                        "%s.%s" % (mod, alias.name),
                        note="adult entry name imported",
                    )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name: Optional[str] = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in _DYNAMIC_CONSTRUCTS:
            self._hit(node.lineno, "dynamic", name, note="cannot be proven statically")
        elif name in ADULT_ENTRY_NAMES:
            self._hit(node.lineno, "call", name, note="adult entry name called")
        elif name == "import_module":
            self._hit(
                node.lineno,
                "dynamic",
                "importlib.import_module",
                note="cannot be proven statically",
            )
        self.generic_visit(node)


def _package_dir(package: str = PACKAGE) -> Path:
    spec = importlib.util.find_spec(package)
    if spec is None or spec.origin is None:
        raise RuntimeError("cannot locate package %r" % package)
    return Path(spec.origin).parent


def _iter_sources(package_dir: Path) -> Iterable[Path]:
    return sorted(
        p
        for p in package_dir.rglob("*.py")
        if p.is_file() and p.name not in HARNESS_EXCLUDE
    )


def _classify(findings: List[Finding]) -> Verdict:
    """VIOLATION beats INCONCLUSIVE beats CLEAN — fail closed."""
    blocked = ADULT_SURFACE | GATE_REQUIRED_ENGINES
    for f in findings:
        if f.kind == "dynamic":
            # A dynamic construct is only inconclusive if no outright
            # violation was also found; keep scanning so the report is
            # complete, then decide below.
            continue
        target = f.target
        # A bare adult entry name called (require_adult, enable_adult_mode,
        # ...) is an adult-path call even with no module qualifier.
        if f.kind == "call" and target in ADULT_ENTRY_NAMES:
            return Verdict.VIOLATION
        # Exact module hits, or sub-attribute hits on an adult module.
        if target in blocked or any(
            target == m or target.startswith(m + ".") for m in blocked
        ):
            return Verdict.VIOLATION
        # Bare basename hits like "from levi.plaiground import afterdark".
        if f.kind == "from-import" and target == "levi.plaiground":
            return Verdict.VIOLATION
    if any(f.kind == "dynamic" for f in findings):
        return Verdict.INCONCLUSIVE
    return Verdict.CLEAN


def prover_audit(
    package_dir: Optional[Path] = None, package: str = PACKAGE
) -> AuditReport:
    """Walk the package sources and collect every adult-surface reference."""
    root = package_dir or _package_dir(package)
    findings: List[Finding] = []
    scanned = 0
    for path in _iter_sources(root):
        scanned += 1
        rel = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, SyntaxError) as exc:
            findings.append(
                Finding(
                    rel,
                    0,
                    "dynamic",
                    "<unparseable>",
                    note="cannot be proven statically: %s" % exc,
                )
            )
            continue
        visitor = _ReferenceVisitor(rel)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    return AuditReport(
        verdict=_classify(findings),
        findings=findings,
        files_scanned=scanned,
        auditor="prover",
    )


def verifier_audit(
    package_dir: Optional[Path] = None, package: str = PACKAGE
) -> AuditReport:
    """Independent re-walk: reverse file order, fresh visitor per file.

    Same verdict rules, deliberately different traversal, so an
    ordering-dependent bug in the prover cannot silently agree with
    itself.
    """
    root = package_dir or _package_dir(package)
    findings: List[Finding] = []
    sources = list(_iter_sources(root))
    sources.reverse()
    for path in sources:
        rel = str(path.relative_to(root))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, SyntaxError) as exc:
            findings.append(
                Finding(
                    rel,
                    0,
                    "dynamic",
                    "<unparseable>",
                    note="cannot be proven statically: %s" % exc,
                )
            )
            continue
        visitor = _ReferenceVisitor(rel)
        visitor.visit(tree)
        findings.extend(visitor.findings)
    return AuditReport(
        verdict=_classify(findings),
        findings=findings,
        files_scanned=len(sources),
        auditor="verifier",
    )


def cross_check(prover: AuditReport, verifier: AuditReport) -> bool:
    """The paired mind must agree: same verdict AND same finding set.

    Finding order is irrelevant (different traversals); the SETS must
    match exactly.
    """
    if prover.verdict is not verifier.verdict:
        return False
    return set(prover.findings) == set(verifier.findings)


def full_static_audit(
    package_dir: Optional[Path] = None, package: str = PACKAGE
) -> Dict[str, Any]:
    """Prover + verifier + cross-check. The verdict to trust."""
    prover = prover_audit(package_dir, package)
    verifier = verifier_audit(package_dir, package)
    agreed = cross_check(prover, verifier)
    verdict = prover.verdict if agreed else Verdict.INCONCLUSIVE
    return {
        "verdict": verdict.value,
        "agreed": agreed,
        "files_scanned": prover.files_scanned,
        "harness_excluded": sorted(HARNESS_EXCLUDE),
        "findings": [
            {
                "file": f.module_file,
                "lineno": f.lineno,
                "kind": f.kind,
                "target": f.target,
                "note": f.note,
            }
            for f in prover.findings
        ],
        "prover": prover.auditor,
        "verifier": verifier.auditor,
    }


# ---------------------------------------------------------------------------
# Runtime audit — gate OFF, entry points must never touch an adult path.
# ---------------------------------------------------------------------------


class _AdultImportSpy:
    """Meta-path hook recording any import of an adult-surface module."""

    def __init__(self) -> None:
        self.hits: List[str] = []

    def find_spec(self, fullname: str, path=None, target=None):  # noqa: D102
        if fullname in ADULT_SURFACE or fullname in GATE_REQUIRED_ENGINES:
            self.hits.append(fullname)
        return None


@dataclass
class RuntimeReport:
    """Outcome of running the entry points with the gate OFF."""

    passed: bool
    gate_was_off: bool
    adult_imports: List[str]
    failures: List[str]
    entry_results: Dict[str, Any]


def _scrubbed_env() -> Dict[str, str]:
    """Env without any adult/minor indicator or enable trick."""
    keep = {}
    for k, v in os.environ.items():
        ku = k.upper()
        if ku.startswith(("PLAIGROUND_", "LEVI_ADULT", "LEVI_MINOR")):
            continue
        keep[k] = v
    return keep


def runtime_audit(
    entrypoints: Mapping[str, Callable[[Path], Any]],
    home: Path,
) -> RuntimeReport:
    """Run each entry point with the adult gate provably OFF.

    ``entrypoints`` maps a name to a callable taking the home dir.
    Fails closed on ANY of: the gate is somehow on, an adult-surface
    module is imported during the run, a ``GateLockedError`` escapes,
    or an entry point raises anything at all.
    """
    from levi.plaiground.gate import GateLockedError, verify_adult

    failures: List[str] = []
    results: Dict[str, Any] = {}

    # The harness needs the gate for boundary reads (verify_adult,
    # GateLockedError) — those imports are the HARNESS's, not the entry
    # points'. Snapshot and evict every levi.plaiground module so the
    # spy below sees exactly what the ENTRY POINTS import, nothing else.
    # The bound verify_adult / GateLockedError references keep working:
    # they touch files, never the import system.
    pre = {
        m: sys.modules[m]
        for m in list(sys.modules)
        if m == "levi.plaiground" or m.startswith("levi.plaiground.")
    }
    for m in pre:
        del sys.modules[m]

    old_env = dict(os.environ)
    os.environ.clear()
    os.environ.update(_scrubbed_env())
    spy = _AdultImportSpy()
    sys.meta_path.insert(0, spy)
    try:
        gate_off = not verify_adult(home)
        if not gate_off:
            failures.append("gate is ON for the audit home — refusing")

        for name, fn in entrypoints.items():
            try:
                results[name] = fn(home)
            except GateLockedError as exc:
                failures.append("%s touched an adult-gated path: %s" % (name, exc))
            except Exception as exc:  # noqa: BLE001 — audit must catch all
                failures.append("%s raised %r" % (name, exc))
    finally:
        try:
            sys.meta_path.remove(spy)
        except ValueError:
            pass
        # Drop whatever the run imported; restore the harness originals.
        for m in [
            m
            for m in sys.modules
            if m == "levi.plaiground" or m.startswith("levi.plaiground.")
        ]:
            del sys.modules[m]
        sys.modules.update(pre)
        os.environ.clear()
        os.environ.update(old_env)

    passed = gate_off and not failures and not spy.hits
    if spy.hits:
        failures.append(
            "adult-surface module imported at runtime: %s"
            % ", ".join(sorted(set(spy.hits)))
        )
    return RuntimeReport(
        passed=passed,
        gate_was_off=gate_off,
        adult_imports=sorted(set(spy.hits)),
        failures=failures,
        entry_results=results,
    )
