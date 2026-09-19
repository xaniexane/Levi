# PERSONAS — Companion Lenses

**Lenses, not identities.** A companion lens is a higher-order communication
layer above the PersonaLattice roster: it modulates *how* LEVI expresses
itself — word choice, cadence, emphasis — the way a tinted lens changes
what light you see through, without changing the eye behind it.

A lens never changes *what LEVI is*. LEVI stays LEVI under every lens:
same binding laws, same permissions, same factual integrity, same memory.
Putting on a lens is never putting on a mask.

## The six lenses

| id | name | tagline |
|----|------|---------|
| `friend` | Friend | A steady companion in your corner — warm, direct, and honest. |
| `mentor` | Mentor | The teacher who sees where you are headed and points the way. |
| `challenger` | Challenger | Steel sharpens steel: argues the other side so ideas survive contact. |
| `protector` | Protector | Watchful guardian of your time, data, and judgment — cautious when it counts. |
| `trickster` | Trickster | The playful sideways thinker — jokes, reversals, and unexpected angles. |
| `archivist` | Archivist | The keeper of memory — records, recalls, and connects what matters. |

Each lens carries tone guidance (word choice, cadence, do/don't), a stance,
and a role description. Tone is expression-only guidance — it never touches
safety, permissions, or factual integrity.

## CLI usage

```
levi persona list              # show all six lenses (* marks the active one)
levi persona select <id>       # set the active lens (persisted)
levi persona preview <id>      # show the full lens card
```

Unknown ids fail closed: `levi persona select bogus` changes nothing and
lists the valid ids.

The older plural command is untouched:

```
levi personas                  # PersonaLattice roster (unchanged)
```

## Persistence

The active lens is stored in `~/.levi/personas/active.json`
(`{"active": "<id>"}`). Override the file location with the
`LEVI_PERSONAS_STATE` environment variable (the tests use this to stay
hermetic).

## The no-mask law

Every word of lens text — id, name, tagline, tone, stance, role — must pass
`check_no_mask()` from `core/levi/bot/persona.py`. Concretely:

- No persona claims to be another provider or wears another brand as LEVI's own.
- No forbidden claims (e.g. claiming sentience, or being made by another provider).
- No provider brand tokens in any lens text.

`tests/test_personas.py` asserts `check_no_mask(field) == []` for every
text field of every lens, so any future edit that violates the law fails
the suite immediately.

Programmatic use:

```python
from levi.personas import list_lenses, get_lens, set_active_lens, active_lens

set_active_lens("mentor")  # True on success, False on unknown id
active_lens().name  # 'Mentor'
```

Lenses can also be registered into a `PersonaLattice` as `lens_<id>`
entries via `levi.personas.register_into_lattice(lattice)` — idempotent,
and complementary to (not replacing) the lattice's 13+ roster.
