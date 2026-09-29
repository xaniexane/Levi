---
skill_id: grey_range_reset_procedure
name: Full Range Reset Procedure
description: Reset the entire exercise range to its pristine snapshot between iterations.
risk: high
permissions: []
requires_confirmation: true
tags: [grey-team, resets, range, hygiene]
version: 1.0.0
team: grey
---
# Full Range Reset Procedure

## Purpose

Between exercise iterations the range must return to pristine: red artifacts gone, blue
changes reverted, logs archived. This procedure resets the full range to its snapshot —
destructive by design, which is why it's HIGH risk with confirmation required.

## When to use

- Between exercise iterations.
- After destructive exercises.
- Before handing the range to the next team.

## Prerequisites

- Pristine snapshot verified restorable.
- Exercise data archived (logs, evidence, artifacts).
- Explicit reset authorization with the scope confirmed.
- All teams notified and off the range.

## Procedure

1. Confirm authorization and scope: which segments reset, what is preserved (archived
   evidence).
2. Verify the pristine snapshot integrity before touching anything.
3. Archive any unarchived exercise data — reset destroys, archiving preserves.
4. Execute the reset: restore snapshots per the runbook order (network, identity,
   endpoints, services).
5. Verify the reset: pristine-state checks (hashes, service states, account lists) against
   the baseline.
6. Re-verify logging pipeline health post-reset.
7. Sign off the range-clean state with the exercise director.

## Expected outputs

- Reset execution log.
- Pristine-state verification results.
- Range-clean sign-off.

## Pitfalls

- Resetting before archiving — exercise data lost is an unrecoverable failure.
- Unverified snapshots — verify restorability before you need it.
- Partial resets leaving red artifacts — verify the full pristine state.

## References

- Range-operations literature.

## Exercise role

The full reset is the range's rebirth — destructive, verified, and never executed
without confirmed authorization.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
