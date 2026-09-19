# The Seven Worlds

A human life spans seven worlds simultaneously — none isolated, none
optional. Adapted from the OMEGA Canon's 7 Core Worlds (Grand Master
Record, Section 6). LEVI-native original implementation.

**Ordering law:** Identity (World 7) is listed last but is FIRST — every
other world is an expression of it.

| ID | World | Domain |
|----|-------|--------|
| identity | Identity World | who you are across all worlds and all eras |
| physical | Physical World | home, work, errands, body |
| digital | Digital World | files, apps, accounts, devices |
| internal | Internal World | stress, energy, mood, cognitive load |
| social | Social World | relationships, communication |
| opportunity | Opportunity World | goals, paths, future states, income |
| frontier | Frontier World | augmented layers, hybrid environments |

## CLI

```bash
PYTHONPATH=core python -m levi.worlds list
PYTHONPATH=core python -m levi.worlds classify --text "job interview tomorrow"
PYTHONPATH=core python -m levi.worlds checkin --world internal --note "low energy today"
PYTHONPATH=core python -m levi.worlds recent --world internal
```

Check-ins append to `~/.levi/worlds/checkins.jsonl` (owner-only, 0600).
