# Factory spec — queue-herald (provisional; final name is Chauncey's word)

- **Spec ID:** `genesis-002`
- **Kind:** `agent`
- **Source:** factory bootstrap (coordinator 🌊)
- **Status:** spec'd

## Purpose

The factory's first minted agent definition. A kin of the dynasty line
(generation 2, commissioned by factory-genesis — NOT one of the eleven).
Watches the factory intake queue and nudges the coordinator when specs sit
unbuilt past their turn. Advisory-only: it never dispatches builders itself.

## Laws (invariants)

1. Subclasses `DynastyAgent`; `agent_id == "queue-herald"`; proficiency values
   pass dna validation; every unreplicable attribute carries name + assertion.
2. `generation == 2`, `commissioned_by == "factory-genesis"` — kin of the line,
   distinct from the eleven (generation 1, commissioned by the keeper).
3. Advisory only: watches and nudges; dispatches nothing, spends nothing.
4. Carries the SECTION 0 Hybrid IP Protection block (dynasty eyes-only
   convention — this material never leaves the local repo).

## Interface

- **Agent:** role — intake queue watcher; authority — advisory-only; seat —
  none (no dynasty seat; seating is Chauncey's word); inputs — queue path;
  outputs — nudge text naming the oldest unbuilt spec; twin-pair link — none.

## Registry target

- New module `core/levi/dynasty/wave/queueherald.py` (`QueueHerald`),
  exported from `core/levi/dynasty/wave/__init__.py`.

## Proof plan

- Instantiation proof: `QueueHerald(home=tmp)` constructs without `AgentError`;
  `agent_id`, `generation`, `commissioned_by` assert as specified.
- `python3 -c "from levi.dynasty.wave import QueueHerald; print(QueueHerald.agent_id)"`
  → `queue-herald`.

## Out of scope

No builder dispatch, no queue mutation, no external action, no seat, no final
name (naming sovereignty: the display name stays provisional until his word).

## Builder

- Glyph: 🌊 (coordinator-built proof-of-run)

---
*Provisional working title. Final name awaits Chauncey's word (naming sovereignty).*
