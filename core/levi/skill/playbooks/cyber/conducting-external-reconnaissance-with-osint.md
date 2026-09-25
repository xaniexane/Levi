---
skill_id: cyber_conducting_external_reconnaissance_with_osint
name: External Attack Surface Monitoring with OSINT
description: Defensive playbook for continuously discovering and monitoring your organization's internet-exposed assets using open-source methods.
risk: info
permissions: []
requires_confirmation: false
tags: [osint, attack-surface, monitoring]
version: 1.0.0
---
## Purpose
Attackers reconnoiter your external footprint before you do -- forgotten subdomains, exposed dev servers, leaked credentials. This playbook turns external reconnaissance into a defensive discipline: continuously discovering your internet-facing assets with OSINT techniques, assessing their exposure, and shrinking the attack surface. It covers only your own organization's assets.

## When to use
- Building an external attack-surface management capability.
- Discovering shadow IT and forgotten internet-facing systems.
- Monitoring for leaked credentials or exposed code repositories tied to your domain.
- Preparing for an external pentest by understanding what testers will find.

## Prerequisites
- Defined organizational scope: domains, IP ranges, brand names, subsidiaries.
- OSINT tooling: certificate transparency monitors, DNS enumeration, search engines.
- Asset-management system to reconcile discovered assets against known inventory.
- Remediation workflow for taking down or securing exposed assets.

## Procedure
1. Define the scope. List owned domains, netblocks, cloud accounts, and brand variants; get written confirmation of what is yours to monitor.
2. Enumerate the footprint. Use certificate transparency logs, passive DNS, and DNS enumeration to discover subdomains; map IPs and hosting providers.
3. Assess exposure. For each discovered asset, check for open services, default credentials risk, exposed admin panels, and sensitive data.
4. Monitor for leaks. Watch code repositories, paste sites, and breach compilations for credentials, keys, and internal documents tied to your organization.
5. Reconcile with inventory. Flag assets not in the official inventory as shadow IT; assign owners or decommission them.
6. Prioritize remediation. Rank exposures by exploitability and data sensitivity; drive takedown or hardening through the owning teams.
7. Automate continuous monitoring. Schedule recurring discovery and alert on new subdomains, new exposures, and new leaks.
8. Report trends. Track attack-surface size, mean time to remediate exposures, and repeat-offender teams for leadership.

## Expected outputs
- External asset inventory reconciled against official records.
- Prioritized exposure remediation backlog.
- Continuous monitoring with alerting on new exposures.

## Pitfalls
- Scanning or probing assets outside your confirmed scope is unauthorized; verify ownership.
- One-time discovery decays fast; automation is what makes this a program.
- Alert fatigue from low-value findings; prioritize ruthlessly.
- Discovering exposures without a remediation workflow just documents the risk.

## References
- NIST SP 800-30 Rev. 1 (risk framing for exposures)
- CISA Binding Operational Directive 23-01 (attack surface management concepts)
- CIS Controls: inventory and control of assets
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
