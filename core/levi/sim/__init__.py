"""LEVI bounded simulations — text-based, deterministic, zero real network.

Scenarios:

* ``bounty-hunt`` — a cinematic simulated bug-bounty recon run. A
  deterministic fictional target org is generated from the seed, the
  bounty pipeline's low-level network functions are shimmed to serve
  that world, and the REAL ``run_recon`` orchestration runs unmodified
  against it (scope gate included, on isolated stores).
* ``soc-shift`` — a simulated SOC night-shift feed: seeded event stream,
  operator triage via menu, scored shift report with a grade.

Hard laws (structural, tested in ``tests/test_sim.py``):

* Every scenario opens and closes with a ``SIMULATION`` banner and
  labels its output simulated — sim output is never presented as real.
* Zero real network in sim mode: sim modules never perform real I/O;
  the bounty-hunt shims replace every network call site before the
  pipeline runs.
* Deterministic: a seed drives ``random.Random``; same seed ->
  identical world and transcript.
* LEVI-only branding: no third-party provider names anywhere in sim
  output.
"""

from __future__ import annotations

from levi.sim.bounty_hunt import run as run_bounty_hunt
from levi.sim.soc_shift import run as run_soc_shift
from levi.sim.world import SimWorld

SCENARIOS = {
    "bounty-hunt": run_bounty_hunt,
    "soc-shift": run_soc_shift,
}

__all__ = ["SCENARIOS", "SimWorld", "run_bounty_hunt", "run_scenario", "run_soc_shift"]


def run_scenario(name: str, seed: int | None = None) -> int:
    """Run scenario ``name`` with ``seed``. Returns a process exit code.

    Unknown scenario -> 2. Sim error -> 1. KeyboardInterrupt -> 130.
    (The parent CLI wires ``levi sim ...`` argparse to this function.)
    """
    fn = SCENARIOS.get(name)
    if fn is None:
        print(f"unknown simulation {name!r}; available: {', '.join(sorted(SCENARIOS))}")
        return 2
    try:
        return int(fn(seed))
    except KeyboardInterrupt:
        print("\nsimulation interrupted.")
        return 130
    except Exception as exc:  # never let a sim traceback escape unlabeled
        print(f"SIMULATION error: {type(exc).__name__}: {exc}")
        return 1
