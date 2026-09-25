---
skill_id: web_sec_tls_hardening
name: TLS Hardening
description: Configure TLS defensively: versions, ciphers, HSTS, certificate hygiene, and ongoing verification.
risk: info
permissions: []
requires_confirmation: false
tags: [security, defense, web, ops]
version: 1.0.0
---
# TLS Hardening
## Purpose
Close the configuration gaps that turn 'we have HTTPS' into a false sense of security.
## Key ideas
- Disable TLS 1.0 and 1.1 and weak ciphers; support 1.2 with strong ciphers and prefer 1.3.
- HSTS with includeSubDomains and a long max-age stops protocol-downgrade tricks.
- Certificates must chain fully, match the hostname, and renew automatically with monitored expiry.
- Forward secrecy (ECDHE ciphers) ensures a future key compromise cannot decrypt past traffic.
- OCSP stapling lets clients check revocation without leaking browsing to the CA.

## In practice
Start from a modern configuration profile (the Mozilla intermediate profile is a sane baseline) and adjust only with reason, not by enabling legacy options 'just in case'. Scan externally after every change and on a schedule; TLS configuration drifts as software updates and vulnerabilities emerge. Test the failure modes, not just the happy path: expired cert in staging, revoked cert, wrong hostname, and confirm clients fail closed. Document the TLS posture alongside the certificate inventory so the next incident starts from facts, not from re-deriving the config under pressure.

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers on;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384;
ssl_session_timeout 10m;
ssl_stapling on;
ssl_stapling_verify on;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

## Common mistakes
- Enabling old TLS versions for a handful of legacy clients and weakening everyone.
- Forgetting HSTS, leaving users one coffee-shop network away from a downgrade attack.
- Never scanning after changes, so weak ciphers creep back with software updates.

## Checklist
- Are TLS 1.0/1.1 off with forward-secret ciphers preferred?
- Is HSTS set with includeSubDomains and long max-age?
- Is the external TLS posture scanned on a schedule?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
