---
skill_id: cyber_b3_dns_tunneling_docker_host_azure_cloud_foundational
name: DNS Tunneling Defense for Docker Hosts in Azure Cloud (Foundational Maturity)
description: "DNS Tunneling defense playbook for Docker Hosts in Azure Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, dns, c2, containers, docker, cloud, azure, maturity-foundational]
version: 1.0.0
---
# DNS Tunneling Defense for Docker Hosts in Azure Cloud (Foundational Maturity)

## Purpose

DNS tunneling smuggles data or C2 inside DNS queries, abusing a protocol almost every network allows outbound. Detection hinges on query shape (length, entropy, volume, record types), not on blocklists. Applies to Docker Hosts in Azure Cloud at Foundational maturity.

## When to use

- Long, high-entropy subdomains (often 50+ chars) in DNS logs, unusual record types (TXT, NULL) at volume, or a single host generating thousands of queries to one domain.
- Beacon-like regularity in query timing to an obscure domain, or DNS queries for domains registered within the last 30 days.
- Responses with abnormally large TXT records relative to the query — data coming back down the tunnel.
- Lens: Best telemetry: Docker daemon logs + host auditd + container stdout/stderr shipped centrally. Activity Log and Entra sign-in/audit logs streamed to Log Analytics/SIEM; Defender for Cloud alerts.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NSG flow logs and storage analytics for data-plane visibility.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Docker daemon log (container create/start with full flags), docker events history and Container image digests and layer histories (docker history) versus expected digests; run `docker ps --format '{{.Names}} {{.Image}}' ; echo ---; docker events --since 24h --until 0s 2>/dev/null | tail -20` then `docker inspect $(docker ps -q) --format '{{.Name}} privileged={{.HostConfig.Privileged}} mounts={{.Mounts}}' 2>/dev/null`.
3. **Analyze.** Decode a sample of tunneled queries/responses in a sandbox to determine direction and content: C2 instructions, exfiltrated data, or both. Then: Identify patient zero by earliest query timestamp, then hunt laterally: tunneling tools are often deployed to multiple hosts.
4. **Contain and harden.** Force all DNS through logged, filtered resolvers; block direct port-53 egress from endpoints and alert on non-standard DNS ports. Asset layer: No --privileged, no host socket mounts except for explicit agents, user namespaces enabled, read-only root filesystems. Environment layer: Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking the domain without finding the implant — the attacker rotates domains faster than you blocklist.
- Ignoring DNS over HTTPS (DoH): tunneled traffic inside DoH is invisible to passive DNS monitoring — log at the endpoint.

## References

- MITRE ATT&CK: T1071.004 (Command and Control: DNS)
- Vendor logging and hardening baselines for Docker Hosts; Azure Policy deny-effects on risky configurations; PIM-gated subscription roles.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
