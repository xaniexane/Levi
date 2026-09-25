---
skill_id: cyber_performing_post_quantum_cryptography_migration
name: Post-Quantum Cryptography Migration
description: Plan and execute migration to quantum-resistant cryptography with a full inventory, prioritization, and crypto-agility roadmap.
risk: info
permissions: []
requires_confirmation: false
tags: [cryptography, pqc, planning]
version: 1.0.0
---

## Purpose
- Prepare the organization for the quantum threat with a structured migration to NIST-standardized post-quantum algorithms.
- Inventory where vulnerable public-key cryptography is used so migration effort can be scoped and prioritized.
- Build crypto-agility so future algorithm changes do not require another forklift migration.

## When to use
- When starting a multi-year PQC readiness program, ideally now given harvest-now-decrypt-later risk.
- When procuring long-lived systems or signing long-term contracts that should specify PQC support.
- When regulators, customers, or insurers begin asking about quantum readiness.
- After NIST finalizes standards, to move from planning to implementation.

## Prerequisites
- Executive sponsorship, since PQC migration touches applications, infrastructure, vendors, and PKI.
- A cryptography inventory or the tooling to build one: code scanners, network traffic analysis, and certificate inventories.
- Understanding of NIST PQC standards (ML-KEM, ML-DSA, SLH-DSA) and hybrid deployment approaches.
- Vendor roadmaps for critical products: operating systems, HSMs, VPNs, and TLS libraries.

## Procedure
1. Establish governance: a PQC program owner, stakeholder map, and reporting cadence to leadership.
2. Build the cryptography inventory: scan code, configurations, certificates, and network traffic for RSA, ECC, and Diffie-Hellman usage.
3. Classify inventory by data longevity and sensitivity; long-lived secrets face harvest-now-decrypt-later risk first.
4. Prioritize systems: external-facing TLS, VPNs, code signing, and long-term data protection lead the queue.
5. Evaluate vendor PQC roadmaps and contract language; push vendors without plans and plan replacements where needed.
6. Pilot hybrid key exchange (classical plus PQC) on non-critical systems to validate performance and interoperability.
7. Update PKI and certificate practices for PQC: larger keys and signatures affect protocols, storage, and HSM capacity.
8. Plan for constrained environments: embedded and OT devices may need hardware refresh rather than software update.
9. Build crypto-agility into standards and architectures: abstract algorithm selection so the next migration is configuration, not code.
10. Track progress with inventory coverage and migration milestones reported to leadership regularly.

## Expected outputs
- A cryptography inventory with quantum-risk classification.
- A phased PQC migration roadmap with priorities, owners, and timelines.
- Vendor requirements and crypto-agility design principles for new systems.
- A PQC readiness dashboard tracking inventory coverage and migration milestones.
- Updated procurement and architecture standards mandating crypto-agility.

## Pitfalls
- Treating PQC as a future problem; harvest-now-decrypt-later means long-lived data is at risk today.
- Migrating without an inventory, which guarantees missed systems and wasted effort.
- Ignoring performance and size impacts of PQC algorithms on constrained devices and high-throughput systems.
- Waiting for every vendor instead of deploying hybrid approaches where the organization controls both endpoints.

## References
- ETSI quantum-safe cryptography migration guidance
- NIST post-quantum cryptography project and FIPS 203, 204, 205
- NIST IR 8547 on transitioning to PQC standards
- CNSA 2.0 timelines for national security systems
- IETF drafts on hybrid key exchange in TLS
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
