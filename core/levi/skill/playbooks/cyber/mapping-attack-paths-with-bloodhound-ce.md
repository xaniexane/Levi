---
skill_id: cyber_mapping_attack_paths_with_bloodhound_ce
name: Mapping Attack Paths with BloodHound CE (Defensive Audit)
description: Use BloodHound Community Edition to map Active Directory attack paths for defensive hardening.
risk: low
permissions: []
requires_confirmation: false
tags: [active-directory, attack-path, hardening]
version: 1.0.0
---
## Purpose
This playbook uses BloodHound Community Edition as a defensive auditing tool: collect AD relationship data you are authorized to gather, identify the shortest paths attackers could take to tier-0 assets, and remediate them. It covers only authorized assessment of your own directory — never target systems you do not own.

## When to use
- You need to know which users, groups, and ACLs give a path to Domain Admins.
- Prioritizing AD hardening: which misconfigurations matter most.
- Validating that tiering and delegation changes actually removed attack paths.

## Prerequisites
- Written authorization to collect AD data in the target domain(s).
- BloodHound CE deployed with a collector (SharpHound) run from an authorized account.
- Understanding of your tier model: which assets are tier-0.

## Procedure
1. **Get authorization and scope.** Document the domains, OUs, and collection window approved; use a least-privilege collection account where possible.
2. **Collect directory data.** Run the collector with an appropriate method (default collection is usually sufficient); import into BloodHound CE.
3. **Mark owned and high-value nodes.** Flag tier-0 assets (DCs, backup, identity infrastructure) as high-value targets in the analysis.
4. **Query shortest paths.** Find paths from low-privilege principals (all users, service accounts) to high-value targets; sort by path length and node count.
5. **Prioritize by exploitability and blast radius.** Focus on paths with the fewest hops, unconstrained delegation, DCSync rights, and admin-count misconfigurations first.
6. **Remediate systematically.** Remove unnecessary ACL grants, fix group nesting, rotate Kerberoastable service account passwords, and enforce tiering; re-collect to verify the path is gone.
7. **Operationalize.** Schedule periodic collection and diffing so new attack paths introduced by daily admin work are caught quickly.

8. **Track path half-life.** Measure how long remediated paths stay closed; paths that reappear indicate broken change control, not bad luck.
9. **Share sanitized trends.** Report aggregate attack-path metrics (not raw graph data) to leadership to sustain funding for AD hardening.

## Expected outputs
- Attack-path report: shortest paths to tier-0 with remediation priority.
- Verified remediation: re-collection showing paths eliminated.
- Recurring collection schedule with diff-based alerting.
- Example: analysis finds a 2-hop path from a helpdesk group to Domain Admins via an ACL misconfiguration; after remediation, re-collection confirms the path is gone and the diff is archived as evidence.

## Pitfalls
- Collecting without authorization or beyond the approved scope.
- Treating the graph as the whole assessment: BloodHound sees relationships, not vulnerabilities or misconfigurations it cannot model.
- One-off analysis that goes stale as AD changes daily.

- Running collectors with domain-admin credentials out of convenience; a compromised collection workstation then hands over the keys to everything.
- Presenting raw path counts to leadership without context; translate "47 paths" into "these 3 changes eliminate 90% of them."

## References
- BloodHound documentation (bloodhound.readthedocs.io).
- Microsoft Learn: securing Active Directory guidance (learn.microsoft.com).
- SpecterOps BloodHound Enterprise documentation — continuous attack-path management concepts.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
