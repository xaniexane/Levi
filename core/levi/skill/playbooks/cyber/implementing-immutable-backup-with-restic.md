---
skill_id: cyber_implementing_immutable_backup_with_restic
name: Implementing Immutable Backup with Restic
description: Build ransomware-resistant backups with restic using append-only repositories and S3 Object Lock immutability, plus tested restore procedures.
risk: low
permissions: []
requires_confirmation: false
tags: [backup, ransomware, recovery]
version: 1.0.0
---
## Purpose

Make backups survive the attacker, not just the disk failure. Restic provides encrypted, deduplicated backups; combined with an append-only repository server and S3 Object Lock (compliance mode) immutability, even an adversary holding your backup credentials cannot delete or alter retained snapshots within the retention window — preserving the last clean recovery path during ransomware.

## When to use

- Designing backup infrastructure explicitly to withstand ransomware that targets backups first.
- Replacing backup tooling that stores credentials on the protected hosts (a single compromise then wipes all backups).
- Meeting 3-2-1-1-0 expectations (3 copies, 2 media, 1 offsite, 1 offline/air-gapped or immutable, 0 errors verified by restore tests).
- Protecting source code, infrastructure state, and critical data where rebuild-from-scratch is not viable.
- Any environment where backup deletion would be a business-ending event.

## Prerequisites

- S3-compatible storage supporting Object Lock (AWS S3, MinIO with locking enabled at bucket creation — Object Lock cannot be added to an existing bucket).
- A dedicated restic repository server (`rest-server`) running in append-only mode, on infrastructure with separate credentials from the protected hosts.
- KMS-managed encryption keys for restic repositories, stored outside the backup path (never on the hosts being backed up).
- Defined retention and immutability windows aligned with business RPO/RTO and compliance needs.
- An isolated restore-test environment that does not depend on production to function.

## Procedure

1. **Create the Object Lock bucket first.** Object Lock must be enabled at bucket creation and set to Compliance mode for the retention period — Governance mode can be overridden by a privileged attacker, Compliance mode cannot, even by the root account. Document the retention window decision and its legal basis.
2. **Deploy rest-server in append-only mode.** Run the restic REST server with `--no-verify-upload` off and append-only enabled so clients can add snapshots but never delete them. The server's credentials differ from the S3 credentials; compromise of a client yields no deletion path.
3. **Initialize repositories with strong encryption:**
   ```bash
   export RESTIC_REPOSITORY="rest:https://backup.example.com/host1"
   export RESTIC_PASSWORD_COMMAND="vault kv get -field=password secret/restic/host1"
   restic init
   ```
   Never store the repository password on the backed-up host in plaintext; pull it from a secrets manager at backup time.
4. **Schedule backups with pre/post hooks.** Snapshot on a schedule meeting RPO, excluding caches and ephemeral data to control size. Run `restic check` after each backup and alert on failures — a silently failing backup is discovered exactly when you need it.
5. **Apply retention on the server side only.** Run `restic forget --prune` from a dedicated admin host holding separate credentials, never from the clients. With Object Lock, pruning only removes metadata for expired snapshots; locked objects persist until retention expires, which is the point.
6. **Segregate credentials aggressively.** Backup clients get append-only credentials; the pruning/admin identity is separate and MFA-protected; the S3 bucket policy denies `s3:BypassGovernanceRetention` and deletion to everyone during the lock window. No single compromised credential set should permit backup destruction.
7. **Test restores on a schedule.** Quarterly, restore a full system and a granular file set into the isolated environment and verify integrity (`restic check`, application smoke tests, checksum spot-checks). Record RTO actually achieved versus the target.
8. **Protect the backup infrastructure itself.** Harden the rest-server host, monitor its logs for anomalous access, and keep an offline copy of repository passwords/keys in a safe — losing the password with perfect immutability is just a slower disaster.

## Expected outputs

- Object Lock Compliance-mode buckets with documented retention windows.
- Append-only rest-server deployment with segregated client/admin credentials.
- Scheduled, monitored backup jobs with post-backup integrity checks.
- Quarterly restore-test reports with measured RTO.
- Runbook for full-environment restore under ransomware conditions.

## Pitfalls

- **Governance mode instead of Compliance.** Governance mode allows privileged users to bypass retention — exactly the privilege ransomware seeks. Use Compliance mode for ransomware resistance.
- **Passwords on the protected host.** A restic password in a root-readable file on the backed-up server hands the attacker your backups. Fetch from a secrets manager at runtime.
- **Prune from clients.** Giving clients prune rights reintroduces deletion; keep forget/prune on the admin host.
- **Untested restores.** Encrypted, immutable, deduplicated garbage is still garbage. Restore tests are the only proof the system works.
- **Retention shorter than dwell time.** If attackers dwell 200 days and your immutability window is 90, the clean snapshots are gone. Set retention from threat-informed dwell-time assumptions, not disk budgets.

## References

- Restic documentation — https://restic.readthedocs.io/
- AWS S3 Object Lock documentation — https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
- NIST SP 800-209, "Security Guidelines for Storage Infrastructure" — https://csrc.nist.gov/publications/detail/sp/800-209/final
- MITRE ATT&CK T1490 (Inhibit System Recovery) — https://attack.mitre.org/techniques/T1490/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
