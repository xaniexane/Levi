# VYVE Threat Model

**Document version:** 1.0.0  
**Methodology:** STRIDE + DREAD  
**Last updated:** 2026-09-04  

---

## 1. System Overview

VYVE is a private messaging and identity layer. Its attack surface includes:

```
External:
├── Android client (APK)
├── Web client (browser)
├── Public API (REST/WS)
└── OAuth endpoints (via Cybrus)

Internal:
├── Identity service (Cybrus)
├── Messaging service
├── Database (SQLite + S3)
├── Object storage
└── Admin tools
```

### Trust Boundaries

```
[Untrusted] Android device
   |
   v TLS 1.3 / Certificate Pin
[Semi-trusted] Public API gateway
   |
   v OAuth token validation
[Trusted] Internal services
   |
   v Database auth
[Trusted] Database & storage
```

---

## 2. STRIDE Threat Categories

### S — Spoofing Identity

| ID | Threat | Vector | Impact | Likelihood | Mitigation |
|----|--------|--------|--------|------------|------------|
| S-1 | Stolen credentials | Phishing, breach reuse | High | Medium | OAuth-only auth, no VYVE-side passwords |
| S-2 | Token replay | Stolen refresh token | High | Low | Refresh token rotation, device binding |
| S-3 | Device impersonation | Rogue device | High | Low | Device key attestation via Cybrus |
| S-4 | Public key spoofing | MITM key swap | High | Low | TOFU + out-of-band verification |
| S-5 | OAuth flow hijack | Redirect URI attack | High | Low | PKCE required, exact redirect match |

### T — Tampering

| ID | Threat | Vector | Impact | Likelihood | Mitigation |
|----|--------|--------|--------|------------|------------|
| T-1 | Message modification | MITM on plaintext | Critical | Very Low | E2EE + auth tags (Poly1305) |
| T-2 | DB tampering | SQL injection | High | Low | Parameterized queries, ORM |
| T-3 | API response tampering | MITM | High | Very Low | TLS 1.3 + HSTS + cert pinning |
| T-4 | Client binary tampering | APK repackage | High | Medium | Play Integrity API, signature pinning |
| T-5 | Stored attachment tampering | S3 access | High | Very Low | Server-side encryption + checksums |

### R — Repudiation

| ID | Threat | Vector | Impact | Likelihood | Mitigation |
|----|--------|--------|--------|------------|------------|
| R-1 | User denies sending message | n/a | Medium | Medium | Signed messages, server-side timestamp, audit log |
| R-2 | User denies account action | n/a | Medium | Medium | Audit trail of account changes |
| R-3 | Admin denies moderation | n/a | High | Low | Immutable audit log, multi-party approval for bans |

### I — Information Disclosure

| ID | Threat | Vector | Impact | Likelihood | Mitigation |
|----|--------|--------|--------|------------|------------|
| I-1 | Eavesdropping on network | Passive sniffer | Critical | Very Low | E2EE, TLS 1.3, certificate pinning |
| I-2 | Database breach | SQLi, unpatched | Critical | Low | Encryption at rest, parameterization, MFA on admin |
| I-3 | Backup leak | Stolen backup | Critical | Low | Encrypted backups, key separation |
| I-4 | Side-channel (metadata) | Traffic analysis | Medium | Medium | Minimal metadata, optional onion routing |
| I-5 | Server logs leak | Misconfigured logging | High | Medium | Log sanitization, no message content in logs |
| I-6 | Server-side decryption | Compromised server | Critical | Very Low | Server NEVER has decryption keys (E2EE) |
| I-7 | Key extraction | Rooted device, malware | Critical | Low | Hardware-backed Keystore, biometric gating |

### D — Denial of Service

| ID | Threat | Vector | Impact | Likelihood | Mitigation |
|----|--------|--------|--------|------------|------------|
| D-1 | Network flooding | Botnet | High | High | Rate limiting, Cloudflare, WAF |
| D-2 | API spam | Scripted requests | Medium | High | CAPTCHA, token bucket per user |
| D-3 | Resource exhaustion | Large payloads | Medium | Medium | Payload size limits, request validation |
| D-4 | DB connection flood | Bad client | Medium | Low | Connection pooling, queue-based throttling |
| D-5 | E2EE abuse (spam) | Encrypted spam | Medium | Medium | Rate limit on message count, not content |

### E — Elevation of Privilege

| ID | Threat | Vector | Impact | Likelihood | Mitigation |
|----|--------|--------|--------|------------|------------|
| E-1 | Scope escalation | Token manipulation | Critical | Very Low | Server-side scope validation |
| E-2 | Horizontal escalation | IDOR | High | Low | Resource ownership checks |
| E-3 | Vertical escalation | Admin access | Critical | Low | Separate admin auth, MFA required |
| E-4 | Code execution | Deserialization | Critical | Very Low | No unsafe deserialization, allowlist |
| E-5 | Supply chain | Malicious dep | Critical | Medium | Pinned deps, signed builds, SBOM |

---

## 3. Specific Adversary Scenarios

### 3.1 Compromised Client
**Assumption:** An attacker has root access to a victim's Android device.

**Impact:**
- Can read decrypted messages in memory
- Can send messages as the user
- Can extract database if unlocked
- Can extract keys if Keystore is bypassed (rooted)

**Mitigations:**
- Hardware-backed Keystore resists extraction on non-rooted devices
- Biometric lock prevents unattended use
- Database auto-locks on screen-off
- Server-side rate limiting reduces abuse potential
- Device revocation invalidates all future messages

**Residual risk:** Medium. Rooted devices are inherently lower-trust.

---

### 3.2 Compromised Server
**Assumption:** An attacker has full control of the VYVE messaging server.

**Impact:**
- Can read encrypted ciphertexts (but cannot decrypt)
- Can log message metadata (sender ID, recipient ID, timestamp, size)
- Can refuse to deliver messages
- Can modify ciphertexts (but Poly1305 will detect tampering)
- CANNOT: read message content, forge signatures without key access

**Mitigations:**
- E2EE ensures server has no plaintext access
- Server holds only opaque ciphertext + metadata
- All messages include auth tags — any modification causes recipient rejection
- User can detect delivery failure and switch to alternative relay
- Optional: deploy via self-hosting for users who don't trust Omega's servers

**Residual risk:** Low. Metadata exposure is the primary concern.

---

### 3.3 Malicious User / Vendor
**Assumption:** A legitimate user with verified account attempts to abuse the platform.

**Impact:**
- Can send messages to non-consenting users
- Can post prohibited content (spam, harassment, illegal goods)
- Can attempt to scam other users
- Can attempt to abuse the marketplace

**Mitigations:**
- Reporting system with human review
- Rate limits on new accounts
- Vendor verification for marketplace
- Content moderation via community reporting
- Automated spam detection (heuristic + AI)
- User block list (server-enforced)

**Residual risk:** Medium. Human-in-the-loop moderation can never catch everything.

---

### 3.4 Database Compromise
**Assumption:** Attacker exfiltrates the entire database (SQLite + S3 snapshots).

**Impact:**
- Gets encrypted message ciphertexts
- Gets hashed credentials (none — we use OAuth)
- Gets user profile data (display name, avatar URL, bio)
- Gets public social graph (followers, posts)
- CANNOT: read messages, access vault, impersonate users (no password hash)

**Mitigations:**
- Encryption at rest (SQLCipher, S3 SSE-KMS)
- No passwords stored (OAuth only)
- Database keys separated from app servers
- Minimal PII stored
- User can delete account, triggering data purge

**Residual risk:** Low. Strong encryption + minimal PII + no credential storage.

---

### 3.5 Relay Compromise
**Assumption:** Attacker controls the relay server for offline message delivery.

**Impact:**
- Can delay or drop messages
- Can read metadata (sender, recipient, size, timestamp)
- CANNOT: read message content (still E2EE)
- CANNOT: forge messages (signature would be invalid)

**Mitigations:**
- Relay is a dumb pipe — holds ciphertext only
- Multiple relay options (user can choose)
- Direct P2P path is preferred when both devices are online
- Relay operator selection is documented and auditable

**Residual risk:** Low for content, medium for metadata.

---

### 3.6 Supply Chain Attack
**Assumption:** A malicious dependency is introduced.

**Impact:** Critical — could affect all clients/servers using that dep.

**Mitigations:**
- Pinned dependency versions (lockfile)
- SBOM (Software Bill of Materials) generated per release
- Automated dependency scanning (Snyk, Dependabot, Trivy)
- Reproducible builds
- Code signing for release artifacts
- Critical deps reviewed manually

**Residual risk:** Medium. Industry-wide issue, no perfect solution.

---

## 4. Out-of-Scope Threats

VYVE explicitly does NOT claim protection against:

- **Nation-state-level attacks** with physical device access
- **Malware on a rooted device** (user accepted lower trust)
- **User choosing weak passphrases** (mitigated by biometric unlock + Argon2id)
- **Side-channel attacks on shared hardware** (no shared hosting without isolation)
- **Physical coercion** (cannot defend against legal compulsion)
- **Future quantum computers** (planned migration to post-quantum algorithms)

---

## 5. Threat Prioritization Matrix

| Priority | Threats |
|----------|---------|
| **P0 - Immediate** | I-1, I-2, T-1, I-6, E-1 |
| **P1 - High** | S-1, S-2, S-3, T-2, T-4, I-3, E-2, E-3, E-5 |
| **P2 - Medium** | S-4, S-5, T-3, T-5, R-1, R-2, R-3, I-4, I-5, I-7, D-1, D-2, D-3 |
| **P3 - Standard** | D-4, D-5, R-3, T-2 |

---

## 6. Review Schedule

This document is reviewed:
- Quarterly by the security team
- After every P0/P1 incident
- When significant architecture changes occur
- When new regulatory requirements are introduced
