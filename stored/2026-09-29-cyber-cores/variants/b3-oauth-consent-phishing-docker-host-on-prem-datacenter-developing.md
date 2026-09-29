---
skill_id: cyber_b3_oauth_consent_phishing_docker_host_on_prem_datacenter_developing
name: OAuth Consent Phishing Defense for Docker Hosts in On-Premises Datacenter (Developing Maturity)
description: "OAuth Consent Phishing defense playbook for Docker Hosts in On-Premises Datacenter at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [identity, cloud, oauth, containers, docker, on-prem, datacenter, maturity-developing]
version: 1.0.0
---
# OAuth Consent Phishing Defense for Docker Hosts in On-Premises Datacenter (Developing Maturity)

## Purpose

Users grant a malicious app OAuth permissions, giving the attacker persistent API access to mailbox, files, or directory — no password needed, survives password resets, invisible in logon logs. Applies to Docker Hosts in On-Premises Datacenter at Developing maturity.

## When to use

- New enterprise app registrations or OAuth consent grants for apps with vague names, especially requesting Mail.Read or Files.ReadWrite.All.
- Consent grants by users outside any change process, or apps verified by unknown publishers.
- API-driven mailbox/file access patterns (Graph API) with no corresponding interactive logon.
- Lens: Best telemetry: Docker daemon logs + host auditd + container stdout/stderr shipped centrally. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Docker daemon log (container create/start with full flags), docker events history and Container image digests and layer histories (docker history) versus expected digests; run `docker ps --format '{{.Names}} {{.Image}}' ; echo ---; docker events --since 24h --until 0s 2>/dev/null | tail -20` then `docker inspect $(docker ps -q) --format '{{.Name}} privileged={{.HostConfig.Privileged}} mounts={{.Mounts}}' 2>/dev/null`.
3. **Analyze.** Inventory every permission the malicious app holds and every API call it made — the data accessed defines the breach. Then: Check for admin-consent abuse: was the app granted tenant-wide access by a compromised admin?
4. **Contain and harden.** Require admin consent for third-party apps; maintain an allowlist of approved publishers. Asset layer: No --privileged, no host socket mounts except for explicit agents, user namespaces enabled, read-only root filesystems. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Resetting the user's password and declaring victory while the OAuth grant keeps working.
- Overlooking that the app may have been granted access by an ADMIN — scope tenant-wide, not per-user.

## References

- MITRE ATT&CK: T1528 (Credential Access: Steal Application Access Token)
- Vendor logging and hardening baselines for Docker Hosts; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
