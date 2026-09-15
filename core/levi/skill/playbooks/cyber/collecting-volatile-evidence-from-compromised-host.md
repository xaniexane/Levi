---
skill_id: cyber_collecting_volatile_evidence_from_compromised_host
name: Collecting Volatile Evidence from a Compromised Host
description: Practitioner guide to forensically sound live collection of memory, process, and network state from a compromised host.
risk: moderate
permissions: []
requires_confirmation: true
tags: [forensics, memory, incident-response]
version: 1.0.0
---
## Purpose
Volatile evidence -- running processes, network connections, memory contents, logged-on sessions -- disappears when a host is powered off. This playbook governs live collection from a compromised system: preparation, tooling, order of volatility, documentation, and handoff to analysis. Because it touches a live, potentially production system, it requires explicit confirmation before proceeding.

## When to use
- Responding to a suspected compromise where memory-resident malware is likely.
- Capturing evidence before isolating or rebuilding a host.
- Supporting legal or HR investigations that require live-state documentation.
- When fileless malware or in-memory-only artifacts are suspected.

## Prerequisites
- Explicit authorization from the incident commander or asset owner (required).
- Forensic toolkit on trusted external media (write-protected USB or network share).
- Sufficient storage for a full memory image, with hashing capability.
- Defined chain-of-custody process and evidence storage location.

## Procedure
1. Confirm authorization and scope. Verify written approval, the exact host, and what collection is permitted; brief the team on the plan.
2. Document the initial state. Record date, time, timezone, who is performing collection, system uptime, and logged-on users before touching anything.
3. Prepare trusted tooling. Use binaries from known-good external media; never rely on the potentially compromised host's own tools.
4. Capture memory first. Acquire a full physical memory image to external storage; hash it immediately (SHA-256) and record the hash.
5. Collect volatile system state in order of volatility: network connections and listening ports, running processes with full command lines, open handles and loaded modules, logged-on sessions, ARP and routing tables, and system time.
6. Minimize footprint. Run the fewest commands necessary; avoid installing software or rebooting, and document every action taken on the host.
7. Secure the evidence. Transfer images and logs to evidence storage; verify hashes after transfer and complete chain-of-custody forms.
8. Hand off to analysis. Provide the analyst with the collection log, hashes, tool versions, and the incident context; then proceed with containment per the IR plan.

## Expected outputs
- Full memory image with verified hashes and chain-of-custody documentation.
- Volatile-state collection (processes, network, sessions) with timestamps.
- Collection log suitable for legal scrutiny.

## Pitfalls
- Collecting without authorization creates legal and employment liability; get it in writing.
- Using the host's own binaries risks trojaned output; always use trusted media.
- Rebooting or running heavy tools before memory capture destroys the evidence you came for.
- Incomplete documentation undermines admissibility; log everything contemporaneously.

## References
- NIST SP 800-86, Guide to Integrating Forensic Techniques into Incident Response
- RFC 3227, Guidelines for Evidence Collection and Archiving
- SANS FOR508 live-response methodology concepts
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
