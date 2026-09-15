---
skill_id: cyber_implementing_rsa_key_pair_management
name: Implementing RSA Key Pair Management
description: Manage RSA key pairs across their lifecycle — secure generation, storage, rotation, and deprecation planning as the industry moves to post-quantum cryptography.
risk: info
permissions: []
requires_confirmation: false
tags: [cryptography, key-management, pki]
version: 1.0.0
---
## Purpose

Treat RSA key pairs as the critical secrets they are: generated securely, stored in hardware or vaults, rotated on schedule, inventoried completely, and retired deliberately. This playbook covers the full lifecycle for RSA keys used in TLS, SSH, code signing, and document signing — plus the forward-looking work of crypto-agility as RSA-2048 faces its long sunset toward post-quantum algorithms.

## When to use

- Establishing key-management discipline where keys currently live in home directories and wikis.
- Meeting key-management requirements (PCI DSS 4.0 Req 3.6–3.7, NIST SP 800-57).
- Auditing SSH authorized_keys and TLS certificate sprawl across the estate.
- Planning rotation after personnel departures or suspected compromise.
- Beginning post-quantum readiness: inventorying where RSA is used so migration is plannable.

## Prerequisites

- Inventory of RSA key usage: TLS certificates, SSH keys, signing keys, application keystores — with owners.
- HSM, KMS, or secrets-manager infrastructure for private-key storage (private keys on filesystems are the finding you're remediating).
- Defined key strengths and lifetimes per use case (2048-bit minimum, 3072+/4096 for long-lived CA/signing keys).
- Certificate lifecycle tooling (ACME, internal CA with automation) for TLS; SSH certificate authority or key-management tooling for SSH.
- Crypto-agility awareness: know which systems can and cannot change algorithms — that's your PQC migration constraint map.

## Procedure

1. **Inventory every RSA key pair.** Scan for: TLS private keys on servers and load balancers, SSH keys in authorized_keys and known_hosts across the fleet, code-signing keys, and keys embedded in applications and CI systems. Record algorithm, bit length, creation date, owner, and location. Unknown keys get investigated — unowned keys are either forgotten (rotate and remove) or malicious (incident).
2. **Generate correctly.** Use a CSPRNG via vetted tooling (`openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072`, or HSM/KMS generation where the key never leaves hardware). Minimum 2048 bits for short-lived, 3072+ for anything long-lived or CA-related. Never reuse a key pair across purposes — the TLS key is not the SSH key is not the signing key.
3. **Store private keys in hardware or vaults.** HSMs for CA and code-signing keys; KMS/secrets manager for application TLS keys with access logging; SSH keys in hardware tokens (FIDO2 resident keys, PIV) for interactive use. Filesystem private keys get migrated or, where unavoidable, protected with strict permissions (0400, dedicated user) and documented as exceptions.
4. **Rotate on schedule and on trigger.** Define lifetimes: TLS via automated ACME (90-day), SSH user keys annually (or move to SSH certificates with hours-long validity), signing keys per policy with ceremony. Trigger immediate rotation on: personnel departure with key access, suspected compromise, or key discovered outside its approved storage. Rotation must include verifying the old key no longer works anywhere.
5. **Tame SSH key sprawl specifically.** Deploy SSH certificates (short-lived, CA-signed) to replace static authorized_keys where feasible; where not, centrally manage authorized_keys, remove keys of departed staff within 24 hours, and prohibit key sharing. SSH keys are the most neglected credential class in most estates — assume yours are too until proven otherwise.
6. **Manage the certificate lifecycle.** Automate issuance and renewal (ACME for public, automated internal CA for private), monitor expiries with alerting (expired certs cause outages, not just findings), and maintain the CA hierarchy with offline roots and documented ceremonies for root operations.
7. **Plan the post-quantum transition.** Inventory RSA usage by system with algorithm-agility notes (can this TLS stack do hybrid key exchange? can this HSM?). Follow NIST's PQC standards (ML-KEM, ML-DSA) and begin hybrid deployments where supported. RSA-2048 isn't broken today, but migration takes years — the inventory you build now is the migration plan later.
8. **Audit and report.** Annual key inventory reconciliation, rotation-compliance reporting, and exception review. Metrics: % of keys in approved storage, rotation SLA compliance, unknown-key count trending to zero, certificate expiry incidents (target: zero).

## Expected outputs

- Complete RSA key inventory with owners, strengths, and locations.
- Generation, storage, and rotation standards per use case.
- SSH key management (certificates or centralized authorized_keys) with leaver-process integration.
- Automated certificate lifecycle with expiry monitoring.
- PQC readiness inventory noting algorithm-agility per system.

## Pitfalls

- **Keys in code and wikis.** Private keys in git history, chat logs, and documentation are compromised keys — rotate them and purge, then add secret scanning to prevent recurrence.
- **Shared keys across purposes.** One key for TLS, SSH, and signing means one compromise breaks everything and rotation is terrifying. Separate by purpose from birth.
- **Rotation without verification.** Rotating the key in the vault while the old key remains in authorized_keys on 200 servers is rotation theater. Verify the old key is dead everywhere.
- **Ignoring SSH.** Teams diligently rotate TLS certs while decade-old SSH keys accumulate in authorized_keys. Attackers know this asymmetry.
- **PQC procrastination.** "Quantum is years away" was also said about SHA-1 deprecation timelines. Inventory and agility work starts now; the cryptography migration is the easy part compared to finding all the keys.

## References

- NIST SP 800-57 Part 1 Rev. 5, "Recommendation for Key Management" — https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final
- NIST post-quantum cryptography standards — https://csrc.nist.gov/projects/post-quantum-cryptography
- PCI DSS v4.0 Requirements 3.6–3.7 (key management) — https://www.pcisecuritystandards.org/
- OpenSSH certificate documentation — https://www.openssh.com/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
