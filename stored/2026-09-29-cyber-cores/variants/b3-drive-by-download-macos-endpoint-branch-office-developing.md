---
skill_id: cyber_b3_drive_by_download_macos_endpoint_branch_office_developing
name: Drive-By Download Defense for macOS Endpoints in Branch Offices (Developing Maturity)
description: "Drive-By Download defense playbook for macOS Endpoints in Branch Offices at Developing maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, macos, endpoint, branch, maturity-developing]
version: 1.0.0
---
# Drive-By Download Defense for macOS Endpoints in Branch Offices (Developing Maturity)

## Purpose

Visiting a compromised or malicious page silently downloads malware via browser or plugin exploits. Patching and browser isolation remove the opportunity; proxy logs reveal the exposure. Applies to macOS Endpoints in Branch Offices at Developing maturity.

## When to use

- Browser spawning unexpected child processes or writing executables to temp/downloads without user download action.
- Proxy logs showing visits to compromised sites followed by executable downloads, often via redirect chains.
- Exploit-kit patterns: rapid plugin version probing, obfuscated JavaScript, then payload fetch.
- Lens: Best telemetry: unified log + EDR agent + Santa/Munki logs where deployed. SD-WAN/branch firewall logs forwarded centrally; local DHCP/DNS logs for device attribution.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to NAC or port-level logs identifying which device was on which port during the incident.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Unified log (log show) for process execution and auth events; login items and LaunchAgents/LaunchDaemons plists and Quarantine attributes (xattr com.apple.quarantine) on downloads; Gatekeeper assessment history; run `log show --predicate 'eventMessage contains "sshd"' --last 2h | tail -20` then `ls -la ~/Library/LaunchAgents/ /Library/LaunchDaemons/ /Library/LaunchAgents/ 2>/dev/null`.
3. **Analyze.** Reconstruct the redirect chain from proxy logs to identify the compromised page or malvertising source. Then: Determine whether the payload executed: browser process tree and EDR execution events after the download timestamp.
4. **Contain and harden.** Automatic browser and OS patching; remove or sandbox legacy plugins (Java, Flash-era); consider browser isolation for high-risk users. Asset layer: Gatekeeper + XProtect current, FileVault on, firewall on, and MDM-enforced configuration profiles. Environment layer: Standardized branch firewall policy deployed as code; no local admin exceptions.
5. **Document and improve.** Assign RACI for each procedure step (who detects, who contains, who communicates) and rehearse it quarterly. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming the user 'must have clicked something' — drive-bys need no click, so user interviews mislead.
- Cleaning the endpoint without blocking the compromised site that will re-infect the next visitor.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise)
- Vendor logging and hardening baselines for macOS Endpoints; Standardized branch firewall policy deployed as code; no local admin exceptions.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
