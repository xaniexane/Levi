---
skill_id: cyber_conducting_wireless_network_penetration_test
name: Conducting Authorized Wireless Network Penetration Tests
description: Practitioner guide to planning and executing authorized wireless security assessments of corporate Wi-Fi and related infrastructure.
risk: info
permissions: []
requires_confirmation: false
tags: [wireless, assessment, pentest]
version: 1.0.0
---
## Purpose
Wireless networks extend the corporate perimeter into parking lots and neighboring buildings. This playbook structures an authorized wireless assessment: scoping, rogue-AP detection, encryption and authentication review, evil-twin resilience, and segmentation validation -- proving what an attacker in range could actually reach.

## When to use
- Assessing corporate Wi-Fi security posture.
- Validating wireless segmentation between corporate, guest, and IoT networks.
- Meeting compliance requirements for wireless testing.
- After wireless infrastructure changes or incidents.

## Prerequisites
- Written authorization defining facilities, SSIDs, and testing windows.
- Rules of engagement: permitted techniques, client-interaction boundaries.
- Coordination with facilities and SOC for on-site testing.
- Understanding of the wireless architecture: controllers, authentication servers, segmentation.

## Procedure
1. Confirm scope and authorization. Document sites, SSIDs in scope, and whether client-side attacks are permitted; get signatures.
2. Survey the RF environment. Map legitimate APs, signal strength, and coverage; identify rogue or misconfigured APs broadcasting corporate SSIDs.
3. Assess encryption and authentication. Verify WPA2/WPA3 enterprise configuration, certificate validation, and that weak protocols are disabled.
4. Test network segmentation. Confirm wireless clients cannot reach unauthorized VLANs or management interfaces; validate guest isolation.
5. Evaluate evil-twin resilience. Within scope, assess whether clients can be lured to rogue APs and what controls (certificates, HSTS) limit impact.
6. Review IoT and special networks. Assess the security of IoT, printer, and building-automation wireless segments that are often neglected.
7. Check monitoring. Verify the wireless IDS/IPS detects rogue APs and deauthentication attacks; test alerting.
8. Report and retest. Document findings with remediation guidance; verify fixes, especially segmentation and authentication issues.

## Expected outputs
- Wireless assessment report with rogue-AP findings and segmentation results.
- Remediation guidance for encryption, authentication, and monitoring gaps.
- Retest confirmation.

## Pitfalls
- Testing from neighboring properties or public areas without clear authorization boundaries.
- Disrupting legitimate wireless users with aggressive deauthentication testing.
- Ignoring IoT wireless networks that bridge into corporate segments.
- Client-side attacks without explicit permission cross ethical and legal lines.

## References
- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment
- NIST SP 800-153, Guidelines for Securing Wireless Local Area Networks
- PCI DSS wireless requirements (where applicable)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
