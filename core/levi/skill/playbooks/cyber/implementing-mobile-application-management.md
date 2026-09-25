---
skill_id: cyber_implementing_mobile_application_management
name: Implementing Mobile Application Management
description: Control corporate data on mobile devices with MAM — app-level policies, conditional access, and selective wipe without full device management.
risk: info
permissions: []
requires_confirmation: false
tags: [mobile, mdm, data-protection]
version: 1.0.0
---
## Purpose

Protect corporate data on mobile devices — including personally owned BYOD devices where full device management is unacceptable — using Mobile Application Management: app-level encryption, conditional access, data-loss-prevention between managed and personal apps, and selective wipe of corporate data on loss, departure, or compromise. MAM secures the data container, not the whole device.

## When to use

- Enabling BYOD without taking management control of employees' personal phones.
- Protecting email, documents, and line-of-business apps on mobile (the device most likely to be lost).
- Meeting data-protection expectations for mobile access to corporate resources (finance, healthcare, legal).
- Supporting frontline or field workers whose primary computing device is a phone or tablet.
- Responding to incidents involving lost/stolen devices or departed employees retaining corporate data.

## Prerequisites

- Chosen MAM platform (Microsoft Intune app protection policies, VMware Workspace ONE, Jamf for Apple fleets) integrated with the identity provider.
- Inventory of corporate mobile apps to manage: email (Outlook/Gmail), file storage, collaboration, and LOB apps — and whether each supports app protection policies natively or needs wrapping/SDK.
- Conditional Access policies in the IdP able to require managed-app/compliant-device signals.
- Legal/HR review of BYOD terms: what the company can wipe, monitor, and require on a personal device — documented in an acceptable-use agreement users actually sign.
- Help-desk readiness for enrollment, wipe requests, and the inevitable "why can't I copy this" tickets.

## Procedure

1. **Define the app protection baseline.** Set the standard policy: require PIN/biometric for managed apps, encrypt app data at rest, block jailbroken/rooted devices, set offline grace periods and recheck intervals. Apply it to the core managed apps (mail, files, browser) first.
2. **Configure data-transfer controls.** Restrict cut/copy/paste, screen capture, and "open in" between managed and unmanaged apps: corporate data stays inside managed apps. Tune per data classification — blocking all sharing breaks legitimate workflows; allowing all of it voids the control. Start restrictive on high-risk apps (email with customer data) and relax deliberately.
3. **Require managed apps via Conditional Access.** Build IdP policies: access to corporate email, SharePoint, and SaaS from mobile requires either a managed app with app protection policy or a compliant device. Block legacy auth and unmanaged mail clients outright — they bypass every app-level control.
4. **Handle enrollment models.** For corporate-owned devices, combine MDM enrollment with MAM for full control. For BYOD, use MAM-without-enrollment (app protection only) to respect privacy boundaries; document exactly what the company can and cannot see on a personal device, and communicate it plainly to users.
5. **Implement selective wipe.** Configure wipe triggers: device reported lost/stolen, employment termination, prolonged non-compliance, or compromise indicators. Selective wipe removes corporate app data and accounts while leaving personal photos and apps untouched — test it on spare devices so help desk can describe exactly what users will experience.
6. **Protect app-to-app and cloud flows.** Extend policies to managed browsers and file apps so downloads from corporate SaaS land in encrypted, managed storage. Review which apps can access corporate data via the app inventory; unmanaged shadow apps with OAuth grants to corporate SaaS bypass MAM entirely — govern OAuth app consent in parallel.
7. **Monitor compliance and threats.** Track policy compliance (non-compliant devices/apps blocked at Conditional Access), jailbreak/root detections, and wipe events in the SOC. Alert on anomalies: mass wipe requests, repeated compliance failures from one user, managed apps on unexpected platforms.
8. **Review and update with OS releases.** Major iOS/Android releases routinely change the APIs MAM depends on. Test app protection policies against beta OS releases with a pilot group before fleet-wide upgrades break enrollment or policy application.

## Expected outputs

- App protection policies deployed to managed apps with documented baseline settings.
- Conditional Access policies requiring managed app or compliant device for mobile access.
- BYOD acceptable-use agreement signed and communicated.
- Tested selective-wipe procedure with help-desk runbook.
- Compliance monitoring and SOC alerting on mobile policy violations.

## Pitfalls

- **MAM without Conditional Access enforcement.** App protection policies that nothing requires are suggestions. Access must be gated on the managed-app signal or users simply use unmanaged clients.
- **Ignoring OAuth shadow apps.** Users grant personal apps access to corporate mail/files via OAuth; MAM never sees that data flow. Restrict OAuth app consent and audit grants.
- **Over-blocking usability.** Blocking screenshots, sharing, and copy entirely drives users to photograph screens with personal devices — worse security and zero visibility. Calibrate restrictions to data risk.
- **Wipe ambiguity on BYOD.** If users fear a full device wipe, they will not enroll. Be explicit and truthful: selective wipe touches corporate data only, and prove it in testing.
- **Unmanaged app wrapping gaps.** Not every LOB app supports app protection natively; wrapping or SDK integration takes development effort. Inventory app support before promising coverage.

## References

- Microsoft Intune app protection policy documentation — https://learn.microsoft.com/en-us/intune/apps/app-protection-policy
- NIST SP 800-124 Rev. 2, "Guidelines for Managing the Security of Mobile Devices" — https://csrc.nist.gov/publications/detail/sp/800-124/rev-2/final
- OWASP Mobile Application Security Verification Standard (MASVS) — https://mas.owasp.org/MASVS/
- MITRE ATT&CK Mobile matrices — https://attack.mitre.org/techniques/mobile/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
