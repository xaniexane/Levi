# VYVE Privacy Model

**Document version:** 1.0.0  
**Classification:** Public — Users & Developers  
**Last updated:** 2026-09-04  

---

## 1. Privacy Philosophy

Traditional platforms:  
`Public by default → users add privacy`

VYVE:  
`Private by default → users choose exposure`

The default state of every piece of data in VYVE is **private**. Any sharing requires explicit user action.

---

## 2. Data Classification

| Class | Definition | Examples | Default |
|-------|-----------|----------|---------|
| **PRIVATE** | Only visible to owner | Vault contents, encryption keys, message content | Always PRIVATE |
| **SHARED** | Visible to specific people | Direct messages, group chats | SHARED with explicit invite |
| **COMMUNITY** | Visible to community members | Community posts, reactions | COMMUNITY if joined |
| **PUBLIC** | Visible to anyone | Public profiles, public channels | Never PUBLIC unless user chooses |

---

## 3. What VYVE Knows (and When)

### 3.1 Registration
| Data | Stored | Purpose | Retention | Deletable |
|------|--------|---------|----------|-----------|
| Username | Yes | Identity | Until account deletion | Yes |
| Public encryption key | Yes | E2EE messaging | Until account deletion | Yes |
| Public signing key | Yes | Message authentication | Until account deletion | Yes |
| Email (if provided) | Yes | Account recovery, notifications | Until account deletion | Yes |
| Password | **NO** | Handled by Cybrus OAuth | n/a | n/a |
| Device public keys | Yes | Multi-device E2EE | Until device revoked | Yes |

---

### 3.2 Messaging
| Data | Server Sees | Other Users See | Deleted When |
|------|------------|-----------------|--------------|
| Message content | **NEVER** (E2EE) | **NEVER** (E2EE) | At user's request (if delivered) |
| Sender key ID | Yes | Yes | At user's request |
| Recipient key IDs | Yes | **NEVER** | At user's request |
| Timestamp | Yes (rounded to 1hr) | Yes (rounded to 1hr) | At user's request |
| Message size | Yes (approximate) | No | At user's request |
| Read receipts | Encrypted blob | Encrypted blob | At user's request |
| Reactions | Encrypted | Encrypted | At user's request |
| Attachments | Encrypted ciphertext | **NEVER** | At user's request |

---

### 3.3 Social Graph
| Data | Stored | Visible To | Deletable |
|------|--------|------------|----------|
| Follows | Yes | User + public (if public profile) | Yes |
| Followers | Yes | User + public (if public profile) | Yes |
| Block list | Encrypted | User + blocked user sees "blocked" | Yes |
| Mutuals | Yes | Computed from follow data | Yes |

---

### 3.4 Marketplace (🔐💲💎)
| Data | Stored | Visible To | Deletable |
|------|--------|------------|----------|
| Vendor identity | Yes | Public | Yes |
| Listings | Yes | Public | Yes |
| Order details | Yes | Buyer + vendor | Yes (buyer), No (regulatory) |
| Payment info | **NEVER** | n/a | n/a (handled by payment provider) |
| Reviews | Yes | Public after posting | Soft delete only |

---

## 4. What VYVE Does NOT Collect

VYVE explicitly does NOT collect or store:

- ❌ Message content (encrypted client-side, server never sees plaintext)
- ❌ Private message recipient list (server sees only key IDs)
- ❌ Private vault contents
- ❌ User passwords (handled by Cybrus)
- ❌ Biometric data (device local only, never transmitted)
- ❌ Precise location data
- ❌ Keystroke logs
- ❌ Audio/video call content (E2EE, never stored)
- ❌ Exact message timestamps (rounded to 1-hour buckets for privacy)
- ❌ Raw social graph (stored as edges, computed on query)
- ❌ Children's personal information (COPPA compliance)
- ❌ Health or financial data from vault (encrypted, never read)
- ❌ Unaggregated usage data from other users

---

## 5. Metadata Minimization

### 5.1 Timestamp Rounding
Precise send/receive times are stored client-side only.
Server receives: `2026-09-04T09:00:00Z` (rounded to hour)
Full precision: `2026-09-04T09:37:42.123456Z` (client local only)

### 5.2 Message Size Obfuscation
Server receives: approximate size bucket (0-1KB, 1-10KB, 10-100KB, 100KB+)
Exact size: never transmitted to server

### 5.3 Connection Metadata
| Data | Stored | Retention |
|------|--------|-----------|
| Last login timestamp | Yes | 90 days |
| Device used | Yes (type only, not model) | Until device revoked |
| Approximate location (city) | Yes | 30 days |
| Connection IP | **NEVER** (proxied through relay) | n/a |
| Session duration | Aggregated only | 30 days |

---

## 6. Data Sovereignty

### 6.1 User Control
Every user has the right to:
1. **View all data VYVE holds about them** (export via Settings → Privacy → Download My Data)
2. **Delete any or all data** (except regulatory-required records)
3. **Choose data residency** (EU, US, or self-hosted — future roadmap)
4. **Control sharing** (every post, profile field, listing is individually scoped)
5. **Disable telemetry** (Settings → Privacy → Share usage data)

### 6.2 Data Portability
- Export format: JSON + encrypted attachments
- Export includes: profile, messages (encrypted), social graph, marketplace activity
- 30-day export window after account deletion request

---

## 7. Third-Party Data Sharing

VYVE does NOT:
- Sell user data to advertisers
- Share data with third parties for advertising purposes
- Share precise behavioral data with analytics companies
- Share encrypted message content with law enforcement (cannot decrypt)
- Share data with Omega OS services outside the documented API

VYVE MAY share (with user notice):
- Aggregated, anonymized platform statistics (e.g., "10,000 messages sent today")
- Data required by law enforcement (metadata only, no message content)
- Data with payment providers (order totals, vendor payouts — not message content)

---

## 8. Legal Requests

| Request Type | VYVE Response | Data Available |
|-------------|---------------|-----------------|
| Subpoena (US) | Challenge overbreadth | Metadata only, no message content |
| GDPR SAR | 30-day response | All held data, exported |
| GDPR Deletion | "Right to be forgotten" | Full deletion (regulatory hold exceptions) |
| COPPA | No service to under-13 | Age gate enforced |
| Foreign government | Consult legal counsel | Varies by treaty |
| National security letter | Cannot confirm or deny | Cannot be discussed |

**Key point:** VYVE cannot provide message content because it is end-to-end encrypted and the server has no access to decryption keys. Only metadata is available, and metadata without content has limited investigative value.

---

## 9. Privacy by Design Checklist

Every feature must pass these questions before shipping:

- [ ] What is the minimum data required to make this feature work?
- [ ] Who can see this data? (owner only? selected users? everyone?)
- [ ] How long is this data retained?
- [ ] Can the user delete it?
- [ ] Can this data remain LOCAL (never sent to server)?
- [ ] Does this data leave the user's device unencrypted?
- [ ] Is this data necessary for platform operation?
- [ ] Is this data shared with any third party?
- [ ] Is the default setting the most private option?
