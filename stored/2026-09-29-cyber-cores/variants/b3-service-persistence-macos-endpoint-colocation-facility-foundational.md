---
skill_id: cyber_b3_service_persistence_macos_endpoint_colocation_facility_foundational
name: Malicious Service Persistence Defense for macOS Endpoints in Colocation Facilities (Foundational Maturity)
description: "Malicious Service Persistence defense playbook for macOS Endpoints in Colocation Facilities at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [windows, persistence, macos, endpoint, on-prem, colocation, maturity-foundational]
version: 1.0.0
---
# Malicious Service Persistence Defense for macOS Endpoints in Colocation Facilities (Foundational Maturity)

## Purpose

Attackers install or hijack Windows services for SYSTEM-level, reboot-surviving execution. Services are trusted by admins, so malicious ones hide with plausible names — verify the binary, not the display name. Applies to macOS Endpoints in Colocation Facilities at Foundational maturity.

## When to use

- 7045 (service installed) with ImagePath in user-writable or temp directories, unsigned binaries, or names mimicking legit services.
- Existing service ImagePath changed (7045 with same name, new binary) or service binary replaced on disk.
- Services running as SYSTEM that were recently created and have no vendor documentation or change record.
- Lens: Best telemetry: unified log + EDR agent + Santa/Munki logs where deployed. Customer-owned network taps and logging (the colo provider's logs are out of scope — verify contractually).

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Badge/physical access logs from the facility correlated with remote-hand ticket times.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Unified log (log show) for process execution and auth events; login items and LaunchAgents/LaunchDaemons plists and Quarantine attributes (xattr com.apple.quarantine) on downloads; Gatekeeper assessment history; run `log show --predicate 'eventMessage contains "sshd"' --last 2h | tail -20` then `ls -la ~/Library/LaunchAgents/ /Library/LaunchDaemons/ /Library/LaunchAgents/ 2>/dev/null`.
3. **Analyze.** Hash and detonate the service binary; check its signature status and first-seen date in threat intel. Then: Review the service account: LocalSystem services have maximum impact — scope accordingly.
4. **Contain and harden.** Alert on all 7045 events; require change tickets for new services and run services as least-privilege virtual accounts. Asset layer: Gatekeeper + XProtect current, FileVault on, firewall on, and MDM-enforced configuration profiles. Environment layer: Locked cabinets, private cages, and escort policies for remote hands.
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Stopping the service without deleting it — it restarts on reboot.
- Missing service DLL hijacking (Services with ServiceDll in writable paths) while hunting only EXE-based services.

## References

- MITRE ATT&CK: T1543.003 (Persistence: Windows Service)
- Vendor logging and hardening baselines for macOS Endpoints; Locked cabinets, private cages, and escort policies for remote hands.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
