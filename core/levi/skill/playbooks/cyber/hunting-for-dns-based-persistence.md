---
skill_id: cyber_hunting_for_dns_based_persistence
name: Hunting for DNS-Based Persistence
description: Detect persistence via malicious DNS configuration: rogue resolvers, hosts-file tampering, and DNS-layer implants.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, persistence, dns]
version: 1.0.0
---
## Purpose

DNS is trusted, rarely inspected deeply, and essential — which makes it
an attractive persistence layer: rogue DNS servers, hosts-file entries,
malicious DNS client configuration, and DNS-based implants that survive
reboots. This playbook covers hunting for DNS-layer persistence
mechanisms on endpoints and in network configuration.

## When to use

- Investigating intrusions where C2 survived host remediation (the
  persistence may live in DNS configuration, not on disk).
- Hunting for DNSChanger-style malware or router/DHCP-based DNS
  hijacking.
- Validating DNS configuration integrity across the fleet after a
  network-device compromise.
- Proactive hunting for hosts-file and resolver tampering.

## Prerequisites

- Endpoint telemetry: registry monitoring (DNS client settings),
  file-integrity data for hosts files, and process telemetry.
- Network configuration sources: DHCP server configs, router/GPO-
  pushed DNS settings, and the authorized resolver inventory.
- DNS query logs to validate which resolvers endpoints actually use.
- Baselines: legitimate DNS servers per segment and legitimate
  hosts-file contents.

## Procedure

1. **Inventory authorized DNS configuration.** Document the legitimate
   DNS servers per network segment (internal resolvers, approved
   forwarders) and the mechanisms that set them (DHCP, GPO, MDM). Any
   deviation from this inventory is the hunting surface.
2. **Hunt rogue resolver settings.** Query endpoints for DNS server
   configurations that do not match the authorized inventory —
   registry (`Tcpip\Parameters\Interfaces`), `resolv.conf`, and MDM-
   pushed profiles. Flag public resolvers on hosts that should use
   internal ones, and any unknown IPs.
3. **Hunt hosts-file tampering.** Monitor hosts files for modifications
   (Windows `System32\drivers\etc\hosts`, `/etc/hosts`): entries
   redirecting security-vendor, update, or banking domains to
   attacker IPs are classic DNS-layer persistence and C2 facilitation.
4. **Hunt DHCP and router tampering.** Review DHCP server configurations
   and scope options for rogue DNS server entries; check network
   devices for unauthorized DNS or DHCP changes — router-level
   tampering persists across endpoint rebuilds.
5. **Validate actual resolver usage.** Compare configured DNS against
   DNS query logs: endpoints querying external resolvers directly
   (port 53 to non-authorized IPs, or DoH to unknown providers)
   despite internal configuration indicate tampering or tunneling.
6. **Check for DNS-implant persistence.** Look for scheduled tasks,
   services, or WMI subscriptions whose purpose is re-applying rogue
   DNS settings — attackers often pair DNS tampering with a
   re-tampering mechanism. Also review for malicious browser or OS
   DoH settings overriding enterprise DNS.
7. **Scope and remediate.** Identify all affected hosts and the
   tampering vector (malware, GPO abuse, router compromise), restore
   authorized DNS configuration, remove re-tampering persistence, and
   investigate what the rogue DNS facilitated (phishing, C2, update
   blocking).
8. **Harden DNS configuration.** Enforce DNS settings via GPO/MDM,
   monitor resolver-configuration changes with file/registry integrity
   monitoring, deploy DNS-layer security (filtering, logging), and
   alert on direct-to-external DNS from endpoints that should use
   internal resolvers.

## Expected outputs

- DNS-configuration inventory vs. authorized baseline, with
   deviations investigated.
- Findings: tampered hosts, rogue resolvers, hosts-file entries, and
   the attacker's DNS infrastructure.
- Remediation records and re-tampering persistence removed.
- Monitoring rules for DNS-configuration drift.

## Pitfalls

- VPN clients and mobile devices legitimately change DNS settings —
   baseline per device class before alerting.
- DoH/DoT adoption complicates "authorized resolver" definitions —
   define policy for encrypted DNS explicitly.
- Router compromises affect entire segments — a single tampered host
   may indicate network-device compromise; check upstream.
- Hosts-file monitoring without integrity tooling is gap-prone —
   deploy FIM on the file rather than relying on periodic hunts.
- Restoring DNS without removing the re-tampering mechanism leads to
   immediate re-compromise.

## References

- MITRE ATT&CK: T1556 (Modify Authentication Process),
  T1137-adjacent persistence techniques; T1562.002 (DNS-based
  defense impairment patterns)
- NIST SP 800-81: Secure Domain Name System Deployment Guide
- CISA: DNS security guidance
- Vendor documentation for DNS-layer security controls
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
