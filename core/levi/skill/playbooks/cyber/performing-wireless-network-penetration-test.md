---
skill_id: cyber_performing_wireless_network_penetration_test
name: Authorized Wireless Assessment and Rogue AP Detection
description: Assess corporate wireless security with authorization and run continuous rogue access point detection.
risk: low
permissions: []
requires_confirmation: false
tags: [wireless, assessment, detection]
version: 1.0.0
---

## Purpose
This playbook covers the defensive side of wireless testing: an authorized assessment of your organization's own WLAN (encryption, authentication, rogue devices) combined with an ongoing rogue access point detection program. Active attacks against clients or third-party networks are out of scope; the objective is to find misconfigurations and unauthorized devices before adversaries exploit them.

## When to use
- Annual wireless security assessment or after WLAN architecture changes.
- Standing up a rogue AP detection capability for corporate offices.
- After reports of evil-twin SSIDs or credential-harvesting portals near facilities.
- Validating a WPA3 or 802.1X migration.

## Prerequisites
- Written authorization with in-scope SSIDs, BSSIDs, frequencies, and facilities.
- Survey hardware: monitor-mode adapters, directional antenna, GPS optional.
- Authorized AP inventory (BSSID, location, expected config) from the network team.
- Wireless IDS/IPS access or a dedicated sensor for ongoing monitoring.

## Procedure
1. Conduct a passive survey of each facility; record every observed SSID, BSSID, channel, signal strength, and encryption.
2. Compare observations against the authorized inventory; flag unknown BSSIDs broadcasting corporate SSIDs as suspected evil twins.
3. Physically locate suspected rogues by signal strength and direction; involve facilities to remove unauthorized devices.
4. Review authorized AP configuration: WPA3-SAE or 802.1X, protected management frames, client isolation on guest, and disabled WPS.
5. Test guest network segmentation: confirm guest clients cannot reach corporate VLANs or management interfaces.
6. Verify certificate validation on 802.1X to catch misconfigurations that enable credential interception.
7. Tune the wireless IDS for deauth floods, KARMA-style probing responses, and new BSSIDs on corporate SSIDs.
8. Report findings with locations, evidence captures, and remediation priorities.
9. Check for WPS enabled on corporate APs and disable it wherever found.
10. Verify that corporate SSIDs are not broadcast by neighboring offices' equipment in shared buildings.
11. Test that deauthentication protection (PMF) is enforced on WPA2-Enterprise and WPA3 networks.

## Expected outputs
- Wireless survey report with authorized vs rogue device inventory.
- Configuration findings for authorized APs with remediation guidance.
- Tuned rogue-detection rules and an ongoing monitoring procedure.
- WPS and PMF status per surveyed AP.
- Shared-building SSID conflict assessment.
- Prioritized remediation plan with facility-specific actions.

## Pitfalls
- Signal bleed from neighboring offices causes false rogue positives; verify by location, not just SSID.
- Personal hotspots are usually policy issues, not attacks; have a proportionate response plan.
- Active probing (KARMA-style) can disrupt clients; keep the assessment passive unless authorized otherwise.
- Encryption alone is not security; open guest networks need segmentation even when corporate WLAN is strong.
- Neighboring offices on the same corporate SSID complicate rogue determination; coordinate across sites.
- WPS PIN brute force remains viable where WPS is left enabled for legacy devices.
- Surveys are point-in-time; rogues planted after the sweep need continuous monitoring.

## References
- NIST SP 800-153, Guidelines for Securing Wireless Local Area Networks.
- CISA guidance on wireless network security.
- Wi-Fi Alliance security best practices.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
