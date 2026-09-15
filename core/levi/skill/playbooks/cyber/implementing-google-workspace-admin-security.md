---
skill_id: cyber_implementing_google_workspace_admin_security
name: Google Workspace Admin Security Hardening
description: Harden Google Workspace administration: super-admin hygiene, roles, alerts, and audit logging.
risk: low
permissions: []
requires_confirmation: false
tags: [saas, identity]
version: 1.0.0
---
## Purpose
Google Workspace is identity, email, docs, and drive for many organizations — and its admin console
is the keys to all of it. Compromised super-admins mean total tenant takeover: email access, file
exfiltration, user impersonation. This playbook hardens Workspace administration: minimal
super-admins, least-privilege admin roles, phishing-resistant MFA, alerting, and audit — the
admin-plane security program.

## When to use
- Securing the administrative plane of a Google Workspace tenant (new or existing).
- After incidents involving admin compromise, or audits flagging excessive super-admins.
- Meeting admin-security expectations (CIS, SOC 2, cyber-insurance).
- Before expanding Workspace usage (more users, more data, more risk).
- As the admin-layer complement to user-facing Workspace phishing and SSO controls.

## Prerequisites
- Super-admin access to the Admin console and an inventory of current admins and roles.
- Hardware security keys available for all admins (phishing-resistant MFA is the requirement).
- Defined admin functions: user management, security, groups, devices — to map to least-privilege
  roles.
- A SIEM or log destination for Admin audit logs (BigQuery export or API).
- Break-glass super-admin accounts created and secured (separate from daily admins).

## Procedure
1. **Minimize super-admins ruthlessly.** Reduce to 2-4 named individuals (plus break-glass). Every
   super-admin must use a hardware security key, have no email/data-access need tied to the role,
   and be documented with business justification. Review quarterly — super-admin count only goes
   down.
2. **Delegate via least-privilege admin roles.** Create custom roles: user management (no security
   settings), helpdesk (password reset only), security (alerts and investigation, no user deletion),
   groups, and device management. Assign the narrowest role that lets each admin do their job.
   Pre-built roles are starting points — customize narrower.
3. **Enforce phishing-resistant MFA for all admins.** Require security-key 2SV for every admin role
   (enforcement setting, not just policy). No SMS, no exceptions. Verify enrollment — an admin
   without enrolled keys is an admin waiting to be phished.
4. **Secure the break-glass accounts.** Two emergency super-admins: 20+ character random passwords
   in sealed storage, security keys in a safe, excluded from SSO, monitored with alerts on any
   sign-in. Test quarterly. Document that these exist and when to use them.
5. **Turn on alert center and rules.** Enable: suspicious login activity, user granted admin
   privilege, admin settings changed, government-backed attack warnings, and Drive sharing
   anomalies. Route alerts to the security team with defined severity and response SLAs — alert
   center is the tenant's IDS.
6. **Export and monitor audit logs.** Stream Admin, Login, Drive, and OAuth token audit logs to
   BigQuery/SIEM. Build detections: privilege grants, settings changes, OAuth grants to suspicious
   apps, mass file downloads/sharing, and admin sign-ins from unusual locations. Retain per policy
   (default retention is limited — export for history).
7. **Control OAuth and API access.** Review third-party OAuth grants tenant-wide: block high-risk
   scopes, allowlist approved apps, and require admin approval for new apps requesting sensitive
   scopes. Malicious OAuth is the quiet tenant-takeover path — govern it.
8. **Harden authentication settings.** Enforce: 2SV for all users (phased: admins first, then
   everyone), disallow less-secure app access, set session lengths appropriately, and enable login
   challenge for suspicious attempts. These are the tenant-wide auth baselines.
9. **Review regularly.** Quarterly access review: admin roles and super-admins (still needed?),
   OAuth grants (still used?), alert-center rule effectiveness, and break-glass tests. Annual: full
   tenant security assessment against the CIS Google Workspace benchmarks.
10. **Document the admin security model.** Write down: role definitions, the super-admin roster with
    justifications, MFA requirements, alert handling, break-glass procedures, and the review
    cadence. Auditors ask for exactly this document.

## Expected outputs
- 2-4 super-admins with security keys; least-privilege custom roles for all other admin functions.
- Phishing-resistant MFA enforced for admins (and phased for users); break-glass tested.
- Alert-center rules active with SOC routing; audit logs exported to SIEM with detections.
- OAuth/API governance: risky scopes blocked, approved-app allowlisting.
- Quarterly reviews and a documented admin security model.

## Pitfalls
- Super-admin sprawl: "temporary" super-admins that never get revoked. Quarterly reviews with
  removal defaults.
- MFA policy without enforcement: "required" in docs but not in settings. Verify enrollment and
  enforcement state.
- Alert center without routing: alerts nobody reads are decoration. SOC integration with SLAs.
- Ignoring OAuth: admin hardening means little when a malicious OAuth app has Drive-wide scopes.
  Govern third-party access.
- Default log retention: Workspace logs age out — export to BigQuery/SIEM for the retention your
  policy requires.

## References
- Google Workspace Admin Help: security best practices and admin roles
- CIS Google Workspace Foundations Benchmark
- Google Workspace Alert Center documentation
- NIST SP 800-53 AC-2, AC-6, AU (account management, least privilege, auditing)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
