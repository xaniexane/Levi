---
skill_id: cyber_implementing_pam_for_database_access
name: Implementing PAM for Database Access
description: Bring database access under privileged access management — vaulted credentials, just-in-time elevation, session proxying, and query-level auditing.
risk: low
permissions: []
requires_confirmation: false
tags: [pam, database, access-control]
version: 1.0.0
---
## Purpose

End the era of shared `sa` passwords in spreadsheets and permanent DBA access. This playbook puts database privileged access under PAM control: credentials vaulted and rotated, human access via checkout or proxied sessions with full query auditing, application access via managed secrets rotation — so every privileged database action is attributable, time-bound, and logged.

## When to use

- Remediating shared database credentials (the most common database audit finding).
- Meeting requirements for privileged database access control (PCI DSS 4.0 Req 7/8, SOX, HIPAA).
- Containing the blast radius of compromised DBA credentials or applications.
- Providing auditors with query-level evidence of who accessed what data.
- Supporting DBAs, developers, and vendors who need occasional production database access.

## Prerequisites

- Inventory of databases (engines, versions, environments) and every account with elevated privileges, including application service accounts.
- PAM platform with database connectors (CyberArk, Delinea, BeyondTrust, or native vaulting with rotation scripts) able to manage your database engines.
- Defined access tiers: who needs what level (read-only analytics, DBA admin, schema-change, break-glass) per environment.
- Application inventory for service accounts that will move to vaulted, rotated credentials.
- SIEM ingestion for PAM session and database audit logs.

## Procedure

1. **Discover and classify privileged database accounts.** Scan every database for privileged roles: sysadmin/superuser, db_owner, accounts with GRANT privileges, and — critically — shared accounts. Classify each as human-interactive, application service account, or legacy/unknown. Unknown privileged accounts get investigated, not grandfathered.
2. **Vault and rotate service-account credentials.** Move application database credentials into the PAM vault with automatic rotation (dual-account rotation where the engine supports it, to avoid application downtime). Update applications to retrieve credentials via the vault API or a secrets-injection sidecar — never config files or environment variables in plaintext.
3. **Eliminate shared human credentials.** Replace shared `sa`/root database logins with named accounts provisioned just-in-time through the PAM portal: request, approve, check out for a bounded window, auto-rotate on check-in. Keep one break-glass account per critical database with split-knowledge custody and monitored use.
4. **Proxy interactive sessions.** Route DBA and vendor interactive access through the PAM session proxy/manager (SSH/RDP for bastion-style, or database-protocol proxying where supported). Proxied sessions give you keystroke/query logging, session recording, and the ability to terminate live sessions — capabilities direct connections never provide.
5. **Enforce least-privilege database roles.** Rebuild database permissions on role-based lines: read-only roles for analytics and support, scoped write roles for application functions, DDL/admin reserved for JIT elevation. Remove `db_owner` and `sysadmin` grants that accumulated over years; most holders need a fraction of those rights.
6. **Enable query-level auditing.** Turn on database audit logging (SQL Server Audit, pgAudit, Oracle Unified Auditing, MySQL Enterprise Audit) capturing privileged actions: logons, schema changes, permission grants, bulk exports, and access to sensitive tables. Ship to the SIEM and alert on: privilege grants, mass exports, access outside change windows, and break-glass use.
7. **Govern schema changes.** Tie elevated database access to the change process: production DDL requires an approved change ticket referenced in the PAM checkout, and all schema changes flow through version-controlled migration scripts — never ad-hoc production edits. Reconcile applied migrations against the repo regularly.
8. **Review access on cadence.** Quarterly, review privileged database grants against the PAM checkout records: standing grants get challenged, dormant privileged accounts get removed, and vendor access gets re-justified. Report metrics: standing privileged accounts trending down, checkout volume, and audit-log coverage per database.

## Expected outputs

- Privileged database account inventory with classification and remediation status.
- Vaulted, auto-rotated service-account credentials with application integration.
- JIT checkout workflows replacing shared credentials; break-glass accounts with monitoring.
- Proxied interactive sessions with recording; query-level audit logging to SIEM.
- Role-based database permissions; change-tied DDL process; quarterly access reviews.

## Pitfalls

- **Rotating credentials without application readiness.** Rotating a service-account password that an application reads once at startup causes an outage at rotation time. Verify dynamic retrieval or use dual-account rotation patterns.
- **Audit logging without storage planning.** Query-level auditing on busy OLTP systems generates enormous volumes. Scope auditing to privileged actions and sensitive objects, and size the log pipeline accordingly.
- **Vendors demanding sysadmin.** Third-party applications and vendor support routinely demand excessive privileges. Push back with scoped roles, time-bound JIT grants, and recorded sessions — "the vendor requires it" is not a risk acceptance.
- **Break-glass without monitoring.** An unmonitored emergency account becomes the persistent backdoor. Any use must page security, and credentials must rotate after each use.
- **Forgetting cloud-managed databases.** RDS, Cloud SQL, and Azure SQL have their own IAM integrations and audit mechanisms — apply the same vaulting and JIT principles via cloud-native paths rather than assuming on-prem tooling covers them.

## References

- NIST SP 800-53 Rev. 5, AC-2, AC-6, AU-2/AU-3 (account management, least privilege, auditing) — https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- PCI DSS v4.0 Requirements 7–8 (access control) — https://www.pcisecuritystandards.org/
- MITRE ATT&CK T1078 (Valid Accounts) and T1505 (Server Software Component) — https://attack.mitre.org/techniques/T1078/
- Database vendor audit documentation (SQL Server Audit, pgAudit, Oracle Unified Auditing)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
