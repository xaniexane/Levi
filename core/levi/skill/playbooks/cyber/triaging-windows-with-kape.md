---
skill_id: cyber_triaging_windows_with_kape
name: Triaging Windows Hosts with KAPE
description: Collect targeted forensic triage data from live Windows hosts with KAPE for rapid incident scoping.
risk: moderate
permissions: []
requires_confirmation: true
tags: [forensics, windows, triage]
version: 1.0.0
---
## Purpose
KAPE (Kroll Artifact Parser and Extractor) rapidly collects targeted forensic artifacts from live Windows systems using predefined targets. This playbook covers forensically sound triage collection during incident response: selecting targets, collecting to external media, and handing off to analysis. Because it touches live production systems and acquires data, it requires authorization and confirmation.

## When to use
- Active incident requiring rapid scoping across many Windows hosts.
- Collecting artifacts before a host is reimaged or taken offline.
- Compromise assessment sweeps of a Windows fleet.
- Preserving volatile-adjacent artifacts (event logs, registry, prefetch) quickly.

## Prerequisites
- Authorization to run collection on the target hosts; incident ticket reference.
- KAPE deployed via approved method (EDR, remote execution, or USB) with target definitions.
- External collection storage with sufficient capacity and encryption.
- Chain-of-custody documentation process.

## Procedure
1. Confirm authorization and record the incident reference, operator, and target host list.
2. Select KAPE targets for the scenario: evidence-of-execution, persistence, lateral movement, or full triage sets.
3. Verify the collection destination is external/encrypted and has capacity; never collect onto the target's own disk.
4. Execute collection with the minimal target set first; expand only if the investigation requires it.
5. Hash and document each collection output immediately; record host, time, targets, and KAPE version.
6. Transfer outputs to the analysis environment over a secure channel; maintain chain of custody.
7. Analyze with parsers (Eric Zimmerman tools, Timeline Explorer) and correlate with EDR/SIEM telemetry.
8. Retain or dispose of collections per the investigation's retention policy.
9. Pre-stage KAPE on gold images so collection starts in minutes during an incident.
10. Pin and test KAPE module versions before an incident; modules update frequently.
11. Validate collection completeness by checking target output counts against expectations.

## Expected outputs
- KAPE collection archives per host with hashes and custody records.
- Parsed artifact sets ready for timeline analysis.
- Triage findings feeding the incident scope assessment.
- Pre-staged KAPE deployment verification.
- Pinned module version manifest.
- Collection completeness check results.

## Pitfalls
- Over-collection across hundreds of hosts creates a storage and analysis bottleneck; target first.
- Running collection tools can alert EDR or the adversary; coordinate with the IR lead on stealth needs.
- KAPE touches the live system; document that timestamps after collection reflect analyst activity.
- Unencrypted collection media with sensitive artifacts is a breach risk; encrypt at rest.
- KAPE modules update frequently; untested updates can break collection mid-incident.
- Pre-staging on gold images needs updating when images change; track the drift.
- Large-scale collection without bandwidth planning saturates the network; throttle.
- KAPE output encryption at rest is essential when collections traverse untrusted networks.

## References
- KAPE documentation (Kroll).
- Eric Zimmerman tool documentation (ericzimmerman.github.io).
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
