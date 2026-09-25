# Factory receipt — queue-herald

- **Spec ID:** `genesis-002`
- **Kind:** `agent`
- **Minted:** 2026-09-24T16:20:00Z
- **Builder glyph:** 🌊 (coordinator-built proof-of-run)
- **Final name status:** provisional — awaits Chauncey's word

## Spec
- Source: factory bootstrap (coordinator 🌊)
- Laws declared: 4 (DynastyAgent subclass validity; gen-2 kin identity;
  advisory-only; SECTION 0 IP block)

## Build
- `core/levi/dynasty/wave/queueherald.py` — `QueueHerald(DynastyAgent)`,
  agent_id `queue-herald`, generation 2, commissioned_by `factory-genesis`,
  `watch()` + `nudge()` (read-only; dispatches nothing)
- `core/levi/dynasty/wave/__init__.py` — exported as `QueueHerald`
- Commits: (see commit below)
- Glyph trailer verified: yes

## Proof
- Instantiation proof: `QueueHerald(home=tmp)` constructs cleanly;
  `first_task()` returns the queue state dict
- Registry verification: `mint_agent()` → verified True
  (agent_id `queue-herald`, generation 2, commissioned_by `factory-genesis`)
- Wave import check: eleven intact (`Herald` still imports as `herald`)
- Laws proved: 4/4

## Registry
- Agent: banked as `queue-herald` — kin of the line, NOT one of the eleven
  (generation 1, commissioned by the keeper, untouched)

## Gated (still needs his word)
- Final agent name (naming sovereignty — display name stays provisional)
- Any dynasty seat (none assigned; seating is his word)

## Notes
- Advisory-only: watches the intake queue, drafts stall nudges; never
  dispatches builders, never mutates the queue.
- Dynasty eyes-only: SECTION 0 block carried; stays in the local repo.
