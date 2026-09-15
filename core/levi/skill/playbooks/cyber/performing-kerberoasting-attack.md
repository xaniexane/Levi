---
skill_id: cyber_performing_kerberoasting_attack
name: Kerberoasting Attack Defense
description: Detect Kerberoasting and harden service accounts against ticket cracking.
risk: low
permissions: []
requires_confirmation: false
tags: [ad, detection, hardening]
version: 1.0.0
---
# Kerberoasting Attack Defense

## Purpose

Kerberoasting abuses Kerberos legitimately: any authenticated user can
request a service ticket (TGS) for an SPN, and tickets for accounts with
weak passwords can be cracked offline. This defensive playbook covers
detecting ticket-request abuse and hardening service accounts so stolen
tickets resist cracking.

## When to use

- Hunting for credential-access activity in Active Directory logs.
- Hardening service accounts after a Kerberoasting finding or alert.
- Reviewing SPN registrations as part of an AD security assessment.
- Responding to alerts on anomalous TGS requests.

## Prerequisites

- Domain Controller security logs (event 4769, Kerberos Service Ticket
  Operations) forwarded to the SIEM with the ticket-encryption-type
  field intact.
- Authority to review and modify service-account passwords and SPN
  registrations.
- An inventory of accounts with registered SPNs.

## Procedure

1. Inventory SPNs: enumerate all accounts with registered service
   principal names; each one is a Kerberoastable target if its
   password is weak.
2. Harden service-account passwords: set long (25+ character),
   randomly generated, managed passwords; prefer Group Managed
   Service Accounts (gMSAs), whose passwords are managed and rotated
   automatically and cannot be Kerberoasted the same way.
3. Remove stale SPNs: deregister SPNs from decommissioned services and
   user accounts — every unnecessary SPN is unnecessary attack
   surface.
4. Hunt in 4769 logs: look for TGS requests with RC4 encryption
   (0x17) for service accounts, high volumes of TGS requests from a
   single user to many SPNs, and requests for SPNs from accounts that
   never normally access those services.
5. Alert on the pattern: a single principal requesting tickets for
   many distinct SPNs in a short window, especially with RC4, is the
   classic Kerberoasting signature.
6. Disable RC4 where possible: enforce AES Kerberos encryption via
   Group Policy so captured tickets are far harder to crack.
7. Respond to suspected success: if a service account's ticket was
   likely cracked, rotate its password immediately, review its
   privilege scope, and hunt for lateral movement from that account.
8. Re-audit quarterly: new SPNs appear with every application
   deployment — make SPN review part of the server-provisioning
   checklist.

## Expected outputs

- A current SPN inventory with password-strength status per account.
- gMSA migration or managed-password coverage for service accounts.
- Detection rules for anomalous TGS request patterns.
- A quarterly SPN-review process.

## Pitfalls

- Rotating the password but leaving the weak account highly
   privileged: reduce the service account's rights too.
- Only watching for RC4: AES tickets can still be attacked, just more
   slowly — volume-based detection matters regardless.
- Breaking applications with abrupt password changes: coordinate
   rotations with service owners and test.
- Forgetting computer accounts: machine accounts with SPNs deserve
   the same review.

## References

- MITRE ATT&CK: Steal or Forge Kerberos Tickets (T1558.003 Kerberoasting)
- Microsoft Learn: Group Managed Service Accounts documentation
- Microsoft Learn: Kerberos event 4769 documentation
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
