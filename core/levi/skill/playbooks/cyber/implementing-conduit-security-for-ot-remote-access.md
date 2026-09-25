---
skill_id: cyber_implementing_conduit_security_for_ot_remote_access
name: Secure Remote Access for OT (Conduit Security)
description: Build secure, monitored remote-access conduits into OT environments with zero standing paths.
risk: moderate
permissions: []
requires_confirmation: true
tags: [ot, remote-access]
version: 1.0.0
---
## Purpose
OT remote access is how vendors maintain equipment — and how attackers reach industrial processes.
"Conduit security" here means: dedicated, controlled communication paths (per IEC 62443
zones-and-conduits) for every remote-access flow into OT, with authentication, session monitoring,
and no persistent inbound connectivity. This playbook replaces flat VPNs and vendor backdoors with
governed conduits. Confirmation is required: changes affect live industrial systems.

## When to use
- Replacing always-on vendor VPNs or direct internet exposure of OT systems.
- After incidents or audits finding uncontrolled remote access to industrial control systems.
- Meeting IEC 62443, NERC CIP, or TSA pipeline security requirements for remote access.
- Onboarding new OT vendors or managed-service providers needing remote support.
- As part of OT network segmentation (zones and conduits architecture).

## Prerequisites
- An OT network architecture with defined zones and conduits (or the mandate to create them).
- Asset inventory of OT systems requiring remote support: vendor, system, access need, criticality.
- A jump-host / privileged-access solution that supports session recording and MFA.
- Change control integrated with operations: OT changes need operations approval and maintenance
  windows.
- Incident response coordination between IT security and OT operations (who owns what during an
  event).

## Procedure
1. **Inventory every remote-access path.** Discover all current remote access into OT: vendor VPNs,
   cellular modems, TeamViewer-style tools, remote-desktop gateways, and undocumented connections.
   Assume you don't know all of them — scan, interview vendors, check firewall rules. Unknown paths
   are the first finding.
2. **Define conduits per IEC 62443.** For each legitimate access need, design a conduit: source zone
   → destination zone, allowed protocols/ports, authentication requirements, and monitoring. One
   conduit per vendor/system need — no shared "vendor VPN" carrying multiple vendors' traffic
   without separation.
3. **Eliminate persistent inbound connectivity.** Replace always-on tunnels with on-demand,
   approved, time-limited sessions: vendor requests access → operations approves → conduit opens for
   the window → auto-closes. No standing inbound paths to OT, period.
4. **Route all access through hardened jump hosts.** Vendors connect to a jump host in a DMZ-style
   zone (never directly to control systems). Jump hosts: MFA, session recording, no internet
   browsing, no data exfiltration paths, rebuilt regularly. All vendor activity is attributable and
   reviewable.
5. **Enforce least-privilege per session.** Vendors get access only to their specific systems, only
   the protocols needed, only during approved windows. Credentials are vaulted and rotated (PAM
   integration); shared vendor accounts are prohibited — individual accountability.
6. **Monitor conduits continuously.** Log: session start/end, user, source, destination,
   commands/actions (session recording), and file transfers. Alert on: sessions outside approved
   windows, access to non-authorized systems, bulk data transfer, and conduit configuration changes.
   Feed to the SOC with OT context.
7. **Control the data leaving OT.** File transfers through conduits go via an inspected transfer
   point (AV scan, allowlist by type); clipboard and drive redirection disabled by default. Process
   data leaving the OT boundary is both a security and safety concern.
8. **Manage vendor lifecycle.** Onboard: background/security requirements in contracts, access
   provisioning tied to the support contract. Offboard: immediate deprovisioning when contracts end.
   Review vendor access quarterly — stale vendor accounts are a classic intrusion vector.
9. **Test with operations.** Exercise: a vendor support scenario (request → approve → session →
   close), an anomalous session (alert and terminate), and conduit failure (fallback procedures that
   don't bypass controls). Operations must trust the process or they'll create bypasses.
10. **Govern and audit.** Quarterly conduit review: are all conduits still needed, correctly scoped,
    and properly monitored? Annual assessment against IEC 62443-3-3 SR requirements. Report: vendor
    session volume, anomalies, and time-to-provision/deprovision.

## Expected outputs
- Complete inventory of OT remote-access paths with undocumented ones eliminated or governed.
- Designed conduits per access need: on-demand, time-limited, jump-host-routed, least-privilege.
- Session monitoring with recording, alerting, and SOC integration.
- Vendor lifecycle management tied to contracts with quarterly reviews.
- Tested failover and anomaly procedures agreed with operations.

## Pitfalls
- Bypasses by operations: if the governed path is slow, staff will create direct connections. Make
  the official path fast and reliable, and monitor for bypasses.
- Shared vendor credentials: unattributable access destroys accountability and incident response.
  Individual vaulted credentials, always.
- Treating IT remote-access tools as OT-ready: TeamViewer/AnyDesk-style tools without OT controls
  (no session approval, no recording, persistent access) are findings, not solutions.
- Ignoring safety implications: OT access changes can affect physical processes — all changes need
  operations approval and safety review, not just security sign-off.
- One-time cleanup: vendors and needs change constantly. Without quarterly reviews, conduits sprawl
  back into uncontrolled access.

## References
- IEC 62443 series (zones and conduits, SR 1.x access control requirements)
- NIST SP 800-82 Rev. 3 (OT security guidance)
- CISA guidance on OT remote access and vendor risk
- NERC CIP standards (for electric-sector applicability)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
