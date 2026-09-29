# Factory spec — ddd-inbox-watcher (provisional; final name is Chauncey's word)

- **Spec ID:** `genesis-004`
- **Kind:** `agent`
- **Source:** factory design (intake source #2 needs its watcher)
- **Status:** spec'd

## Purpose

Watches the DDD inbox (`~/workspace/ddd-inbox/`) for new briefs and drafts
factory specs from them. A kin of the dynasty line (generation 2,
commissioned by factory-genesis — NOT one of the eleven). Advisory-only: it
drafts specs as text; it never writes to the queue, never dispatches
builders, spends nothing.

## Laws (invariants)

1. Subclasses `DynastyAgent`; `agent_id == "ddd-inbox-watcher"`;
   proficiency values pass dna validation; every unreplicable attribute
   carries name + assertion.
2. `generation == 2`, `commissioned_by == "factory-genesis"` — kin of the
   line, distinct from the eleven.
3. Advisory only: drafts spec text from inbox briefs; dispatches nothing,
   mutates nothing, spends nothing, touches no accounts.
4. Carries the SECTION 0 Hybrid IP Protection block (dynasty eyes-only
   convention — this material never leaves the local repo).

## Interface

- **Agent:** role — DDD inbox watcher; authority — advisory-only; seat —
  none (no dynasty seat; seating is Chauncey's word); inputs — inbox dir
  path; outputs — spec draft text per new brief; twin-pair link — none.

## Registry target

- New module `core/levi/dynasty/wave/dddinboxwatcher.py`
  (`DDDInboxWatcher`), exported from
  `core/levi/dynasty/wave/__init__.py`.

## Proof plan

- Instantiation proof: `DDDInboxWatcher(home=tmp)` constructs;
  `agent_id`, `generation`, `commissioned_by` assert as specified;
  `first_task()` returns inbox status dict.
- `python3 -c "from levi.dynasty.wave import DDDInboxWatcher;
  print(DDDInboxWatcher.agent_id)"` → `ddd-inbox-watcher`.

## Out of scope

No builder dispatch, no queue mutation, no external action, no seat, no
final name (naming sovereignty: provisional until his word).

## Builder

- Glyph: 🧵

---
*Provisional working title. Final name awaits Chauncey's word (naming sovereignty).*
