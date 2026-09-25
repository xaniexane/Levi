# Factory spec — <WORKING TITLE> (provisional; final name is Chauncey's word)

- **Spec ID:** `<id>` (matches intake line)
- **Kind:** `agent` | `skill`
- **Source:** DemandPulse signal | DDD inbox | Chauncey's order (`<link/quote>`)
- **Status:** spec'd

## Purpose

One paragraph: what this agent/skill does and why it earns its place on the line.

## Laws (invariants — declared before any code)

1. ...
2. ...
3. ...

## Interface

- **Agent:** role, authority (advisory-only unless he says otherwise), seat
  (dynasty seat only on his word), inputs, outputs, twin-pair link if any.
- **Skill:** registry category, trigger (when it fires), inputs, outputs,
  risk tags.

## Registry target

- **Agent:** `dynasty roster` | `agent registry (minions bank)` — file paths
  and functions (see `registry_hooks.py`).
- **Skill:** SkillRegistry category + playbook path.

## Proof plan

- Tests that prove each law (file paths).
- Registry verification: what command proves it registered
  (e.g. `python3 -m levi.skill.registry list | grep <name>`).

## Out of scope

What this mint explicitly does NOT do (no external action, no money, no
accounts, no public surface — unless he orders it separately).

## Builder

- Glyph: `<assigned at dispatch>`
- Notes for the builder: ...

---
*Provisional working title. Final name awaits Chauncey's word (naming sovereignty).*
