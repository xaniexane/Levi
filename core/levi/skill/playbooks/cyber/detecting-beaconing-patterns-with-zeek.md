---
skill_id: cyber_detecting_beaconing_patterns_with_zeek
name: Detecting Beaconing Patterns with Zeek
description: Hunt C2 beaconing in Zeek connection logs with periodicity, jitter, and byte-pattern analysis.
risk: info
permissions: []
requires_confirmation: false
tags: [network, detection, c2]
version: 1.0.0
---
## Purpose

Find command-and-control beaconing — the regular "phone home" heartbeat of compromised hosts — by analyzing Zeek connection logs for periodicity, low jitter, and suspicious uniformity. Beaconing detection catches the C2 channel even when the malware itself is unknown.

## When to use

- Hunting for active C2 in an environment with suspected compromise.
- Triaging an alert where a host may be beaconing to unknown infrastructure.
- Building continuous beaconing detection for the SOC.
- Validating that egress controls are actually stopping C2 (beaconing attempts that get blocked still show as connection attempts).

## Prerequisites

- Zeek deployed on egress choke points with `conn.log` centralized (SIEM or data lake) and retained 30+ days.
- DNS logs (`dns.log`) and SSL/TLS logs (`ssl.log`, `x509.log`) from the same sensors for correlation.
- Baseline knowledge of legitimate beaconing (software updaters, cloud agents) to exclude.
- An analysis environment (Python/RITA-style tooling or SIEM analytics) for periodicity computation.

## Procedure

1. **Extract candidate long connections.** From `conn.log`, pull connections grouped by (source IP, destination IP:port): count, duration span, total bytes, and inter-arrival times. Filter to destinations with 10+ connections over the window — beaconing needs repetition; one-off connections aren't beacons.
2. **Score periodicity and jitter.** For each candidate pair, compute the inter-arrival time distribution: beacons show low variance (regular intervals) with small jitter. Flag pairs with high connection counts, consistent intervals (e.g. every 60s ± 5s), and uniform byte counts. Tools like RITA automate this scoring — use them rather than hand-rolling statistics.
3. **Filter legitimate beaconing.** Exclude known-good: software update services, cloud management agents, NTP, and SaaS sync clients — identified by destination reputation, SNI/certificate, and JA3 fingerprints. Maintain the allowlist explicitly; an attacker mimicking a legitimate beacon's timing to a malicious domain is exactly what you're hunting, so allowlist on destination identity, not just pattern.
4. **Correlate with DNS and TLS signals.** For surviving candidates, check `dns.log`: beaconing to algorithmically generated or newly registered domains, high NXDOMAIN rates, or DNS tunneling patterns. Check `ssl.log`/`x509.log`: self-signed or unusual certificates, JA3 hashes matching known malware, and SNI mismatches. A periodic beacon to a 3-day-old domain with a weird JA3 is a finding.
5. **Investigate the beaconing host.** On the endpoint: identify the owning process (EDR process-to-connection mapping), check the binary's prevalence and reputation, review the process tree (who launched it?), and capture memory if the process is suspicious. Beaconing + unknown process + persistence mechanism = active compromise.
6. **Build continuous detection.** Operationalize the analysis as a scheduled job: daily beaconing scores on the last 24h of `conn.log`, auto-ticketing for scores above threshold with the enrichment from steps 3–4 attached. Track precision weekly and tune thresholds — beaconing detection is statistical and needs ongoing calibration.
7. **Respond to confirmed C2.** Isolate the host, block the C2 domain/IP at DNS and firewall (after capturing the current resolution for intel), preserve full packet capture and memory for forensics, and hunt laterally: which other hosts talked to the same infrastructure? Beaconing is rarely a single-host story.

## Expected outputs

- A beaconing-analysis pipeline scoring Zeek connection periodicity with legitimate-beacon allowlists.
- DNS/TLS correlation enriching beacon candidates with domain age, cert, and JA3 context.
- Continuous daily detection with weekly precision tuning and a confirmed-C2 response runbook.

## Pitfalls

- No allowlist for legitimate beaconing — the SOC drowns in updater noise and ignores the feed.
- Allowlisting on pattern instead of destination — attackers mimic legitimate timing; identity matters.
- Short retention on conn.log — beaconing analysis needs weeks of history to distinguish patterns.
- Treating the beacon as the whole incident — find the malware, the persistence, and the lateral movement.
- Blocking the C2 before preserving evidence — capture first, then block.

## References

- Zeek documentation (zeek.org) — conn.log, dns.log, ssl.log field references
- RITA (Real Intelligence Threat Analytics) documentation — beaconing analysis methodology
- MITRE ATT&CK T1071 (Application Layer Protocol) and T1573 (Encrypted Channel)
- SANS / threat-hunting resources on C2 beaconing detection
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
