---
skill_id: cyber_performing_ssl_certificate_lifecycle_management
name: SSL Certificate Lifecycle Management
description: Manage TLS certificate inventory, issuance, renewal, and revocation to prevent outages and weak configurations.
risk: low
permissions: []
requires_confirmation: false
tags: [tls, certificates, operations]
version: 1.0.0
---

## Purpose
- Prevent outages from expired certificates with complete inventory and automated renewal.
- Enforce consistent certificate standards: key sizes, validity periods, and approved CAs.
- Respond quickly to CA compromises or algorithm deprecations with an accurate inventory.

## When to use
- Continuously as an operational control, with periodic program reviews.
- When certificate-related outages occur, to fix the systemic cause.
- Before CA migrations, algorithm changes, or validity-period reductions.
- During audits that examine cryptographic controls.

## Prerequisites
- Discovery tooling or CA and CT-log data to build the certificate inventory.
- Defined certificate standards: approved CAs, key types and sizes, maximum validity.
- Automation capability: ACME or CA APIs integrated with deployment pipelines.
- Ownership assigned for every certificate or certificate group.

## Procedure
1. Build the inventory: scan networks, query CAs, and mine certificate transparency logs for organizational domains.
2. Reconcile discovered certificates against approved issuance records to find shadow IT certificates.
3. Assign an owner to every certificate and record its purpose, environment, and renewal method.
4. Define standards: minimum key sizes, approved signature algorithms, maximum validity periods, and approved CAs.
5. Automate renewal with ACME or CA APIs, integrated into deployment so new certificates actually get installed.
6. Set up expiry alerting with escalating notifications at 60, 30, 14, and 7 days.
7. Test renewal in non-production first, including the full chain and any pinned clients.
8. Document emergency issuance and revocation procedures for compromises and CA incidents.
9. Review wildcard and multi-SAN certificates for over-broad scope and reduce where possible.
10. Audit private key storage: HSMs or secure vaults, never in code repositories or shared drives.
11. Track metrics: expiry incidents, automation coverage, and time to remediate findings.
12. Review the program annually against evolving browser and CA requirements.

## Expected outputs
- A complete certificate inventory with owners and renewal automation status.
- Expiry alerting and emergency procedures.
- Metrics showing automation coverage and zero expiry incidents.
- A certificate policy document approved by security leadership.
- Post-quantum cryptography readiness notes for the certificate estate.

## Pitfalls
- Automating issuance but not installation; the new certificate must actually reach the server.
- Missing certificates on appliances, load balancers, and IoT devices outside standard discovery.
- Ignoring certificate transparency monitoring, which reveals unauthorized issuance.
- Letting automation credentials expire, silently breaking renewal.

## References
- Mozilla SSL configuration generator documentation
- CA/Browser Forum baseline requirements
- NIST SP 800-52 Guidelines for TLS
- Certificate transparency documentation, https://www.certificate-transparency.org/
- Vendor ACME and CA API documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
