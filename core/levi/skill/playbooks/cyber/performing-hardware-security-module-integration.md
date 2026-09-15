---
skill_id: cyber_performing_hardware_security_module_integration
name: Hardware Security Module Integration
description: Integrate HSMs for key custody: provisioning, access control, and audit.
risk: low
permissions: []
requires_confirmation: false
tags: [cryptography, hsm, key-management]
version: 1.0.0
---
# Hardware Security Module Integration

## Purpose

Keys that live in application memory or on disk are one breach away from
exposure. Hardware Security Modules keep private keys inside tamper-
resistant hardware and perform operations there. This playbook covers
integrating an HSM — cloud or on-premises — with correct key custody,
access control, and auditing.

## When to use

- Protecting CA keys, code-signing keys, or TLS private keys.
- Meeting compliance requirements for key custody (PCI DSS, eIDAS).
- Replacing software keystores with hardware-backed storage.
- Designing key management for a new high-value service.

## Prerequisites

- An HSM selected and provisioned: cloud HSM (AWS CloudHSM, Azure
  Dedicated HSM, GCP Cloud HSM) or on-premises appliance, with network
  and administrative access established.
- A key-ceremony plan: who generates keys, who holds operator and
  administrator credentials, and how custody is documented.
- Application support for PKCS#11, JCE, CNG, or the cloud provider's
  KMS/HSM API.

## Procedure

1. Initialize the HSM per vendor guidance: set Security Officer and
   operator credentials, enable tamper-response policies, and record
   the initialization in the key-ceremony log.
2. Generate keys inside the HSM — never import plaintext private keys
   except during a documented migration, and then only through the
   vendor's secure import (wrapping) mechanism.
3. Mark keys non-exportable where the use case allows; signing and
   decryption can usually happen inside the HSM without the key ever
   leaving.
4. Configure access control: separate HSM administrators from key
   users, require quorum (m-of-n) for sensitive operations, and bind
   application access to dedicated service identities.
5. Integrate applications via PKCS#11/JCE/CNG or the cloud API;
   verify in staging that signing, decryption, and TLS termination
   work through the HSM with acceptable latency.
6. Enable audit logging: HSM audit logs (key usage, admin actions)
   forwarded to the SIEM, with alerts on failed authentications and
   unexpected key operations.
7. Plan backup and recovery: back up keys via HSM-to-HSM cloning or
   wrapped export under quorum control; test restore before you need
   it.
8. Document the key lifecycle: generation, rotation schedule, and
   destruction procedures, each with named owners.

## Expected outputs

- An initialized HSM with keys generated in hardware and custody
  documented.
- Application integration verified in staging and production.
- Audit logging to the SIEM with alerting on anomalous key use.
- Tested backup/restore and a documented key lifecycle.

## Pitfalls

- Importing private keys as plaintext "just this once": it defeats the
   purpose — use wrapped import.
- Granting every application full HSM admin rights instead of
   least-privilege key-user roles.
- No tested recovery: a lost HSM with non-exportable keys and no
   backup is data loss.
- Ignoring latency: chatty protocols over a network HSM can bottleneck
   — measure before rollout.

## References

- NIST SP 800-57, Recommendation for Key Management
- NIST FIPS 140-3, Security Requirements for Cryptographic Modules
- Cloud provider HSM documentation (AWS CloudHSM, Azure Dedicated HSM)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
