---
skill_id: cyber_implementing_usb_device_control_policy
name: Implementing USB Device Control Policy
description: Define and enforce policy and technical controls for removable media on endpoints.
risk: low
permissions: []
requires_confirmation: false
tags: [endpoint-security, dlp, device-control]
version: 1.0.0
---
## Purpose
This playbook establishes a USB and removable-media control program: a clear policy, technical enforcement via endpoint controls, exception handling, and monitoring for violations — reducing malware ingress and data exfiltration via removable devices.

## When to use
- Unrestricted USB usage on endpoints handling sensitive data.
- After a malware incident traced to removable media or a data-loss event via USB.
- Compliance frameworks requiring media controls (PCI DSS, CMMC, ISO 27001).

## Prerequisites
- Endpoint management platform with device-control capability (EDR, Intune, or similar).
- Inventory of legitimate business needs for removable media by role.
- Data classification policy so you know which data must never leave on removable media.

## Procedure
1. **Write the policy.** Define allowed device classes (e.g., encrypted storage only), prohibited uses, encryption requirements, and the exception process with approver roles.
2. **Baseline current usage.** Audit which endpoints currently see removable media and which users rely on it, so enforcement does not break legitimate workflows on day one.
3. **Enforce by tiers.** Start in audit/monitor mode, then move to block-by-default with allowlists: approved encrypted devices by hardware ID for approved roles.
4. **Require encryption.** Any permitted removable storage must use enforced encryption (BitLocker To Go, hardware-encrypted drives); block unencrypted writes.
5. **Build the exception workflow.** Time-bound approvals with business justification, recorded in the ticketing system and reviewed quarterly.
6. **Monitor and alert.** Alert on blocked-device attempts, mass file copies to removable media, and use of unapproved devices; feed events to the SIEM.
7. **Review and report.** Quarterly, review exceptions, violation trends, and policy effectiveness with data owners.

8. **Cover contractors and visitors.** Apply the same device-control policy to non-employee endpoints connecting to corporate systems; unmanaged devices are the usual exception abusers.
9. **Test with red-team scenarios.** Periodically attempt data exfiltration to unapproved media in a controlled test to verify the controls actually stop it.

## Expected outputs
- Published removable-media policy with exception process.
- Endpoint device-control configuration in enforce mode with audit trail.
- Metrics: blocked attempts, active exceptions, violation trends.
- Example: a finance workstation blocks an unencrypted USB drive, logs the attempt to the SIEM, and the user receives guidance on requesting an approved encrypted device through the exception workflow.

## Pitfalls
- Going straight to block mode without a baseline: expect helpdesk meltdown.
- Allowlisting by device class instead of specific hardware IDs, which attackers can spoof.
- Forgetting non-USB vectors: SD cards, phones in MTP mode, and optical media need the same treatment.

- Allowing "temporary" exceptions that never expire; every exception needs an owner, a review date, and automatic escalation on expiry.
- Blocking USB while ignoring Bluetooth file transfer and Wi-Fi Direct, which move the same data through a different radio.

## References
- NIST SP 800-53 Rev. 5, control MP (Media Protection) family.
- CISA guidance on removable media risks (cisa.gov).
- NIST SP 800-124 Rev. 2, Guidelines for Managing the Security of Mobile Devices.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
