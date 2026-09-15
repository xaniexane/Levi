---
skill_id: cyber_auditing_entra_id_with_aadinternals
name: Auditing Entra ID with AADInternals
description: Deep Entra ID assessment with AADInternals: recon, misconfigurations, and drift.
risk: moderate
permissions: [cloud.read]
requires_confirmation: true
tags: [identity, cloud]
version: 1.0.0
---
# Auditing Entra ID with AADInternals

## Purpose

Use the AADInternals PowerShell module — a community auditing toolkit for Microsoft Entra
ID (formerly Azure AD) — to export tenant configuration, analyze hybrid identity settings,
and surface misconfigurations that the Entra admin center makes hard to review at scale.
This is a defensive configuration audit: export, analyze, and report.

## When to use

- Deep-dive Entra ID assessments where portal clicking does not scale across hundreds of
  policies, apps, and role assignments.
- Hybrid identity reviews (Entra Connect sync configuration, password hash sync, seamless
  SSO, federation trust settings).
- Repeating an audit on a schedule — scripted exports make quarter-over-quarter diffs
  practical.
- Complementing the portal-based audit in auditing-azure-active-directory-configuration
  with bulk-exported evidence.

## Prerequisites

- Written authorization and a defined scope (tenant ID(s) in bounds).
- A Windows or PowerShell 7 workstation with the AADInternals module installed from the
  PowerShell Gallery (`Install-Module AADInternals`); review the module version and keep
  it pinned for reproducibility.
- An audit account with `Global Reader` + `Security Reader` (no write roles needed for
  export-based auditing).
- A secure, access-controlled folder for exports — tenant exports contain sensitive
  configuration and must be handled as confidential.

## Procedure

1. **Prepare the environment.**
   - Install and pin the module version; record it in the working papers.
   - Discover available capabilities with `Get-Command -Module AADInternals` and read
     `Get-Help` for any cmdlet before running it — cmdlet names and parameters change
     between releases.

2. **Authenticate with least privilege.**
   - Sign in with the read-only audit account and acquire tokens scoped to the Microsoft
     Graph / Azure AD Graph endpoints the export cmdlets need.
   - Verify the signed-in identity and tenant ID before exporting anything.

3. **Export conditional access policies.**
   - Use the module's conditional access export capability to dump every policy to JSON.
   - Review each policy's state (enabled vs. report-only), included/excluded users, apps,
     conditions, and grant controls — the same coverage analysis as the portal audit, but
     diffable.

4. **Export application and service principal inventory.**
   - Dump app registrations, enterprise apps, and their OAuth permission grants.
   - Flag unverified publishers, broad delegated/application scopes, and recently modified
     apps by comparing `createdDateTime` / credential addition timestamps.

5. **Analyze hybrid identity configuration.**
   - Export Entra Connect sync settings: which attributes sync, password hash sync state,
     seamless SSO configuration, and federation trust details.
   - Flag password hash sync disabled without justification, stale sync servers, and
     federation trusts pointing at decommissioned ADFS farms.

6. **Review privileged role assignments in bulk.**
   - Export directory role assignments and membership of privileged roles.
   - Cross-reference against the break-glass inventory and PIM eligibility from the
     companion portal audit.

7. **Check authentication methods and legacy exposure.**
   - Export per-user MFA/authentication-method registration state to find privileged
     accounts with weak or missing methods.
   - Correlate with sign-in log exports for legacy protocol usage (IMAP/POP/SMTP AUTH).

8. **Diff against the previous audit.**
   - If a prior export exists, diff the JSON exports to produce a change list: new apps,
     policy edits, role changes.
   - Investigate every unexpected change; expected changes should map to approved change
     tickets.

9. **Sanitize and store evidence.**
   - Strip secrets/tokens from exports before filing; keep the raw exports in the
     access-controlled folder with a retention policy.
   - Record the exact cmdlets, parameters, and module version used so the export is
     reproducible.

10. **Report findings with tenant evidence.**
    - For each finding cite the exported object (policy name, app ID, role assignment) and
      the export file/line or query that proves it.

## Key tools & commands

- AADInternals PowerShell module (`Install-Module AADInternals`; discover with
  `Get-Command -Module AADInternals`, document with `Get-Help <cmdlet> -Full`).
- Microsoft Graph PowerShell SDK — cross-checks exports against live Graph data.
- `Compare-Object` / JSON diffing (`diff`, `jq`) for quarter-over-quarter export
  comparison.
- Entra admin center — spot-verify a sample of exported findings in the portal so the
  tenant team can reproduce them without the module.

## Expected outputs

- Versioned, timestamped tenant configuration exports (conditional access, apps, roles,
  hybrid sync settings).
- Diff report against the previous audit period with change investigation notes.
- Findings register with evidence pointers into the exports.
- Reproducibility notes: module version, cmdlets, parameters, and account used.

## Pitfalls

- Asserting cmdlet names from memory — the module evolves; always confirm with
  `Get-Command`/`Get-Help` in the installed version rather than copying old blog posts.
- Exporting with an over-privileged account and then storing the exports carelessly —
  least privilege applies to the auditor too.
- Treating an export as a point-in-time truth weeks later; tenants change daily, so date
  every export.
- Some AADInternals capabilities are dual-use (built for both administration and
  offensive research) — stay strictly within the authorized read-only audit scope and do
  not touch token-forging or PRT-related functions.

## References

- AADInternals project documentation and cmdlet help (PowerShell Gallery / project site).
- Microsoft Learn: "Microsoft Entra Connect Sync" documentation, "What is Conditional
  Access", "Application consent and permissions".
- Microsoft Graph API reference for the underlying resources being exported.
- MITRE ATT&CK: T1078 (Valid Accounts), T1556 (Modify Authentication Process).

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
