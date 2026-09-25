---
skill_id: cyber_detecting_network_scanning_with_ids_signatures
name: Detecting Network Scanning with IDS Signatures
description: Write and tune IDS signatures that detect network reconnaissance scanning.
risk: low
permissions: []
requires_confirmation: false
tags: [ids, reconnaissance, detection]
version: 1.0.0
---
## Purpose

Network scanning — port sweeps, host sweeps, service probes — is the audible precursor to most intrusions. This playbook covers building IDS (Suricata/Snort) signatures and threshold logic that detect scanning reliably: distinguishing attacker reconnaissance from vulnerability scanners and monitoring tools, and turning scan detections into early-warning intelligence.

## When to use

- You need IDS coverage for reconnaissance, not just exploitation.
- Scan alerts are either silent or overwhelming — you need tuned signatures.
- Threat hunting: finding the recon that preceded a confirmed intrusion.
- Validating that authorized scanning (vuln management) doesn't mask attacker scans.

## Prerequisites

- IDS sensors (Suricata or Snort) with visibility into relevant segments, including internal spans for insider/foothold scanning.
- Baseline knowledge of authorized scanning: vulnerability scanner IPs, schedules, and target ranges.
- Signature management workflow: test, deploy, tune, review.
- Flow/state tracking enabled (IDS must correlate packets into flows for scan detection).

## Procedure

1. Use threshold-based detection, not single-packet signatures. Scanning is a pattern over time, so write signatures that count: e.g., N distinct destination ports from one source within T seconds (port scan), or N distinct destination hosts on one port (host sweep). In Suricata, use threshold/detection_filter options; in Snort, use detection_filter and sfPortscan preprocessor tuning. Single-packet 'scan' signatures are nearly useless.
2. Separate scan types into distinct signatures. Port scans, host sweeps, and service-specific probes (e.g., SMB/RDP sweeps) have different thresholds and different meanings — one signature for 'scanning' forces a single threshold that fits nothing. Write per-type rules with per-type thresholds derived from your environment.
3. Exclude authorized scanners explicitly and narrowly. Maintain a passlist of vulnerability-scanner and monitoring IPs with their schedules, applied as rule suppressions — not as sensor blind spots. An attacker who compromises a scanner host is a real scenario; review passlisted scanner behavior for anomalies too.
4. Tune thresholds from measured data. Run candidate signatures in alert-only mode for two weeks, measure hits per source, and set thresholds above legitimate administrative scanning (which exists: admins do probe hosts) but below typical attacker tool defaults. Document the rationale per signature — future you will need it.
5. Correlate scans with what follows. A scan alone is low severity; a scan followed by exploitation attempts or successful connections to discovered services is an incident. Build SIEM correlation: scan alert from source X → subsequent IDS/exploit alerts or new connections from X within 24 hours escalates severity automatically.
6. Use scan data as threat intelligence. Track external scanning sources over time: persistent scanners of your perimeter deserve firewall blocks and intel notes; internal scanning from a workstation is a compromise indicator until proven otherwise. Feed confirmed-malicious scanners into blocklists and share with peers where appropriate.

## Expected outputs

- IDS scan signatures: port-scan, host-sweep, service-probe — each with documented thresholds.
- Tuning record: two-week alert-only measurements and threshold rationale.
- Authorized-scanner passlist with schedules and review dates.
- SIEM correlation: scan → exploitation/follow-on connection escalation logic.

## Pitfalls

- Single-packet scan signatures generate noise without detecting real scans — always threshold over time.
- One threshold for all scan types fits nothing; separate port scans, sweeps, and probes.
- Passlisting scanner IPs without reviewing their behavior creates a blind spot if the scanner is compromised.
- External internet background scanning is constant — alert on persistent/targeted scanning, log the rest.
- Internal scanning alerts without asset context (is the source a server? a printer?) waste triage time.

## References

- Suricata documentation: rule options, thresholding, and the portscan detector; Snort manual: sfPortscan preprocessor; MITRE ATT&CK T1595 (Active Scanning) — https://attack.mitre.org/techniques/T1595/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
