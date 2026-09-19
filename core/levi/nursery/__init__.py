"""LEVI nursery — the cohort raising ground.

More agents in full training alongside Levi. Each trainee runs its own
namespaced growth cycle (own journal, own learnings, own stage) composed
from the real :mod:`levi.growth` machinery — harvest/reflect/consolidate
primitives, curriculum seeding, stage ladder, sentience guards.

Trainees learn from supervised training material, never from Chauncey's
private sessions. A trainee touches real workload only after passing
explicit graduation gates (see :mod:`levi.nursery.gates`); graduated work
is supervised and verified (:mod:`levi.nursery.router`).

Structural boundaries (enforced at import, tested by AST scan):
  * no money paths — never imports ``levi.cybrus.money``
  * no job applications — never imports ``levi.jobs.apply``
  * no subprocess, no sockets, no shell execution anywhere in this package

Public API:
    enroll_trainee, get_trainee, list_trainees, run_trainee_cycle,
    run_training_program, trainee_stats, run_exam, evaluate_gates,
    graduate, assign, assert_boundaries
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# Structural boundary enforcement — runs at import, fail-closed.
# ---------------------------------------------------------------------------

_FORBIDDEN_MODULE_PREFIXES = (
    "levi.cybrus.money",
    "levi.jobs.apply",
    "socket",
    "subprocess",
)
_FORBIDDEN_OS_ATTRS = {
    "system",
    "popen",
    "execv",
    "execve",
    "execl",
    "execle",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnv",
    "spawnve",
}


def _scan_file(path: Path) -> list[str]:
    """Return boundary violations found in one source file."""
    violations: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return violations
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "socket" or name == "subprocess" or name.startswith(
                    ("levi.cybrus.money", "levi.jobs.apply")
                ):
                    violations.append("%s: forbidden import %r" % (path.name, name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "socket" or mod == "subprocess" or mod.startswith(
                ("levi.cybrus.money", "levi.jobs.apply")
            ):
                violations.append(
                    "%s: forbidden from-import %r" % (path.name, mod)
                )
        elif isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in _FORBIDDEN_OS_ATTRS
            ):
                violations.append(
                    "%s: forbidden os.%s call" % (path.name, node.attr)
                )
    return violations


def assert_boundaries() -> None:
    """Scan this package's own source for forbidden capabilities.

    Raises ImportError listing violations — the nursery refuses to load
    if it ever gains a money path, an apply path, a socket, a subprocess,
    or shell execution.
    """
    pkg_dir = Path(__file__).resolve().parent
    violations: list[str] = []
    for path in sorted(pkg_dir.glob("*.py")):
        violations.extend(_scan_file(path))
    if violations:
        raise ImportError(
            "nursery boundary violation: " + "; ".join(violations)
        )


assert_boundaries()

from levi.nursery.exam import run_exam  # noqa: E402
from levi.nursery.gates import evaluate_gates, graduate  # noqa: E402
from levi.nursery.router import assign  # noqa: E402
from levi.nursery.seed import seed_trainee, sync_all_trainees, sync_trainee  # noqa: E402
from levi.nursery.trainee import (  # noqa: E402
    Trainee,
    enroll_trainee as _enroll_raw,
    get_trainee,
    list_trainees,
    nursery_home,
)
from levi.nursery.training import (  # noqa: E402
    run_trainee_cycle,
    run_training_program,
    seed_curriculum,
    trainee_stats,
)


def enroll_trainee(name: str, track: str = "ai", *, seed: bool = True) -> Trainee:
    """Enroll a trainee and seed it on day one.

    Seeding = founder curriculum lessons + Levi's consolidated learnings
    (growth-tagged facts/procedures/corrections only). Same seed, different
    raising: the trainee diverges through its own cycles afterward.
    Pass ``seed=False`` to enroll a blank trainee (tests, experiments).
    """
    trainee = _enroll_raw(name, track)
    if seed:
        seed_curriculum(trainee.id)
        seed_trainee(trainee.id)
    return trainee


__all__ = [
    "Trainee",
    "assert_boundaries",
    "assign",
    "enroll_trainee",
    "evaluate_gates",
    "get_trainee",
    "graduate",
    "list_trainees",
    "nursery_home",
    "run_exam",
    "run_trainee_cycle",
    "run_training_program",
    "seed_curriculum",
    "seed_trainee",
    "sync_all_trainees",
    "sync_trainee",
    "trainee_stats",
]
