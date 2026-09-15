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

## Expected outputs
- Published removable-media policy with exception process.
- Endpoint device-control configuration in enforce mode with audit trail.
- Metrics: blocked attempts, active exceptions, violation trends.

## Pitfalls
- Going straight to block mode without a baseline: expect helpdesk meltdown.
- Allowlisting by device class instead of specific hardware IDs, which attackers can spoof.
- Forgetting non-USB vectors: SD cards, phones in MTP mode, and optical media need the same treatment.

## References
- NIST SP 800-53 Rev. 5, control MP (Media Protection) family.
- CISA guidance on removable media risks (cisa.gov).
