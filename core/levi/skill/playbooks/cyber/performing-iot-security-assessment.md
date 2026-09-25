---
skill_id: cyber_performing_iot_security_assessment
name: IoT Security Assessment
description: Assess IoT devices and fleets for common security weaknesses.
risk: low
permissions: []
requires_confirmation: false
tags: [iot, assessment, hardening]
version: 1.0.0
---
# IoT Security Assessment

## Purpose

IoT devices ship with default credentials, unencrypted protocols, and
rarely patched firmware — then sit on networks for a decade. This
playbook assesses IoT devices and fleets you are authorized to test,
from device hardening to cloud-backend review, and produces a
remediation plan.

## When to use

- Vetting IoT devices before enterprise deployment.
- Assessing smart-building, camera, or sensor fleets already in
  production.
- Incident response involving a compromised IoT device.
- Procurement security requirements for IoT purchases.

## Prerequisites

- Written authorization covering the devices, the network segments,
  and any cloud backends in scope.
- A lab network segment isolated from production for device testing.
- Tooling: firmware extraction (binwalk), network capture, and the
  vendor's management interfaces.

## Procedure

1. Inventory the fleet: device models, firmware versions, network
   placement, and which devices are reachable from the Internet or
   from untrusted segments.
2. Check authentication: default and hardcoded credentials on web,
   SSH, Telnet, and API interfaces; test for weak password policies
   and unprotected recovery mechanisms.
3. Inspect network behavior: capture boot and steady-state traffic;
   flag plaintext protocols, hardcoded DNS/NTP, unexpected outbound
   connections, and open listening ports.
4. Extract and review firmware: look for hardcoded keys and
   credentials, insecure update mechanisms (unsigned updates, HTTP
   downloads), and debug interfaces left enabled.
5. Test the update path: verify updates are signed, delivered over
   TLS, and applied atomically with rollback — an unsigned update
   channel is a fleet-wide compromise vector.
6. Review the cloud backend and mobile app: API authentication,
   device-identity provisioning, and whether one compromised device
   can impersonate others.
7. Assess physical and lifecycle gaps: debug headers (UART/JTAG),
   unencrypted storage of credentials, and the vendor's patch
   commitment and EOL policy.
8. Prioritize remediation by exposure: Internet-facing and
   safety-relevant devices first; produce network-segmentation and
   replacement recommendations for unfixable devices.

## Expected outputs

- A device inventory with firmware versions and exposure mapping.
- Findings with severity, affected models, and concrete fixes.
- Segmentation and lifecycle recommendations for unpatchable devices.
- Procurement requirements derived from the gaps found.

## Pitfalls

- Testing in production: device reboots and scans can disrupt
   building systems or safety functions — use the lab.
- Stopping at the device: the cloud backend is usually the softer
   target.
- Assuming a firmware update fixes everything: verify the update
   mechanism itself is trustworthy first.
- Ignoring EOL: a device the vendor abandoned needs a replacement
   plan, not a finding that lingers for years.

## References

- NIST SP 800-213, IoT Device Cybersecurity Guidance
- OWASP Internet of Things Top 10
- ETSI EN 303 645, Cyber Security for Consumer IoT
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
