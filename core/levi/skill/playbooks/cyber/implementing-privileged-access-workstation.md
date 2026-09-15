---
skill_id: cyber_implementing_privileged_access_workstation
name: Implementing Privileged Access Workstation
description: Deploy hardened Privileged Access Workstations (PAWs) — dedicated, locked-down devices for administrative tasks, separating admin activity from daily-use machines.
risk: low
permissions: []
requires_confirmation: false
tags: [pam, hardening, endpoints, identity]
version: 1.0.0
---
## Purpose

Ensure administrative credentials are only ever used from clean, hardened, dedicated workstations — never from the laptop that also opens email attachments and browses the web. A Privileged Access Workstation (PAW, or Secure Admin Workstation) is a locked-down device used exclusively for administration: no email, no web browsing, application allowlisting, and credential hygiene (Credential Guard, no cached admin creds on user devices) that breaks the credential-theft attack chain.

## When to use

- Protecting Tier 0 / domain admin and cloud admin credentials from workstation compromise (pass-the-hash, token theft).
- Implementing the administrative tiering model (ESA E / Microsoft's privileged access strategy).
- Meeting requirements for secure administration (PCI DSS, government, cyber-insurance).
- After incidents where admin credentials were stolen from a compromised user workstation.
- Any environment where admins currently RDP/SSH to critical systems from daily-driver laptops.

## Prerequisites

- Administrative tier model defined (Tier 0: identity systems, Tier 1: servers/apps, Tier 2: workstations) with accounts and assets assigned.
- Hardware for PAWs (dedicated laptops or VDI-based secure desktops) and a provisioning process (Intune, SCCM, or hardened images).
- Identity infrastructure supporting the model: separate admin accounts (no daily-use account with admin rights), MFA on all admin logons.
- Jump host / bastion infrastructure if PAWs connect through an admin network segment.
- Executive and admin buy-in — PAWs change how every administrator works daily; without leadership support it becomes shelfware.

## Procedure

1. **Define the tiers and the rules.** Tier 0 admins (domain/cloud identity) use PAWs only; Tier 0 credentials never touch Tier 1/2 devices — not for logon, not cached, not in memory. Write the tiering rules plainly: "Tier 0 creds on Tier 0 devices only, administering Tier 0 assets only." Exceptions require CISO-level approval with expiry.
2. **Build the hardened PAW image.** Hardened OS baseline (CIS/STIG), application allowlisting (admin tools only — no Office, no browsers except for admin consoles where unavoidable, and then hardened), host firewall default-deny, full-disk encryption, EDR with aggressive exploit protection, and Credential Guard / LSA protection enabled. No local admin rights for the admin on their own PAW — the PAW is a tool, not a playground.
3. **Separate the accounts.** Provision dedicated admin accounts per tier (`adm-` prefix convention), disabled for email and interactive logon on user devices. Remove administrative rights from daily-use accounts entirely — including the "just for this one server" exceptions that accumulate. Enforce via GPO/Intune: deny logon of Tier 0 accounts to Tier 1/2 devices.
4. **Protect credentials in use.** Enable Credential Guard/VBS, disable WDigest and unconstrained delegation, enforce Protected Users group membership for Tier 0 accounts, and require phishing-resistant MFA for all admin authentication. PAW logons never cache credentials usable elsewhere.
5. **Network the PAWs correctly.** Place PAWs on a dedicated admin VLAN/segment reachable only to administrative targets (domain controllers, PAM vault, cloud admin portals via conditional access). No internet browsing from PAWs except allowlisted admin endpoints (update servers, vendor portals) through a filtered proxy. Admin traffic never traverses the user network.
6. **Deploy in waves with support.** Pilot with the identity/server admin teams, gather friction points (missing tools, workflow breaks), fix the image, then expand tier by tier. Provide a clear escalation path for "I need a tool not on the allowlist" — handled in hours, or admins will bypass the PAW.
7. **Monitor PAW compliance.** Alert on: Tier 0 credential use from non-PAW devices (the critical detection), PAW policy drift (allowlist violations, disabled EDR), and admin logons bypassing the PAW path. These detections validate the entire model — a Tier 0 logon from a user laptop is either a misconfiguration or an attack.
8. **Maintain and recertify.** Rebuild PAW images on schedule (don't patch indefinitely — reimage), review tier assignments quarterly, and re-validate that no admin workflows bypass the PAW. Include PAW compliance in privileged-access metrics reported to leadership.

## Expected outputs

- Documented administrative tier model with credential/device/asset separation rules.
- Hardened PAW image with allowlisting, Credential Guard, and EDR.
- Dedicated per-tier admin accounts; daily-use accounts stripped of admin rights.
- Dedicated admin network segment with filtered egress.
- Monitoring for tier violations; quarterly recertification.

## Pitfalls

- **PAW without account separation.** A hardened workstation used with the same account that also logs into the daily laptop provides minimal protection. Separate accounts are the point; the hardened device is the enforcement.
- **Allowlist too restrictive to work.** If admins can't do their jobs from the PAW, they'll do them from their laptops. Invest in understanding admin workflows before locking the image.
- **Forgetting service and vendor admins.** Third-party admins and service accounts with Tier 0-equivalent access need the same treatment (dedicated accounts, PAW or equivalent jump path) — they're part of the tier whether you planned for them or not.
- **Credential caching on user devices.** Old habits: RDP sessions from user laptops that cache Tier 0 creds. Hunt for and eliminate cached privileged credentials on Tier 2 devices (they're the actual attack path PAWs are meant to close).
- **VDI PAW without endpoint hygiene.** Virtual PAWs accessed from compromised physical devices inherit keylogging and screen-capture risk. If using VDI, still enforce clean access devices or accept the residual risk explicitly.

## References

- Microsoft privileged access strategy / Secure Privileged Access documentation — https://learn.microsoft.com/en-us/security/privileged-access-workstations/
- NIST SP 800-53 Rev. 5, AC-6 (Least Privilege), IA-2 (Identification and Authentication) — https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- MITRE ATT&CK T1003 (OS Credential Dumping), T1550 (Use Alternate Authentication Material) — https://attack.mitre.org/
- CIS Benchmarks for workstation hardening baselines — https://www.cisecurity.org/cis-benchmarks
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
