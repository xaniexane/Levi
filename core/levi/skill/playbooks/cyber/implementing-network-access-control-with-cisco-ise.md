---
skill_id: cyber_implementing_network_access_control_with_cisco_ise
name: Implementing Network Access Control with Cisco ISE
description: Deploy Cisco Identity Services Engine for 802.1X NAC — policy sets, profiling, posture, TrustSec segmentation, and phased enforcement.
risk: low
permissions: []
requires_confirmation: false
tags: [network, access-control, cisco, 802.1x]
version: 1.0.0
---
## Purpose

Operationalize network access control on Cisco infrastructure with Identity Services Engine as the policy brain: RADIUS authentication, device profiling, posture assessment, guest access, and TrustSec software-defined segmentation — with the phased rollout discipline that keeps NAC deployments from becoming outage generators.

## When to use

- Standardizing NAC across a Cisco switching/wireless estate.
- Replacing legacy ACS or standalone RADIUS with policy-driven access control.
- Implementing TrustSec/SGT-based segmentation without re-VLANing the network.
- Meeting compliance requirements for admission control with centralized audit evidence.
- Unifying wired, wireless, and VPN authorization policy in one engine.

## Prerequisites

- Cisco ISE deployment sized for the endpoint count (PSN/MnT/pxGrid personas distributed for HA), on supported versions with current patches.
- Network devices configured as ISE network access devices (RADIUS clients) with correct shared secrets, CoA support, and 802.1X-capable firmware.
- AD/IdP integration (join ISE to AD for machine/user lookup), PKI for EAP-TLS, and MDM/EDR integrations for posture/compliance signals.
- Device inventory and the political capital for phased enforcement — ISE projects fail on rushing, not on technology.
- pxGrid ecosystem plan if integrating Firepower, Stealthwatch, or third-party tools.

## Procedure

1. **Deploy and harden the ISE cluster.** Stand up Admin, Policy Service (PSN), and Monitoring (MnT) nodes per Cisco's distributed deployment guidance with HA pairs. Harden: change default credentials, restrict admin access, enable alarms, and back up configurations on schedule — ISE holds the keys to network admission.
2. **Integrate identity sources.** Join AD, configure certificate authentication (EAP-TLS) via your PKI, and connect MDM for device compliance and EDR via pxGrid for threat signals. Validate each integration independently before building policy on it.
3. **Build policy sets top-down.** Structure policy sets by access type (Wired, Wireless, VPN) with authentication policies (EAP-TLS for corporate, MAB for IoT, guest portal flows) feeding authorization policies. Write authorization as explicit conditions: `AD:ExternalGroups == Corporate-Users AND Posture:Status == Compliant → PermitAccess-Production`. Keep a default-deny or quarantine default.
4. **Enable profiling in monitor mode.** Turn on ISE profiling (DHCP, RADIUS, SNMP, DNS, NetFlow probes) with enforcement in monitor/low-impact mode. Let it run for weeks: the profiler discovers the true device population — every printer, camera, badge reader, and mystery box — and builds the endpoint identity groups your MAB policies will use.
5. **Implement posture assessment.** Deploy the AnyConnect/ISE posture agent (or agentless posture where appropriate) checking patch state, AV/EDR health, disk encryption, and required software. Route non-compliant endpoints to remediation with limited access; define grace periods and escalation before moving to deny.
6. **Phase enforcement.** Progress per switch/wired segment: Monitor → Low-Impact (auth but permit) → Closed mode. For wireless, migrate SSIDs one at a time. Staff each cutover with network and help-desk support, and keep the emergency "open mode" rollback procedure tested — you will need it at least once.
7. **Layer TrustSec for segmentation.** Assign Security Group Tags (SGTs) via ISE authorization results and enforce SGACLs on switches/firewalls: SGT-based policy follows users and devices across VLANs and buildings without re-addressing. Start with a few high-value segments (servers, IoT, guests) before attempting matrix-wide segmentation.
8. **Operationalize with pxGrid and monitoring.** Share session context via pxGrid to Firepower (adaptive quarantine on threat detection), Stealthwatch, and the SIEM. Build dashboards for authentication failures, profiler unknowns, posture compliance rates, and CoA actions — and alert on anomalies like MAB devices changing ports or mass re-authentication failures.

## Expected outputs

- HA ISE deployment with hardened configuration and backups.
- Policy sets for wired/wireless/VPN with documented authentication and authorization logic.
- Profiler-built endpoint identity groups and MAB exception inventory.
- Posture policies with remediation flows.
- TrustSec SGT design for priority segments; pxGrid integrations feeding SOC tooling.

## Pitfalls

- **Undersized PSNs.** Authentication latency and RADIUS timeouts under load cause mysterious intermittent connectivity. Size for peak (morning logon storms) with headroom, and monitor PSN load.
- **Profiler unknowns.** Devices the profiler cannot identify become policy orphans. Maintain a process for investigating unknowns — some are rogue, most are just new IoT purchases.
- **Certificate lifecycle gaps.** EAP-TLS at scale means thousands of machine certificates; expired certs equal mass authentication failures. Automate issuance/renewal via SCEP/EST and monitor expiries.
- **CoA misconfiguration.** Change-of-Authorization (bounce/port-shutdown on posture change) misconfigured can flap ports during business hours. Test CoA behavior per switch model in the lab.
- **Treating ISE as the segmentation strategy.** ISE admits devices to the network; TrustSec/SGTs and firewalls segment what they can reach. Admission without segmentation still leaves a flat interior.

## References

- Cisco ISE documentation — https://www.cisco.com/c/en/us/support/security/identity-services-engine/products-documentation-roadmaps-list.html
- Cisco TrustSec documentation — https://www.cisco.com/c/en/us/solutions/enterprise-networks/trustsec/index.html
- IEEE 802.1X standard — https://standards.ieee.org/
- MITRE ATT&CK T1078 (Valid Accounts — device identity abuse context) — https://attack.mitre.org/techniques/T1078/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
