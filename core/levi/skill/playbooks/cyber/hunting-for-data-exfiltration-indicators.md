---
skill_id: cyber_hunting_for_data_exfiltration_indicators
name: Hunting for Data Exfiltration Indicators
description: Detect data exfiltration via egress anomalies, DNS/ICMP tunnels, cloud uploads, and endpoint staging telemetry.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, exfiltration, dlp]
version: 1.0.0
---
## Purpose

Exfiltration is the stage where intrusions become breaches. This playbook
covers hunting for data leaving the network: volumetric egress anomalies,
tunneling over DNS/ICMP, abuse of legitimate cloud services, and the
endpoint-side staging that precedes exfiltration — across both
adversary-driven and insider-threat scenarios.

## When to use

- During incident response: determining whether (and what) data left
  the network.
- Proactive hunting on egress telemetry, especially after detecting
  staging activity.
- Insider-threat investigations involving large or unusual transfers.
- Validating DLP and egress-monitoring coverage.

## Prerequisites

- Egress telemetry: proxy logs (with bytes and URLs), firewall logs,
  NetFlow, DNS logs, and cloud-access (CASB) logs.
- Endpoint telemetry: file-access auditing for sensitive shares,
  USB/removable-media events, and archive-tool execution.
- Baselines: normal egress volumes per host role, approved cloud
  services, and typical upload sizes.
- Data-classification knowledge: which shares and systems hold crown-
  jewel data.

## Procedure

1. **Establish egress baselines.** Compute normal upload volumes per
   host role, per user, and per destination category. Exfiltration
   hunting is anomaly hunting — without baselines, everything looks
   suspicious.
2. **Hunt volumetric anomalies.** Flag hosts with uploads far above
   their baseline, especially to rare or newly seen destinations, and
   uploads occurring outside business hours or immediately after
   staging events (large archive creation).
3. **Hunt tunneling protocols.** Look for DNS exfiltration (high query
   volumes, long labels, TXT/NULL record abuse), ICMP tunneling
   (unusual ICMP volumes/payload sizes between internal and external
   hosts), and data over non-standard ports.
4. **Hunt cloud and web-service abuse.** Review uploads to personal
   cloud storage, paste sites, anonymous file shares, and webmail from
   corporate hosts — cross-reference against the approved-service list.
   Check for OAuth grants to unknown third-party apps (consent phishing
   as an exfil path).
5. **Hunt endpoint staging precursors.** Correlate egress anomalies with
   archive-tool execution (7z, rar, tar with encryption flags), bulk
   file access on sensitive shares, and USB mass-storage connections on
   the same host within the preceding hours/days.
6. **Inspect the content where lawful.** Where authorization and policy
   permit, examine proxy-captured uploads, DLP alerts on the same flows,
   and file types/sizes to characterize what left — this determines
   breach-notification obligations.
7. **Scope and contain.** Identify all affected hosts and accounts,
   determine the data categories involved with data owners, preserve
   evidence (proxy captures, endpoint images) for legal hold, and
   contain per the IR plan (isolate hosts, revoke OAuth grants, block
   destinations).
8. **Close the egress gaps.** Deploy DLP rules for the observed
   techniques, restrict unapproved cloud services at the proxy, alert
   on archive-then-upload sequences, and add the hunt to recurring
   analytics.

## Expected outputs

- Exfiltration findings: hosts, accounts, destinations, volumes, and
  timeframes.
- Data-impact characterization with data-owner input.
- Evidence preserved under legal hold with chain of custody.
- New DLP rules and recurring egress-hunt analytics.

## Pitfalls

- Encrypted uploads hide content — you may prove exfiltration
   occurred without knowing exactly what left; document the uncertainty
   honestly.
- Legitimate bulk transfers (backups, migrations, video production)
   mimic exfiltration — baseline by role and confirm with asset owners.
- Focusing only on network: USB and physical exfiltration need
   endpoint telemetry — check removable-media events.
- DLP alone is not exfiltration hunting — tuned DLP misses novel
   channels; behavioral hunting catches what signatures miss.
- Legal and HR constraints on content inspection — get authorization
   before examining user data.

## References

- MITRE ATT&CK: T1041, T1048, T1567 (exfiltration techniques)
- NIST SP 800-150: threat information sharing (breach context)
- Vendor DLP/CASB documentation for control tuning
- Applicable breach-notification regulations for your jurisdiction
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
