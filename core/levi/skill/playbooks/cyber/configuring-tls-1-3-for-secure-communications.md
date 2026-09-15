---
skill_id: cyber_configuring_tls_1_3_for_secure_communications
name: Configuring TLS 1.3 for Secure Communications
description: Deploy TLS 1.3 with modern cipher suites, HSTS, and certificate hygiene to eliminate legacy protocol weaknesses.
risk: low
permissions: []
requires_confirmation: false
tags: [crypto, network, hardening]
version: 1.0.0
---
## Purpose

Standardize on TLS 1.3 across services: forward secrecy by default, no obsolete cipher suites, no protocol downgrade, and certificate practices that don't expire on a Friday night. TLS misconfiguration is still a top audit finding — this playbook closes it.

## When to use

- Hardening web servers, APIs, load balancers, and mail servers against protocol downgrade and weak-cipher attacks.
- Remediating SSL Labs scores or audit findings citing TLS 1.0/1.1, RC4, 3DES, or weak DH parameters.
- Deploying new services where the TLS baseline must be defined before launch.
- Implementing mutual TLS for service-to-service authentication.

## Prerequisites

- Administrative access to the TLS terminators (nginx, Apache, HAProxy, cloud load balancers, mail servers).
- A certificate inventory: issuers, expiry dates, key types, and where each cert is installed.
- Client compatibility data — confirm legacy clients requiring TLS 1.2 are identified before removing it.
- A test endpoint to validate configuration changes without touching production.

## Procedure

1. **Enable TLS 1.3 and retire the old protocols.** Configure `TLSv1.3` as the only version; disable TLS 1.0, TLS 1.1, and all SSL versions. Keep TLS 1.2 enabled only where a documented legacy client requires it, with a sunset date — not as a permanent backdoor.
2. **Restrict cipher suites aggressively.** With TLS 1.3, only five AEAD suites exist; prefer `TLS_AES_256_GCM_SHA384` and `TLS_CHACHA20_POLY1305_SHA256`, then `TLS_AES_128_GCM_SHA256`. For any retained TLS 1.2 endpoints, allow only ECDHE+AEAD suites and explicitly exclude RC4, 3DES, CBC-mode without care, and RSA key exchange (no forward secrecy).
3. **Disable TLS compression and risky extensions.** Turn off TLS compression (CRIME) and ensure secure renegotiation. Generate fresh, strong DH parameters (2048-bit minimum) if DHE is used at all; prefer ECDHE with P-256/P-384.
4. **Deploy HSTS with preload in mind.** Send `Strict-Transport-Security: max-age=31536000; includeSubDomains` on all HTTPS responses. Fix any mixed-content or plain-HTTP dependencies first, then submit to the HSTS preload list for long-term protection.
5. **Automate certificate lifecycle.** Use ACME (Let's Encrypt or internal CA automation) with auto-renewal and alerting at 30/14/7 days to expiry. Use 90-day certificates with automation rather than 1-year certificates with manual tracking — the failure mode of manual tracking is an outage.
6. **Validate the configuration independently.** Scan every public endpoint with SSL Labs and an internal scanner (testssl.sh) after each change; require A+ / no warnings. Scan internal endpoints on the same cadence — attackers don't skip RFC1918 space.
7. **Log and monitor the TLS layer.** Alert on certificates expiring soon, unexpected certificate changes (possible interception or mis-issuance), and negotiation of disabled protocols (downgrade attempts). Monitor Certificate Transparency logs for unauthorized certs issued for your domains.
8. **For mTLS deployments:** issue client certificates from a dedicated internal CA, validate the full chain and revocation status server-side, and rotate client certs on a defined schedule with an automated distribution path.

## Expected outputs

- TLS 1.3-only (or 1.2-with-sunset) configuration on all terminators, verified by SSL Labs A+ / testssl.sh.
- HSTS deployed with preload eligibility; mixed content eliminated.
- Automated certificate issuance/renewal with expiry alerting and CT-log monitoring.

## Pitfalls

- Keeping TLS 1.2 "temporarily" for years — document the sunset and enforce it.
- Cipher-suite ordering mistakes: listing a weak suite first because of a copy-paste config.
- Forgetting internal services — the scanner findings on public sites are the easy part; internal APIs and mail servers are where the old protocols hide.
- HSTS without fixing HTTP dependencies first — you'll break your own site and then disable HSTS "temporarily."
- Manual certificate renewals tracked in a spreadsheet — the outage is a matter of time.

## References

- RFC 8446 (The Transport Layer Security (TLS) Protocol Version 1.3)
- Mozilla Server Side TLS configuration guidelines
- NIST SP 800-52 Rev. 2 (Guidelines for the Selection, Configuration, and Use of TLS)
- Certificate Transparency (RFC 6962) — crt.sh for monitoring
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
