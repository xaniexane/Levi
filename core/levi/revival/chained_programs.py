"""chained_programs — external programs as first-class extensions.

Studied from: dead-networks-20260916/report.md (WWIV BBS: Turbo Pascal
"chaining", the ancestor of BBS "doors").

The load-bearing idea: the host never recompiles to gain a feature.
An external program is registered with a name, a command, a budget,
and an argument contract; the host hands control to it, collects its
output, and resumes. New capability arrives without touching the core.

LEVI's take: ``ChainRegistry`` holds ``ChainSpec`` entries (name,
argv, time budget, description). ``run_chain`` executes one under a
timeout and returns a ``ChainResult`` with stdout/stderr/exit code.
Argument contracts are declared, not enforced by a shell — no
shell=True anywhere. This is an original, from-scratch implementation
for LEVI.

Honest limits: the host does NOT sandbox the chain — a registered
chain runs with the host's own privileges, so registration is a
trust decision. ``run_chain`` blocks the calling thread for up to
the budget. Commands are argv lists, never strings.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

ORIGIN = "levi-revival/chained-programs"


@dataclass(frozen=True)
class ChainSpec:
    """One registered external program."""

    name: str  # registry key, e.g. "tradewars"
    argv: List[str]  # command as an argv list; no shell
    budget_s: float = 10.0  # max wall-clock seconds
    description: str = ""
    max_args: int = 8  # how many caller-supplied args are accepted


@dataclass(frozen=True)
class ChainResult:
    """What a chain run produced."""

    name: str
    returncode: int
    stdout: str  # truncated to 64 KiB
    stderr: str  # truncated to 64 KiB
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.returncode == 0


_MAX_CAPTURE = 65536


class ChainRegistry:
    """Registry of chainable external programs."""

    def __init__(self) -> None:
        self._chains: Dict[str, ChainSpec] = {}

    def register(self, spec: ChainSpec) -> None:
        key = spec.name.strip().lower()
        if not key:
            raise ValueError("chain name must be non-empty")
        if not spec.argv:
            raise ValueError("chain argv must be non-empty")
        self._chains[key] = spec

    def unregister(self, name: str) -> bool:
        return self._chains.pop(name.strip().lower(), None) is not None

    def names(self) -> List[str]:
        return sorted(self._chains)

    def get(self, name: str) -> Optional[ChainSpec]:
        return self._chains.get(name.strip().lower())

    def run_chain(self, name: str, args: Sequence[str] = ()) -> ChainResult:
        """Run a registered chain with extra caller args appended.

        Caller args are limited by the spec's ``max_args`` and passed
        as literal argv items (no shell interpolation). Blocks up to
        ``budget_s`` seconds, then kills the process and reports a
        timeout.
        """
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"no chain registered under {name!r}")
        extra = [str(a) for a in args][: spec.max_args]
        argv = list(spec.argv) + extra
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=spec.budget_s,
                shell=False,
            )
            return ChainResult(
                name=spec.name,
                returncode=proc.returncode,
                stdout=proc.stdout[:_MAX_CAPTURE],
                stderr=proc.stderr[:_MAX_CAPTURE],
            )
        except subprocess.TimeoutExpired as exc:
            out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            err = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            return ChainResult(
                name=spec.name,
                returncode=-1,
                stdout=str(out)[:_MAX_CAPTURE],
                stderr=str(err)[:_MAX_CAPTURE],
                timed_out=True,
            )
        except OSError as exc:  # executable missing, permission denied
            return ChainResult(
                name=spec.name,
                returncode=-1,
                stdout="",
                stderr=f"launch failed: {exc}",
            )

    def describe(self) -> List[Dict[str, object]]:
        """Human-readable menu of registered chains."""
        return [
            {
                "name": s.name,
                "command": " ".join(s.argv),
                "budget_s": s.budget_s,
                "description": s.description,
            }
            for s in (self._chains[k] for k in sorted(self._chains))
        ]


def demo() -> Dict[str, object]:
    """Small end-to-end demo: register and run a harmless echo chain."""
    import sys

    reg = ChainRegistry()
    reg.register(
        ChainSpec(
            name="greet",
            argv=[
                sys.executable,
                "-c",
                "import sys; print('chain says: ' + ' '.join(sys.argv[1:]))",
            ],
            budget_s=5.0,
            description="demo chain that echoes its arguments",
        )
    )
    result = reg.run_chain("greet", ["hello", "levi"])
    return {
        "menu": reg.describe(),
        "run": {
            "ok": result.ok,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
        },
    }
