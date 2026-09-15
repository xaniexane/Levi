---
skill_id: cyber_implementing_delinea_secret_server_for_pam
name: PAM with Delinea Secret Server
description: Implement privileged access management with Delinea Secret Server: vaulting, rotation, and session control.
risk: low
permissions: []
requires_confirmation: false
tags: [pam, secrets]
version: 1.0.0
---
## Purpose
Privileged credentials scattered in spreadsheets, scripts, and engineers' memories are unmanageable:
no rotation, no audit, no revocation when someone leaves. Delinea Secret Server (formerly Thycotic)
centralizes privileged credentials in a vault with automated rotation, checkout workflows, and
session proxying. This playbook implements it as the privileged-access control plane: vault
everything, rotate automatically, monitor every use.

## When to use
- Eliminating shared privileged credentials and spreadsheet-based password management.
- After incidents involving compromised or ex-shared privileged accounts.
- Meeting PAM requirements for SOC 2, PCI DSS, HIPAA, or cyber-insurance.
- Managing service-account and break-glass credential lifecycles.
- As the credential-vault layer beneath jump-host and session-recording architectures.

## Prerequisites
- Inventory of privileged accounts: domain admins, local admins, service accounts, network devices,
  cloud consoles, databases, and break-glass.
- Defined access model: who may check out which secrets, approval requirements, and checkout
  duration.
- Infrastructure for the vault: hardened server(s), HSM or key-management integration,
  backup/recovery tested.
- MFA enforced for vault access (the vault is the keys to the kingdom — protect accordingly).
- HR joiner/mover/leaver integration so access follows employment status.

## Procedure
1. **Deploy the vault securely.** Install Secret Server on hardened, patched infrastructure;
   integrate with HSM for the master key; enable MFA for all vault users; restrict network access to
   the vault (admin networks + jump hosts only). Test backup and restore before storing a single
   real secret — recovery must be proven.
2. **Onboard secrets in priority order.** Wave 1: domain admin and break-glass credentials, cloud
   console root/IAM privileged users. Wave 2: network infrastructure, databases, hypervisors. Wave
   3: service accounts and application credentials. Each wave: import, verify, rotate, then
   decommission the old storage (the spreadsheet must die).
3. **Enable automated rotation.** Configure rotation for every secret type the platform supports:
   Windows service accounts (with service dependency handling), AD accounts, databases, network
   devices, and cloud keys. Set intervals by risk (privileged human accounts: 30-90 days; service
   accounts: per policy). Verify rotation actually works per secret — failed rotations that nobody
   notices are worse than manual ones.
4. **Implement checkout with accountability.** Require: ticket/justification for checkout,
   time-limited access with auto-check-in, and one-click rotation on check-in for the most sensitive
   secrets. Eliminate standing knowledge of privileged passwords — checkout, use, rotate, forget.
5. **Proxy privileged sessions.** Route admin sessions through the vault's session proxy with
   recording: RDP/SSH to critical systems without exposing the underlying credential to the user.
   Session recordings are the audit trail for "what did the admin do" — retain per policy.
6. **Discover and remediate vault sprawl.** Run discovery scans for privileged accounts not yet
   vaulted (local admins via EDR/GPO data, shadow service accounts). New privileged accounts must be
   vaulted at creation — integrate with provisioning workflows so the vault stays complete.
7. **Alert on vault events.** To the SIEM: failed vault logins, checkout outside business hours,
   bulk secret exports, permission changes, rotation failures, and break-glass checkouts (page
   immediately). Vault telemetry is high-signal — treat it as such.
8. **Manage service accounts specially.** Service accounts can't do checkout workflows: use the
   platform's application-to-application credential brokering or managed rotation with automatic
   distribution to dependent systems. Document every service account's owner and purpose — ownerless
   service accounts get disabled on review.
9. **Run access reviews.** Quarterly: review who can access which secrets, remove stale access (role
   changes, departures), and verify break-glass procedures. Access to the vault itself gets the
   strictest review — vault admins are the ultimate privileged users.
10. **Test disaster recovery.** Annually (at least): restore the vault from backup in an isolated
    environment and verify secrets decrypt and rotation works. Also test the "vault is down"
    procedure: how do admins get emergency access without creating permanent backdoors?

## Expected outputs
- Hardened Secret Server deployment with HSM-backed keys, MFA, and tested backup/restore.
- Prioritized secret onboarding waves with old storage decommissioned.
- Automated rotation verified per secret; checkout workflows with justification and auto-expiry.
- Proxied, recorded privileged sessions for critical systems.
- SIEM alerting on vault events, quarterly access reviews, tested DR.

## Pitfalls
- Vaulting without rotation: a centralized spreadsheet of static passwords is barely better.
  Rotation is the control; the vault is the mechanism.
- Unverified rotations: rotation jobs fail silently (service dependencies, permission issues) —
  verify each one, alert on failures.
- No break-glass for vault outage: if the vault is down and nobody can get credentials, pressure
  builds for permanent backdoors. Tested emergency procedures prevent this.
- Service accounts ignored: human checkout workflows don't fit services — use A2A brokering or
  managed rotation, or service accounts remain the unrotated weak link.
- Over-permissioned vault admins: apply the same least-privilege and review rigor to vault
  administrators as to the secrets themselves.

## References
- Delinea Secret Server documentation (deployment, rotation, session proxy)
- NIST SP 800-53 IA-2, AC-2, AU (identification, account management, auditing — PAM mappings)
- CIS Controls (privileged account management)
- MITRE ATT&CK T1078, T1552 (valid accounts, unsecured credentials — what PAM constrains)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
