---
skill_id: cyber_deploying_active_directory_honeytokens
name: Deploying Active Directory Honeytokens
description: Seed deceptive credentials and objects in Active Directory that alert the moment an attacker touches them.
risk: low
permissions: []
requires_confirmation: false
tags: [deception, active-directory, detection]
version: 1.0.0
---
## Purpose

Plant honeytokens inside Active Directory — fake user accounts, credentials in SYSVOL/GPO comments, and decoy SPNs — that no legitimate process ever touches, so any interaction is high-confidence evidence of compromise. Deception, deployed defensively and legally.

## When to use

- Adding early-warning detection for AD enumeration, credential theft, and lateral movement.
- Validating that your monitoring actually catches AD abuse (honeytokens are a self-testing detection).
- Post-incident hardening to catch re-entry or missed persistence.
- Environments where EDR coverage is incomplete and you need cheap, high-signal tripwires.

## Prerequisites

- Domain admin cooperation and written authorization — you're creating objects in production AD.
- A SIEM or alerting path for the honeytoken tripwires (Event IDs 4624, 4768, 4769, 4662, LDAP binds).
- A naming scheme that blends in but is documented internally so admins don't "clean up" the decoys.
- Change control: honeytokens are production objects with owners and review dates.

## Procedure

1. **Design the token set.** Plan 3–5 token types: (a) a fake privileged user account (e.g. a plausible `svc-backup` or `adm-jdoe` style name) that is disabled-but-monitored or enabled with a long random password; (b) fake credentials planted in a GPO comment or SYSVOL-adjacent share; (c) a decoy computer account; (d) a honey SPN registered to trigger Kerberoasting alerts (4769 with RC4 encryption type requested). Each token gets a documented purpose and owner.
2. **Make them attractive but inert.** The fake admin account should look like it has privileges (group memberships that suggest access) but actually grant nothing — membership in a monitored group with no real rights, or an account whose password is vaulted and never used. The credential in the GPO comment should look like a real service password. Never grant real access: a honeytoken that actually works is a backdoor, not a decoy.
3. **Instrument every token.** Alert on: any logon attempt (4624/4625) or Kerberos TGT request (4768) for the fake user, any TGS request (4769) for the honey SPN, any LDAP query or attribute read (4662) touching the decoy objects, and any use of the planted credential string anywhere in authentication logs. These alerts go to the SOC as high priority — legitimate users never touch these objects.
4. **Deploy quietly.** Create the objects during a normal change window without broadcast. Don't document the exact names in widely shared runbooks — the SOC needs the alert logic, not a treasure map. Restrict knowledge of token identities to the security team.
5. **Test each tripwire.** From an isolated test host, attempt a logon with the fake account, request a TGS for the honey SPN, and query the decoy object via LDAP. Confirm every action generates the expected alert in the SIEM within minutes. A honeytoken nobody monitors is just AD clutter.
6. **Handle alerts as incidents.** Any honeytoken trigger means active AD abuse until proven otherwise: immediately scope (which host, which account, what time), check for lateral movement from the source host, and preserve evidence. Do not dismiss a honeytoken alert as a misconfiguration without investigation — that's exactly the dismissal an attacker hopes for.
7. **Rotate and maintain.** Rotate planted credential strings quarterly, review token plausibility (do the fake names still match your naming conventions?), and audit that alerts still fire after AD/SIEM changes. Remove tokens that have become widely known internally — a known decoy is a dead decoy.

## Expected outputs

- A documented set of AD honeytokens (fake accounts, planted credentials, honey SPNs, decoy objects) with owners and review dates.
- SIEM alerts on any interaction, tested end-to-end and treated as high-priority incidents.
- Quarterly rotation and plausibility review.

## Pitfalls

- Granting the decoy account real privileges — you've created an attacker account, not a honeytoken.
- Alerting the whole company about the honeytokens — insiders will avoid them and you'll lose the signal.
- Tokens so implausible nobody touches them — a `zz-test-admin` account fools no one; match your naming conventions.
- Forgetting the tripwire after deployment — AD upgrades and SIEM migrations silently break the alerting.
- Planting credentials that get picked up by legitimate vulnerability scanners — coordinate scan exclusions or expect noise.

## References

- MITRE Engage (engage.mitre.org) — adversary engagement and deception planning
- Microsoft Learn — auditing Active Directory (Event IDs 4624, 4768, 4769, 4662)
- NIST SP 800-53 SC-26 (honeypots) and SI-4 (system monitoring)
- SANS / DFIR community guidance on AD deception deployments
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
