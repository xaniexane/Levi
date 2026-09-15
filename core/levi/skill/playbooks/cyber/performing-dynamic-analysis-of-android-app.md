---
skill_id: cyber_performing_dynamic_analysis_of_android_app
name: Dynamic Analysis of Android Applications
description: Execute Android apps in an instrumented sandbox and capture behavioral indicators.
risk: low
permissions: []
requires_confirmation: false
tags: [malware, mobile, sandbox]
version: 1.0.0
---
# Dynamic Analysis of Android Applications

## Purpose

Static inspection misses what an app only does at runtime: C2 callbacks,
dynamic code loading, SMS exfiltration, overlay attacks. This playbook
standardizes dynamic analysis of Android APKs in an instrumented emulator or
sandbox to extract behavioral indicators defenders can act on.

## When to use

- Triaging a suspicious APK from a device, phishing lure, or app-store
  takedown request.
- Confirming behaviors hinted at by static analysis (reflection, dynamic
  class loading, suspicious receivers).
- Generating IOCs (domains, IPs, package names, certificates) for blocking.
- Validating MDM policy coverage against the techniques a sample uses.

## Prerequisites

- The APK detonated only inside an isolated lab network — never on a device
  holding personal or corporate data.
- An instrumented environment: an emulator with root and Frida, or a mobile
  sandbox (MobSF dynamic analyzer, DroidBox-style tooling).
- A capture workstation with mitmproxy or an intercepting proxy and a
  controlled DNS sink, plus host firewall rules blocking outbound Internet.

## Procedure

1. Hash the APK (SHA-256) and record metadata: package name, version code,
   SDK targets, signing certificate, and embedded URLs from a quick static
   pass (APKTool or jadx) so you know what to watch for.
2. Install the APK on the instrumented emulator and start a full capture:
   network traffic, logcat, file-system changes, and process activity.
3. Exercise the app thoroughly: walk every screen, grant and deny
   permissions separately, toggle connectivity, and inject typical inputs
   (SMS with OTP text, contacts with varied data) to trigger conditional
   behavior.
4. Monitor high-value APIs via Frida hooks: SMS send/read, accessibility
   service abuse, overlay window creation, `DexClassLoader` usage, device
   admin requests, and clipboard access.
5. Record persistence and privilege actions: boot receivers, scheduled jobs,
   new device-admin policies, VPN profile creation, and any attempt to
   disable security settings.
6. Capture network behavior in detail: DNS queries, TLS handshakes (with
   the proxy CA installed), HTTP endpoints, WebSocket channels, and
   fallback transports; note any domain generation or fast-flux patterns.
7. Extract staged payloads: dump dex files written at runtime, downloaded
   APKs/DEX/JARs, and decrypted strings, hashing each for IOC lists.
8. Restore the emulator snapshot after the run so residual services or
   callbacks cannot contaminate the next analysis.

## Expected outputs

- A behavior report: permissions exercised, API abuse observed, persistence
  mechanisms, and data accessed versus declared purpose.
- A network IOC set: domains, IPs, ports, URL paths, JA3 fingerprints.
- Dropped-payload hashes and samples for static follow-up.
- A disposition recommendation: malicious, unwanted, or benign.

## Pitfalls

- Sandbox evasion: samples may stay dormant when they detect emulators,
  rooted devices, or debuggers — compare results against multiple
  instrumentation profiles before declaring a sample benign.
- Letting captured traffic reach the real Internet: always sink or block
  egress at the lab boundary.
- Triggering only the happy path: many samples delay execution or wait for
  specific triggers (SIM change, charging state, SMS keywords).
- Contaminating evidence: work from copies and snapshots; never analyze on
  a device enrolled in production MDM.

## References

- Android Developers: Security best practices documentation
- OWASP Mobile Application Security Verification Standard (MASVS)
- NIST SP 800-124, Guidelines for Managing the Security of Mobile Devices
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
