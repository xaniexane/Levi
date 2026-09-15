---
skill_id: cyber_detecting_lateral_movement_with_splunk
name: Detecting Lateral Movement with Splunk
description: Build Splunk searches and dashboards that surface lateral movement in authentication and network data.
risk: low
permissions: []
requires_confirmation: false
tags: [splunk, siem, lateral-movement]
version: 1.0.0
---
## Purpose

This playbook is for defenders who have authentication and network logs in Splunk and need practical, tunable searches for lateral movement — not generic advice. It covers which data to onboard, the search patterns that work, and how to turn one-off hunts into scheduled detections without flooding the queue.

## When to use

- Splunk is your SIEM and you need lateral-movement coverage this quarter.
- Ad-hoc hunts found movement once; you need it as a scheduled, alerting detection.
- False positives from naive 'any RDP' searches are burning analyst time.
- You need dashboards leadership can read: movement attempts over time, top source hosts, top abused accounts.

## Prerequisites

- Windows Security logs (EventCodes 4624, 4625, 4672, 4648) and/or Sysmon, indexed with consistent host/user/src_ip fields; Linux secure/auth logs and VPN/IdP logs if in scope.
- A lookup of admin jump hosts, service accounts, and scanner IPs to suppress known-good traffic.
- Sufficient Splunk license headroom — authentication data is high volume; plan for aggregation.
- Saved baseline statistics (normal logon counts per host-pair) for anomaly thresholds.

## Procedure

1. Verify field extraction first. Confirm src_ip, dest host, user, Logon_Type, and EventCode are reliably extracted across all forwarders. Inconsistent field names across sourcetypes are the number one reason lateral-movement searches silently miss data — normalize with field aliases or a common information model.
2. Build the fan-out search. Aggregate successful network/RDP logons by source host and count distinct destinations per hour; alert when a workstation-class host authenticates to an unusual number of distinct targets. Tune the threshold from your baseline — start with statistical outliers (e.g., 3+ standard deviations) rather than a guessed number.
3. Build the first-seen host-pair search. Maintain a lookup of historically observed (src_host, dest_host, user) triples; alert on first-seen pairs involving privileged accounts or server-to-workstation direction. Update the lookup on a schedule and expire entries deliberately, not accidentally.
4. Build the credential-reuse search. Find single accounts authenticating to many hosts in a short window, especially local administrator or shared service accounts. Correlate with 4672 (special privileges assigned) to weight privileged sessions higher.
5. Add the impossible-path check. Flag authentications where a low-privilege workstation user suddenly logs into tier-0 assets (domain controllers, backup servers), or where a server initiates outbound interactive logons — servers should rarely be the source of interactive sessions.
6. Promote hunts to scheduled alerts carefully. Run each search over 30 days of history first, measure precision, add suppressions for scanners and deployment tools via lookups, then schedule with throttling (per src_host+user) and a runbook link in the alert. Start in 'log only' mode before paging anyone.

## Expected outputs

- Saved Splunk searches: fan-out, first-seen host-pair, credential-reuse, impossible-path — each with baseline-tuned thresholds.
- Lookup tables: known-good admin paths, service accounts, scanner IPs, with owners and review dates.
- Dashboard: lateral-movement attempts, top sources/destinations/accounts, alert precision trend.
- Runbook linked from each alert: triage steps, scoping queries, escalation criteria.

## Pitfalls

- Searching raw 4624 without filtering logon type and success/failure mixes signal with noise — filter early.
- Throttling by src_ip alone hides multi-host campaigns; throttle by src_host+user and keep a separate unthrottled hunt.
- Lookups that nobody owns go stale and start suppressing real attacks — assign an owner and a review cadence.
- License blowout: aggregate with stats/tstats before the alert condition; never alert on raw event streams.
- A detection that only runs in Splunk while half your DCs don't forward is a false sense of coverage — verify log-source health.

## References

- Splunk documentation: Search Reference and tstats; MITRE ATT&CK TA0008 (Lateral Movement) — https://attack.mitre.org/tactics/TA0008/; SANS: Windows event log lateral movement hunting guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
