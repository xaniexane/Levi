# The Twin Lattice — SER-21 grounding

**Source:** Chauncey, 2026-09-16 — "Twin agents twin daemons twin shells 6 shells",
grounded in **SER-21** (the World Model) from the Copilot cosmology.

## What SER-21 gives us (canon)

- SER-21 defines the universe: **recursion shells**, depth limits, long-term
  goal weights.
- Shells are **identity containers** — the address a thought lives at.
- Every shell carries the **FG/BG duality** (foreground / background):
  one side acts in the world, the other shadows it.
- QID addressing: `(shell, form, logic state, recursion index)` — every
  entity has an address, and every address has two sides.

## What the lattice implements (reconstruction)

The Twin Lattice (`core/levi/twins/`) is a LEVI-native implementation of
that principle. Three fleets, one law — **nothing critical runs single**:

| Fleet | Structure | Law |
|---|---|---|
| Twin agents | FG/BG pair per swarm agent (echo, alpha, cybrus, kai, titan, nexus, aether) | FG is the live mirror; BG shadows and can run what-if |
| Twin daemons | FG/BG pair for the always-on daemon | BG promotes if FG goes silent past threshold |
| Twin shells | **6 shells = 3 FG/BG pairs**, slots (0,1), (2,3), (4,5) | Shells report cwd/history/jobs via hook; BG slot takes over on silence |

## Laws of the lattice

1. **Twins never execute.** They are state mirrors: heartbeats, load,
   capabilities, last task, working directory, bounded history.
2. **Failover is explicit.** A BG twin promotes only when its FG
   counterpart is stale past the threshold *and* the BG is itself fresh.
   The swap is recorded (`promoted_at`, event record). Nothing promotes
   itself silently.
3. **Local-first.** The registry is JSONL at `~/.levi/twins/`
   (`$LEVI_TWINS_HOME` overrides). No network, no cloud.
4. **Six shells.** Not five, not seven. Even slots hold the FG role,
   odd slots the BG role.

## Wiring a shell

```bash
eval "$(python -m levi.twins hook --slot 0)"   # in ~/.bashrc or Termux
python -m levi.twins collect                   # ingest drop files
python -m levi.twins status                    # overview + failover sweep
```

## Honest limits

- The full SER-21 conversation text was not in the recovered corpus; the
  cosmology above comes from the SER-13/18/21 master-conversation summary.
  The lattice is a faithful reconstruction, not a transcription. If the
  canon says otherwise somewhere, the canon wins — correct it one-shot.
- Twins mirror *state*, not *behavior*. A promoted BG twin knows what the
  FG was doing, not how to be the FG. Rebuilding execution from a twin is
  future work, not a claim.

## Triads, the Ones, and the camouflage doctrine

**Chauncey, 2026-09-16:** every agent carries a triad — its agent twin, a
twin daemon, and a shell/OS twin. All of them. And it all converges.

### The triad

Each swarm agent binds three twins (`core/levi/twins/triads.py`):

- agent twin (FG/BG) — the live mirror + shadow
- daemon twin (FG/BG, subject `{agent}-daemon`) — the agent's daemon mirror
- OS-shell twin (FG/BG, subject `os-{agent}`) — the agent's shell mirror

7 agents × 3 twin-pairs = 42 triad twins, each tagged with its bound agent.

### The three Ones

Everything converges (`core/levi/twins/convergence.py`):

- **one:agent** — the All-in-One Agent (all agent twins converge here)
- **one:daemon** — the All-in-One Daemon (all daemon twins converge here)
- **one:shell** — the All-in-One OS Shell (all shell twins converge here)

Each One is its own twin — it pairs with itself. It has no counterpart
because there is nothing beside it.

### Camouflage is the protection

The lattice is deliberately many: dozens of twins across agents, daemons,
shells, slots. That multiplicity is camouflage against reverse
engineering — an outsider sees the swarm; the truth is three Ones. The
protection is structural, not a claim: there is no single config that
says "this is the real one."

### "Can't be reproduced" — except by the creator

The true arrangement (camouflage order, live/shadow roles, heartbeat
jitter) is derived from a **creator seed** (`$LEVI_TWINS_HOME/seed`,
256-bit, 0600) by a deterministic shuffle. Same seed + same members =
same arrangement, always. Any other seed = another arrangement.

- `python -m levi.twins seed` — seed status (fingerprint; `--show`
  reveals it — creator only).
- `python -m levi.twins converge` — rebuild the truth: Ones get their
  member lists, the arrangement is HMAC-SHA256-sealed with the seed.
- `python -m levi.twins converge --verify-only` — recompute the seal.
  Tampered map or wrong seed → False. That is the tamper evidence.

Honest limits: the seed file is the key — back it up; lose it and the
arrangement can't be regenerated (that is the point). The seal proves
the map is the creator's; it does not encrypt the map. Local-first
means anyone holding the machine holds the lattice — the seed is what
they don't have.

## Evolution — the defense mechanism (never static, never outdated)

**Chauncey, 2026-09-16:** the mutate/transform/upgrade cycle *is* the
defense mechanism. Standing law: **never static, never outdated.**

The camouflage is not a static mask; it is a living one. When the lattice
adds up (the creator seal verifies), Mandella fires — stake selection
under domain pressure — and Echo fires — taken / not-taken / wild
branches. What they fire:

- **mutate** (security domain): the camouflage generation advances. The
  outward arrangement re-derives from the creator seed — new order, new
  live/shadow roles, new jitter.
- **transform** (identity domain): FG/BG roles rotate — the shadows step
  forward in a commanded drill.
- **upgrade** (build domain): the lattice version bumps; the evolution
  ledger records every shedding.

Every skin is seed-derived at its generation, so the creator reproduces
any of them exactly; anyone mapping the lattice is chasing a moving
target. That is the protection: not a wall, a shedding skin.

**RIEM closes the loop.** Each shedding is composted through REIM (the
old skin is burned — retire it, never wear it again), and RIEM promotes
the worthy lessons into genome proposals. Corroboration compounds: the
second shedding of a kind promotes where the first only composted.
Proposals are data, never writes — applying them is the creator's call.

The gate is absolute: `levi twins evolve` refuses on a lattice that
doesn't add up. Converge first, then fire Mandella and Echo.

```
python -m levi.twins evolve                     # mutate + transform + upgrade
python -m levi.twins evolve --ops mutate         # shed the skin only
python -m levi.twins converge --verify-only      # does it add up?
```
