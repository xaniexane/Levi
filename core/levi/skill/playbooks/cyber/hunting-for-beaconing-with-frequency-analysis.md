---
skill_id: cyber_hunting_for_beaconing_with_frequency_analysis
name: Hunting for Beaconing with Frequency Analysis
description: Detect C2 beaconing in network telemetry using periodicity and jitter analysis of connection timing patterns.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, network, c2]
version: 1.0.0
---
## Purpose

Command-and-control implants check in on schedules — periodic "beaconing"
that stands out statistically from human-driven traffic. This playbook
covers detecting beaconing through frequency/periodicity analysis of
network connection logs: finding the metronome-like patterns (with and
without jitter) that indicate automated C2.

## When to use

- Post-compromise hunting: finding additional C2 channels after one
  implant is discovered.
- Proactive network threat hunting on proxy, firewall, or NetFlow data.
- Validating that egress monitoring would catch a new implant family.
- Investigating hosts with suspicious but unidentified periodic traffic.

## Prerequisites

- Network connection logs with timestamps, source/destination, ports,
  and bytes: proxy logs, firewall logs, NetFlow/IPFIX, or Zeek
  conn.log — ideally 30+ days.
- Analytical tooling (Python/pandas, or SIEM aggregation) for interval
  statistics.
- Baselines of legitimate periodic traffic: software updaters, NTP,
  monitoring agents, and SaaS sync clients.

## Procedure

1. **Aggregate connections by pair.** Group connections by
   (source host, destination IP/domain, destination port) and compute
   inter-arrival times. Beaconing candidates are pairs with many
   connections and low variance in interval.
2. **Score periodicity.** For each pair, compute interval statistics:
   mean, standard deviation, and coefficient of variation. Low variation
   relative to the mean (e.g. connections every 60s ± 2s) is the classic
   beacon signature. Rank pairs by connection count × periodicity score.
3. **Account for jitter.** Real implants add random jitter (often 0-25%
   of the interval) to defeat naive periodicity checks. Use robust
   measures (median absolute deviation) and also test for
   "interval clustering" — beacons with jitter still cluster around a
   central interval rather than spreading uniformly.
4. **Filter known-good periodic traffic.** Exclude baselined updaters,
   monitoring, and SaaS sync by destination and process attribution
   (correlate with endpoint data where available). Maintain this
   allow-list as living documentation.
5. **Enrich the candidates.** For top candidates, examine: destination
   reputation and age, TLS certificate details, bytes in/out symmetry
   (beacons are often small and symmetric), user-agent anomalies, and
   whether the destination is rare across the fleet.
6. **Correlate with endpoint telemetry.** For the source hosts, check
   process-creation logs around beacon times: which process initiates
   the connections, its parent chain, and whether it is signed and
   expected. A browser-named process beaconing to a fresh domain is a
   strong signal.
7. **Confirm or refute.** True beacons show persistence across days,
   survive reboots (check process start times), and often pause during
   host sleep. One-off periodic bursts are usually legitimate jobs —
   require multi-day persistence before escalating.
8. **Operationalize.** Convert validated beaconing patterns into
   scheduled analytics (not just one-off hunts), and feed confirmed C2
   infrastructure into blocking and intel sharing.

## Expected outputs

- Ranked beaconing candidates with interval statistics and
   persistence evidence.
- Dispositions per candidate (malicious, benign with justification,
   inconclusive).
- Endpoint correlation for confirmed beacons: implant process and
   attack chain.
- A recurring beaconing analytic with tuned thresholds.

## Pitfalls

- Jittered beacons defeat simple standard-deviation thresholds — use
   robust statistics and clustering, not a single cutoff.
- Legitimate software (updaters, telemetry) beacons constantly —
   without an allow-list the hunt drowns in noise.
- NAT and proxy aggregation can merge or distort per-host timing —
   analyze as close to the endpoint as possible.
- Short analysis windows miss low-frequency beacons (hourly/daily
   check-ins) — use the longest retention available.
- Encrypted traffic still leaks timing — but attribution needs
   endpoint correlation; network-only analysis has limits.

## References

- MITRE ATT&CK: T1071 (Application Layer Protocol), T1573
  (Encrypted Channel)
- Academic and industry research on C2 periodicity detection
  (beaconing analytics)
- Zeek documentation (conn.log fields for timing analysis)
- NIST SP 800-94: Guide to Intrusion Detection and Prevention Systems
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
