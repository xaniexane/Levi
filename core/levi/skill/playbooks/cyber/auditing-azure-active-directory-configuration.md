# Auditing Azure Active Directory Configuration

## Purpose

Assess the security configuration of Azure Active Directory (Microsoft Entra ID) tenants:
identity protection, conditional access coverage, legacy protocol exposure, privileged role
hygiene, and app consent posture. (Tenant configuration auditing; for Entra ID attack
detection see the companion Roadtools playbook.)

## When to use

- Annual identity security reviews or compliance audits.
- After mergers, tenant migrations, or major conditional access changes.
- When onboarding a new tenant into the security program.
- Following a privileged-account or consent-grant incident.
- Before enabling new authentication methods (FIDO2, Temporary Access Pass) tenant-wide.

## Prerequisites

- Written authorization and a defined scope (tenant ID(s) in bounds).
- Read-only audit access: `Global Reader` plus `Security Reader` roles, or scoped Graph API
  permissions (`Policy.Read.All`, `Directory.Read.All`, `IdentityRiskEvent.Read.All`,
  `AuditLog.Read.All`).
- Inventory of expected break-glass accounts, legacy applications requiring old protocols,
  and approved OAuth apps.

## Procedure

1. **Inventory privileged roles.**
   - List all assignments for Global Administrator, Privileged Role Administrator, and
     other high-impact roles via Graph `roleManagement/directoryRoleAssignments`.
   - Flag standing assignments that should be PIM-eligible, dormant privileged accounts
     (no sign-in in 90+ days), and privileged accounts without MFA (excluding break-glass).

2. **Verify break-glass accounts.**
   - Confirm at least two emergency-access accounts exist, are excluded from conditional
     access, use FIDO2 or strong MFA, and have long, vaulted passwords.
   - Confirm alerting fires on any use of these accounts.

3. **Review conditional access coverage.**
   - Export all policies (`GET /policies/conditionalAccessPolicies`) and check that every
     policy has no unintended exclusions.
   - Verify legacy authentication is blocked, risky sign-ins trigger MFA or block, and
     policies apply to all users, all cloud apps, and all device platforms unless
     explicitly justified.

4. **Check legacy authentication.**
   - In sign-in logs, filter for legacy protocols: IMAP, POP, SMTP AUTH, older Office
     clients (`clientAppUsed` values like "IMAP4", "POP3", "SMTP").
   - Any success here bypasses modern MFA — block via conditional access and disable SMTP
     AUTH per mailbox where unused.

5. **Audit Identity Protection and risk policies.**
   - Confirm risky-user and risky sign-in policies are enabled and enforced (not
     report-only), MFA registration policy covers all users, and risk detections are
     triaged rather than auto-dismissed.

6. **Review app registrations and consent.**
   - List all app registrations; flag apps with unused-but-valid secrets, recently added
     redirect URIs, unverified publishers requesting broad scopes, and admin consent
     grants to third-party multi-tenant apps.
   - Confirm user consent is restricted and the admin consent workflow is enabled.

7. **Check external identities and guest hygiene.**
   - Review guest users with privileged or broad group memberships and stale guests (no
     sign-in in 90+ days).
   - Review cross-tenant access settings for unexpected inbound access allowances.

8. **Audit PIM and access reviews.**
   - Confirm Privileged Identity Management is used for eligible assignments, activation
     requires MFA and justification, and approval workflows exist for the most sensitive
     roles.
   - Confirm recurring access reviews cover privileged roles and guest access, with
     reviewers who actually act on them.

9. **Review audit log retention and alerting.**
   - Confirm diagnostic settings export audit and sign-in logs with adequate retention for
     investigation timelines.
   - Confirm alerts exist for role assignments, conditional access policy changes, and
     break-glass account use.

10. **Report with tenant evidence.**
    - For each finding record the policy/role/app name, current setting, expected setting,
      and the Graph query or portal path used so the tenant team can reproduce it.
    - Prioritize by exploitability: legacy auth and standing global admins first.

## Key tools & commands

- Microsoft Graph: `GET /policies/conditionalAccessPolicies`, `/directoryRoles`,
  `/roleManagement/directoryRoleAssignments`, `/applications`,
  `/auditLogs/directoryAudits` — scriptable, repeatable evidence.
- Entra admin center: Identity → Users, Roles, Conditional Access, App registrations,
  Identity Protection dashboards.
- Microsoft Graph PowerShell (`Get-MgPolicyConditionalAccessPolicy` and related cmdlets)
  for offline review and diffing between audits.
- Microsoft Secure Score (Identity section): useful directional signal, not a substitute
  for the checks above.

## Expected outputs

- Privileged role assignment inventory with dormant/standing flags.
- Conditional access gap analysis (uncovered users, apps, platforms, protocols).
- App consent and registration risk list with scope details.
- Findings register with reproduction steps and prioritized remediation.

## Pitfalls

- Report-only conditional access policies that look like coverage but enforce nothing —
  check policy state, not just existence.
- Exclusions that swallow the policy: "all users except…" lists grow silently; diff
  exclusions each audit.
- Service accounts excluded from MFA without compensating controls (migrate to managed
  identities, or gate with compliant-device conditional access).
- Confusing Secure Score improvements with real risk reduction — enabling low-value
  controls to raise the score does not equal coverage.

## References

- MITRE ATT&CK: T1078 (Valid Accounts), T1556 (Modify Authentication Process), T1528
  (Steal Application Access Token).
- Microsoft Learn: "Plan a Conditional Access deployment", "Secure privileged access",
  "Detect and remediate illicit consent grants".
- CIS Microsoft 365 Foundations Benchmark: identity controls.
- Microsoft Graph API reference: conditionalAccessPolicy, directoryRoleAssignment
  resources.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
