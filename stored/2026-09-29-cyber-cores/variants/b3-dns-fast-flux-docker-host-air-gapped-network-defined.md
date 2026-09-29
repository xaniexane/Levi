---
skill_id: cyber_b3_dns_fast_flux_docker_host_air_gapped_network_defined
name: DNS Fast-Flux Defense for Docker Hosts in Air-Gapped Networks (Defined Maturity)
description: "DNS Fast-Flux defense playbook for Docker Hosts in Air-Gapped Networks at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, dns, c2, containers, docker, air-gap, ot, high-security, maturity-defined]
version: 1.0.0
---
# DNS Fast-Flux Defense for Docker Hosts in Air-Gapped Networks (Defined Maturity)

## Purpose

Fast-flux networks rotate DNS answers across many compromised hosts every few minutes, making malicious infrastructure hard to takedown. Defenders detect the flux pattern itself: low TTLs, high answer churn, and geographically scattered A records. Applies to Docker Hosts in Air-Gapped Networks at Defined maturity.

## When to use

- DNS answers with TTLs under 300 seconds rotating across dozens of IPs in unrelated ASNs and countries for a single domain.
- Short-lived domains (registered days ago) resolving to residential or compromised-server IPs with no legitimate business relationship.
- Endpoint connections to flux domains correlating with malware detonations or phishing kit infrastructure.
- Lens: Best telemetry: Docker daemon logs + host auditd + container stdout/stderr shipped centrally. Local SIEM/log collector inside the enclave (no cloud shipping); removable-media transfer logs.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Strict allowlisting logs: every binary execution recorded, since the set is small and known.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Docker daemon log (container create/start with full flags), docker events history and Container image digests and layer histories (docker history) versus expected digests; run `docker ps --format '{{.Names}} {{.Image}}' ; echo ---; docker events --since 24h --until 0s 2>/dev/null | tail -20` then `docker inspect $(docker ps -q) --format '{{.Name}} privileged={{.HostConfig.Privileged}} mounts={{.Mounts}}' 2>/dev/null`.
3. **Analyze.** Profile the flux: record TTL, unique IPs per hour, ASN/country spread, and name-server patterns to fingerprint the specific flux service or kit. Then: Pivot from the domain to find sibling infrastructure: shared name servers, registration patterns, and certificate overlaps.
4. **Contain and harden.** DNS response policy zones (RPZ) blocking confirmed flux domains, plus alerting on sub-300s TTL answers at the resolver. Asset layer: No --privileged, no host socket mounts except for explicit agents, user namespaces enabled, read-only root filesystems. Environment layer: Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Blocking individual flux IPs — they churn in minutes; block the domain pattern and the detection logic instead.
- Confusing legitimate CDN behavior (low TTL, many IPs) with flux; require the ASN-scatter plus short-domain-age combination.

## References

- MITRE ATT&CK: T1568.002 (Command and Control: Domain Generation Algorithms)
- Vendor logging and hardening baselines for Docker Hosts; Data diodes or strictly controlled one-way transfers; media sanitization procedures for anything crossing.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
