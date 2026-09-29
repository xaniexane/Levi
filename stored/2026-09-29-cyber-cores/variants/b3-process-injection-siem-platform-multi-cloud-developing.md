---
skill_id: cyber_b3_process_injection_siem_platform_multi_cloud_developing
name: Process Injection Defense for SIEM Platforms in Multi-Cloud (Developing Maturity)
description: "Process Injection defense playbook for SIEM Platforms in Multi-Cloud at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, malware, soc, siem, monitoring, cloud, multi-cloud, maturity-developing]
version: 1.0.0
---
# Process Injection Defense for SIEM Platforms in Multi-Cloud (Developing Maturity)

## Purpose

Malware hides inside legitimate processes via injection (CreateRemoteThread, APC, process hollowing), blending with normal activity. Memory-focused detection — EDR telemetry and targeted memory analysis — is the answer; disk forensics alone misses it. Applies to SIEM Platforms in Multi-Cloud at Developing maturity.

## When to use

- EDR alerts on cross-process memory writes (CreateRemoteThread, NtQueueApcThread) from unusual sources, or hollowed processes (image path mismatches the in-memory PE).
- Legitimate processes (explorer, svchost) making unexpected network connections or spawning children they never normally do.
- Sysmon event 8 (CreateRemoteThread) and event 10 (ProcessAccess) with suspicious granted-access masks.
- Lens: Best telemetry: ingestion health metrics + rule-hit history + analyst audit trail. Cloud-agnostic SIEM normalizing AWS CloudTrail, Azure Activity Log, and GCP Audit Logs into one schema.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CSPM coverage across all clouds with consistent misconfiguration alerting.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Detection rule hit history for the incident's indicators across the full retention window and Ingestion gap reports: which sources stopped logging and when (coverage blind spots); run `# conceptually (SIEM query languages differ):` then `index=* <indicator> earliest=-30d | stats count by sourcetype`.
3. **Analyze.** Capture process memory before killing anything; extract the injected payload for family identification. Then: Trace the injector: which process performed the injection and how did IT get compromised (the delivery chain).
4. **Contain and harden.** EDR with behavioral blocking on injection primitives; application control to prevent the initial injector from running. Asset layer: Separate SIEM admin credentials, tamper-evident storage, monitored ingestion pipelines. Environment layer: Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Killing the host process without capturing memory — the payload exists only in RAM and the evidence is gone.
- Whitelisting the injected process because its NAME is legitimate; verify the in-memory image, not the filename.

## References

- MITRE ATT&CK: T1055 (Defense Evasion: Process Injection)
- Vendor logging and hardening baselines for SIEM Platforms; Federated identity across clouds from one IdP; consistent tagging and logging standards per cloud.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
