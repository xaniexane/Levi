---
skill_id: cyber_configuring_ldap_security_hardening
name: Configuring LDAP Security Hardening
description: Practitioner guide to hardening LDAP and Active Directory directory services: signing, channel binding, LDAPS, and access control.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, hardening, identity]
version: 1.0.0
---
## Purpose
LDAP carries authentication and directory queries in clear text unless hardened, enabling credential theft and relay attacks. This playbook hardens directory services: enforcing LDAP signing and channel binding, deploying LDAPS, tightening ACLs, and monitoring for downgrade or relay attempts.

## When to use
- Hardening Active Directory against credential interception and relay.
- Responding to findings about unsigned LDAP or cleartext binds.
- Preparing for compliance audits covering directory-service security.
- After incidents involving LDAP-based credential theft.

## Prerequisites
- Inventory of LDAP clients: applications, scripts, and devices that bind to the directory.
- Domain-controller patch level supporting signing and channel-binding enforcement.
- Certificate infrastructure for LDAPS deployment.
- Change window and rollback plan, since legacy clients may break.

## Procedure
1. Inventory LDAP usage. Identify which clients use simple binds, unsigned SASL, or cleartext LDAP; this determines the blast radius of enforcement.
2. Deploy LDAPS. Install certificates on domain controllers; verify clients can connect over port 636 before enforcing anything.
3. Enforce LDAP signing. Set domain-controller policy to require signing; remediate or except legacy clients explicitly with documented risk.
4. Enable channel binding. Require LDAP channel binding tokens to tie the TLS channel to the authentication, defeating relay.
5. Disable cleartext binds. Prohibit simple binds over unencrypted connections; monitor for clients attempting them.
6. Tighten directory ACLs. Review who can read sensitive attributes (such as LAPS passwords or confidential flags); apply least privilege.
7. Monitor for bypass attempts. Alert on unsigned bind attempts, channel-binding failures, and unusual LDAP query volumes.
8. Maintain the posture. Re-audit after application deployments; include LDAP requirements in new-application onboarding.

## Expected outputs
- Enforced LDAP signing and channel binding with documented exceptions.
- LDAPS deployed on directory servers.
- Monitoring for downgrade and relay attempts.

## Pitfalls
- Enforcing signing without inventorying clients breaks legacy applications abruptly.
- Exceptions granted permanently instead of driving application upgrades.
- Channel binding unsupported by old clients; plan upgrades, not permanent waivers.
- Monitoring bind failures without acting on them.

## References
- Microsoft security advisories on LDAP signing and channel binding (ADV190023 and related)
- Microsoft Learn: LDAP signing and channel binding configuration
- MITRE ATT&CK: T1557 (Adversary-in-the-Middle)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
