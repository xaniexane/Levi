# VYVE Security Model

**Document version:** 1.0.0  
**Classification:** Internal — Platform Engineering  
**Owner:** VYVE Security Team  

---

## 1. Overview

VYVE implements defense-in-depth across five layers:

| Layer | Threat | Primary Countermeasure |
|-------|--------|------------------------|
| Identity | Account takeover, impersonation | Cybrus OAuth2/OIDC + device attestation |
| Transport | Eavesdropping, MITM | TLS 1.3 + certificate pinning |
| Messaging | Message interception | E2EE via libsodium (NaCl box) |
| Storage | Database breach | SQLCipher AES-256 encryption at rest |
| Application | Code injection, XSS | Input sanitization, CSP, sandboxing |

---

## 2. Authentication Architecture

### 2.1 Identity Provider
- **Cybrus OAuth 2.0 / OpenID Connect** is the sole identity authority for VYVE
- VYVE NEVER stores user passwords
- VYVE NEVER operates its own credential database
- Session tokens are short-lived (1 hour default) with refresh token rotation

### 2.2 Token Lifecycle
```
LOGIN → authorization_code + PKCE
      → access_token (1h) + refresh_token (30d) + id_token (OIDC claims)
      → refresh_token rotation on every use
      → device revocation invalidates all tokens for that device
```

### 2.3 Device Attestation
Each device registers a unique device key with Cybrus:
- Device key pair generated on first launch (libsodium kx())
- Public key sent to Cybrus, signed by device
- Server stores: `device_id, public_key, user_id, registered_at, last_seen`
- Device key can be revoked independently of account

---

## 3. Cryptographic Architecture

### 3.1 Key Hierarchy
```
Master Identity Key (user)
├── Signing Key (message authentication)
├── Encryption Key (message confidentiality)
└── Device Keys (per-device, derived from master)
    ├── Device Signing Key
    └── Device Encryption Key
```

### 3.2 Algorithms (No Homemade Crypto)
| Purpose | Algorithm | Library |
|---------|-----------|---------|
| Key exchange | X25519 | libsodium / PyNaCl |
| Authenticated encryption | XChaCha20-Poly1305 | libsodium |
| Hashing | BLAKE2b | libsodium |
| Signatures | Ed25519 | libsodium |
| Key derivation | Argon2id | libsodium |
| TLS | TLS 1.3 | System default |

### 3.3 Forward Secrecy
- Session keys are derived using ephemeral Diffie-Hellman (X25519)
- Old session keys are securely wiped after key rotation
- Long-term identity keys are separate from session keys

---

## 4. Transport Security

### 4.1 TLS Configuration
- **Minimum:** TLS 1.2 with forward secrecy (ECDHE)
- **Preferred:** TLS 1.3
- Certificate pinning for VYVE server endpoints
- HSTS with includeSubDomains

### 4.2 Certificate Pinning (Android)
Pins are rotated on key rotation events with a pin backup:
```
Primary pin: SPKI hash of current certificate
Backup pin: SPKI hash of next certificate
Emergency pin: SPKI hash of previous certificate
```

### 4.3 Network Security Config
```xml
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.vyve.local</domain>
        <pin-set expiration="2025-01-01">
            <pin digest="SHA-256">...</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

---

## 5. End-to-End Encryption (E2EE)

### 5.1 Message Encryption Flow
```
Sender:
  1. Generate ephemeral session key (X25519)
  2. Compute shared secret with recipient's device key
  3. Encrypt message with XChaCha20-Poly1305
  4. Send: {ephemeral_pubkey, nonce, ciphertext, sender_key_id}

Recipient:
  1. Receive encrypted payload
  2. Compute shared secret with sender's ephemeral key
  3. Decrypt with authenticated decryption
  4. Verify sender key_id matches known device
```

### 5.2 Multi-Device Support
- Each device has its own encryption key pair
- Message is encrypted separately for each recipient device
- Server stores ciphertexts but never has the plaintext
- Key IDs allow efficient device-specific encryption

### 5.3 What the Server CANNOT See
- Message content (always encrypted client-side)
- Sender/recipient usernames in message body
- Attachments (encrypted with per-file key)
- Read receipts (encrypted metadata)
- Typing indicators

### 5.4 What the Server DOES Store
- Encrypted ciphertexts (stored, not readable)
- Sender and recipient key IDs (not usernames)
- Timestamps (not content)
- Message size (approximate, not exact)
- Device IDs and key IDs (not plaintext identity)

---

## 6. Local Storage Security

### 6.1 SQLite with SQLCipher
- Database encryption key derived from user master key + device key
- Key stored in Android Keystore (hardware-backed where available)
- Automatic database lock on screen-off (configurable timeout)

### 6.2 Android Keystore Usage
```
Key generation:
  - AES-256 key generated via AndroidKeyGenerator
  - SetBlockModes(GCM) + SetEncryptionPaddings(PKCS7Padding)
  - SetUserAuthenticationRequired(true) for biometric unlock
  - Sticky bit set to prevent extraction even on rooted devices
```

---

## 7. Access Control

### 7.1 Permission Model
Every API call requires:
1. Valid (non-expired) access token
2. Token scoped for the requested resource
3. Resource owned by or shared with the token holder

### 7.2 Scopes
| Scope | Grants |
|-------|--------|
| `read:v1` | Read own profile, conversations, messages |
| `write:v1` | Send messages, update profile |
| `social:v1` | Create posts, comments, reactions |
| `marketplace:v1` | List products, place orders |
| `ai_context:v1` | Allow AI to read selected context |
| `admin:v1` | Platform administration (restricted) |

---

## 8. Security Event Handling

### 8.1 Automatic Responses
| Event | Automated Action | Requires CJ Approval |
|-------|-----------------|----------------------|
| Failed login (5x in 10min) | Temporary account lock (15min) | No |
| Suspicious device login | Notify user, require verification | No |
| Mass report spike | Content review queue | No |
| Breach attempt detected | IP block + alert | No |
| Account ban | Perm lockout | YES |
| Feature removal | Any user-facing change | YES |
| Data export | User data portability | No |

### 8.2 Audit Log
- Every admin action is logged: `who, what, when, target, result`
- Logs retained 1 year
- Audit logs NOT accessible to standard admins
- CJ-only access via separate authentication path

---

## 9. Secure Development Practices

### 9.1 Dependency Management
- Automated dependency scanning (Snyk/Dependabot)
- Critical vulnerabilities: 24-hour patch SLA
- High vulnerabilities: 7-day patch SLA
- No new dependencies without security review

### 9.2 Code Signing
- Android: Google Play Signing or self-signed with keystore
- Backend: Sigstore / Gitsign for container images
- Release artifacts signed and checksummed

### 9.3 Penetration Testing
- External pen test: quarterly
- Internal review: continuous (code review gate)
- Bug bounty: public program for responsible disclosure

---

## 10. Incident Response

### 10.1 Severity Levels
| Level | Description | Response Time |
|-------|-------------|---------------|
| P0 | Active breach, data exfiltration | Immediate |
| P1 | Unauthorized access, account takeover | < 1 hour |
| P2 | Service degradation, DoS | < 4 hours |
| P3 | Non-critical vulnerability | < 72 hours |

### 10.2 Notification Policy
- Users affected by P0/P1: within 72 hours of discovery
- Regulatory bodies: per applicable law (GDPR: 72h, state laws vary)
- Breach disclosure: public post within 7 days

---

## 11. Compliance

- GDPR: Data minimization, right to erasure, DPA agreements
- CCPA: Right to know, delete, opt-out
- COPPA: No data collection from users under 13
- ADA: WCAG 2.1 AA accessibility
- SOC 2 Type II: annual audit (future roadmap)
