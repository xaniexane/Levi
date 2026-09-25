---
skill_id: cyber_scanning_network_with_nmap_advanced
name: Advanced Network Scanning with Nmap
description: Authorized network discovery and assessment with Nmap: host discovery, service fingerprinting, and NSE scripting.
risk: low
permissions: []
requires_confirmation: false
tags: [network, scanning, nmap]
version: 1.0.0
---
## Purpose
Nmap remains the essential network assessment tool. This playbook covers using it as a defender: authorized discovery and inventory of your networks, service and OS fingerprinting for asset management, and safe use of NSE scripts for vulnerability enumeration. Scanning is limited to networks you own or are authorized to test, with timing tuned to avoid disruption.

## When to use
- Network asset discovery and inventory reconciliation.
- Verifying firewall rules and segmentation from both sides.
- Authorized vulnerability enumeration before deeper assessment.
- Incident response: finding rogue or unexpected hosts on a segment.

## Prerequisites
- Written authorization with in-scope ranges and excluded sensitive hosts.
- Nmap installed with updated NSE scripts.
- Baseline inventory to compare discoveries against.
- Agreed scan windows and rate limits for sensitive segments.

## Procedure
1. Start with host discovery (`-sn`) to map live hosts without port noise.
2. Run service/version detection (`-sV`) on discovered hosts to build a service inventory.
3. Use OS detection (`-O`) sparingly; it is noisier and less reliable through modern stacks.
4. Apply safe NSE scripts (`--script=safe` or targeted vuln scripts) for enumeration; avoid intrusive/exploit scripts on production.
5. Tune timing (`-T2`/`-T3`, `--max-rate`) for sensitive networks; aggressive timing can DoS fragile devices.
6. Compare results to the authorized inventory; investigate unknown hosts, unexpected open ports, and changed banners.
7. Document firewall and segmentation verification results from scans run on each side of boundaries.
8. Save outputs in all three formats (`-oA`) for reporting, diffing, and evidence.
9. Diff scan results against the previous cycle to highlight new hosts, new services, and disappeared assets for investigation.
10. Feed confirmed findings into the vulnerability management system with asset ownership attached.
11. Include IPv6 ranges in discovery; v6 is often unscanned and unmonitored.
12. Use idle or decoy scans only where explicitly authorized; they have legal and operational implications.
13. Schedule recurring discovery scans so new hosts are found within days, not quarters.

## Expected outputs
- Network inventory: hosts, open ports, services, OS guesses per segment.
- Unknown-host and unexpected-service findings with investigation notes.
- Segmentation verification evidence.
- Scan-to-scan diff report highlighting environmental changes.
- IPv6 discovery coverage report.
- Recurring discovery scan schedule.
- New-host alerting workflow for unknown devices.

## Pitfalls
- Default Nmap timing can overwhelm printers, OT devices, and legacy systems; throttle first.
- Intrusive NSE scripts can crash services; restrict to safe scripts on production.
- Banner grabbing is easily fooled by proxies and honeypots; verify surprising results.
- Scanning cloud networks may violate provider acceptable-use policies; check before scanning.
- IPv6 is often unscanned and unmonitored; include v6 ranges or explicitly document the gap.
- IPv6 link-local and SLAAC addressing make inventory harder; plan the methodology.
- Decoy scanning without authorization can implicate innocent third parties.
- One-off scans go stale; discovery must be recurring to be useful.

## References
- Nmap documentation (nmap.org/docs.html).
- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
