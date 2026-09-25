---
skill_id: cyber_validating_backup_integrity_for_recovery
name: Validating Backup Integrity for Recovery
description: Prove backups are restorable: integrity checks, test restores, immutability verification, and RPO validation.
risk: info
permissions: []
requires_confirmation: false
tags: [resilience, backup, recovery]
version: 1.0.0
---
## Purpose
Backups that have never been validated are hopes, not controls. This playbook establishes backup integrity validation: cryptographic integrity checks, regular test restores, immutability and offline-copy verification, and RPO measurement, so recovery works when ransomware or disaster strikes.

## When to use
- Backup program assurance review or audit.
- After backup infrastructure or software changes.
- Following any backup failure or corruption event.
- Pre-ransomware-season readiness validation.

## Prerequisites
- Backup inventory: systems, schedules, retention, and storage locations.
- Isolated restore test environment.
- Immutability/offline copy configuration details.
- Defined RPO/RTO targets per data tier.

## Procedure
1. Inventory all backup jobs: scope, frequency, retention, destination, and encryption status.
2. Verify backup job success rates over 90 days; investigate recurring warnings, not just failures.
3. Run cryptographic integrity verification (checksums/verification passes) on a sample of backup sets.
4. Perform test restores of tier-1 systems into the isolated environment quarterly at minimum.
5. Validate restored data: application startup, record counts, and spot-checks against production.
6. Verify immutability locks and offline/air-gapped copies exist, are current, and are inaccessible from production credentials.
7. Measure actual RPO: how much data would be lost if recovery started now; compare to targets.
8. Document results, remediate gaps (missing systems, failed verifications), and trend metrics over time.
9. Verify that backup encryption keys are themselves backed up and recoverable offline.
10. Treat backup consoles as tier-0 assets; ransomware targets them first.
11. Test granular (file/mailbox-level) restores, not just full-system restores.

## Expected outputs
- Backup validation report: integrity, restore, and immutability results.
- Measured RPO/RTO vs targets per tier.
- Gap remediation backlog with owners.
- Key-escrow verification for backup encryption.
- Backup-console hardening assessment.
- Granular restore test results.

## Pitfalls
- 'Backup succeeded' does not mean 'restore works'; only test restores prove recovery.
- Backups reachable with domain credentials are encrypted with the domain; verify separation.
- Untested restores of databases often fail on log replay or version mismatch; test the full chain.
- Retention policies that expire the only clean copy before an incident is discovered are a real failure mode.
- Ransomware increasingly targets backup consoles first; harden and monitor them as tier-0.
- Encryption keys stored only alongside the backups are lost with them; escrow offline.
- Granular restores fail differently than full restores; test both.
- Backup test restores should include bare-metal scenarios, not just file-level recovery.

## References
- NIST SP 800-34 Rev. 1, Contingency Planning Guide.
- NIST Cybersecurity Framework: Recover function (RC.RP).
- CISA StopRansomware Guide (backup guidance).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
