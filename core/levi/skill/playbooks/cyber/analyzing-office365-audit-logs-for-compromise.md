---
skill_id: cyber_analyzing_office365_audit_logs_for_compromise
name: Analyzing Office 365 Audit Logs for Compromise
description: Detect M365 compromise: impossible travel, inbox rules, and consent grants.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, siem]
version: 1.0.0
---
# Analyzing Office 365 Audit Logs for Compromise

## Purpose

Detect mailbox and tenant compromise in Microsoft 365 unified audit logs — anomalous logons, mailbox rule creation, eDiscovery abuse, and consent-grant attacks — and scope the blast radius.

## When to use

- A phishing or credential-stuffing wave hit the tenant; you need to know which accounts fell.
- An alert fired on impossible travel, mass file downloads, or forwarding-rule creation.
- Post-incident validation that attacker-created persistence (rules, OAuth grants) is fully removed.

## Prerequisites

- Written authorization; tenant Global Reader / Security Reader equivalent access (use least privilege, no Global Admin for analysis).
- Unified audit logging enabled in the tenant (verify: it can be off; enablement is not retroactive).
- Incident window defined; list of known-good admin accounts and expected admin IPs.
- Timezone: M365 audit timestamps are UTC — keep everything in UTC.

## Procedure

1. Confirm unified audit logging is (and was) enabled for the window; note any gap — absence of logs is a finding, not clearance.
2. Export the relevant audit records for the window. Via Purview audit search or:
   `Search-UnifiedAuditLog -StartDate <UTC> -EndDate <UTC> -ResultSize 5000`
   Page through results; do not assume the first page is complete.
3. Hunt anomalous logons: filter `Operation = "UserLoggedIn"` and flag logons from new countries/ASNs, Tor/VPN exit nodes, or outside the user's normal hours.
4. Hunt mailbox persistence rules (T1137): `Operation = "New-InboxRule"` / `"Set-InboxRule"`.
   Flag rules that forward to external addresses, mark-as-read and move to RSS/Archive, or were created outside business hours.
5. Check OAuth consent grants (T1528): `Operation = "Consent to application"` — review newly consented apps, especially those requesting `Mail.Read`/`Files.Read.All` with unverified publishers.
6. Review eDiscovery and search activity: `Operation` like `"SearchMailbox"` / `"New-ComplianceSearch"` by non-standard admins — attackers use it for internal reconnaissance and collection.
7. Look for mass access patterns: `Operation = "MailItemsAccessed"` spikes, or SharePoint `FileDownloaded` bursts from one user across many libraries (exfiltration staging).
8. Check admin role changes and MFA modifications: `Operation = "Add member to role"` and `"Set-MsolUser"`/`Update StsRefreshTokenValidFrom` equivalents — persistence via privilege.
9. Correlate each suspicious operation with sign-in logs (IP, ASN, user agent, MFA result) to separate attacker sessions from legitimate travel.
10. Scope: for each confirmed-compromised account, list every operation in the window — sent mail, rules created, files accessed, apps consented — to define remediation (password reset, session revoke, rule deletion, app removal).
11. Check Teams and SharePoint for attacker-created persistence: malicious Teams apps or SharePoint sharing links created during the window extend access beyond mail.
12. Review organization-wide mail-flow rules: `Get-TransportRule` — a transport rule BCCing external addresses is stealthier than an inbox rule and survives mailbox remediation.
13. Audit legacy-protocol usage: Basic-auth or SMTP-AUTH logons in the window indicate credential replay that persists even after MFA enforcement.
14. Check mailbox delegation: `Add-MailboxPermission` operations or folder-level delegation grants the attacker persistent access without needing the password.
15. Review sent-mail flow for the forwarding rules' effects: search Sent Items during the compromise window for auto-forwarded sensitive content.
16. Check for attacker-registered MFA methods: new phone numbers or authenticator registrations signal account-takeover persistence.
17. Check Conditional Access policies for attacker-added exclusions that would survive credential resets.
18. Review app registrations (not just consent grants): attacker-created apps with mail permissions are full backdoors.
19. Check Teams chat for attacker-sent messages — compromised accounts get reused for internal phishing.
20. Cross-check with Defender/MCAS alerts for the same accounts and timeframe before closing.
21. Remediate per account: revoke sessions, reset credentials, delete malicious inbox rules and OAuth grants, then re-run the searches to verify cleanliness.
22. Preserve the exported logs with hashes; note the exact search parameters so the export is reproducible.

## Key tools & commands

- Microsoft Purview audit search (UI) — filtered export of unified audit log.
- `Search-UnifiedAuditLog -StartDate -EndDate -Operations <list> -ResultSize 5000` — Exchange Online PowerShell.
- `Get-InboxRule -Mailbox <user>` — enumerate existing rules for verification.
- `Get-AzureADServicePrincipal` / Entra app consent review — audit granted applications.
- Sign-in logs in Entra ID — IP/ASN/user-agent/MFA correlation.
- `Get-TransportRule` — organization-wide mail-flow rules.
- `Revoke-AzureADUserAllRefreshToken -ObjectId <id>` — session revocation during remediation.
- Entra application consent-grant review — inventory of granted app permissions.
- Purview alert policies — turning findings into ongoing detections.

## Expected outputs

- Compromised-account list with per-account activity timelines.
- Malicious inbox rules and OAuth grants inventoried (and removed).
- eDiscovery/admin-abuse findings with actor attribution.
- Evidence exports with hashes and reproducible search parameters.
- Remediation checklist per account, verified by re-search.
- Transport-rule inventory (organization-wide forwarding/BCC rules).
- Legacy-protocol (Basic auth / SMTP AUTH) logon findings.

## Pitfalls

- Audit logging was disabled for part of the window — you cannot prove a negative; say so explicitly.
- `ResultSize 5000` truncation silently dropping records — always page and count.
- Treating impossible-travel alerts as proof without checking VPN/proxy egress IPs.
- Removing the inbox rule but leaving the OAuth grant — the attacker walks back in.
- Forgetting service accounts and shared mailboxes in scoping.
- Purging audit logs before the retention review is complete.
- Missing app-only (daemon) permissions that operate with no user context.
- Shared mailboxes lacking sign-in logs — use the audit log instead of assuming no access.
- Unified audit log latency: events can lag by hours — re-run searches before closing.
- `Search-UnifiedAuditLog` date parameters are UTC — local-time queries shift the window.
- Missing guest/B2B account activity — scope includes external users.
- Confusing "MFA succeeded" with "legitimate" — session-cookie theft passes MFA.
- Not checking Conditional Access policy exclusions the attacker may have added.
- Searching only the primary mailbox — check archives and litigation holds.
- Forgetting that audit-log retention varies by license — E3 vs. E5 matters.
- Not exporting the raw JSON — CSV exports lose nested fields.
- Assuming one compromised account — check for lateral consent grants.
- Missing Teams private-channel activity in the audit scope.
- Closing the case before the 24-hour re-check for delayed log arrival.
- Unified Audit Log disabled by default in some tenants — enable it before you need it.
- 90-day retention on E3 — export to Sentinel/SIEM or evidence ages out.
- `Search-UnifiedAuditLog` throttles on large result sets — page with `-SessionId`.
- Service-principal sign-ins do not appear where user sign-ins do — check both.
- UAL timestamps are UTC — convert before correlating with local logs.
- Mailbox audit bypass — verify `AuditBypassEnabled` is not set on target mailboxes.

## References

- Microsoft Purview auditing documentation: https://learn.microsoft.com/purview/audit-log-search
- Microsoft Entra sign-in log documentation: https://learn.microsoft.com/entra/id-protection/concept-identity-protection-sign-in-risk
- Microsoft — investigating compromised accounts guidance
- MITRE ATT&CK T1137 (Office Application Startup / inbox rules), T1528 (Steal Application Access Token), T1114.002 (Remote Email Collection), T1136 (Create Account)
- CISA guidance on Microsoft 365 compromise detection

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
