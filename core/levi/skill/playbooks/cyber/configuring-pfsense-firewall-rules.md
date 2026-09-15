---
skill_id: cyber_configuring_pfsense_firewall_rules
name: Configuring pfSense Firewall Rules
description: Build a least-privilege pfSense rule set with correct ordering, stateful inspection, and change auditing.
risk: low
permissions: []
requires_confirmation: false
tags: [firewall, network, hardening]
version: 1.0.0
---
## Purpose

Turn a default-allow pfSense posture into an explicit least-privilege rule set: correct rule ordering, stateful filtering, strict egress, and logged denies — so the firewall is an enforcement point, not a suggestion.

## When to use

- Initial deployment or hardening of a pfSense (or OPNsense-compatible) perimeter / segmentation firewall.
- Periodic firewall rule audits and cleanup of stale or overly broad rules.
- After a breach where the firewall's allow rules are suspected of enabling lateral movement or egress.
- Segmenting trusted, untrusted, DMZ, and management networks.

## Prerequisites

- Console or web-UI admin access to the pfSense instance plus a tested backup of the current configuration (Diagnostics > Backup & Restore).
- A network map: interfaces, VLANs, address ranges, and which traffic each zone legitimately needs.
- A documented change window and rollback plan — a mis-ordered rule can isolate management access.
- Logging destination ready (local log plus remote syslog to the SIEM).

## Procedure

1. **Inventory and snapshot.** Document every interface, alias, and existing rule. Export a config backup and save it with the date and author before touching anything. Record the rule count as a baseline for the audit trail.
2. **Define the zone policy in writing first.** For each interface pair, decide the intended default: typically deny-any-any between untrusted and internal zones, allow-management only from the admin network, and DMZ services reachable only on required ports. The rule set implements this document — write the document before the rules.
3. **Order rules from most specific to most general.** pfSense evaluates top-down with first match. Place explicit allow rules for known services above broader rules, and put the default deny at the bottom of each interface tab. A broad early allow silently nullifies everything below it.
4. **Use aliases for everything.** Define aliases for RFC1918 space, management subnets, service port groups (e.g. web-services = 80/443), and host groups. Aliases make rules readable and let one edit update every rule that references them.
5. **Implement strict egress filtering.** Default-deny outbound on internal interfaces, then allow only what's needed: DNS to the internal resolvers, HTTP/HTTPS to the proxy, specific application ports. Block direct outbound 53 except from resolvers (kills casual DNS tunneling) and deny outbound SMTP from clients (kills spam bots).
6. **Harden the management plane.** Restrict the web UI and SSH to the management network only, change default ports if policy allows, enable HTTPS with a trusted certificate, and put the admin interface on a dedicated VLAN unreachable from user segments.
7. **Log the denies, sample the allows.** Enable logging on deny rules (that's your tripwire telemetry) and log allows selectively for sensitive flows. Forward to syslog/SIEM and alert on denied outbound bursts, management-interface probes, and firewall rule-change events.
8. **Set state timeouts deliberately.** Tighten TCP/UDP state timeouts on untrusted interfaces to bound resource exhaustion, and enable conservative state handling for asymmetric-routing environments. Monitor state-table utilization under load.
9. **Schedule and schedule review.** Tag every rule with a description including owner and ticket reference. Review the full rule set quarterly: disable rules with no logged hits over the period, remove temporary rules, and verify each broad rule is still justified.
10. **Test the enforcement, not just the config.** From each zone, verify a permitted flow works and — critically — that a denied flow is actually blocked (nmap from untrusted, curl to blocked egress). Record test results with the change.

## Expected outputs

- A backed-up, documented, least-privilege rule set with default deny on untrusted and internal interfaces.
- Alias-based rules with owner/ticket descriptions and a quarterly review cadence.
- Syslog-forwarded deny logs feeding SIEM alerts for scans, egress attempts, and config changes.
- Test evidence that allows work and denies hold.

## Pitfalls

- A broad "allow all" at the top of an interface tab — the single most common pfSense misconfiguration.
- Forgetting that floating rules process before interface rules — misplaced floating rules can override intended denies.
- Blocking your own management access remotely with no out-of-band path — always test from console-adjacent access first.
- Assuming NAT rules imply filtering — pfSense requires the firewall rule even when NAT port-forwards exist.
- Leaving the web UI exposed to WAN for "temporary" remote admin; disable when done, ideally permanently.

## References

- pfSense official documentation — Firewall Rules and NAT (docs.netgate.com)
- NIST SP 800-41 Rev. 1 (Guidelines on Firewalls and Firewall Policy)
- MITRE ATT&CK T1562.004 (Impair Defenses: Disable or Modify System Firewall)
