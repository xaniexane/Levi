---
skill_id: cyber_b3_cicd_pipeline_abuse_ot_controller_on_prem_datacenter_defined
name: CI/CD Pipeline Abuse Defense for OT Controllers in On-Premises Datacenter (Defined Maturity)
description: "CI/CD Pipeline Abuse defense playbook for OT Controllers in On-Premises Datacenter at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, devops, ot, ics, critical-infrastructure, on-prem, datacenter, maturity-defined]
version: 1.0.0
---
# CI/CD Pipeline Abuse Defense for OT Controllers in On-Premises Datacenter (Defined Maturity)

## Purpose

Compromised build pipelines inject malicious code into artifacts or exfiltrate secrets from build environments. Pipelines hold production credentials AND ship code — treat them as tier-zero assets. Applies to OT Controllers in On-Premises Datacenter at Defined maturity.

## When to use

- Pipeline runs triggered outside normal commits, modified build scripts, or runners executing unexpected network calls.
- Secrets accessed by pipeline jobs that never needed them, or new pipeline variables containing exfil endpoints.
- Artifacts whose hashes differ from reproducible-build expectations.
- Lens: Best telemetry: passive OT network monitoring + engineering-workstation logs + change-management records. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in OT protocol logs (Modbus/DNP3/OPC) from passive taps — never active-scan OT networks and Engineering workstation access and project-file change logs; run `# PASSIVE ONLY on OT networks — no active scanning:` then `tshark -r /captures/ot-span.pcap -Y 'modbus' -T fields -e frame.time -e modbus.func_code 2>/dev/null | head -20`.
3. **Analyze.** Diff the pipeline definition against the last known-good version; identify exactly which jobs were tampered with. Then: Determine which secrets the compromised jobs could read and rotate all of them — assume exposure.
4. **Contain and harden.** Pipeline definitions in version control with required reviews; ephemeral, isolated runners; OIDC-based short-lived credentials instead of stored secrets. Asset layer: Air-gap or data-diode segmentation from IT, unidirectional gateways, strict change control on logic. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Cleaning the pipeline but shipping artifacts it already poisoned — quarantine recent builds.
- Long-lived cloud credentials stored as pipeline secrets; rotate and replace with OIDC federation.

## References

- MITRE ATT&CK: T1195.002 (Supply Chain: Compromise Software Supply Chain)
- Vendor logging and hardening baselines for OT Controllers; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
