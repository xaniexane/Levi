---
skill_id: cyber_b3_process_injection_docker_host_branch_office_defined
name: Process Injection Defense for Docker Hosts in Branch Offices (Defined Maturity)
description: "Process Injection defense playbook for Docker Hosts in Branch Offices at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, malware, containers, docker, branch, network, maturity-defined]
version: 1.0.0
---
# Process Injection Defense for Docker Hosts in Branch Offices (Defined Maturity)

## Purpose

Malware hides inside legitimate processes via injection (CreateRemoteThread, APC, process hollowing), blending with normal activity. Memory-focused detection — EDR telemetry and targeted memory analysis — is the answer; disk forensics alone misses it. Applies to Docker Hosts in Branch Offices at Defined maturity.

## When to use

- EDR alerts on cross-process memory writes (CreateRemoteThread, NtQueueApcThread) from unusual sources, or hollowed processes (image path mismatches the in-memory PE).
- Legitimate processes (explorer, svchost) making unexpected network connections or spawning children they never normally do.
- Sysmon event 8 (CreateRemoteThread) and event 10 (ProcessAccess) with suspicious granted-access masks.
- Lens: Best telemetry: Docker daemon logs + host auditd + container stdout/stderr shipped centrally. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Docker daemon log (container create/start with full flags), docker events history and Container image digests and layer histories (docker history) versus expected digests; run `docker ps --format '{{.Names}} {{.Image}}' ; echo ---; docker events --since 24h --until 0s 2>/dev/null | tail -20` then `docker inspect $(docker ps -q) --format '{{.Name}} privileged={{.HostConfig.Privileged}} mounts={{.Mounts}}' 2>/dev/null`.
3. **Analyze.** Capture process memory before killing anything; extract the injected payload for family identification. Then: Trace the injector: which process performed the injection and how did IT get compromised (the delivery chain).
4. **Contain and harden.** EDR with behavioral blocking on injection primitives; application control to prevent the initial injector from running. Asset layer: No --privileged, no host socket mounts except for explicit agents, user namespaces enabled, read-only root filesystems. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Killing the host process without capturing memory — the payload exists only in RAM and the evidence is gone.
- Whitelisting the injected process because its NAME is legitimate; verify the in-memory image, not the filename.

## References

- MITRE ATT&CK: T1055 (Defense Evasion: Process Injection)
- Vendor logging and hardening baselines for Docker Hosts; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
