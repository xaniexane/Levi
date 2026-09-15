---
skill_id: cyber_scanning_infrastructure_with_nessus
name: Scanning Infrastructure with Nessus
description: Run authorized Nessus vulnerability scans of infrastructure with credentialed checks, scheduling, and triage.
risk: low
permissions: []
requires_confirmation: false
tags: [vulnerability-management, nessus, scanning]
version: 1.0.0
---
## Purpose
Nessus is a staple for infrastructure vulnerability assessment. This playbook covers running it defensively and professionally: scoping, credentialed scanning for accuracy, safe scheduling, result triage, and remediation tracking. All scanning is limited to systems you own or are authorized to assess.

## When to use
- Regular vulnerability assessment cycles (monthly/quarterly).
- Pre-audit or compliance validation (PCI, SOC 2, internal policy).
- After major changes: new subnets, acquisitions, cloud migrations.
- Emergency scanning for a newly disclosed critical vulnerability.

## Prerequisites
- Nessus installed, licensed, and updated (plugins and engine).
- Written authorization with in-scope IP ranges, hostnames, and cloud accounts.
- Credentials for credentialed scans (service account with least privilege).
- Scan windows agreed with operations; exclusion list for fragile systems.

## Procedure
1. Define targets precisely: IP ranges, DNS names, and cloud connectors; exclude fragile or out-of-scope systems.
2. Configure credentialed scans for accuracy; uncredentialed scans miss patch-level detail.
3. Select appropriate scan templates (e.g. basic network scan for discovery, advanced for depth); enable safe checks only on fragile hosts.
4. Schedule during agreed windows with throttling; stagger large ranges to avoid network impact.
5. Review results: verify criticals, check for false positives from backported patches, and merge with prior scan data.
6. Export findings to the vulnerability management system with asset context and ownership.
7. Track remediation and rescan; measure SLA compliance and scan coverage (credentialed success rate).
8. Archive scan configurations and reports for audit evidence.
9. Run a discovery scan first and reconcile live hosts against the CMDB before vulnerability scanning.
10. Monitor the credentialed-scan success rate; silent downgrades to uncredentialed scans hide coverage gaps.
11. Tag scan targets with business criticality so reporting prioritizes itself.

## Expected outputs
- Nessus scan reports per cycle with coverage statistics.
- Verified findings in the VM system with owners and SLAs.
- Coverage and SLA metrics for leadership.
- Discovery-to-CMDB reconciliation report.
- Credentialed-scan success rate trend.
- Criticality-tagged findings export.

## Pitfalls
- Uncredentialed scans are fast but shallow; push credentialed coverage as the real metric.
- Plugin false positives on backported Linux packages waste triage time; verify with package managers.
- Scanning without a window can disrupt OT, VoIP, or fragile legacy systems; always coordinate.
- A scan is a point in time; continuous monitoring fills the gaps between cycles.
- Credentialed scan failures silently downgrade to uncredentialed; monitor the success rate.
- Scan user accounts with expired passwords produce the same silent downgrade; rotate them.
- Overlapping scan ranges double-count assets; deduplicate targets.
- Scan credentials themselves are high-value targets; vault and rotate them like any privileged secret.

## References
- Tenable Nessus documentation.
- NIST SP 800-40 Rev. 4, Guide to Enterprise Patch Management Planning.
- CIS Controls: continuous vulnerability management.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
