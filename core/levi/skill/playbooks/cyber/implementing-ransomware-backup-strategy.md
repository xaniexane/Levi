---
skill_id: cyber_implementing_ransomware_backup_strategy
name: Implementing Ransomware Backup Strategy
description: Design backups to survive ransomware — 3-2-1-1-0 architecture, immutability, offline copies, and restore drills that prove recovery works.
risk: low
permissions: []
requires_confirmation: false
tags: [backup, ransomware, recovery, resilience]
version: 1.0.0
---
## Purpose

Make ransomware's leverage — "pay or lose your data" — false. A ransomware-resistant backup strategy follows 3-2-1-1-0 (three copies, two media types, one offsite, one offline/air-gapped or immutable, zero errors verified by testing), with the explicit design goal that an attacker holding domain admin cannot destroy or encrypt the recovery path.

## When to use

- Building backup infrastructure where ransomware is in the threat model (which is everywhere).
- After ransomware incidents revealed backups were encrypted, deleted, or never tested.
- Meeting recovery expectations (cyber-insurance, regulators, board-level resilience questions).
- Protecting virtualization, Active Directory, databases, and SaaS data (M365/Google Workspace backups are routinely forgotten).
- Validating that existing backups would actually restore under adversarial conditions.

## Prerequisites

- Critical data and system inventory prioritized by recovery priority (what restores first is a business decision, not an IT one).
- Defined RPO/RTO per tier, agreed with business owners — the strategy is engineered to these numbers.
- Backup infrastructure separated from production identity: separate admin credentials, ideally separate identity provider or offline admin accounts.
- Offline/air-gap capable storage or immutable cloud storage (S3 Object Lock compliance mode, immutable vaults).
- Isolated restore-test environment.

## Procedure

1. **Architect 3-2-1-1-0.** Three copies of critical data, on two different media/technologies, one offsite, one offline/air-gapped or immutable — and zero backup errors, verified by actual restore tests. Map every critical system to this model and document which copy serves which recovery scenario (file restore, system rebuild, site loss, ransomware).
2. **Isolate backup credentials and control plane.** Backup admin accounts must not be domain accounts an attacker compromises alongside everything else: dedicated backup-admin credentials in the PAM vault, MFA enforced, and the backup console unreachable from the production network except through the PAM jump path. Attackers target backup infrastructure deliberately and early.
3. **Make deletion impossible for attackers.** Enable immutability (Object Lock compliance mode, immutable backup vaults) with retention exceeding maximum expected dwell time; maintain a true offline/air-gapped copy (tape, rotated external media, or cloud vault with multi-person authorization for deletion). Test that a simulated-compromised admin cannot delete retained backups — red-team the backup system specifically.
4. **Protect the often-forgotten systems.** Include in scope: Active Directory (system-state backups with tested forest recovery — rebuilding AD wrong extends outages by days), virtualization control planes, network device configurations, SaaS data (M365/Workspace/Github — the provider's redundancy is not your backup), and encryption/key material (losing keys with perfect backups is still total loss).
5. **Harden backup jobs and monitoring.** Alert on: backup job failures, unexpected job configuration changes, backup size anomalies (sudden drops suggest exclusion tampering; spikes may indicate encryption-in-progress being backed up), and any deletion or retention-policy change attempts. Backup monitoring belongs in the SOC, not just with the backup admin.
6. **Document the recovery runbook per scenario.** Ransomware recovery runbooks differ from disaster recovery: assume the network is hostile, assume credentials are compromised, define the clean-room rebuild sequence (identity first, then backup infrastructure verification, then tier-by-tier restoration), and include the decision framework for ransom payment (legal, never as plan A).
7. **Drill restores quarterly.** Full-system restores into the isolated environment: measure actual RTO against targets, verify application integrity (not just "files restored"), and practice the AD forest recovery specifically — it's the most complex and most botched. Every drill produces findings; track them to closure.
8. **Review retention against dwell time.** Annually reassess: attacker dwell times in your sector, regulatory retention requirements, and storage costs. If median dwell time exceeds your immutable retention, the strategy has a hole — extend retention or add earlier detection, preferably both.

## Expected outputs

- 3-2-1-1-0 architecture document mapping systems to recovery scenarios.
- Isolated backup credentials and control plane with PAM integration.
- Immutability + offline/air-gapped copies with attacker-simulated deletion testing.
- Ransomware-specific recovery runbooks including clean-room rebuild sequence.
- Quarterly restore drill reports with measured RTO; annual retention review.

## Pitfalls

- **Backups on the domain.** Backup servers joined to the same AD the ransomware encrypts are not a recovery path — they're a target list. Isolate identity and network.
- **Untested restores.** The industry's most expensive fiction: "we have backups" that have never been restored. Ransomware is when you discover the backups are corrupt, incomplete, or encrypted too.
- **Retention shorter than dwell time.** Attackers dwell for months specifically to poison backups. Size immutability windows from threat-informed dwell assumptions.
- **Forgetting AD recovery.** Without Active Directory, nothing authenticates and nothing restores properly. AD forest recovery planning is non-optional and rarely practiced — practice it.
- **Backing up encrypted data unknowingly.** If ransomware encrypts files and the backup job dutifully backs up the encrypted versions over the good ones (without versioning/immutability), the backup is worthless. Versioning and immutability exist precisely for this.

## References

- CISA ransomware guide (backup and recovery guidance) — https://www.cisa.gov/stopransomware
- NIST SP 800-209, "Security Guidelines for Storage Infrastructure" — https://csrc.nist.gov/publications/detail/sp/800-209/final
- NIST SP 800-184, "Guide for Cybersecurity Event Recovery" — https://csrc.nist.gov/publications/detail/sp/800-184/final
- MITRE ATT&CK T1486 (Data Encrypted for Impact), T1490 (Inhibit System Recovery) — https://attack.mitre.org/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
