---
skill_id: cyber_implementing_aes_encryption_for_data_at_rest
name: Implementing AES Encryption for Data at Rest
description: Deploy AES encryption for data at rest: algorithm/mode selection, key management lifecycle, and platform-native encryption controls.
risk: low
permissions: []
requires_confirmation: false
tags: [cryptography, data-protection, hardening]
version: 1.0.0
---
## Purpose

Encryption at rest protects data when storage media, backups, or cloud
volumes fall into the wrong hands. This playbook covers implementing AES
encryption correctly: choosing algorithms and modes, managing keys
through their lifecycle, using platform-native controls, and avoiding
the classic implementation mistakes that render encryption theater.

## When to use

- Designing encryption for databases, file storage, backups, and cloud
  volumes.
- Meeting compliance requirements for data-at-rest protection
  (PCI DSS, HIPAA, internal policy).
- Remediating audit findings on unencrypted sensitive storage.
- Reviewing existing encryption implementations for correctness.

## Prerequisites

- Data classification: know which data requires encryption and its
  residency requirements.
- Key-management capability: an HSM or managed KMS — never roll your
  own key storage in application code.
- Inventory of storage layers: databases, object storage, block
  volumes, backups, and endpoint disks.
- Threat model: who are you protecting against (theft, cloud-provider
  access, co-tenant) — it determines key-ownership choices.

## Procedure

1. **Choose AES-256 with an authenticated mode.** Standardize on
   AES-256-GCM (authenticated encryption) for new implementations;
   AES-256-CBC is acceptable only with separate HMAC and secure IV
   handling. Never use ECB mode — it leaks plaintext patterns.
2. **Use platform-native encryption first.** Prefer managed controls:
   cloud KMS-backed volume/disk encryption, database TDE, and
   OS-level full-disk encryption (BitLocker, FileVault, LUKS). They
   are audited, integrated with key management, and harder to misuse
   than hand-rolled crypto.
3. **Design the key hierarchy.** Implement envelope encryption: data
   encryption keys (DEKs) encrypt data, key-encryption keys (KEKs) in
   the KMS/HSM wrap DEKs. This enables rotation without re-encrypting
   all data and limits KMS call volume.
4. **Manage the key lifecycle.** Define key generation (CSPRNG in the
   HSM/KMS), rotation schedules, versioning, revocation procedures,
   and destruction (crypto-shredding for decommissioned data). Document
   who can administer keys — separation of duties between key admins
   and data admins.
5. **Protect keys in use and in transit.** Keys must never appear in
   logs, config files, or source control. Applications fetch DEKs at
   runtime from the KMS; use IAM policies to scope which principals
   can decrypt with which keys.
6. **Cover backups and replicas.** Encrypt backups with keys
   independent of production where possible, verify backup encryption
   actually works (restore tests), and ensure replicas, snapshots, and
   caches inherit encryption — attackers target the unencrypted copy.
7. **Validate the implementation.** Test: data files are unreadable
   without keys (inspect raw blocks), rotation works without downtime,
   revocation actually denies access, and key-access logging captures
   every decrypt operation for audit.
8. **Monitor and audit continuously.** Alert on anomalous KMS decrypt
   volumes, key-policy changes, and disabled/deleted keys; review key
   usage against data-access patterns as a detective control.

## Expected outputs

- An encryption standard: algorithms, modes, and key-hierarchy design.
- KMS/HSM configuration with lifecycle policies and access controls.
- Per-storage-layer implementation records with validation test
  results.
- Key-inventory and rotation schedule with ownership.
- Monitoring rules for key misuse and policy changes.

## Pitfalls

- ECB mode or homegrown ciphers — use standard authenticated modes
   from vetted libraries only.
- Hardcoded keys in code or config — the most common real-world
   failure; use KMS-backed envelope encryption.
- Encrypting the database but not the backups — attackers take the
   unencrypted copy.
- No rotation or revocation plan — keys leak eventually; plan for it.
- Confusing encryption at rest with access control — encrypted data
   with broad decrypt permissions is barely protected; scope KMS
   policies tightly.

## References

- NIST SP 800-38D: GCM mode; SP 800-38A: block-cipher modes
- NIST SP 800-57: key-management lifecycle guidance
- Cloud provider KMS/HSM documentation
- PCI DSS / HIPAA encryption-at-rest requirement guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
