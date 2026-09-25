"""Broken-window sweeps — periodic tiny-fix sweeps of accumulated mess.

The labor directive says tedious cleanup is LEVI's favorite meal. A
sweep is a registered spec with two halves: ``check(root)`` lists
issues (relative paths), ``fix(root, issue)`` repairs one. The runner
executes checks, auto-applies fixes ONLY for specs marked ``safe``,
and reports unsafe specs without ever running them.

Safety contract (binding):
  - ``run_sweep`` requires an explicit ``root``. There is no default
    that resolves to the real repo or the real home. Tests default to
    a tmp dir; the caller chooses the blast radius.
  - Roots ``/`` and the real ``$HOME`` are refused outright
    (``SweepRefusedError``). Nothing runs there, even with safe specs.
  - Every issue path is verified to stay inside ``root`` (no ``..``
    escapes); escapes are reported as errors, never followed.
  - ``safe=True`` means: purely local, reversible-or-regenerable, no
    deletions outside the explicit root. Unsafe specs are checked and
    reported; their fixes never run automatically.
  - Built-in sweeps only ever delete what Python regenerates
    (``__pycache__``), what is provably empty (empty dirs), or what is
    provably disposable (stale tmp files).

stdlib-only. Local filesystem only; no network, no daemons.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

__all__ = [
    "SweepReport",
    "SweepSpec",
    "SweepRefusedError",
    "builtin_specs",
    "list_specs",
    "register",
    "run_sweep",
    "unregister",
]

CheckFn = Callable[[Path, float], List[str]]
FixFn = Callable[[Path, str], bool]


class SweepRefusedError(RuntimeError):
    """Raised when a sweep target is outside the allowed blast radius."""


@dataclass
class SweepSpec:
    """One sweep: check lists issues, fix repairs one.

    ``check`` receives ``(root, max_age_days)`` and returns issue paths
    *relative* to root. ``fix`` receives ``(root, issue)`` and returns
    True when the issue was actually repaired. ``safe`` gates auto-run.
    """

    id: str
    area: str
    description: str
    check: CheckFn
    fix: FixFn
    safe: bool = True


@dataclass
class SweepReport:
    """Outcome of one ``run_sweep``."""

    root: str
    fixed: List[str] = field(default_factory=list)
    remaining: List[str] = field(default_factory=list)
    skipped_unsafe: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)

    def format(self) -> str:
        lines = ["sweep @ %s" % self.root]
        lines.append("  fixed: %d" % len(self.fixed))
        for f in self.fixed:
            lines.append("    + %s" % f)
        lines.append("  remaining: %d" % len(self.remaining))
        for r in self.remaining:
            lines.append("    - %s" % r)
        lines.append("  skipped_unsafe: %d" % len(self.skipped_unsafe))
        for s in self.skipped_unsafe:
            lines.append(
                "    ! %s (%d issue(s) NOT auto-fixed)" % (s["id"], len(s["issues"]))
            )
        if self.errors:
            lines.append("  errors: %d" % len(self.errors))
            for e in self.errors:
                lines.append("    x %s: %s" % (e["issue"], e["error"]))
        return "\n".join(lines)


_REGISTRY: Dict[str, SweepSpec] = {}


def register(spec: SweepSpec) -> SweepSpec:
    """Register (or replace) a sweep spec by id."""
    if not spec.id or not spec.id.strip():
        raise ValueError("sweep id is required")
    _REGISTRY[spec.id] = spec
    return spec


def unregister(spec_id: str) -> bool:
    """Remove a spec. Returns True when one was present."""
    return _REGISTRY.pop(spec_id, None) is not None


def list_specs() -> List[SweepSpec]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def _refuse_dangerous(root: Path) -> None:
    resolved = root.resolve()
    if resolved == Path("/").resolve():
        raise SweepRefusedError("refusing to sweep filesystem root '/'")
    home = Path.home().resolve()
    if resolved == home:
        raise SweepRefusedError(
            "refusing to sweep the real HOME %s — pass an explicit subdirectory" % home
        )
    # Also refuse the LEVI source checkout itself: sweeps run on data
    # roots, never on the product tree, unless the caller names a
    # subdirectory explicitly.
    here = Path(__file__).resolve().parents[3]  # .../workspace/levi
    if resolved == here:
        raise SweepRefusedError(
            "refusing to sweep the LEVI repo root — pass an explicit subdirectory"
        )


def _within(root: Path, issue: str) -> Optional[Path]:
    """Resolve an issue path, returning None when it escapes root."""
    candidate = (root / issue).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def run_sweep(
    root: Any,
    *,
    only: Optional[List[str]] = None,
    max_age_days: float = 7,
) -> SweepReport:
    """Run registered sweeps against an explicit root.

    Safe specs: check, then auto-fix each issue, re-checking nothing —
    a failed fix lands in ``remaining``. Unsafe specs: check only; their
    issues are reported under ``skipped_unsafe`` and never fixed.
    """
    root = Path(root).expanduser()
    _refuse_dangerous(root)
    if not root.exists():
        raise SweepRefusedError("root does not exist: %s" % root)
    report = SweepReport(root=str(root))
    specs = list_specs()
    if only:
        wanted = set(only)
        specs = [s for s in specs if s.id in wanted]
    for spec in specs:
        try:
            issues = spec.check(root, max_age_days)
        except OSError as exc:
            report.errors.append({"issue": spec.id, "error": "check failed: %s" % exc})
            continue
        if not spec.safe:
            report.skipped_unsafe.append(
                {"id": spec.id, "area": spec.area, "issues": issues}
            )
            continue
        for issue in issues:
            target = _within(root, issue)
            if target is None:
                report.errors.append(
                    {"issue": issue, "error": "escapes root — not touched"}
                )
                report.remaining.append(issue)
                continue
            try:
                ok = bool(spec.fix(root, issue))
            except OSError as exc:
                report.errors.append({"issue": issue, "error": "fix failed: %s" % exc})
                report.remaining.append(issue)
                continue
            (report.fixed if ok else report.remaining).append(issue)
    return report


# ------------------------------------------------------------------ builtins


def _older_than(path: Path, max_age_days: float) -> bool:
    try:
        age_days = (time.time() - path.stat().st_mtime) / 86400.0
    except OSError:
        return False
    return age_days > max_age_days


def _check_stale_pycache(root: Path, max_age_days: float) -> List[str]:
    """__pycache__ dirs older than N days — Python regenerates them."""
    found = []
    for pyc in root.rglob("__pycache__"):
        if pyc.is_dir() and _older_than(pyc, max_age_days):
            found.append(str(pyc.relative_to(root)))
    return sorted(found)


def _fix_remove_dir(root: Path, issue: str) -> bool:
    target = _within(root, issue)
    if target is None or not target.is_dir():
        return False
    shutil.rmtree(target)
    return not target.exists()


def _check_empty_dirs(root: Path, max_age_days: float) -> List[str]:
    """Directories with nothing in them — deleting loses nothing.

    Computed structurally, deepest-first: a dir is removable when it
    holds no files and every subdir is itself removable, so a chain
    like a/b/c collapses in a single pass. Never the root itself, and
    never a __pycache__ (bytecode races with a live interpreter).
    """
    _ = max_age_days  # age is irrelevant; emptiness is the criterion
    resolved = root.resolve()
    entries: List[tuple] = []
    for dirpath, dirnames, filenames in os.walk(root):
        entries.append((Path(dirpath), list(dirnames), list(filenames)))
    removable = set()
    for path, dirnames, filenames in sorted(
        entries, key=lambda e: len(e[0].parts), reverse=True
    ):
        if path.resolve() == resolved:
            continue
        if path.name == "__pycache__":
            continue
        if filenames:
            continue
        if all((path / d) in removable for d in dirnames):
            removable.add(path)
    # Deepest first so fixes succeed in one pass.
    return sorted(
        (str(p.relative_to(root)) for p in removable),
        key=lambda s: s.count(os.sep),
        reverse=True,
    )


_TMP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
_TMP_SUFFIXES = (".tmp", ".bak", ".swp", ".swo", "~")


def _check_stale_tmp_files(root: Path, max_age_days: float) -> List[str]:
    """Disposable temp files older than N days."""
    found = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        name = path.name
        if name in _TMP_NAMES or name.endswith(_TMP_SUFFIXES):
            if _older_than(path, max_age_days):
                found.append(str(path.relative_to(root)))
    return sorted(found)


def _fix_remove_file(root: Path, issue: str) -> bool:
    target = _within(root, issue)
    if target is None or not target.is_file():
        return False
    target.unlink()
    return not target.exists()


def _register_builtins() -> None:
    register(
        SweepSpec(
            id="stale-pycache",
            area="tree hygiene",
            description=(
                "Remove __pycache__ dirs older than N days. "
                "Safe: Python regenerates bytecode on next import."
            ),
            check=_check_stale_pycache,
            fix=_fix_remove_dir,
            safe=True,
        )
    )
    register(
        SweepSpec(
            id="empty-dirs",
            area="tree hygiene",
            description=(
                "Remove empty directories (never the root itself). "
                "Safe: an empty dir holds no data."
            ),
            check=_check_empty_dirs,
            fix=_fix_remove_dir,
            safe=True,
        )
    )
    register(
        SweepSpec(
            id="stale-tmp-files",
            area="tree hygiene",
            description=(
                "Remove *.tmp/*.bak/*.swp/.DS_Store-style files older "
                "than N days. Safe: disposable by definition."
            ),
            check=_check_stale_tmp_files,
            fix=_fix_remove_file,
            safe=True,
        )
    )


def builtin_specs() -> List[SweepSpec]:
    return [
        s
        for s in list_specs()
        if s.id in ("stale-pycache", "empty-dirs", "stale-tmp-files")
    ]


_register_builtins()
