# Detecting Shadow Credential Abuse for Privilege Escalation

## Purpose

Detect and investigate abuse of Active Directory "shadow credentials" —
alternate authentication material (KeyCredential objects) added to an
account's `msDS-KeyCredentialLink` attribute. An attacker who can write to
that attribute can authenticate as the victim via Kerberos PKINIT without
knowing the password. Covers detection, forensic attribution, containment,
and durable hardening.

## When to use

- A DCSync-equivalent or ACL-abuse alert names an account with write access
  to another account's `msDS-KeyCredentialLink`.
- You see Kerberos PKINIT / certificate-based logons for accounts that
  should only use password auth.
- During AD security assessments or incident response where the path
  "generic write → shadow credential → privesc" is suspected.
- After containing an AD compromise, to sweep for persisted shadow
  credentials (a common, quiet persistence mechanism).
- When onboarding Windows Hello for Business, to distinguish legitimate
  KeyCredentialLink writes from malicious ones.

## Prerequisites

- Written authorization from the AD/domain owner to query and, if needed,
  clear `msDS-KeyCredentialLink` values.
- Chain-of-custody notes: export the attribute values, `whenChanged`, and
  replicating DC before modifying anything.
- A domain-joined workstation with RSAT (ActiveDirectory PowerShell module)
  or equivalent LDAP access, plus rights to read the attributes in question.
- Centralized DC event logs (Security log: 4662 directory-service access,
  4768/4769 Kerberos events) with sufficient retention.
- An inventory of legitimate KeyCredentialLink writers (Hello for Business
  provisioning, hybrid-join services) to avoid false positives.

## Procedure

1. **Understand the primitive.** Shadow credentials work by writing a KeyCredential (a public key bound to the account) into `msDS-KeyCredentialLink`. The attacker then authenticates via Kerberos PKINIT using the matching private key. Detection therefore centers on *writes* to that attribute and *PKINIT logons* — traditional failed-logon monitoring will miss it entirely.
2. **Inventory current KeyCredentialLink values.** Enumerate which accounts presently carry key credentials for a baseline:
   ```powershell
   Get-ADUser -Filter * -Properties msDS-KeyCredentialLink |
     Where-Object { $_.'msDS-KeyCredentialLink' } |
     Select-Object SamAccountName, DistinguishedName
   ```
   Repeat for computer objects with `Get-ADComputer`. Compare against your known-good inventory — hybrid-joined devices and Windows Hello for Business enrollments legitimately populate this attribute.
3. **Hunt for unauthorized writes.** On domain controllers, search the Security log for event 4662 with access to `msDS-KeyCredentialLink` or write access against user/computer objects outside change windows. Correlate the caller's identity — service accounts and helpdesk accounts writing key credentials they never wrote before are high priority. Note: this requires "Audit Directory Service Changes" enabled *before* the incident.
4. **Hunt for anomalous PKINIT authentication.** Look for Kerberos TGT requests (4768) using certificate-based pre-authentication for accounts with no legitimate Hello-for-Business enrollment. A password-only service account suddenly authenticating via PKINIT is a strong signal. Build the expected-PKINIT population from your Hello for Business deployment records.
5. **Trace the write path.** Determine *how* the attacker gained the write: check ACLs on the victim object for GenericWrite/GenericAll/WriteProperty grants, review group memberships granting those rights (Account Operators, custom helpdesk groups), and map the path with BloodHound if available. Document each hop — remediation must break the path, not just clear the attribute.
6. **Check for persistence beyond the attribute.** Attackers who add shadow credentials often modify other attributes too. Review `whenChanged`/`whenCreated` on the victim object and diff recent attribute changes with replication metadata:
   ```powershell
   repadmin /showobjmeta <DC> "<victim DN>"
   ```
   Look for concurrent changes to `servicePrincipalName` (Kerberoasting setup), group memberships, or `userAccountControl`.
7. **Assess what the shadow credential was used for.** Correlate the PKINIT logons with subsequent activity: which hosts were accessed, which resources touched, whether DCSync or further privilege escalation followed. This determines whether this was a foothold, a persistence mechanism, or the actual privilege-escalation step — each drives different scoping.
8. **Contain.** With authorization: remove the rogue KeyCredentialLink values, disable or reset the foothold account, and revoke Kerberos tickets issued via the abused key (force a password reset, which invalidates the key-material binding). Verify removal by re-querying the attribute afterward — don't assume.
9. **Eradicate the write path.** Remove the excessive ACL grant or group membership that permitted the write. Do not just clear the attribute — the attacker will re-add it if the path remains. Re-run the ACL enumeration to confirm the path is closed.
10. **Build durable detections.**
    SIEM rules: (a) 4662 writes to `msDS-KeyCredentialLink` where the
    subject is not an approved provisioning service; (b) PKINIT 4768 events
    for accounts outside the Hello-for-Business population; (c) a scheduled
    LDAP sweep diffing KeyCredentialLink populations daily and alerting on
    unexplained additions.
11. **Harden AD structurally.**
    Tier the AD control plane, remove standing GenericWrite grants on
    privileged objects, monitor privileged-group membership changes, require
    approval workflows for ACL changes on Tier-0 objects, and document the
    legitimate KeyCredentialLink writer list as a living control.

## Key tools & commands

- ActiveDirectory PowerShell module (`Get-ADUser`, `Get-ADComputer`,
  `-Properties msDS-KeyCredentialLink`) — inventory and baselining.
- `repadmin /showobjmeta` — attribute-level replication metadata showing
  who changed what and when.
- DC Security log, event 4662 — directory-service object access auditing
  (requires Advanced Audit Policy "Audit Directory Service Changes").
- Kerberos events 4768/4769 — TGT/service-ticket requests; the pre-auth
  type field reveals PKINIT usage.
- BloodHound / SharpHound (defensive attack-path mapping) — identify which
  principals hold write rights over high-value targets.
- AD ACL review tooling (`Get-ACL` on the AD: drive, or `dsacls`) — find
  the excessive write grants enabling the attack path.

## Expected outputs

- Accounts with KeyCredentialLink values, classified legitimate vs. rogue,
  with evidence for each classification.
- A timeline: foothold account → ACL/write path → attribute write → PKINIT
  logon → privilege achieved → subsequent activity.
- Remediation records: rogue keys removed (verified), write path closed,
  tickets revoked, passwords rotated.
- Two or more durable detections (attribute-write alert, PKINIT anomaly
  alert, daily LDAP diff) deployed and tuned.
- An updated legitimate-writer inventory and AD change-control procedure.

## Pitfalls

- Windows Hello for Business and Azure AD hybrid join legitimately write
  KeyCredentialLink. Whitelist by provisioning-service identity; never alert
  on the attribute's mere presence.
- 4662 volume on busy DCs is enormous. Scope directory-service auditing
  carefully or your SIEM budget will suffer; filter to the specific
  attribute where possible.
- Clearing a legitimate Hello for Business key locks the user out of
  passwordless sign-in. Verify with the identity team before removing values.
- Shadow credentials can survive password resets of the *victim* in some
  configurations — confirm the rogue key is actually gone by re-querying
  the attribute after remediation.
- PKINIT pre-auth data in 4768 requires the right audit subcategories;
  verify "Audit Kerberos Authentication Service" is enabled before you need it.
- Focusing only on users: computer objects are equally valid targets and
  are monitored less often.

## References

- MITRE ATT&CK: T1558 (Steal or Forge Kerberos Tickets), T1078 (Valid
  Accounts), T1484 (Domain Policy Modification — the ACL-enabling side)
- Microsoft Docs: "Windows Hello for Business" (KeyCredential /
  msDS-KeyCredentialLink background)
- Microsoft Docs: "Advanced security audit policy settings — Audit
  Directory Service Changes"
- Microsoft Docs: "Audit Kerberos Authentication Service" (4768
  pre-authentication visibility)
- Public AD-security research on shadow-credential attack paths (defensive
  summaries)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
