---
skill_id: cyber_prioritizing_vulnerabilities_with_cvss_scoring
name: Prioritizing Vulnerabilities with CVSS Scoring
description: Apply CVSS base, temporal, and environmental metrics, enriched with threat intel, to prioritize patching.
risk: info
permissions: []
requires_confirmation: false
tags: [vulnerability-management, cvss, prioritization]
version: 1.0.0
---
## Purpose
CVSS gives every vulnerability a common severity language, but base scores alone mislead. This playbook shows how to combine CVSS base, temporal, and environmental metrics with real-world exploit intelligence (such as CISA's KEV catalog) to produce a patching order that reflects actual risk to your environment.

## When to use
- Weekly or monthly patch prioritization cycles.
- When a high-volume disclosure (e.g. Patch Tuesday) overwhelms the queue.
- Justifying emergency patching or downtime to business stakeholders.
- Tuning SLA definitions in the vulnerability management program.

## Prerequisites
- Vulnerability scan data with CVE identifiers per asset.
- Asset criticality and exposure data for environmental scoring.
- Access to FIRST CVSS calculator/specification and the CISA KEV catalog.
- Defined remediation SLAs tied to final priority tiers.

## Procedure
1. Collect all open vulnerabilities with CVE IDs, affected assets, and scanner severities.
2. Record the published CVSS base score and vector for each CVE from NVD or the vendor.
3. Adjust with temporal metrics: is a public exploit available, is a patch available, is the report confirmed.
4. Apply environmental metrics: asset exposure (internet-facing), data criticality, and compensating controls.
5. Boost any CVE present in the CISA Known Exploited Vulnerabilities catalog regardless of base score.
6. Rank the final list and assign to priority tiers mapped to SLA deadlines.
7. Communicate the top tier with business justification: exploitability plus business impact.
8. Re-score on a schedule and whenever new exploit intelligence or asset changes arrive.
9. Incorporate EPSS scores as a supporting signal for real-world exploit likelihood.
10. Document the CVSS version used and keep the program on one version for consistency.
11. Re-score the top tier monthly; exploit intelligence changes faster than patch cycles.

## Expected outputs
- Ranked remediation queue with CVSS vectors and final priority per item.
- KEV-listed items flagged for emergency handling.
- SLA mapping document tying priority tiers to deadlines.
- EPSS-enriched priority list for the top remediation tier.
- Scoring standard document (CVSS version, environmental model).
- Monthly re-scoring log showing priority changes and reasons.

## Pitfalls
- A CVSS 9.8 on an isolated lab host is less urgent than a 7.5 on an internet-facing payment server.
- CVSS does not measure exploit weaponization well; always pair it with KEV and threat intel.
- Scoring every CVE manually does not scale; automate base ingestion and focus analyst time on environmental scoring.
- Vector strings matter more than the number; two 8.8s can demand very different responses.
- CVSS scope and version differences confuse stakeholders; standardize on one version.
- EPSS is probabilistic, not deterministic; use it to order, not to dismiss.
- Vendor-provided CVSS scores can differ from NVD; decide which is authoritative in advance.
- Patch windows negotiated without the priority data revert to squeaky-wheel ordering; bring the ranked list to every change review.

## References
- FIRST CVSS v3.1/v4.0 Specification and Calculator (first.org/cvss).
- CISA Known Exploited Vulnerabilities Catalog (cisa.gov/known-exploited-vulnerabilities-catalog).
- NIST SP 800-40 Rev. 4, Guide to Enterprise Patch Management Planning.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
