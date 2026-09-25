---
skill_id: cyber_triaging_vulnerabilities_with_ssvc_framework
name: Triaging Vulnerabilities with the SSVC Framework
description: Prioritize vulnerabilities with CISA's Stakeholder-Specific Vulnerability Categorization decision trees.
risk: info
permissions: []
requires_confirmation: false
tags: [vulnerability-management, ssvc, prioritization]
version: 1.0.0
---
## Purpose
CVSS scores severity; SSVC decides what to do about it. CISA's Stakeholder-Specific Vulnerability Categorization uses decision trees tailored to your role (supplier, deployer, coordinator) to produce actionable priorities: track, attend, or act now. This playbook applies SSVC to vulnerability triage so decisions reflect exploitability and mission impact, not just a number.

## When to use
- Prioritizing patching across a large vulnerability backlog.
- Coordinating vulnerability response between suppliers and deployers.
- Replacing CVSS-only prioritization with decision-based triage.
- Justifying deferred patching with a documented decision record.

## Prerequisites
- Vulnerability data with CVE IDs and affected products.
- SSVC decision tree for your stakeholder role (deployer is most common).
- Inputs per decision point: exploitation status, exposure, utility, safety impact.
- Threat intel feeds for exploitation state (e.g. KEV, EPSS as supporting data).

## Procedure
1. Gather the candidate vulnerabilities with product, version, and deployment context.
2. Determine exploitation status: none, proof-of-concept, or active exploitation in the wild.
3. Assess exposure: is the vulnerable component reachable, and is there a workaround or control in place?
4. Evaluate technical and mission impact: what breaks, and how critical is the affected system?
5. Walk the SSVC decision tree for your stakeholder role to reach a priority outcome.
6. Record the decision inputs, not just the outcome, so the triage is auditable and repeatable.
7. Act per outcome: immediate remediation, scheduled remediation, or tracked acceptance with review dates.
8. Re-evaluate when exploitation status changes; active exploitation upgrades priority automatically.
9. Pilot SSVC on one product line before rolling it across the vulnerability program.
10. Customize the safety-impact branch for safety-critical systems; the default tree underweights them.
11. Train triage analysts on the decision trees; inconsistent inputs produce inconsistent priorities.

## Expected outputs
- SSVC decision records per vulnerability with inputs and outcome.
- Prioritized action list: act now, scheduled, tracked.
- Re-evaluation triggers tied to exploitation intelligence.
- Pilot results with lessons learned.
- Customized decision tree for safety-critical assets.
- Analyst training records for SSVC.

## Pitfalls
- SSVC needs honest inputs; garbage exploitation data produces garbage priorities.
- Different stakeholder roles get different answers for the same CVE; use the right tree.
- 'Tracked' is not 'ignored'; accepted risk needs review dates and owners.
- SSVC complements CVSS; use both rather than treating them as competitors.
- Decision trees need local customization for safety-critical systems; adapt them.
- Analysts unfamiliar with the trees give inconsistent answers; train and calibrate.
- SSVC outcomes need executive buy-in; socialize the model before replacing CVSS-only processes.
- SSVC decisions need revisiting when a public exploit appears; wire KEV changes to re-triage triggers.

## References
- CISA Stakeholder-Specific Vulnerability Categorization Guide (cisa.gov/ssvc).
- CISA Known Exploited Vulnerabilities Catalog.
- NIST SP 800-40 Rev. 4, Guide to Enterprise Patch Management Planning.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
