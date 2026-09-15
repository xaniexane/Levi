---
skill_id: cyber_deploying_ransomware_canary_files
name: Deploying Ransomware Canary Files
description: Build a managed canary-file program with automated monitoring and pre-authorized containment for ransomware early warning.
risk: low
permissions: []
requires_confirmation: false
tags: [ransomware, deception, detection]
version: 1.0.0
---
## Purpose

Run canary files as a managed detection program, not a one-off trick: strategically placed tripwire files with real-time monitoring, automated containment on trigger, and lifecycle management. The difference between a canary file and a canary program is the response that follows the chirp.

## When to use

- Formalizing ransomware early warning beyond ad-hoc decoy files.
- Protecting file servers, NAS, and backup staging areas where ransomware does the most damage.
- Meeting ransomware-readiness requirements from insurers or regulators.
- Complementing EDR with a control that works even when the endpoint agent is disabled.

## Prerequisites

- File-integrity monitoring or EDR file-event telemetry on target systems; a SIEM with fast alerting.
- Administrative access to shares and endpoints for deployment (GPO, Ansible, or EDR custom deployment).
- Pre-authorized containment actions documented in the IR plan.
- Backup verification process — canaries detect; backups recover. Both must exist.

## Procedure

1. **Map the ransomware blast radius.** Identify where encryption hurts most: file servers, department shares, NAS volumes, backup staging, and user profile redirection targets. Prioritize by data criticality and by historical ransomware targeting (shared drives first — that's where the money is).
2. **Deploy canaries with a managed toolset.** Use a consistent deployment method (script/GPO/EDR) that places canary files with randomized-but-plausible names per host, records their paths and hashes in a central inventory, and verifies placement. Randomize names per deployment so attackers can't fingerprint a static canary name across the fleet.
3. **Monitor for the full modification spectrum.** Alert on: content modification, rename, deletion, permission/attribute changes, and encryption-header signatures. Ransomware variants differ — some rename first, some encrypt in place — so the tripwire must cover all mutation types, not just writes.
4. **Correlate canary triggers with process context.** On trigger, automatically capture: the modifying process and its parent chain, the user context, and the count of other files modified in the last 60 seconds. A single canary touch by `explorer.exe` during a user rename is noise; a canary touch by an unknown process with 500 sibling modifications is ransomware.
5. **Automate containment on high-confidence triggers.** Pre-authorize: EDR network isolation of the host, disabling the affected user account's sessions, and snapshotting the process tree for forensics. Define the confidence rule in advance (e.g. canary modified + mass file events within 60s = auto-contain) so the SOC doesn't debate during the incident.
6. **Distinguish canary signal from noise.** Build an allowlist for legitimate modifiers (backup agents, AV scanners, search indexers) verified by hash and path — but alert if an allowlisted process modifies canaries outside its normal pattern, since ransomware has been known to masquerade as legitimate tools.
7. **Run the program like a program.** Quarterly: verify canary existence fleet-wide (missing canaries = broken deployment), rotate names and content, expand to new shares, and run a benign-trigger test of the full detect→contain→page chain. Report canary coverage as a metric to leadership alongside backup-test results.

## Expected outputs

- A centrally inventoried canary deployment on high-value shares and endpoints with randomized names.
- Multi-type modification monitoring with process-context correlation and auto-containment rules.
- Quarterly existence checks, rotation, and end-to-end trigger tests reported as a program metric.

## Pitfalls

- Static, fleet-wide canary names — attackers learn and avoid them; randomize.
- Alerting without auto-containment — ransomware outruns human response every time.
- Legitimate tools (backup, indexing) triggering canaries with no allowlist — alert fatigue kills the program.
- Monitoring modification but not deletion — some ransomware deletes-then-recreates.
- No existence monitoring — canaries silently deleted by cleanup scripts leave you unprotected without warning.

## References

- CISA StopRansomware guidance (cisa.gov/stopransomware)
- NIST SP 800-61 Rev. 2 — malware incident handling
- MITRE ATT&CK T1486 (Data Encrypted for Impact)
- MITRE Engage (engage.mitre.org) — deception operations planning
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
