---
skill_id: cyber_b3_service_persistence_vpn_gateway_branch_office_foundational
name: Malicious Service Persistence Defense for VPN Gateways in Branch Offices (Foundational Maturity)
description: "Malicious Service Persistence defense playbook for VPN Gateways in Branch Offices at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, network, vpn, remote-access, branch, maturity-foundational]
version: 1.0.0
---
# Malicious Service Persistence Defense for VPN Gateways in Branch Offices (Foundational Maturity)

## Purpose

Attackers install or hijack Windows services for SYSTEM-level, reboot-surviving execution. Services are trusted by admins, so malicious ones hide with plausible names — verify the binary, not the display name. Applies to VPN Gateways in Branch Offices at Foundational maturity.

## When to use

- 7045 (service installed) with ImagePath in user-writable or temp directories, unsigned binaries, or names mimicking legit services.
- Existing service ImagePath changed (7045 with same name, new binary) or service binary replaced on disk.
- Services running as SYSTEM that were recently created and have no vendor documentation or change record.
- Lens: Best telemetry: authentication logs + session logs (user, IP, bytes, duration) + gateway patch state. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in VPN auth logs (success/failure per user with source IPs), session tables with data volumes and Gateway admin audit log and firmware/patch version; client version inventory; run `# conceptually (vendor CLIs differ):` then `show vpn-sessiondb detail anyconnect | grep -E 'Username|Assigned IP|Login Time'`.
3. **Analyze.** Hash and detonate the service binary; check its signature status and first-seen date in threat intel. Then: Review the service account: LocalSystem services have maximum impact — scope accordingly.
4. **Contain and harden.** Alert on all 7045 events; require change tickets for new services and run services as least-privilege virtual accounts. Asset layer: MFA on every VPN profile, device posture checks before granting access, gateway firmware patched urgently. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the service without deleting it — it restarts on reboot.
- Missing service DLL hijacking (Services with ServiceDll in writable paths) while hunting only EXE-based services.

## References

- MITRE ATT&CK: T1543.003 (Persistence: Windows Service)
- Vendor logging and hardening baselines for VPN Gateways; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
