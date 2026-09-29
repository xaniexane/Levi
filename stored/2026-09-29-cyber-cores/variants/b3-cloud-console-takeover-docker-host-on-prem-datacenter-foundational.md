---
skill_id: cyber_b3_cloud_console_takeover_docker_host_on_prem_datacenter_foundational
name: Cloud Console Takeover Defense for Docker Hosts in On-Premises Datacenter (Foundational Maturity)
description: "Cloud Console Takeover defense playbook for Docker Hosts in On-Premises Datacenter at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, identity, containers, docker, on-prem, datacenter, maturity-foundational]
version: 1.0.0
---
# Cloud Console Takeover Defense for Docker Hosts in On-Premises Datacenter (Foundational Maturity)

## Purpose

Stolen cloud credentials used in the web console give attackers point-and-click infrastructure control. Console logons from unusual locations followed by IAM changes are the classic takeover sequence. Applies to Docker Hosts in On-Premises Datacenter at Foundational maturity.

## When to use

- CloudTrail/Entra sign-in logs showing console logons from new countries or anonymizing services for privileged users.
- IAM policy changes, new access keys, or new users created within minutes of the anomalous logon.
- Disabling of CloudTrail/logging or deletion of log data — the attacker covering tracks.
- Lens: Best telemetry: Docker daemon logs + host auditd + container stdout/stderr shipped centrally. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Docker daemon log (container create/start with full flags), docker events history and Container image digests and layer histories (docker history) versus expected digests; run `docker ps --format '{{.Names}} {{.Image}}' ; echo ---; docker events --since 24h --until 0s 2>/dev/null | tail -20` then `docker inspect $(docker ps -q) --format '{{.Name}} privileged={{.HostConfig.Privileged}} mounts={{.Mounts}}' 2>/dev/null`.
3. **Analyze.** Reconstruct the full API call sequence after takeover: what was created, modified, exfiltrated, or destroyed. Then: Check for persistence: new IAM users, roles with trust policies pointing outward, or modified instance user-data.
4. **Contain and harden.** Phishing-resistant MFA on all console users, especially root/ break-glass; SCPs preventing logging disablement. Asset layer: No --privileged, no host socket mounts except for explicit agents, user namespaces enabled, read-only root filesystems. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Rotating the compromised user's keys but missing the backdoor IAM role the attacker created.
- Trusting the account's own logs after the attacker had admin — verify against the immutable archive.

## References

- MITRE ATT&CK: T1078 (Persistence: Valid Accounts) — cloud console
- Vendor logging and hardening baselines for Docker Hosts; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
