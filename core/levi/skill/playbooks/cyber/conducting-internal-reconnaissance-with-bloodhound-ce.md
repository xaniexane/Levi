---
skill_id: cyber_conducting_internal_reconnaissance_with_bloodhound_ce
name: Detecting BloodHound-Based Active Directory Reconnaissance
description: Defensive playbook for recognizing BloodHound collection activity and hardening Active Directory attack paths it reveals.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, detection, hardening]
version: 1.0.0
---
## Purpose
BloodHound maps Active Directory attack paths -- who can reach domain admin and how. Attackers use it for reconnaissance; defenders should use its insights to close those paths. This playbook covers detecting unauthorized BloodHound collection in your environment and systematically eliminating the attack paths it would reveal. It does not describe how to operate the tool offensively.

## When to use
- Hunting for AD reconnaissance after a suspected intrusion.
- Auditing your own AD for dangerous attack paths (defensive use).
- Responding to alerts about mass LDAP queries or unusual enumeration.
- Prioritizing AD hardening with attack-path analysis.

## Prerequisites
- LDAP and domain-controller query logging or network visibility into LDAP traffic.
- Endpoint telemetry to identify the collecting process and host.
- Understanding of your AD structure: tiers, privileged groups, trusts.
- Authority to modify AD ACLs and group memberships for remediation.

## Procedure
1. Recognize collection signatures. BloodHound-style collection generates high-volume LDAP queries enumerating users, groups, sessions, ACLs, and trusts in a short window from a single host.
2. Build the detection. Alert on anomalous LDAP query volume and breadth from non-administrative hosts, correlated with the collecting process on the endpoint.
3. Identify the collector. Determine the host, user account, and process performing enumeration; distinguish authorized assessments from unauthorized activity.
4. Contain if unauthorized. Isolate the host, disable or reset the involved credentials, and investigate as a potential intrusion.
5. Map your own attack paths defensively. In a controlled, authorized review, analyze which accounts have paths to privileged groups.
6. Remediate the paths. Remove dangerous ACLs, reduce privileged-group membership, fix unconstrained delegation, and enforce tiering.
7. Monitor continuously. Re-run attack-path analysis after AD changes; alert on new dangerous paths as they appear.
8. Harden collection telemetry. Ensure LDAP auditing is enabled so future reconnaissance is visible.

## Expected outputs
- Detection for AD enumeration and collection activity.
- Remediated attack paths with before-and-after documentation.
- Ongoing attack-path monitoring process.

## Pitfalls
- Legitimate administrative tools also query AD heavily; baseline before alerting.
- Remediating ACLs without understanding dependencies breaks applications; test changes.
- One-time cleanup decays; AD changes recreate attack paths constantly.
- Treating the tool as the threat instead of the misconfigurations it reveals.

## References
- MITRE ATT&CK: T1087 (Account Discovery), T1018 (Remote System Discovery)
- Microsoft Learn: Active Directory security best practices
- CISA guidance on Active Directory hardening
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
