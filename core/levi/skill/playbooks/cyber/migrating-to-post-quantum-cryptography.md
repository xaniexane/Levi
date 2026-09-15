---
skill_id: cyber_migrating_to_post_quantum_cryptography
name: Migrating to Post-Quantum Cryptography
description: Plan and execute migration to quantum-resistant cryptography across the estate.
risk: info
permissions: []
requires_confirmation: false
tags: [cryptography, post-quantum, migration]
version: 1.0.0
---
## Purpose
This playbook plans a post-quantum cryptography (PQC) migration: inventorying cryptographic dependencies, prioritizing by "harvest now, decrypt later" risk, and adopting NIST-standardized algorithms with hybrid deployments where prudent.

## When to use
- Long-lived encrypted data or long-lived products face harvest-now-decrypt-later risk.
- Procurement and product roadmaps need quantum-readiness requirements.
- Regulators or customers begin asking for PQC transition plans.

## Prerequisites
- Executive sponsorship: this is a multi-year program, not a patch cycle.
- Cryptographic inventory capability: code scanning, SBOMs, and protocol analysis.
- Tracking of NIST PQC standards (FIPS 203 ML-KEM, FIPS 204 ML-DSA, FIPS 205 SLH-DSA).

## Procedure
1. **Build the crypto inventory.** Discover where public-key cryptography is used: TLS libraries, VPNs, code signing, firmware, PKI, protocols, and vendor products; record algorithms, key sizes, and data lifetimes.
2. **Prioritize by risk.** Rank by data confidentiality lifetime and exposure: long-lived secrets and widely-distributed encrypted data first; short-lived session keys later.
3. **Demand crypto-agility.** For new development and procurements, require the ability to swap algorithms without re-architecting; avoid hardcoded algorithm assumptions.
4. **Adopt hybrid schemes first.** Where available, deploy hybrid key exchange (classical + PQC) to gain quantum resistance without abandoning battle-tested classical security.
5. **Migrate in waves.** Start with internal PKI and high-value systems, then customer-facing TLS, then embedded/long-lifecycle products; test interoperability at each wave.
6. **Update policies and contracts.** Add PQC requirements to security standards, vendor questionnaires, and product security baselines.
7. **Track and report.** Maintain a migration dashboard: percent of inventory assessed, hybrid-enabled, and fully migrated; report to the risk committee.

8. **Address symmetric crypto too.** Grover's algorithm halves effective symmetric key strength; plan AES-256 and SHA-384 as the long-term baselines alongside the PQC asymmetric migration.
9. **Coordinate with vendors.** Require PQC roadmaps from critical suppliers now; your migration is only as complete as your most stagnant vendor product.

## Expected outputs
- Cryptographic bill of materials with algorithm and lifetime data.
- Phased migration plan with hybrid-first approach and success criteria.
- Updated procurement and development standards requiring crypto-agility.
- Example: the CBOM reveals a 10-year-lifecycle VPN appliance using RSA-2048 for key exchange; it becomes a wave-one priority with a hybrid key-exchange upgrade path negotiated with the vendor.

## Pitfalls
- Waiting for "the perfect standard" while harvest-now-decrypt-later exposure accumulates.
- Migrating algorithms but leaving protocols that cannot negotiate them.
- Ignoring the long tail: firmware, IoT, and vendor appliances with decade-long lifecycles.

- Migrating to PQC algorithms but keeping the same weak key-management practices; the algorithm was never the weakest link.
- Underestimating performance impacts on constrained devices; benchmark handshake and verification costs on your actual hardware before committing.

## References
- NIST Post-Quantum Cryptography standards (csrc.nist.gov/projects/post-quantum-cryptography).
- NIST IR 8547 (initial public draft), Transition to Post-Quantum Cryptography Standards.
- IETF PQUIP working group drafts (datatracker.ietf.org/wg/pquip) — protocol integration guidance.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
