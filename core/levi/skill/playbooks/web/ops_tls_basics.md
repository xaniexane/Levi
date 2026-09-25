---
skill_id: web_ops_tls_basics
name: TLS Basics
description: How TLS protects traffic: handshakes, certificates, and why HTTPS is the only sane default.
risk: info
permissions: []
requires_confirmation: false
tags: [ops, deployment, security]
version: 1.0.0
---
# TLS Basics
## Purpose
Understand enough TLS to deploy HTTPS correctly and diagnose the common failures.
## Key ideas
- TLS encrypts traffic in transit, protecting against eavesdropping and tampering on the path.
- The handshake negotiates a version and cipher, then the server proves identity with a certificate.
- Certificates bind a public key to a domain name, vouched for by a certificate authority the client trusts.
- Modern TLS means 1.2 minimum, 1.3 preferred; older versions have known weaknesses and should be off.
- Mixed content (HTTPS page loading HTTP resources) undermines the whole guarantee; serve everything over HTTPS.

## In practice
Serve everything over HTTPS with HSTS so browsers refuse to downgrade; there is no longer a performance excuse for plaintext. Prefer TLS 1.3, allow 1.2 with a modern cipher list, and disable everything older explicitly. When a TLS error appears, read it literally: certificate expired means renew, hostname mismatch means the cert is for a different name, untrusted issuer means the chain is incomplete. Test with a scanner periodically; configuration drift and new vulnerabilities mean 'it worked last year' is not evidence. Redirect all HTTP to HTTPS at the edge so no request ever travels in the clear.

```text
# What a healthy handshake looks like (conceptually)
Client -> Server: ClientHello (offers TLS 1.3, cipher list)
Server -> Client: ServerHello + certificate chain for shop.example.com
Both: derive session keys, verify certificate against trusted CAs
Client -> Server: HTTP request, now encrypted

# Quick check from the shell
openssl s_client -connect shop.example.com:443 -servername shop.example.com
```

## Common mistakes
- Leaving TLS 1.0/1.1 enabled for compatibility, keeping known-weak protocols alive.
- Serving HTTPS pages that load scripts or images over HTTP, breaking the security model.
- Ignoring certificate expiry until users see browser warnings.

## Checklist
- Is TLS 1.3 preferred with 1.0/1.1 disabled?
- Does HSTS enforce HTTPS with no mixed content?
- Are certificates monitored for expiry with alerting?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
