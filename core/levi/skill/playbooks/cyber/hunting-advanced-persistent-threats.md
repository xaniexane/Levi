---
skill_id: cyber_hunting_advanced_persistent_threats
name: Hunting Advanced Persistent Threats
description: Run hypothesis-driven APT hunts across endpoint, identity, and network telemetry, from scoping through containment handoff.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, apt, dfir]
version: 1.0.0
---
## Purpose

Advanced persistent threats are defined by patience, stealth, and
objectives — long dwell times, living-off-the-land techniques, and quiet
persistence. This playbook structures APT hunting as a disciplined
campaign: building hypotheses from threat intel, hunting across telemetry
layers, and converting findings into incident response or durable
detections.

## When to use

- Threat intel describes an APT campaign targeting your sector or
  technology stack.
- Anomalies suggest a low-and-slow intrusion (unexplained privileged
  access, odd service installations, rare external connections).
- Post-incident: hunting for additional footholds after containing one
  APT implant.
- Proactive campaigns on a quarterly or intel-driven cadence.

## Prerequisites

- 90+ days (ideally 12 months) of retained telemetry: EDR/Sysmon,
  authentication logs, DNS, proxy, firewall, and email logs.
- Current threat intel on relevant APT groups: TTPs, infrastructure,
  and targeting.
- A hunt-tracking system and authority to escalate findings into
  incident response.
- Baselines of normal admin behavior — APTs hide in administrative
  noise.

## Procedure

1. **Select the adversary and build hypotheses.** From intel, extract
   the group's known TTPs (initial access, persistence, C2) and write
   specific, falsifiable hypotheses: "APT-X establishes persistence via
   WMI event subscriptions on servers, which our EDR would log as
   event 5861 without a corresponding change ticket."
2. **Map hypotheses to data.** For each hypothesis, identify the exact
   log sources and fields that would prove or disprove it. If the data
   does not exist or retention is too short, record the collection gap
   as a finding — do not hand-wave.
3. **Hunt layer by layer.** Work through persistence mechanisms,
   privileged-account activity, lateral movement, and C2 indicators in
   turn. Start broad (rare processes, rare network destinations) then
   narrow with intel-specific indicators.
4. **Investigate anomalies, not just IOCs.** APT infrastructure rotates;
   TTPs persist. Prioritize behavioral anomalies (a service account
   logging on interactively, a server initiating outbound connections)
   over hash/domain matches, and validate each against known-good
   baselines.
5. **Corroborate across sources.** A single log source is never enough
   for an APT call — require endpoint + network or identity
   corroboration before escalating. Build mini-timelines for each
   candidate host.
6. **Escalate with a scoping package.** Confirmed or high-confidence
   findings go to IR with: affected hosts/accounts, timeline, TTPs
   observed, intel correlation, and recommended containment that avoids
   tipping off the adversary prematurely (coordinate timing with IR
   leadership).
7. **Hunt for the rest of the iceberg.** One APT foothold implies more:
   sweep the fleet for the same TTPs, review historical logs back to
   maximum retention, and check cloud/SaaS and identity providers — APTs
   are rarely confined to endpoints.
8. **Convert to durable detection.** Every validated TTP becomes a
   detection (Sigma/SIEM rule) or a recurring hunt; every collection gap
   becomes a logging improvement ticket. Close the loop in the hunt
   report.

## Expected outputs

- Hunt hypotheses with intel citations and data mappings.
- Investigation notes per hypothesis: proven, disproven, or
  inconclusive with evidence.
- Escalation packages for confirmed findings.
- New detections and recurring hunts from validated TTPs.
- Collection-gap remediation tickets.

## Pitfalls

- IOC-only hunting misses APTs — infrastructure churns weekly while
  TTPs persist for years.
- Alerting the adversary through noisy containment (mass password
  resets, host isolations) before scoping is complete — coordinate with
  IR on timing.
- Short retention silently kills APT hunts — verify retention *before*
  promising coverage.
- Analyst fatigue on long inconclusive hunts — time-box hypotheses and
  rotate hunters.
- Treating "no evidence found" as "no intrusion" when the data to
  detect the TTP was never collected.

## References

- MITRE ATT&CK (APT group pages and technique mappings)
- CISA: APT-related advisories and hunting guidance
- NIST SP 800-86: forensic techniques in incident response
- "Threat hunting" methodologies (Sqrrl/THF model references)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
