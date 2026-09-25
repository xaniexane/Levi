---
skill_id: cyber_performing_privileged_account_discovery
name: Privileged Account Discovery
description: Discover unknown privileged accounts across endpoints, servers, and cloud to bring them under management.
risk: low
permissions: []
requires_confirmation: false
tags: [pam, discovery, inventory]
version: 1.0.0
---

## Purpose
- Find the privileged accounts nobody knows about: local admins, shadow service accounts, and forgotten cloud roles.
- Build a complete inventory as the foundation for vaulting, rotation, and monitoring.
- Reduce the unmanaged privileged footprint that attackers love to exploit.

## When to use
- When starting or expanding a privileged access management program.
- After mergers or infrastructure growth that outpaced account governance.
- When incidents reveal attacker use of unknown privileged accounts.
- Periodically, to catch new shadow privileged accounts as they appear.

## Prerequisites
- Discovery tooling: PAM discovery features, endpoint agents, or scripts approved for the environment.
- Credentials or agent deployment rights sufficient to enumerate accounts on target systems.
- A defined classification scheme for what counts as privileged on each platform.
- A plan for onboarding discovered accounts: vaulting, rotation, and ownership assignment.

## Procedure
1. Define what counts as privileged for each platform: local admins, domain admins, root-equivalents, cloud admin roles.
2. Run discovery across endpoints, servers, network devices, databases, and cloud accounts.
3. Correlate discovered accounts against the known inventory to isolate the unknowns.
4. Classify each unknown account: legitimate but unmanaged, orphaned, or suspicious.
5. Investigate suspicious accounts immediately: check creation dates, logon history, and group memberships.
6. Assign owners to legitimate accounts and onboard them to vaulting and rotation.
7. Disable or remove orphaned accounts after a quarantine period and stakeholder notice.
8. Document service-account dependencies before changing any credential so rotations do not break applications.
9. Establish continuous discovery so new privileged accounts are caught as they are created.
10. Report the unmanaged privileged footprint trend to show the program is shrinking it.

## Expected outputs
- A complete privileged account inventory with ownership and classification.
- Onboarding or removal actions for every discovered account.
- Continuous discovery coverage and trend metrics.
- A vaulting and rotation onboarding queue with dependency-mapped priorities.
- An attestation from system owners for every account brought under management.

## Pitfalls
- Rotating a service account credential without mapping dependencies, causing application outages.
- Discovering accounts but never onboarding them; discovery without follow-through is just a report.
- Missing cloud and SaaS privileged roles while focusing only on traditional servers.

## References
- NIST SP 800-57 key management guidance for vaulted credential lifecycles
- NIST SP 800-53 access control family
- CIS Controls on controlled use of administrative privileges
- Vendor PAM discovery documentation
- MITRE ATT&CK valid accounts technique, https://attack.mitre.org/techniques/T1078/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
