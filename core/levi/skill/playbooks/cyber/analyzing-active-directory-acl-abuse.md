# Analyzing Active Directory ACL Abuse

## Purpose

Detect, investigate, and remediate abuse of Active Directory discretionary access control lists — the misconfigured permissions (GenericAll, GenericWrite, WriteDacl, WriteOwner, WriteProperty on sensitive attributes) that turn ordinary accounts into domain-compromise paths. This is one of the highest-leverage AD hardening activities: most domain compromises traverse a permission that should never have existed.

## When to use

- BloodHound/SharpHound attack-path output shows unexpected principals with write rights over Tier-0 objects.
- Incident response finds evidence of DCSync, targeted Kerberoasting, or attribute writes (e.g., `msDS-KeyCredentialLink`, `servicePrincipalName`) and you need the enabling permission.
- Proactive AD hardening reviews or pre-assessment attack-path audits.
- After any AD compromise, to close the permission paths the attacker used or could have used.
- Before/after identity-system migrations, which frequently introduce excessive delegated permissions.

## Prerequisites

- Written authorization from the AD/domain owner to enumerate ACLs, collect replication metadata, and modify permissions during remediation.
- Chain-of-custody notes: export ACLs and `repadmin /showobjmeta` output before changing anything.
- A domain-joined analysis host with RSAT / ActiveDirectory module; BloodHound with SharpHound collector for path analysis (used defensively, with authorization).
- DC Security logs with "Audit Directory Service Changes" enabled for historical write attribution — verify this *before* you need it.
- A list of legitimate delegated-administration models (who is *supposed* to manage what) to distinguish design from drift.

## Procedure

1. **Collect the current ACL posture.** Ingest AD objects with SharpHound (defensive collection you authorized) and load into BloodHound, or enumerate directly without third-party tools:
   ```powershell
   $obj = [ADSI]"LDAP://CN=Administrator,CN=Users,DC=corp,DC=example,DC=com"
   $obj.ObjectSecurity.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]) |
     Select-Object IdentityReference, ActiveDirectoryRights, AccessControlType
   ```
   For broad sweeps, script this across OUs and privileged groups; store the raw output versioned so you can diff over time.
2. **Prioritize dangerous rights on high-value targets.** Rank findings: GenericAll/WriteDacl/WriteOwner on the domain object, AdminSDHolder, Domain Admins/Enterprise Admins groups, GPOs linked at domain level, and KRBTGT-adjacent objects first. Then GenericWrite/WriteProperty on user and computer objects — these enable targeted Kerberoasting via SPN writes, shadow credentials via KeyCredentialLink writes, and Resource-Based Constrained Delegation via `msDS-AllowedToActOnBehalfOfOtherIdentity`.
3. **Distinguish legitimate from excessive.** Built-in principals (SYSTEM, Domain Admins, Enterprise Admins, the object's own SELF where expected) are normal. Flag: helpdesk groups with GenericWrite on all users, service accounts with WriteDacl anywhere, any non-admin with rights over privileged groups or GPOs, and delegated "account management" groups whose scope quietly expanded beyond their OU.
4. **Attribute suspected writes to actors.** For each abused permission, pull replication metadata to find what changed and when:
   ```powershell
   repadmin /showobjmeta <DC> "<distinguished name>"
   ```
   Correlate with DC Security event 4662 (directory service access) for the writer's identity, and with 5136 (directory service object modified) for the before/after values. This turns "a bad permission exists" into "this account used it at this time."
5. **Map the full attack path.** In BloodHound, trace from the attacker's foothold principal through group nesting to the abused right to the target. Document each hop — remediation must break the *path*, and nested groups are where paths hide. Export the path as evidence; "remove user X from group Y" is an actionable ticket, "fix AD" is not.
6. **Check for persistence the ACL enabled.** Common follow-ons once write access exists: DCSync rights (Replicating Directory Changes) granted to non-DCs, GPO modifications pushing malicious settings, SID-history injection, `msDS-KeyCredentialLink` writes, and SPN additions for Kerberoasting. If the ACL abuse is confirmed, sweep for each of these — assume the attacker used the access until evidence says otherwise.
7. **Remediate the permission.** With authorization, remove the excessive ACE. Prefer removing the principal from the granting group over editing the ACL directly when the grant came via group nesting — group-based remediation is auditable and survives SDPropagator cycles. Re-run the enumeration to confirm the path is closed, and diff before/after.
8. **Reset potentially compromised targets.** If the abused right could have been *used* (not just held), treat the target as compromised: reset passwords, rotate KRBTGT if domain-level compromise is possible (twice, per Microsoft guidance), review GPO versions for unauthorized changes, and audit privileged-group memberships.
9. **Deploy detections.** SIEM rules: 4662 events for WriteDacl/WriteOwner/GenericWrite against Tier-0 object classes; scheduled SharpHound diffs alerting on new dangerous ACEs; alerts on new "Replicating Directory Changes" grants to non-DC principals; and monitoring of AdminSDHolder ACL modifications.
10. **Prevent recurrence.** Implement an AD change-control workflow requiring approval for ACL changes on protected objects, run the ACL audit on a schedule (monthly for Tier-0, quarterly elsewhere), and include ACL review in the joiner/mover/leaver process for delegated-administration groups.

## Key tools & commands

- SharpHound + BloodHound — attack-path visualization from authorized defensive collection; the fastest way to see nested-group paths.
- PowerShell `[ADSI]` / `Get-ACL 'AD:\...'` — direct ACL enumeration without third-party tools.
- `repadmin /showobjmeta` — who changed which attribute and when, per replication metadata.
- `dsacls` — command-line ACL review and modification on directory objects.
- DC Security log 4662 (access) and 5136 (modification) with Advanced Audit Policy "Audit Directory Service Access/Changes".

## Expected outputs

- A ranked list of dangerous ACEs: principal, right, target object, and legitimacy verdict with justification for each.
- Attack-path traces from foothold to Tier-0 for each confirmed abuse path, exported as evidence.
- Remediation log: ACEs removed, groups changed, before/after diffs, re-verification results.
- Compromise-scoping results for abused rights: what was checked, what was reset.
- Scheduled ACL-drift detection and an AD change-control procedure with an owner.

## Pitfalls

- AdminSDHolder/SDPropagator overwrites ACLs on protected objects hourly — editing a protected object's ACL directly without fixing AdminSDHolder means your change gets reverted (or the attacker's does, which can mask the issue). Fix the source.
- Removing a legitimate ACE (backup software, identity-sync service, PAM solution) breaks production. Verify the granting business need with the service owner before removal, and schedule changes in maintenance windows.
- 4662 without proper SACLs/audit policy gives you nothing; confirm "Audit Directory Service Changes" is actually enabled before an incident, not during.
- Focusing only on users: computer objects and GPOs are equally abused (RBCD starts with a single WriteProperty on a computer object).
- One-time audits decay: permissions accrete through helpdesk tickets and project work. Without scheduled re-audits, you're clean for exactly one day.

## References

- MITRE ATT&CK: T1078 (Valid Accounts), T1484 (Domain Policy Modification), T1207 (Rogue Domain Controller / DCSync rights), T1134 (Access Token Manipulation — SID history)
- Microsoft Docs: "AdminSDHolder protected groups" (SDPropagator behavior)
- Microsoft Docs: "Audit Directory Service Changes" advanced audit policy
- Microsoft guidance on KRBTGT reset procedures (double-reset)
- BloodHound documentation (defensive attack-path analysis)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
