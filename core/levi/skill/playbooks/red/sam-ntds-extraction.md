---
skill_id: red_sam_ntds_extraction
name: SAM/NTDS Extraction Test
description: Test SAM and NTDS.dit extraction paths to validate DC hardening and backup security.
risk: high
permissions: []
requires_confirmation: true
tags: [red-team, credential-access, sam, ntds, active-directory]
version: 1.0.0
team: red
tests_blue: cyber_detecting_t1003_credential_dumping_with_edr
---
# SAM/NTDS Extraction Test

## Purpose

The SAM and NTDS.dit are the credential databases; extracting them is total credential
compromise. This test validates the extraction paths — registry hive saves, VSS copies,
DCSync alternatives — and the DC/backup hardening that should block them.

## When to use

- During credential-access phases with elevated access.
- To validate domain-controller hardening and backup-file security.
- Lab-preferred; production DCs only with explicit approval.

## Prerequisites

- Authorization for the target tier; lab preferred for NTDS.dit.
- Strict credential-material handling per the ROE.

## Procedure

1. Test SAM extraction paths on a member host: reg save of SAM/SYSTEM hives with authorized
   privileges.
2. Test NTDS.dit paths in the lab: VSS snapshot copy, ntdsutil snapshot — verify each
   step's telemetry.
3. Record detection per path: EDR alerts, 4662-style audit events, VSS creation alerts.
4. Handle all extracted material as credential material: lab-only analysis, destruction
   logged.
5. Audit backup locations for unprotected NTDS.dit/system-state copies — the real-world
   exposure.
6. Deliver the extraction-path matrix with DC-hardening and backup-security
   recommendations.

## Expected outputs

- Per-path extraction feasibility and detection results.
- Backup-location audit for credential-database exposure.
- Credential-material destruction log.

## Pitfalls

- Extracting production NTDS.dit without explicit approval — lab first, always.
- Backup copies of NTDS.dit forgotten in the audit — check backup storage, not just the
  DC.
- Leaving VSS snapshots behind — clean every snapshot created.

## References

- MITRE ATT&CK: OS Credential Dumping — SAM (T1003.002), NTDS (T1003.003).

## Blue-team control under test

This playbook validates their DC hardening and backup hygiene are under test — an
unprotected NTDS.dit in backups is a finding regardless of live extraction. Paired blue-
team counterpart: `cyber_detecting_t1003_credential_dumping_with_edr`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
