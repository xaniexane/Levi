---
skill_id: cyber_enumerating_cloud_with_cloudfox
name: Enumerating Cloud with CloudFox
description: Use CloudFox for defensive cloud enumeration: asset discovery and exposure mapping.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, asset-discovery, aws]
version: 1.0.0
---
## Purpose

CloudFox enumerates cloud environments — instances, storage, IAM, network paths — quickly from an operator's perspective. Defenders can use the same capability for authorized asset discovery: finding forgotten resources, mapping exposure, and validating that the inventory matches reality. This playbook covers defensive cloud enumeration: authorized discovery, exposure analysis, and hardening follow-through — never unauthorized assessment.

## When to use

- You need to discover what actually exists in your cloud accounts.
- Asset inventory is incomplete and shadow resources are suspected.
- Post-incident: mapping the blast radius of a cloud compromise.
- Validating that decommissioned resources are actually gone.

## Prerequisites

- Read-only cloud credentials for the accounts in scope (CloudFox works with standard credential chains).
- Written authorization for enumeration, with the account list explicitly in scope.
- A baseline inventory (CMDB, IaC state) to diff discovered assets against.
- Knowledge of the account structure: OUs, subscriptions, projects in scope.

## Procedure

1. Scope and authorize explicitly. Document which accounts/subscriptions/projects are in scope, use read-only credentials, and confirm with account owners. Cloud enumeration touches every resource's metadata — in regulated environments this needs the same authorization as a vulnerability scan. Never enumerate accounts outside your written scope.
2. Enumerate broadly, then focus. Run CloudFox's enumeration modules across in-scope accounts to capture: compute instances, storage buckets/containers, databases, IAM users/roles/policies, network security groups and routes, secrets stores, and public exposures. Export results to structured files for diffing and trending — screenshots don't diff.
3. Diff against the known inventory. Compare discovered assets with CMDB/IaC: resources in CloudFox output but not in inventory are shadow IT or forgotten infrastructure — investigate each. Resources in inventory but not discovered may indicate credential scope gaps or decommissioning failures. Both directions matter.
4. Analyze exposure from the attacker's view. For discovered assets assess: public accessibility (public IPs, open security groups, public storage), IAM privilege breadth (overly permissive roles, unused access), unencrypted storage, and missing logging. Prioritize internet-facing + sensitive-data combinations — these are the findings that become incidents.
5. Turn findings into remediation with owners. For each exposure: assign an owner, set a remediation (restrict access, encrypt, delete, or formally accept with expiry), and verify. Shadow resources with no owner get an owner assigned or get deleted — 'nobody owns it' is not a disposition.
6. Operationalize discovery. Run enumeration on a schedule (monthly minimum), trend the shadow-resource count, feed new resources into vulnerability management and logging coverage, and integrate discovery into account-provisioning so new accounts enter the inventory at creation.

## Expected outputs

- Scoped, authorized enumeration runs with read-only credentials.
- Discovery diff: found-vs-inventory with shadow-resource investigations.
- Exposure analysis: public access, IAM breadth, encryption, logging gaps — prioritized.
- Scheduled re-discovery with trending and remediation tracking.

## Pitfalls

- Enumerating without written scope is indistinguishable from attacker reconnaissance — authorize explicitly.
- Read-only credentials prevent accidents; operator credentials invite them.
- Inventory diffs are only as good as the baseline — maintain IaC/CMDB hygiene in parallel.
- Public-access findings need validation (some 'public' resources are intentionally public) — check before alarming.
- One-time enumeration decays immediately — schedule it.

## References

- CloudFox documentation (cloudfoxable); CIS cloud benchmarks for exposure criteria; MITRE ATT&CK T1580 (Cloud Infrastructure Discovery) — https://attack.mitre.org/techniques/T1580/ (defensive application)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
