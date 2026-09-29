---
skill_id: cyber_b3_watering_hole_siem_platform_on_prem_datacenter_defined
name: Watering Hole Attack Defense for SIEM Platforms in On-Premises Datacenter (Defined Maturity)
description: "Watering Hole Attack defense playbook for SIEM Platforms in On-Premises Datacenter at Defined maturity."
risk: low
permissions: []
requires_confirmation: false
tags: [network, malware, soc, siem, monitoring, on-prem, datacenter, maturity-defined]
version: 1.0.0
---
# Watering Hole Attack Defense for SIEM Platforms in On-Premises Datacenter (Defined Maturity)

## Purpose

Attackers compromise websites your targets frequent, turning trusted browsing into infection. Detection is epidemiological: multiple infections sharing one browsing history overlap. Applies to SIEM Platforms in On-Premises Datacenter at Defined maturity.

## When to use

- Several hosts infected with the same payload whose proxy histories share a common site visited shortly before each infection.
- A trusted industry/partner site serving malicious scripts or redirects (verified via sandbox fetch).
- Infections clustered by department or role matching the compromised site's audience.
- Lens: Best telemetry: ingestion health metrics + rule-hit history + analyst audit trail. Full network tap/SPAN coverage at core and distribution layers feeding IDS and full-packet capture.

## Prerequisites

- Written authorization from the asset owner and incident commander before active containment.
- Access to Centralized syslog from all infrastructure with NTP-synced timestamps for cross-device correlation.

## Procedure

1. **Authorize and scope.** Open a ticket, confirm written authorization, and preserve evidence before changing anything.
2. **Detect and collect.** Hunt the signals above in Detection rule hit history for the incident's indicators across the full retention window and Ingestion gap reports: which sources stopped logging and when (coverage blind spots); run `# conceptually (SIEM query languages differ):` then `index=* <indicator> earliest=-30d | stats count by sourcetype`.
3. **Analyze.** Confirm the watering hole by fetching the suspect site in a sandbox and capturing the injected code. Then: Enumerate all visitors to the site in the compromise window — the exposed population, not just the infected.
4. **Contain and harden.** Notify the site owner; block the malicious URLs/paths (not necessarily the whole domain) at the proxy. Asset layer: Separate SIEM admin credentials, tamper-evident storage, monitored ingestion pipelines. Environment layer: Physical access controls with badge logs correlatable to logical access during investigations.
5. **Document and improve.** Map each detection signal to the relevant MITRE technique and confirm coverage in the detection engineering backlog. Record the timeline, indicators, actions taken, and lessons learned.

## Expected outputs

- Scoped timeline; affected assets, accounts, and data with containment status each.
- Hardening verified effective; detection improvements filed.

## Pitfalls

- Treating each infection as independent and missing the common source — always compare browsing histories across cases.
- Blocking the entire legitimate domain permanently instead of the injected path, breaking business access.

## References

- MITRE ATT&CK: T1189 (Initial Access: Drive-by Compromise) — watering hole variant
- Vendor logging and hardening baselines for SIEM Platforms; Physical access controls with badge logs correlatable to logical access during investigations.

---
*Original work authored for LEVI. Defensive blue-team playbook; all content written from scratch for LEVI.*
