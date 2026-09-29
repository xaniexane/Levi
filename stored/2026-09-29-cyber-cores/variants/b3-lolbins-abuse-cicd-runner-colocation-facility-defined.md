---
skill_id: cyber_b3_lolbins_abuse_cicd_runner_colocation_facility_defined
name: Living-off-the-Land Binaries Abuse Defense for CI/CD Runners in Colocation Facilities (Defined Maturity)
description: "Living-off-the-Land Binaries Abuse defense playbook for CI/CD Runners in Colocation Facilities at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, defense-evasion, devops, supply-chain, on-prem, colocation, maturity-defined]
version: 1.0.0
---
# Living-off-the-Land Binaries Abuse Defense for CI/CD Runners in Colocation Facilities (Defined Maturity)

## Purpose

Attackers use built-in tools (certutil, bitsadmin, mshta, rundll32, wmic) for download, execution, and exfiltration — no malware to signature. Defense is behavioral: baseline normal LOLBin usage and alert on anomalous parents, arguments, and network activity. Applies to CI/CD Runners in Colocation Facilities at Defined maturity.

## When to use

- LOLBins spawned by Office apps, browsers, or scripts with network arguments (certutil -urlcache, bitsadmin /transfer) — parents that never legitimately drive them.
- Encoded or obfuscated arguments, downloads to temp/appdata, or LOLBin-initiated outbound connections.
- Rare LOLBins (mshta, regsvr32, cmstp) executing at all in environments that never use them legitimately.
- Lens: Best telemetry: job execution logs + runner registration events + secret-access audit. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Job logs with executed commands and exit codes for suspect runs and Runner registration/deregistration events and runner version inventory; run `runner-cli jobs list --status failed --last 7d | head -20` then `runner-cli runners list --format table`.
3. **Analyze.** Reconstruct the full command line — the arguments reveal intent (download URL, payload path, execution method). Then: Check whether the LOLBin fetched a second stage; if so, the investigation continues at the downloaded payload.
4. **Contain and harden.** Application control policies blocking LOLBin network/download primitives where unused; constrained language mode for PowerShell. Asset layer: Ephemeral isolated runners, OIDC short-lived credentials, no persistent secrets on runners. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking a LOLBin outright and breaking admin workflows — constrain by parent and argument, not by existence.
- Missing LOLBin use on Linux/macOS (curl, wget, python) while hunting Windows only.

## References

- MITRE ATT&CK: T1218 (Defense Evasion: System Binary Proxy Execution)
- Vendor logging and hardening baselines for CI/CD Runners; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
