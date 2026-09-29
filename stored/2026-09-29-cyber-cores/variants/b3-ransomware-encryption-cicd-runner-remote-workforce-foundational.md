---
skill_id: cyber_b3_ransomware_encryption_cicd_runner_remote_workforce_foundational
name: Ransomware Encryption Defense for CI/CD Runners in Remote Workforce (Foundational Maturity)
description: "Ransomware Encryption defense playbook for CI/CD Runners in Remote Workforce at Foundational maturity."
risk: moderate
permissions: []
requires_confirmation: true
tags: [malware, ransomware, devops, supply-chain, remote, endpoint, zero-trust, maturity-foundational]
version: 1.0.0
---
# Ransomware Encryption Defense for CI/CD Runners in Remote Workforce (Foundational Maturity)

## Purpose

Ransomware encrypts files and demands payment, usually after days of dwell time spent disabling recovery. Speed of isolation decides whether you lose one host or the fleet. Never pay without a deliberate, documented decision process. Applies to CI/CD Runners in Remote Workforce at Foundational maturity.

## When to use

- EDR fires on mass file rename/extension changes, vssadmin delete shadows, bcdedit recovery disabling, or known ransomware process names within seconds of each other.
- Ransom notes (README, DECRYPT files) appearing in multiple directories, wallpaper changes, or a sudden burst of encrypted file extensions across shares.
- Precursor activity in the prior 72 hours: disabled EDR tamper protection, cleared event logs, or backup job failures and backup-server logons from unusual accounts.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Identify the variant from the note text, extension, and ransom portal; check public decryptor availability before any recovery decision — some variants have free decryptors. Then: Reconstruct the entry vector (phishing, exposed RDP/VPN, software vulnerability) and the dwell timeline: first access, privilege escalation, backup targeting, detonation.
4. **Contain and harden.** Immutable, offline-tested backups with alerting on backup tampering; network segmentation so one host cannot reach all shares. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rebuilding from backups that the attacker already found and poisoned — verify backup integrity and isolation first.
- Paying the ransom without confirming the decryptor works and without legal/regulatory review of sanctions exposure.

## References

- MITRE ATT&CK: T1486 (Impact: Data Encrypted for Impact)
- Vendor logging and hardening baselines for CI/CD Runners; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
