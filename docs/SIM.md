# Simulations — `core/levi/sim/`

Bounded, text-based simulations: deterministic, clearly labeled, and
**zero real network I/O**. Used for safe rehearsal of dangerous
pipelines (bug-bounty recon) and operator training (SOC shifts).

## Purpose

Let LEVI exercise real orchestration code (the actual bounty `run_recon`
pipeline, unmodified) against a fully fictional world — proving the
logic works without ever touching the real internet.

## Key APIs

- `SCENARIOS = {"bounty-hunt": run_bounty_hunt, "soc-shift": run_soc_shift}`
- `run_scenario(name, seed=None) -> int` — exit codes: 0 ok, 1 sim
  error, 2 unknown scenario, 130 interrupted
- `SimWorld` — seeded fictional world (hosts, orgs, banners);
  `SimShim` — replaces every network call site of the bounty pipeline
  before it runs (same seed → same run)
- Structural laws (tested in `tests/test_sim.py`):
  - every scenario opens/closes with a `SIMULATION` banner;
  - sim modules never perform real I/O;
  - output is never presented as real.

## CLI usage

```bash
levi sim --list
levi sim bounty-hunt --seed 7
python -m levi.sim soc-shift --seed 42
```

## Honest limits

- Fiction only: findings from a sim are **not** real findings and are
  never written to the real findings store (isolated stores).
- Deterministic but simplified — a sim passing says the orchestration
  logic works, not that the real network path will.
- SOC shift is a training narrative, not a certification.
