# PREMORTEM — the pre-mortem ritual

**Purpose.** Before a big commitment, a structured "imagine it
failed" cause-listing. The ritual assumes the failure already
happened and harvests causes — then ranks them and emits a
mitigation checklist. It is the cheapest insurance LEVI sells:
ten minutes of imagination before months of commitment.

**Why it exists.** Post-mortems are honest but late. Planning
reviews are early but defensive — nobody wants to attack their own
plan in front of the room. The pre-mortem sidesteps the defensiveness
by granting the failure as a premise: *it's a year from now and this
died — why?* People who won't criticize a plan will happily
autopsy a corpse.

## Red team vs pre-mortem (binding distinction)

These are different rituals and must not be conflated:

- **Red team attacks the plan's LOGIC.** It argues the strategy is
  wrong, the assumptions are false, the sequencing is broken. It
  debates the plan while the plan is still hypothetical. Adversarial,
  dialectical, aimed at the plan's reasoning.
- **Pre-mortem assumes failure ALREADY HAPPENED and harvests
  causes.** It does not argue with the plan; it lists what killed
  it. No debate, no defense — just causes, scored and ranked.

Red-teaming asks *"is this plan right?"*; pre-mortem asks *"given it
died, what killed it?"*. Run the red team to stress the plan; run
the pre-mortem to insure against its death. A plan can survive a
red team and still die of a cause nobody listed.

## Honesty contract

- `likelihood` and `impact` are **integers 1–5, stated by the
  human**. The module never invents them and never defaults them
  silently — missing or out-of-range scores are rejected
  (`ValueError`; bools are not ints).
- Ranking is arithmetic: **risk = likelihood × impact**, ties broken
  by impact, then by order added. No hidden weighting.
- A **closed session is immutable**: closing or adding causes to a
  closed session is refused, so the ritual cannot be quietly
  rewritten after the fact.
- The checklist is a *prompt* to write mitigations, not a mitigation
  itself: causes without a stated mitigation are flagged
  **UNMITIGATED** rather than silently treated as handled.

## API

```python
from levi.premortem.ritual import Premortem

pm = Premortem()  # $LEVI_HOME/premortem/sessions.json (else ~/.levi)

s = pm.begin("rewrite the billing system")  # open the session
pm.add_cause(
    s.id,
    "double-billing on retry",
    likelihood=4,
    impact=5,
    mitigation="idempotency keys on every charge",
)
pm.add_cause(s.id, "migration locks the ledger", likelihood=3, impact=5)

result = pm.close(s.id)  # rank + checklist; session now immutable
# {"session_id": ..., "task": ..., "n_causes": 2, "top_risk": 20,
#  "ranked": [{"cause": ..., "likelihood": 4, "impact": 5, "risk": 20,
#              "mitigated": True, "item": "[ ] risk 20 — ..."}, ...],
#  "checklist": ["[ ] risk 20 — double-billing on retry → mitigate: ...",
#                "[ ] risk 15 — migration locks the ledger → UNMITIGATED: ..."],
#  "unmitigated": 1}

print(pm.format_close(result))
pm.sessions(status="open")  # list sessions
```

## CLI

```bash
python -m levi.premortem begin "rewrite the billing system"
python -m levi.premortem cause pm-1a2b3c4d "double-billing on retry" \
    --likelihood 4 --impact 5 --mitigation "idempotency keys"
python -m levi.premortem close pm-1a2b3c4d
python -m levi.premortem list [--status open]
```

## Suggested instinct specs

```yaml
# Before a big commitment locks, prompt the ritual.
- id: instinct.premortem_before_lock
  fires_on: commitments.big_locked==true
  cooldown: 0             # fires on every big lock; each deserves its own autopsy
  max_grade: ASK
  does: open a pre-mortem session on the commitment; walk likelihood/impact per cause

# If a session closes with unmitigated top risks, do not let it slide.
- id: instinct.premortem_unmitigated
  fires_on: premortem.unmitigated_top>=1
  cooldown: 86400
  max_grade: ASK
  does: list unmitigated causes risk-desc; ask for a mitigation or an explicit accept
```

**Storage:** `$LEVI_HOME/premortem/sessions.json` (else `~/.levi`).
**Deps:** stdlib only.
