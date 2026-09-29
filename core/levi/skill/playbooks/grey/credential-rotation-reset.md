---
skill_id: grey_credential_rotation_reset
name: Exercise Credential Rotation Reset
description: Rotate all exercise credentials between iterations to prevent cross-contamination.
risk: moderate
permissions: []
requires_confirmation: true
tags: [grey-team, resets, credentials, rotation]
version: 1.0.0
team: grey
---
# Exercise Credential Rotation Reset

## Purpose

Exercise credentials leak across iterations: red learns them, participants remember
them, notes preserve them. This rotation resets every exercise credential between
iterations — accounts, service principals, API keys, canary secrets — so each iteration
starts clean.

## When to use

- Between exercise iterations.
- After any suspected credential exposure.
- Before a new team uses the range.

## Prerequisites

- Credential inventory for the range (every account, key, secret).
- Rotation tooling/scripts.
- Reset authorization.

## Procedure

1. Inventory every exercise credential: user accounts, service accounts, API keys,
   certificates, canary secrets.
2. Rotate all of them: new passwords, new keys, reissued certificates — per the inventory,
   no exceptions.
3. Update the credential vault/store the teams use; revoke the old material.
4. Verify the rotation: sample-authenticate with new credentials, confirm old ones fail.
5. Brief incoming teams on the new credential set.
6. Log the rotation with timestamps.

## Expected outputs

- Credential inventory with rotation status.
- Old-credential invalidation verification.
- Rotation log.

## Pitfalls

- Missed credentials — the inventory must be complete, or the rotation is theater.
- Old credentials still valid somewhere — verify invalidation, don't assume.
- Credentials shared outside the vault — rotate and re-brief the handling rules.

## References

- Credential-management literature.

## Exercise role

Credential rotation is the iteration boundary — every secret fresh, every old secret
dead, verified.

> **Exercise guard.** This is range-operations material for the grey team (exercise infrastructure). It builds, scores, observes, resets, or snapshots exercise environments. Destructive operations require confirmation. Invoking this skill only reads this playbook.
