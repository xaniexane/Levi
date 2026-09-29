---
skill_id: cyber_b3_lolbins_abuse_proxy_server_gcp_cloud_developing
name: Living-off-the-Land Binaries Abuse Defense for Proxy Servers in GCP Cloud (Developing Maturity)
description: "Living-off-the-Land Binaries Abuse defense playbook for Proxy Servers in GCP Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, defense-evasion, network, proxy, web, cloud, gcp, maturity-developing]
version: 1.0.0
---
# Living-off-the-Land Binaries Abuse Defense for Proxy Servers in GCP Cloud (Developing Maturity)

## Purpose

Attackers use built-in tools (certutil, bitsadmin, mshta, rundll32, wmic) for download, execution, and exfiltration — no malware to signature. Defense is behavioral: baseline normal LOLBin usage and alert on anomalous parents, arguments, and network activity. Applies to Proxy Servers in GCP Cloud at Developing maturity.

## When to use

- LOLBins spawned by Office apps, browsers, or scripts with network arguments (certutil -urlcache, bitsadmin /transfer) — parents that never legitimately drive them.
- Encoded or obfuscated arguments, downloads to temp/appdata, or LOLBin-initiated outbound connections.
- Rare LOLBins (mshta, regsvr32, cmstp) executing at all in environments that never use them legitimately.
- Lens: Best telemetry: full URL logs with user identity + TLS SNI logs + block/allow verdicts. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Access logs (user, URL, category, verdict, bytes) for the incident window and Blocked-request logs showing attempted C2/malware/phishing destinations; run `grep <username> /var/log/squid/access.log | awk '{print $7}' | sort | uniq -c | sort -rn | head -20` then `grep -E 'TCP_DENIED|BLOCK' /var/log/squid/access.log | tail -30`.
3. **Analyze.** Reconstruct the full command line — the arguments reveal intent (download URL, payload path, execution method). Then: Check whether the LOLBin fetched a second stage; if so, the investigation continues at the downloaded payload.
4. **Contain and harden.** Application control policies blocking LOLBin network/download primitives where unused; constrained language mode for PowerShell. Asset layer: Authenticated proxying (no anonymous egress), category blocking, TLS inspection where policy allows. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking a LOLBin outright and breaking admin workflows — constrain by parent and argument, not by existence.
- Missing LOLBin use on Linux/macOS (curl, wget, python) while hunting Windows only.

## References

- MITRE ATT&CK: T1218 (Defense Evasion: System Binary Proxy Execution)
- Vendor logging and hardening baselines for Proxy Servers; Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
