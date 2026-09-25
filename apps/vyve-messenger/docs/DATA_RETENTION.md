# VYVE Data Retention Policy

**Document version:** 1.0.0  
**Classification:** Public — Users & Compliance  
**Last updated:** 2026-09-04  

---

## 1. Retention Principles

1. **Minimal by default** — VYVE retains only what is operationally necessary
2. **Time-limited** — Every data class has a defined retention period
3. **User-controllable** — Users can delete their data; deletion is honored unless legally constrained
4. **Auditable** — Retention enforcement is automated and auditable
5. **No indefinite storage** — No data class has "indefinite" retention

---

## 2. Data Retention Schedule

### 2.1 Identity Data
| Data | Retention | Deletion Method |
|------|-----------|-----------------|
| Username | Until account deletion | Hard delete |
| Public keys | Until account deletion | Hard delete |
| Email (if provided) | Until account deletion | Hard delete + 30-day grace |
| OAuth tokens | 1 hour (access) / 30 days (refresh) | Automatic expiration |
| Refresh token rotation | Old tokens invalidated on use | Immediate |

### 2.2 Messaging Data
| Data | Retention | Deletion Method |
|------|-----------|-----------------|
| Encrypted ciphertext | Until both parties delete OR 90 days past last activity | Hard delete |
| Sender/recipient key IDs | Same as ciphertext | Hard delete |
| Timestamps (rounded) | 1 year | Soft delete, then hard |
| Read receipts | Until message deletion OR 90 days | Hard delete |
| Message metadata (size bucket) | 90 days | Aggregation, then discard |

### 2.3 Social Data
| Data | Retention | Deletion Method |
|------|-----------|-----------------|
| Posts (public) | Until user deletes | Hard delete |
| Posts (deleted) | 30-day recoverable window, then hard delete | Hard delete |
| Comments | Same as posts | Hard delete |
| Reactions | Same as posts | Hard delete |
| Follows/Followers | Until user unfollows OR deletes | Hard delete |
| Block list | Until user unblocks | Hard delete |

### 2.4 Marketplace Data
| Data | Retention | Deletion Method |
|------|-----------|-----------------|
| Vendor profile | Until vendor deletes | Hard delete |
| Listings | Until vendor removes OR 1 year inactive | Hard delete |
| Order history (buyer) | Until user deletes OR 7 years (tax law) | Hard delete after retention |
| Order history (vendor) | 7 years (regulatory) | Hard delete after retention |
| Reviews | Soft delete only (preserved for trust) | Anonymized after 2 years |
| Payouts | 7 years (financial regulation) | Hard delete after retention |

### 2.5 Operational Data
| Data | Retention | Deletion Method |
|------|-----------|-----------------|
| Server access logs | 30 days | Automated purge |
| Error logs (sanitized) | 90 days | Automated purge |
| Audit logs (admin actions) | 1 year | Hard delete after retention |
| Security event logs | 1 year | Hard delete after retention |
| Aggregated analytics | Indefinite (no PII) | N/A — anonymous aggregates only |
| Backups | 30 days rolling | Encrypted, then expired |

---

## 3. Data Deletion Behavior

### 3.1 User-Initiated Deletion
When a user deletes a specific item:
- Item is marked for deletion immediately
- Visible to no one except the user (for 30-day recovery window if applicable)
- Hard-deleted from active databases within 24 hours
- Purged from backups within 30 days (next backup cycle)

### 3.2 Account Deletion
When a user deletes their account:
1. All user-owned content is hard-deleted within 24 hours
2. User is removed from all social graph edges
3. User is removed from all groups, communities, channels
4. Public content shows "[deleted user]" placeholder for 30 days
5. After 30 days, public content is anonymized (replaced with random ID)
6. User keys are securely wiped
7. Account cannot be recovered after 30 days
8. Records required by law (financial) are retained per regulatory schedule

### 3.3 Cascading Deletion
When a user deletes their account:
- All messages they sent: tombstoned (recipient can see "User deleted")
- All messages they received: deleted from user's view, retained on recipient's view
- All group memberships: removed
- All marketplace listings: removed
- All reviews written: removed or anonymized

---

## 4. Data Backup Retention

### 4.1 Backup Strategy
- **Frequency:** Daily full backups, hourly incremental
- **Retention:** 30 days rolling
- **Encryption:** AES-256-GCM with key in HSM
- **Location:** Encrypted on S3 with separate IAM credentials
- **Access:** Read-only, requires 2-person approval for restore

### 4.2 Restore Process
- Restore operations are logged to immutable audit log
- Restored data re-encrypted with new keys
- Old backup data marked for hard deletion after 30 days

---

## 5. Data Anonymization

### 5.1 When Data is Anonymized
- Account deletion (after 30-day grace period)
- User requests "anonymize me" (GDPR/CCPA)
- Legal hold expires
- Operational data aging out of retention

### 5.2 Anonymization Methods
| Data Type | Anonymization |
|-----------|---------------|
| Username | Replaced with `user_<random_id>` |
| Public keys | Regenerated as dummy values |
| Email | Replaced with `email_<random_id>@invalid` |
| IP addresses | Replaced with `0.0.0.0` |
| Device IDs | Replaced with `device_<random_id>` |
| Content | Replaced with `[redacted]` |
| Timestamps | Shifted by random delta in seconds |

---

## 6. Retention Compliance

| Regulation | Maximum Retention | VYVE Implementation |
|------------|------------------|----------------------|
| GDPR (Art. 5(1)(e)) | Not longer than necessary | All categories have explicit retention |
| CCPA | Right to delete honored | 30-day deletion process |
| COPPA | Under-13: no service | Age gate, deletion on detection |
| HIPAA | 6 years (if applicable) | Not applicable — no health data |
| SOX | 7 years (financial) | Marketplace transactions: 7 years |
| Tax regulations | Varies by jurisdiction | Financial records: 7 years minimum |

---

## 7. Monitoring and Enforcement

### 7.1 Automated Enforcement
- Daily cron job identifies data past retention
- Automated deletion (no human review needed for non-sensitive data)
- Sensitive data deletion requires 2-person review (CJ + admin)

### 7.2 Audit Trail
- Every deletion event is logged: `what, when, why, by_whose_request`
- Logs are immutable and retained 1 year beyond retention period
- CJ-only access to full audit log

### 7.3 Annual Review
- Retention policy reviewed annually
- Adjustments require CJ + legal counsel approval
- Policy changes communicated to users 30 days in advance

---

## 8. Data Inventory

Complete list of all data classes stored by VYVE:

| # | Data Class | Sensitivity | Retention | Encrypted? | Deletable? |
|---|-----------|-------------|-----------|-----------|-----------|
| 1 | Username | Medium | Account lifetime | Yes | Yes |
| 2 | Public keys | Medium | Account lifetime | Yes (at rest) | Yes |
| 3 | Private keys (server) | N/A | n/a | n/a | n/a |
| 4 | Encrypted messages | High | 90 days post-activity | Yes | Yes |
| 5 | Message metadata | Low | 90 days | Aggregated | Yes |
| 6 | Profile data | Medium | Until user updates | Yes | Yes |
| 7 | Public posts | Low | Until user deletes | No (by design) | Yes |
| 8 | Direct messages | High | Until user deletes | Yes | Yes |
| 9 | Group messages | High | Until user/group deletes | Yes | Yes |
| 10 | Follow graph | Low | Until user unfollows | Yes | Yes |
| 11 | Block list | Medium | Until user unblocks | Yes | Yes |
| 12 | Vault items | Critical | Until user deletes | Yes (with E2EE) | Yes |
| 13 | Vendor profile | Medium | Until vendor deletes | Yes | Yes |
| 14 | Product listings | Low | 1 year inactive | Yes | Yes |
| 15 | Order history (financial) | Medium | 7 years (legal) | Yes | No (regulatory) |
| 16 | Reviews | Low | Anonymized after 2 years | Yes | Soft delete |
| 17 | OAuth tokens | High | 1h / 30d rotation | Yes | Auto-expire |
| 18 | Server access logs | Low | 30 days | Yes | Auto-purge |
| 19 | Error logs | Low | 90 days | Yes | Auto-purge |
| 20 | Audit logs | Medium | 1 year | Yes | Auto-purge |
| 21 | Backups | High | 30 days | Yes | Auto-expire |
| 22 | Analytics (aggregated) | None | Indefinite | N/A | No PII |
| 23 | Telemetry (opt-in) | Low | 90 days | Yes | Yes (toggle off) |
| 24 | Push notification tokens | Low | Until app uninstall | Yes | Yes |
| 25 | AI memory (opt-in) | High | Until user clears | Yes | Yes |

---

## 9. Right to Be Forgotten (GDPR Article 17)

VYVE honors the right to erasure with these exceptions:

| Exception | VYVE Response |
|-----------|---------------|
| Legal obligation (financial records) | Retain per regulatory schedule, then delete |
| Public interest (public health, etc.) | Not applicable to VYVE |
| Legitimate interests (fraud prevention) | Retain for 1 year post-account-deletion in fraud DB |
| Archiving (public interest, research) | Not applicable |

User can request a status update on their erasure request at any time.
