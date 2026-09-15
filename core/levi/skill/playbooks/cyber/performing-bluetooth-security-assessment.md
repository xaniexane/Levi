---
skill_id: cyber_performing_bluetooth_security_assessment
name: Bluetooth Security Assessment
description: Assess Bluetooth and BLE deployments for pairing, encryption, and exposure weaknesses, and harden them.
risk: low
permissions: []
requires_confirmation: false
tags: [wireless, assessment, hardening]
version: 1.0.0
---

## Purpose

Bluetooth Classic and Bluetooth Low Energy ship in headsets, medical devices, industrial sensors, door locks, and employee laptops — often with default settings, legacy pairing, and always-on discoverability. This playbook provides a defensive assessment methodology: discover Bluetooth assets in your environment, evaluate their pairing and encryption posture, test for common misconfigurations on devices you own, and apply hardening. All active testing is limited to your own devices or explicitly authorized scope.

## When to use

- Rolling out or auditing BLE-enabled IoT, medical, or industrial devices.
- A policy question about whether Bluetooth should be enabled on corporate endpoints.
- Investigating a suspected unauthorized Bluetooth connection or data exfiltration path.
- Procurement security review of a Bluetooth peripheral before fleet deployment.
- After a Bluetooth-stack CVE (e.g., BlueBorne-class flaws) to determine fleet exposure.

## Prerequisites

- Authorization covering the devices and the RF environment you will survey.
- Assessment tooling on a Linux host: BlueZ stack, `hcitool`/`bluetoothctl`, `btmon`, and optionally Ubertooth One for passive BLE sniffing.
- An inventory (or the ability to build one) of Bluetooth-capable assets in scope.
- Vendor documentation for target devices: supported pairing modes, firmware update mechanism, and configurability.

## Procedure

1. **Discover the Bluetooth footprint.** Perform passive and active scans of the target area: `bluetoothctl scan on` for Classic discovery and BLE advertisement capture. Record MAC addresses (noting randomization on modern devices), device names, advertised services (GATT profiles), and signal strength as a rough proximity indicator.
2. **Classify devices by risk.** Flag devices that are permanently discoverable, advertise sensitive services (HID, serial port, health data), or belong to high-value categories (medical, access control, industrial). Prioritize assessment effort accordingly.
3. **Evaluate pairing and authentication.** For each owned device, determine the pairing method in use: Numeric Comparison, Passkey Entry, Out-of-Band, or the legacy Just Works. Just Works provides no man-in-the-middle protection — document every device relying on it and check whether Secure Connections (ECDH) is enforced or if legacy pairing is still accepted.
4. **Check encryption and key handling.** Verify that connections require encryption (Security Mode 4, encrypted), inspect negotiated key sizes (reject 7-octet minimums where policy allows enforcing 16), and confirm that long-term keys are not shared or hard-coded across a fleet. Review whether "bonding" data persists securely.
5. **Test authorization on GATT services.** Against your own devices, attempt to read/write characteristics without pairing and with unauthenticated pairing. Overly permissive characteristics (firmware update over unauthenticated GATT, debug interfaces) are findings; record the exact handle, UUID, and required (or missing) authentication.
6. **Review firmware and stack patching.** Identify the Bluetooth chipset/firmware version on fleet devices and cross-reference published CVEs. Confirm the vendor provides updates and that your MDM or maintenance process actually deploys them; unpatchable Bluetooth stacks are a procurement finding.
7. **Assess endpoint policy.** On corporate laptops and phones, check whether Bluetooth is centrally managed: discoverability defaults, allowed profiles, and whether pairing with untrusted devices is restricted. Unmanaged Bluetooth on endpoints handling sensitive data is a data-exfiltration and attack-surface concern.
8. **Apply hardening.** Disable Bluetooth where there is no business need (BIOS/OS policy or MDM). Where needed: enforce Secure Connections pairing, require encryption and authentication for GATT access, shorten or disable discoverable windows, remove unnecessary advertised services, and segment BLE gateways onto isolated network zones.
9. **Establish ongoing monitoring.** For high-risk sites, consider periodic RF surveys or fixed BLE sensors that alert on new or rogue advertisers (e.g., unexpected HID devices suggesting a BadUSB-style implant). Feed findings into asset management.

## Expected outputs

- A Bluetooth asset inventory: device identities, classes, advertised services, and locations.
- Per-device pairing, encryption, and GATT authorization findings with severity ratings.
- Firmware/CVE exposure analysis for fleet chipsets.
- Hardening recommendations: policy changes, configuration deltas, and devices slated for replacement.
- An assessment report with scope, methodology, findings, and remediation priorities.

## Pitfalls

- Active scanning in shared or public spaces can capture bystander devices — limit collection to what scope authorizes and avoid retaining personal device data.
- MAC randomization makes BLE tracking unreliable; do not build asset identity solely on observed addresses.
- Assuming "paired once" means "secure forever" — check re-pairing behavior and whether keys can be downgraded.
- Testing pairing or GATT writes against devices you do not own, which can disrupt medical or industrial equipment.
- Treating Bluetooth as low-risk by default; in access-control and healthcare contexts it is often the primary attack surface.

## References

- Bluetooth SIG Security guidance and Core Specification (Secure Connections, Security Modes)
- NIST SP 800-121, "Guide to Bluetooth Security"
- MITRE ATT&CK T1200-adjacent techniques for hardware additions (context)
- BlueZ and Ubertooth project documentation for tooling usage
- Vendor security advisories for fleet chipsets under assessment
