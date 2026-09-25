---
skill_id: cyber_implementing_device_posture_assessment_in_zero_trust
name: Device Posture Assessment in Zero Trust
description: Implement continuous device posture assessment feeding zero-trust access decisions.
risk: low
permissions: []
requires_confirmation: false
tags: [zero-trust, endpoint]
version: 1.0.0
---
## Purpose
Zero trust promises "never trust, always verify" — but access decisions are only as good as the
device signals behind them. A compliant-device check based on week-old MDM data grants network
access to compromised laptops. This playbook implements continuous device posture assessment:
collecting fresh health signals (OS, patch, EDR, encryption, jailbreak/root) and feeding them to the
policy engine so access follows actual device trust, not enrollment alone.

## When to use
- Making zero-trust access decisions (Conditional Access, ZTNA) actually device-aware.
- After incidents where compromised or non-compliant devices had broad access.
- Supporting BYOD or hybrid work where device trust varies widely.
- Meeting device-compliance requirements (CIS, cyber-insurance, regulated endpoints).
- As the device pillar of the CISA ZTMM program.

## Prerequisites
- Device management: Intune, Jamf, or equivalent MDM/UEM covering the fleet (including mobile).
- EDR on endpoints reporting health status to a queryable API.
- A policy engine consuming posture: Entra Conditional Access, ZTNA proxy, or NAC.
- Defined compliance baselines per device class (corporate laptop, mobile, BYOD, server).
- SIEM ingestion for posture-change events and compliance drift.

## Procedure
1. **Define compliance baselines per device class.** Corporate laptops: supported OS version,
   patches within N days, EDR installed/healthy, disk encryption on, firewall on, no jailbreak/root.
   Mobile: OS current, screen lock, encryption, MDM enrolled, no sideloaded risky apps. BYOD:
   minimum subset with containerization. Document each baseline — it's the contract.
2. **Ensure signal freshness.** Configure MDM/EDR check-in intervals so posture data is hours fresh,
   not days. Stale signals are the silent failure: verify last-check-in timestamps are actually
   current across the fleet, and alert on devices that stop reporting (a device that goes dark may
   be compromised or tampered with).
3. **Build the posture evaluation pipeline.** Aggregate signals (MDM compliance, EDR health, patch
   status, cert presence) into a per-device verdict: compliant, non-compliant, or unknown. Unknown
   (new, unenrolled, stale) must fail closed for sensitive resources — fail-open on unknown is the
   classic bypass.
4. **Wire verdicts to access policy.** Feed posture into: Entra Conditional Access (require
   compliant/hybrid-joined device), ZTNA proxy device tiers, VPN/NAC decisions, and Wi-Fi
   certificate issuance. Test each integration: a deliberately non-compliant test device must be
   denied sensitive apps.
5. **Handle the non-compliant user experience.** When access is denied for posture, tell the user
   exactly why and how to fix it (self-remediation: "update OS," "enable encryption," link to
   instructions). Cryptic denials flood the helpdesk; actionable ones get devices fixed.
6. **Cover the edge cases explicitly.** New hires (grace period with limited access), loaners, lab
   devices, IoT/OT-adjacent endpoints, and executives' personal devices — each gets a documented
   posture path, not an ad-hoc exception. Exceptions expire and are reviewed.
7. **Monitor posture drift.** Dashboard: compliant %, non-compliant by reason, unknown/stale
   devices, and mean time to remediate non-compliance. Alert on: mass non-compliance events (bad
   patch, MDM outage), EDR tamper/disable signals, and jailbreak/root detections (immediate
   containment).
8. **Respond to compromised-device signals.** EDR quarantine, jailbreak detection, or tamper signals
   should trigger: access revocation (via the policy engine), SOC investigation, and re-imaging
   before re-enrollment. A compromised device re-enrolling without remediation re-poisons the well.
9. **Extend to servers and special fleets.** Servers: patch compliance, EDR health, and
   config-baseline signals feeding maintenance windows and (where applicable) workload admission.
   Special fleets (kiosks, lab) get their own baselines — one baseline for everything fits nothing.
10. **Review and tighten quarterly.** Analyze denial logs for false positives (legitimate devices
    blocked — fix baselines or integrations), raise the bar progressively (shorter patch windows,
    new signals like secure-boot attestation), and retire exceptions. Posture assessment matures by
    iteration.

## Expected outputs
- Documented compliance baselines per device class with fresh, monitored signals.
- Posture verdicts wired into Conditional Access, ZTNA, and network access decisions (fail-closed on
  unknown).
- Self-remediation UX for denied users; documented edge-case paths.
- Drift dashboards and alerting on tamper, jailbreak, and mass non-compliance.
- Compromised-device response (revoke → investigate → reimage) and quarterly tightening.

## Pitfalls
- Stale signals: posture based on days-old data is theater. Monitor signal freshness as a control.
- Fail-open on unknown: new or unenrolled devices getting sensitive access defeats the program. Fail
  closed, with a usable enrollment path.
- Cryptic denials: users who can't tell why they're blocked will demand exceptions instead of fixing
  devices.
- One baseline for all: servers, mobiles, and BYOD need different contracts. Forcing one creates
  unmeetable requirements and mass exceptions.
- Ignoring the human process: re-imaging and remediation need helpdesk capacity. Understaffed
  support turns posture enforcement into a backlog.

## References
- NIST SP 800-207 (Zero Trust Architecture — device trust)
- CISA Zero Trust Maturity Model (Devices pillar)
- Microsoft Learn: Intune compliance policies and Conditional Access device conditions
- CIS Benchmarks (endpoint configuration baselines)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
