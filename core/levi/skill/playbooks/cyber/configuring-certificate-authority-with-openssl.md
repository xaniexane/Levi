---
skill_id: cyber_configuring_certificate_authority_with_openssl
name: Configuring a Certificate Authority with OpenSSL
description: Practitioner guide to building and operating a private certificate authority using OpenSSL, from root key ceremony to issuance and revocation.
risk: info
permissions: []
requires_confirmation: false
tags: [pki, cryptography, hardening]
version: 1.0.0
---
## Purpose
A private CA issues the certificates that secure internal services, VPNs, and device authentication. Built carelessly, it becomes a skeleton key for your network. This playbook creates an OpenSSL-based CA with proper key protection, certificate profiles, issuance workflow, and revocation -- suitable for internal PKI needs.

## When to use
- Standing up internal PKI for services, VPNs, or device certificates.
- Replacing self-signed certificates with a managed trust hierarchy.
- Learning PKI operations before adopting a managed CA product.
- Auditing an existing OpenSSL CA for operational weaknesses.

## Prerequisites
- Secure, isolated host for the root CA (ideally offline or air-gapped).
- Defined certificate policies: validity periods, key types, and approved uses.
- Backup and disaster-recovery plan for CA keys and database.
- Process for distributing the root certificate to trusting systems.

## Procedure
1. Plan the hierarchy. Design a root CA with one or more intermediate CAs; the root signs intermediates and then goes offline.
2. Perform the root key ceremony. Generate the root key on the isolated host with strong parameters; document witnesses, date, and procedures.
3. Create intermediates. Generate intermediate keys and CSRs, sign them with the root, then take the root offline and store it securely with backups.
4. Define certificate profiles. Create OpenSSL configurations for server, client, and code-signing uses with appropriate extensions and validity periods.
5. Establish the issuance workflow. Require authenticated CSRs, verify requester identity, and log every issuance with justification.
6. Publish revocation. Maintain a CRL and, where feasible, OCSP; define the process for emergency revocation of compromised certificates.
7. Distribute trust. Deploy the root certificate to managed systems through configuration management; document the trust store contents.
8. Operate and audit. Monitor expiry, audit issuance logs regularly, rehearse key compromise response, and plan CA renewal before expiry.

## Expected outputs
- Operational root and intermediate CA with documented ceremony.
- Certificate profiles and issuance workflow.
- Revocation infrastructure and key-compromise response plan.

## Pitfalls
- Root key on a networked host negates the entire trust model; keep it offline.
- Overly long validity periods amplify the impact of key compromise.
- No revocation checking means compromised certificates remain trusted indefinitely.
- Losing the CA key without backups forces rebuilding the entire PKI.

## References
- OpenSSL documentation (openssl-ca, openssl-req, openssl-x509)
- NIST SP 800-57, Recommendation for Key Management
- RFC 5280, Internet X.509 Public Key Infrastructure Certificate and CRL Profile
- CA/Browser Forum baseline requirements (for public-trust context)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
