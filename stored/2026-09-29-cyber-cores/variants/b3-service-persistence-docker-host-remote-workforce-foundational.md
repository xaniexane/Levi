---
skill_id: cyber_b3_service_persistence_docker_host_remote_workforce_foundational
name: Malicious Service Persistence Defense for Docker Hosts in Remote Workforce (Foundational Maturity)
description: "Malicious Service Persistence defense playbook for Docker Hosts in Remote Workforce at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, containers, docker, remote, endpoint, zero-trust, maturity-foundational]
version: 1.0.0
---
# Malicious Service Persistence Defense for Docker Hosts in Remote Workforce (Foundational Maturity)

## Purpose

Attackers install or hijack Windows services for SYSTEM-level, reboot-surviving execution. Services are trusted by admins, so malicious ones hide with plausible names — verify the binary, not the display name. Applies to Docker Hosts in Remote Workforce at Foundational maturity.

## When to use

- 7045 (service installed) with ImagePath in user-writable or temp directories, unsigned binaries, or names mimicking legit services.
- Existing service ImagePath changed (7045 with same name, new binary) or service binary replaced on disk.
- Services running as SYSTEM that were recently created and have no vendor documentation or change record.
- Lens: Best telemetry: Docker daemon logs + host auditd + container stdout/stderr shipped centrally. EDR on every endpoint as the primary sensor (no corporate network tap for remote hosts).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to VPN/ZTNA access logs and SaaS/IdP sign-in logs as the network-visibility substitute.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Docker daemon log (container create/start with full flags), docker events history and Container image digests and layer histories (docker history) versus expected digests; run `docker ps --format '{{.Names}} {{.Image}}' ; echo ---; docker events --since 24h --until 0s 2>/dev/null | tail -20` then `docker inspect $(docker ps -q) --format '{{.Name}} privileged={{.HostConfig.Privileged}} mounts={{.Mounts}}' 2>/dev/null`.
3. **Analyze.** Hash and detonate the service binary; check its signature status and first-seen date in threat intel. Then: Review the service account: LocalSystem services have maximum impact — scope accordingly.
4. **Contain and harden.** Alert on all 7045 events; require change tickets for new services and run services as least-privilege virtual accounts. Asset layer: No --privileged, no host socket mounts except for explicit agents, user namespaces enabled, read-only root filesystems. Environment layer: Zero-trust access: device compliance + MFA per application, not per network.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the service without deleting it — it restarts on reboot.
- Missing service DLL hijacking (Services with ServiceDll in writable paths) while hunting only EXE-based services.

## References

- MITRE ATT&CK: T1543.003 (Persistence: Windows Service)
- Vendor logging and hardening baselines for Docker Hosts; Zero-trust access: device compliance + MFA per application, not per network.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
