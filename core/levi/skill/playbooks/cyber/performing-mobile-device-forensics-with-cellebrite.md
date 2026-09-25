---
skill_id: cyber_performing_mobile_device_forensics_with_cellebrite
name: Mobile Device Forensics with Cellebrite
description: Acquire and analyze mobile device data with Cellebrite tooling under proper legal authority and chain of custody.
risk: moderate
permissions: []
requires_confirmation: true
tags: [mobile, forensics, acquisition]
version: 1.0.0
---

## Purpose
- Recover call logs, messages, location history, and application data from mobile devices for investigations.
- Maintain a defensible chain of custody from seizure through extraction to reporting.
- Choose the least intrusive extraction method that still answers the investigative questions.
- Protect the organization legally by keeping every examination strictly within its authorized scope.

## When to use
- When a mobile device is seized or surrendered as part of an internal investigation or legal matter.
- When message or location evidence on a phone is needed to corroborate network or endpoint findings.
- When corporate policy or a court order authorizes examination of a company-owned device.
- When a lost or stolen corporate device must be examined after recovery for data exposure.

## Prerequisites
- Documented legal authority: consent, company policy acknowledgment, warrant, or court order, reviewed by counsel.
- A Cellebrite workstation with current licenses, validated extraction methods, and write-blocking where applicable.
- Faraday isolation for the device from the moment of seizure to prevent remote wipe or new data writes.
- A defined scope of examination in writing, including any categories of data explicitly excluded.

## Procedure
1. Record seizure details: who, when, where, device state, and place the device in a Faraday bag immediately.
2. Photograph the device and record identifiers: make, model, OS version, IMEI or serial, and lock state.
3. Confirm the legal basis for examination in writing before connecting the device to any forensic tool.
4. Select the least intrusive extraction that answers the questions, preferring logical or file-system extraction over physical when sufficient.
5. Perform the extraction with Cellebrite, verifying hash values of the resulting image or package.
6. Analyze artifacts relevant to scope: communications, location, browser history, and installed applications, filtering out privileged or out-of-scope data.
7. Recover deleted artifacts where supported, documenting the recovery method and its reliability limits.
8. Correlate mobile findings with other evidence sources such as carrier records, MDM logs, or endpoint telemetry.
9. Write the examination report with methods, tools and versions, findings, and limitations; retain the extraction for the retention period.
10. Brief counsel on any privileged, personal, or out-of-scope material encountered before it appears in any report.

## Expected outputs
- A forensically sound extraction with verified hashes and a complete chain-of-custody log.
- An examination report limited to the authorized scope, suitable for HR, legal, or law-enforcement handoff.
- Correlated findings that place mobile evidence alongside network and endpoint timelines.
- A retention and disposition plan for the extraction media.

## Pitfalls
- Exceeding the authorized scope, which can taint evidence and create legal exposure for the organization.
- Allowing the device to remain on a network after seizure, inviting remote wipe or silent data changes.
- Using outdated tool versions that misparse new OS artifacts and produce misleading timelines.
- Including personal or privileged data in reports; filter and segregate before writing.

## References
- NIST SP 800-101 Guidelines on Mobile Device Forensics
- Cellebrite official product documentation and validation materials
- SWGDE best practices for mobile device forensics
- NIST SP 800-88 Guidelines for Media Sanitization for disposition planning
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
