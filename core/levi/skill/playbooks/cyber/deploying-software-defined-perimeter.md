---
skill_id: cyber_deploying_software_defined_perimeter
name: Deploying Software-Defined Perimeter
description: Deploy a software-defined perimeter with single-packet authorization and identity-based access for darkened infrastructure.
risk: low
permissions: []
requires_confirmation: false
tags: [ztna, network, architecture]
version: 1.0.0
---
## Purpose

Make infrastructure invisible: deploy a software-defined perimeter (SDP) where protected services accept no inbound connections at all until a client proves identity via single-packet authorization (SPA). No open ports, no VPN concentrator to attack — just darkened services and authenticated, encrypted tunnels.

## When to use

- Protecting administrative interfaces (SSH, RDP, admin consoles) from internet scanning and exploitation.
- Replacing VPN for privileged and third-party access with per-service, per-user tunnels.
- Securing multi-cloud workloads behind a single identity-aware access layer.
- Meeting requirements to eliminate publicly listening management ports.

## Prerequisites

- An SDP solution selected (open-source OpenZiti, commercial ZTNA/SDP products, or WireGuard-based SPA implementations).
- Identity provider integrated for user authentication; device identity (certificates) for workload-to-workload paths.
- Inventory of protected services: hosts, ports, and authorized users/devices per service.
- Client deployment mechanism for user devices and workload identities.

## Procedure

1. **Choose the architecture: controller, gateways, clients.** Deploy the SDP controller (policy decision point) in a hardened, highly available configuration, and gateways/routers adjacent to each protected network segment. Controllers never proxy data — they issue policy; gateways enforce it. Keep the controller's own attack surface minimal.
2. **Darken the protected services.** Firewall every protected service to drop all inbound traffic by default — no listening ports visible to scanners. Verify with external port scans: the services should appear as filtered/dead. This is the core SDP promise; if a port is reachable without SPA, the deployment is incomplete.
3. **Implement single-packet authorization.** Configure clients to send an authenticated SPA packet (HMAC-signed, time-bound, single-use) before any TCP handshake. Gateways open a temporary firewall pinhole only for validated SPA packets, then require mutual TLS for the actual session. Log and alert on SPA failures — they're reconnaissance or misconfiguration.
4. **Write least-privilege service policies.** Each policy binds specific identities (users, devices, workloads) to specific services and ports. No identity gets "the network" — they get named services. Review policies for the classic drift: a policy that started as one app and grew into a subnet.
5. **Enforce mutual TLS on every session.** After SPA, clients and gateways authenticate each other with certificates (short-lived, auto-rotated). Pin the CA, validate the full chain, and reject sessions on any validation failure. This replaces the implicit trust that VPNs grant at the network layer.
6. **Monitor the control and data planes.** Forward controller audit logs (policy decisions, SPA validations) and gateway session logs to the SIEM. Alert on: SPA failure bursts, policy-denied access attempts to sensitive services, new device enrollments, and any direct-to-service connection attempt observed at the host firewall (bypass attempt).
7. **Plan for controller and gateway failure.** Document the failure mode: if the controller is down, existing sessions continue (gateways cache policy) but new authorizations fail — decide whether that's acceptable or whether you need controller HA across regions. Test failover, don't assume it.
8. **Decommission the old access paths.** Remove VPN profiles, close firewall rules that allowed direct access, and verify quarterly that protected services remain dark to unauthenticated scans. The SDP is only as strong as the paths you actually closed.

## Expected outputs

- Protected services with no publicly reachable ports, verified by external scanning.
- SPA + mutual-TLS access bound to per-service, identity-based policies.
- SIEM alerting on SPA failures, policy denies, and bypass attempts; documented failover behavior.

## Pitfalls

- Leaving the old VPN or direct firewall rules in place — the SDP becomes theater.
- Overly broad service policies ("all developers to all dev servers") — per-service granularity is the point.
- Single controller with no HA plan — new access dies with it.
- SPA shared secrets that never rotate — treat them like the credentials they are.
- Forgetting UDP or non-TCP services in the darkening — scan and verify all protocols.

## References

- Cloud Security Alliance — Software-Defined Perimeter specification and architecture guide
- NIST SP 800-207 (Zero Trust Architecture) — SDP as a ZTA deployment model
- NIST SP 800-53 SC-7 (boundary protection)
- MITRE ATT&CK T1133 (External Remote Services) — the attack surface SDP removes
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
