---
skill_id: cyber_detecting_network_reconnaissance_and_port_scanning
name: Detecting Network Reconnaissance and Port Scanning
description: Detect, classify, and respond to network scanning against your infrastructure using firewall, IDS, and flow telemetry, then harden exposed services.
risk: low
permissions: []
requires_confirmation: false
tags: [reconnaissance, network, ids]
version: 1.0.0
---
# Detecting Network Reconnaissance and Port Scanning

## Purpose

Give defenders a repeatable workflow for spotting network reconnaissance —
port sweeps, service fingerprinting, and OS-detection probes — directed at
their own infrastructure, distinguishing hostile scanning from benign
activity (your own vulnerability scanners, researchers, misconfigured
peers), and responding proportionately. Covers telemetry sources, scan
classification from packet behavior, containment options, and the hardening
that makes future scans return as little as possible.

## When to use

- An IDS/IPS or firewall fires scan-detection signatures (port sweep,
  SYN flood heuristics, sequential connection attempts).
- Firewall deny logs or WAF logs show a sudden spike of rejected
  connections from a small set of sources.
- Threat intel warns of pre-attack reconnaissance against your sector.
- After deploying a new internet-facing service, to validate that your
  own monitoring actually sees probing against it.
- During incident response, to determine whether an intrusion was
  preceded by a reconnaissance phase and how far it reached.

## Prerequisites

- Written authorization from the asset/network owner to collect and
  analyze traffic logs for the networks in scope.
- Access to the relevant telemetry: perimeter firewall logs, IDS/IPS
  alerts, NetFlow/IPFIX or VPC flow logs, and host firewall logs for
  critical servers.
- A baseline of normal connection patterns for the monitored networks
  (business hours, backup windows, CDN health checks) to keep false
  positives down.
- A list of your own authorized scanners (vulnerability management,
  pentest windows, uptime monitors) with their source IPs, so they can
  be excluded quickly.
- An escalation path: who can approve a perimeter block, and who must
  be notified before you block a source that might be a customer or
  partner.

## Procedure

1. **Establish scope and time window.** Record the targeted assets
   (IPs, ranges, hostnames), the alerting source, and the earliest and
   latest suspicious timestamps. Pull all four telemetry sources for
   that window before drawing conclusions — a single log type lies by
   omission.
2. **Correlate across telemetry.** Join firewall denies, IDS scan
   signatures, flow records, and host logs on source IP and time.
   Look for the classic patterns: many destination ports on one host
   (vertical scan), one port across many hosts (horizontal sweep), and
   low-and-slow probing designed to evade rate-based signatures.
3. **Classify the scan from packet behavior.** SYN-only with no
   completion suggests stealth port sweeping; completed handshakes
   followed by banner grabs indicate service fingerprinting; unusual
   flag combinations and ICMP/TCP probes aimed at stack quirks suggest
   OS detection attempts. Classification drives the response — a
   banner grab against a patched service is less urgent than a sweep
   across your management VLAN.
4. **Attribute the source before acting.** Check the source against
   your authorized-scanner list, threat-intel feeds, and reverse DNS.
   An internal source may be a compromised host or a forgotten
   appliance; an external source may be a researcher, a botnet, or a
   targeted actor. Never block first and ask later when the source
   could be a partner network or your own cloud NAT egress.
5. **Contain proportionately.** For clearly hostile external sources:
   block at the perimeter firewall or WAF, add the indicator to the
   SIEM watchlist, and consider sharing with your sector ISAC. For
   internal sources: isolate the host for triage rather than just
   dropping its traffic, since scanning from inside often means
   compromise or policy violation.
6. **Harden what the scan found.** Close or firewall off every port
   the scan touched that has no business being reachable. Minimize
   service banners, disable ICMP responses that are not operationally
   needed, put management interfaces behind VPN or allow-lists, and
   confirm default-deny is actually the effective policy on each
   edge device.
7. **Document, tune, and close the loop.** Write up the timeline,
   classification, source disposition, and actions taken. Tune the
   detection that fired (thresholds, exclusions) based on what you
   learned, and schedule a follow-up check that the hardening from
   step 6 is still in place after the next change window.

## Expected outputs

- A correlated timeline of the reconnaissance activity: sources,
  targets, scan classification, and duration.
- Source disposition for each scanner (authorized, benign-external,
  hostile, internal-compromise) with evidence.
- Containment actions taken (blocks, isolations) with approvals noted.
- Hardening changes applied to reduce exposed services and
  fingerprintable banners.
- Tuned detection rules with measured false-positive rates.

## Pitfalls

- **Blocking your own scanners.** The most common self-inflicted
  outage in scan response is null-routing the vulnerability
  management platform. Maintain and check the allow-list first.
- **Treating every scan as an emergency.** Internet background
  radiation means every public IP is scanned constantly. Respond to
  targeting and persistence, not to mere existence.
- **Single-source tunnel vision.** Sophisticated actors distribute
  scans across many sources. Correlate by target and technique, not
  just by source IP.
- **Forgetting IPv6 and cloud edges.** Scans arrive over every
   address family and through every peering. If your flow logging
   covers only IPv4 on-prem, you are blind elsewhere.
- **Hardening theater.** Changing a banner string while leaving the
  vulnerable service exposed helps no one. Fix exposure first,
  obscurity second.

## References

- Your IDS/IPS vendor's scan-detection signature documentation and
  tuning guides.
- NetFlow/IPFIX analysis references for recognizing scan patterns in
  flow data.
- NIST SP 800-94 (Guide to Intrusion Detection and Prevention Systems)
  for detection architecture.
- CIS Benchmarks for the firewall and server platforms you operate,
  for hardening baselines.
- Sector ISAC or national CERT guidance on reporting and sharing
  scanning indicators.

---
*Original work authored for LEVI. Defensive blue-team playbook — detection, analysis, and hardening guidance only. Topic inspired by a network-detection phase script; no content copied from any external source.*
