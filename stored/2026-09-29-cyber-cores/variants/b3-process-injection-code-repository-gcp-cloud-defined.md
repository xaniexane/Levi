---
skill_id: cyber_b3_process_injection_code_repository_gcp_cloud_defined
name: Process Injection Defense for Code Repositories in GCP Cloud (Defined Maturity)
description: "Process Injection defense playbook for Code Repositories in GCP Cloud at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, malware, devops, supply-chain, secrets, cloud, gcp, maturity-defined]
version: 1.0.0
---
# Process Injection Defense for Code Repositories in GCP Cloud (Defined Maturity)

## Purpose

Malware hides inside legitimate processes via injection (CreateRemoteThread, APC, process hollowing), blending with normal activity. Memory-focused detection — EDR telemetry and targeted memory analysis — is the answer; disk forensics alone misses it. Applies to Code Repositories in GCP Cloud at Defined maturity.

## When to use

- EDR alerts on cross-process memory writes (CreateRemoteThread, NtQueueApcThread) from unusual sources, or hollowed processes (image path mismatches the in-memory PE).
- Legitimate processes (explorer, svchost) making unexpected network connections or spawning children they never normally do.
- Sysmon event 8 (CreateRemoteThread) and event 10 (ProcessAccess) with suspicious granted-access masks.
- Lens: Best telemetry: push/audit logs + secret-scanning alerts + branch-protection change history. Cloud Audit Logs (admin + data access) exported to a locked-down logging project.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Security Command Center findings and VPC flow logs centralized.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Push logs (who pushed what to which branch), force-push and history-rewrite records and Secret-scanning and code-scanning alerts with their resolution state; run `git log --since='7 days ago' --format='%h %an %ad %s' --date=short | head -30` then `git log --all --diff-filter=A -- '*secret*' '*credential*' '*key*' --format='%h %an %s' | head -20`.
3. **Analyze.** Capture process memory before killing anything; extract the injected payload for family identification. Then: Trace the injector: which process performed the injection and how did IT get compromised (the delivery chain).
4. **Contain and harden.** EDR with behavioral blocking on injection primitives; application control to prevent the initial injector from running. Asset layer: Branch protection with required reviews, signed commits, push protection for secrets. Environment layer: Organization policies constraining public exposure, API enablement, and service-account key creation.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Killing the host process without capturing memory — the payload exists only in RAM and the evidence is gone.
- Whitelisting the injected process because its NAME is legitimate; verify the in-memory image, not the filename.

## References

- MITRE ATT&CK: T1055 (Defense Evasion: Process Injection)
- Vendor logging and hardening baselines for Code Repositories; Organization policies constraining public exposure, API enablement, and service-account key creation.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
