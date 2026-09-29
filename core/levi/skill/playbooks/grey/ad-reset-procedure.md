---
skill_id: grey_ad_reset_procedure
name: Active Directory Reset Procedure
description: Reset the lab AD forest to its baseline between exercise iterations.
risk: high
permissions: []
requires_confirmation: true
tags: [grey-team, resets, active-directory, forest]
version: 1.0.0
team: grey
---
# Active Directory Reset Procedure

## Purpose

AD accumulates the most persistent exercise artifacts: backdoor accounts, Golden
Tickets, modified ACLs, replication metadata. This procedure resets the lab forest to
its baseline — authoritative restore or rebuild — between iterations.

## When to use

- Between AD-focused exercise iterations.
- After domain-compromise scenarios.
- When AD state can't be trusted.

## Prerequisites

- Baseline DC snapshots or rebuild scripts verified.
- Exercise data archived.
- Explicit reset authorization.
- All teams off the range.

## Procedure

1. Confirm authorization and the reset method (snapshot restore vs. authoritative rebuild).
2. Archive AD exercise data: event logs, replication metadata of interest, the attack
   timeline.
3. Execute the reset: restore DC snapshots in the correct order or rebuild from scripts.
4. Verify the reset: account inventory vs. baseline, ACL spot-checks, replication health,
   no residual exercise artifacts.
5. Re-verify auditing and log forwarding post-reset.
6. Sign off the clean forest with the exercise director.

## Expected outputs

- AD reset execution log.
- Baseline-verification results.
- Clean-forest sign-off.

## Pitfalls

- Resetting DCs out of order — replication will punish you.
- Assuming the rebuild scripts still work — test them before the exercise, not during
  reset.
- Residual exercise accounts — verify the account inventory against baseline.

## References

- Microsoft AD DS recovery documentation.

## Exercise role

The AD reset is the forest's clean slate — verified account by account, because AD
remembers everything.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
