---
skill_id: sys_net_tls_basics
name: Networking TLS Basics
description: How HTTPS gets its S: handshakes, certificates, and verification.
risk: info
permissions: []
requires_confirmation: false
tags: [networking, security]
version: 1.0.0
---
# Networking TLS Basics

## Purpose

How HTTPS gets its S: handshakes, certificates, and verification.

## Overview

TLS encrypts and authenticates connections (HTTPS = HTTP over TLS). The handshake negotiates a version and cipher suite, authenticates the server via its certificate chain (leaf -> intermediate -> root CA in the trust store), and establishes session keys - with forward secrecy (ECDHE) so a later key theft cannot decrypt past traffic. Certificates bind a public key to domain names (Subject Alternative Names); the client verifies the chain, the name match, the validity dates, and revocation status. Let's Encrypt made certificates free and automated (ACME); renew before the ~90-day expiry with automated cron/systemd timers. TLS 1.2 is the floor, 1.3 the modern standard (faster handshake, fewer footguns). Never disable certificate verification to 'fix' an error - you are removing the authentication that stops impersonation; fix the cert or the trust store instead. Common failures: expired cert, name mismatch (connecting via IP or wrong hostname), incomplete chain (missing intermediate), clock skew on the client. Inspect with openssl s_client -connect host:443 -servername host. Defense in depth: HSTS tells browsers to refuse plaintext, and pinning/cert-transparency logs watch for rogue issuance.

## Quick reference

- Handshake: negotiate version/cipher, verify cert chain, establish keys.

- Verify: chain to trusted root, SAN name match, dates, revocation.

- Forward secrecy (ECDHE): past traffic stays safe if keys leak later.

- Let's Encrypt + automation: free certs, renew before ~90-day expiry.

- TLS 1.3 modern, 1.2 floor. Never disable verification to 'fix' errors.

- Debug: openssl s_client -connect host:443 -servername host.


## Worked example

Inspecting a server's TLS setup:

```
# Show the certificate chain and negotiated parameters:
openssl s_client -connect example.com:443 -servername example.com < /dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates

# Check expiry across your domains:
for d in example.com www.example.com; do
  echo "== $d"
  echo | openssl s_client -connect "$d:443" -servername "$d" 2>/dev/null | openssl x509 -noout -dates
done

# Python: verification is ON by default - keep it that way
import ssl, urllib.request
ctx = ssl.create_default_context()   # verifies chain + hostname
print(urllib.request.urlopen('https://example.com', timeout=10, context=ctx).status)
```

- -servername sends SNI: required for multi-cert hosts.

- x509 -dates reveals expiry: the most common TLS outage cause.

- create_default_context verifies; unverified contexts are the vulnerability.


## Common mistakes

- ssl._create_unverified_context() or verify=False to silence errors.
  Fix: That disables impersonation defense. Fix the cert/chain/clock instead.

- Serving only the leaf cert without intermediates: chain breaks for clients.
  Fix: Serve leaf + intermediates; keep the root out (clients have it).


## Quick checks

Q: The error says 'certificate verify failed' - quick fix?
A: There is no safe quick fix. Diagnose: expired? (renew), name mismatch? (connect with the right name), missing intermediate? (serve the full chain), client clock wrong? Disabling verification invites impersonation - fix the cause.


Q: Why do certificates expire in ~90 days now?
A: Short lifetimes bound the damage of a compromised key and force automation (ACME). Manual yearly renewals were the actual outage factory; automation is the point.


## Mental model

TLS is a verified courier service: the handshake agrees on a secret code language (session keys), the courier shows a badge (certificate) issued by an authority you trust (CA), and you check the badge photo matches the face (hostname). Disabling verification is accepting packages from anyone with a laminated card.
