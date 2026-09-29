---
skill_id: cyber_b3_drive_by_download_network_switch_aws_cloud_foundational
name: Drive-By Download Defense for Network Switches in AWS Cloud (Foundational Maturity)
description: "Drive-By Download defense playbook for Network Switches in AWS Cloud at Foundational maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, switching, cloud, aws, maturity-foundational]
version: 1.0.0
---
# Drive-By Download Defense for Network Switches in AWS Cloud (Foundational Maturity)

## Purpose

Visiting a compromised or malicious page silently downloads malware via browser or plugin exploits. Patching and browser isolation remove the opportunity; proxy logs reveal the exposure. Applies to Network Switches in AWS Cloud at Foundational maturity.

## When to use

- Browser spawning unexpected child processes or writing executables to temp/downloads without user download action.
- Proxy logs showing visits to compromised sites followed by executable downloads, often via redirect chains.
- Exploit-kit patterns: rapid plugin version probing, obfuscated JavaScript, then payload fetch.
- Lens: Best telemetry: syslog (port up/down, STP changes, config changes) + SNMP/NetFlow + NAC logs. Organization CloudTrail in all regions, GuardDuty, and VPC flow logs shipped to the security account.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to CloudWatch and workload logs centralized; S3 access logging on sensitive buckets.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Syslog: link-state changes, MAC flaps, STP topology changes, login attempts and MAC address tables and ARP tables for device-to-port mapping during incidents; run `show mac address-table | include <suspect-mac>` then `show logging | include %SEC-6-IPACCESSLOGP|%PORT_SECURITY`.
3. **Analyze.** Reconstruct the redirect chain from proxy logs to identify the compromised page or malvertising source. Then: Determine whether the payload executed: browser process tree and EDR execution events after the download timestamp.
4. **Contain and harden.** Automatic browser and OS patching; remove or sandbox legacy plugins (Java, Flash-era); consider browser isolation for high-risk users. Asset layer: Port security / 802.1X on access ports, BPDU guard, DHCP snooping + dynamic ARP inspection. Environment layer: SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).
5. **Document and improve.** Define one escalation trigger in advance (e.g., confirmed credential theft, more than 3 hosts) that moves the case from analyst to incident commander. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Assuming the user 'must have clicked something' — drive-bys need no click, so user interviews mislead.
- Cleaning the endpoint without blocking the compromised site that will re-infect the next visitor.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise)
- Vendor logging and hardening baselines for Network Switches; SCPs as guardrails (deny leaving org, deny disabling logging, region restrictions).

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
