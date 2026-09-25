---
skill_id: cyber_detecting_rogue_devices_on_the_local_network
name: Detecting Rogue Devices on the Local Network
description: Detect unauthorized or unknown devices joining your own LAN using ARP and neighbor-table baselining, with scoping guardrails and a proportionate response workflow.
risk: low
permissions: []
requires_confirmation: false
tags: [network, asset-management, detection]
version: 1.0.0
---
# Detecting Rogue Devices on the Local Network

## Purpose

Give defenders a repeatable workflow for spotting unknown or unauthorized
devices on networks they own — a contractor laptop plugged into a wall
jack, a rogue access point, an IoT device that appeared overnight, or an
attacker's foothold bridging into the LAN. Covers building a baseline of
known devices from ARP and neighbor tables, detecting newcomers, scoping
the activity strictly to your own networks, and responding without
disrupting legitimate users.

## When to use

- As a recurring hygiene control for office, lab, and OT-adjacent
  networks where the device population should be known and stable.
- After a physical-security incident (tailgating, unescorted visitor,
  missing badge) where a drop device may have been planted.
- When NAC or 802.1X is not deployed and you need a lightweight
  compensating control.
- During incident response, to determine whether an attacker has
  established a new network presence.
- When onboarding a new site: establish the device baseline before
  treating anomalies as incidents.

## Prerequisites

- Written authorization from the network owner covering the specific
  subnets and VLANs in scope. Never run discovery scans against
  networks you do not own or are not authorized to assess.
- A sensor host or existing infrastructure (switch ARP tables, DHCP
  logs, wireless controller client lists) with visibility into the
  target broadcast domains.
- An asset inventory or CMDB to reconcile discovered devices against —
  detection without an expected-device list is just noise.
- A contact path to facilities/IT for physically locating a suspect
  device (switch, port, AP, room).
- Change-control awareness: baseline during a known-good window, not
  during a move, office expansion, or mass reimaging.

## Procedure

1. **Scope strictly to your own networks.** Write down the exact
   subnets, VLANs, and SSIDs in scope, and confirm authorization for
   each. Discovery techniques (ARP sweeps, ping sweeps) are active —
   they touch every host — so scoping is a safety requirement, not
   paperwork.
2. **Collect multiple independent device views.** Pull the ARP/neighbor
   table from a sensor host, query switch CAM/ARP tables via SNMP or
   the management interface, export DHCP lease logs, and list wireless
   controller associations. No single source sees everything; correlate
   them.
3. **Build the known-device baseline.** During a clean window, record
   IP, MAC, hostname, switch port or AP, and first-seen time for every
   device. Reconcile against the asset inventory: every entry should
   map to a known asset, a documented exception (guest VLAN, lab gear),
   or an investigation ticket. Store the baseline where the team can
   diff against it.
4. **Run scheduled comparisons.** Re-collect the device views on a
   schedule (hourly for sensitive segments, daily for general office)
   and diff against the baseline. Alert on: MAC addresses never seen
   before, known MACs appearing on unexpected ports/VLANs (possible
   spoofing or relocation), and multiple IPs claiming one MAC.
5. **Triage each newcomer before reacting.** Check DHCP logs for the
   device's hostname and lease history, check the asset inventory and
   recent tickets (new hire? loaner laptop? conference room Apple TV?),
   and look at its traffic profile — a device that only talks to the
   update server is a different story from one scanning the subnet.
6. **Respond proportionately.** For confirmed-rogue devices: locate
   the physical port or AP, disable the switch port or quarantine the
   device to a remediation VLAN, capture its MAC/IP/DHCP fingerprint
   for the record, and image or inspect it if compromise is suspected.
   For benign-but-unknown devices: document them into the baseline
   with an owner and justification.
7. **Close the loop and harden.** Feed findings into the asset
   inventory, review why the device wasn't in the baseline (process
   gap or shadow IT), and where rogue devices keep appearing, make the
   case for 802.1X/NAC, port-security, or disabling unused wall jacks —
   detection is the compensating control, not the end state.

## Expected outputs

- A documented, reconciled baseline of known devices per in-scope
  segment (IP, MAC, hostname, location, owner).
- Scheduled diff reports with alerting on unknown or relocated
  devices, tuned against legitimate churn.
- Triage records for each alert: benign (baselined), unauthorized
  (remediated), or malicious (escalated to incident response).
- Remediation actions taken (port disables, quarantines) with
  approvals noted.
- A hardening backlog where detection keeps firing (NAC, port
  security, jack management).

## Pitfalls

- **Scanning networks you don't own.** ARP and ping sweeps are
  active techniques. Keep them inside your authorized scope —
  "the Wi-Fi reached the neighbor's office" is not authorization.
- **Baseline during churn.** Building the baseline during onboarding
  week or a hardware refresh bakes noise into ground truth. Pick a
  quiet window and re-baseline after planned changes.
- **MAC-only identity.** MACs are trivially spoofed. Treat a
  never-before-seen MAC as a lead and corroborate with DHCP
  fingerprints, traffic behavior, and physical location before
  accusing anyone.
- **Alerting on every DHCP renewal.** Laptops sleep, phones roam,
  printers get replaced. Tune for genuinely new devices, not for
  normal lease churn, or the SOC will mute the rule.
- **Forgetting wireless and VPN.** A LAN-only view misses the rogue
  AP bridged to your wired network and the device that only appears
  over VPN. Cover all entry paths or say explicitly which ones you
  don't.

## References

- Your switch vendor's documentation for ARP/CAM table export via
  SNMP or management API.
- DHCP server logging guides for lease-history forensics.
- NIST SP 800-53 (CM-8 system component inventory) for the
  inventory discipline behind detection.
- 802.1X/NAC vendor documentation, for the hardening step when
  detection alone isn't enough.
- SANS or CERT guidance on rogue-device response procedures.

---
*Original work authored for LEVI. Defensive blue-team playbook — detection, analysis, and hardening guidance only. Topic inspired by a LAN device-guard script; no content copied from any external source.*
