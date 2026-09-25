---
skill_id: cyber_deploying_edr_agent_with_crowdstrike
name: Deploying EDR Agent with CrowdStrike
description: Roll out CrowdStrike Falcon sensors with tuned prevention policies, containment, and alert workflows.
risk: low
permissions: []
requires_confirmation: false
tags: [edr, endpoint, deployment]
version: 1.0.0
---
## Purpose

Deploy CrowdStrike Falcon sensors across the fleet with prevention policies that actually prevent, containment workflows the SOC can execute in one click, and alert tuning that keeps analysts focused. An EDR that isn't fully deployed and tuned is a compliance checkbox, not a control.

## When to use

- Initial Falcon rollout or expanding coverage to unmanaged segments (servers, cloud workloads, VDI).
- Tuning a noisy Falcon tenant where analysts are ignoring detections.
- Validating prevention efficacy before decommissioning a legacy AV.
- Post-incident hardening to close the coverage gaps the incident exposed.

## Prerequisites

- Falcon console admin access and a sensor deployment method (SCCM/Intune/GPO, MDM, or gold-image baking).
- An asset inventory with OS versions to confirm sensor compatibility.
- Defined prevention-policy tiers (e.g. workstations-aggressive, servers-conservative, VDI-specific).
- SIEM integration planned (Falcon Data Replicator or streaming API) with alert routing defined.

## Procedure

1. **Stage the rollout in waves.** Pilot on IT and security team machines first, then a representative slice of each business unit, then the fleet. Each wave runs at least one week with prevention in detect-then-review mode for the most aggressive settings. Track install success rate per wave — anything under 95% means your deployment method is broken, not your users.
2. **Build prevention policies by tier.** Workstations: enable all NGAV prevention sliders (malware, ransomware, behavioral) at aggressive, plus script-based execution monitoring. Servers: start conservative on anything that could block legitimate services (test thoroughly), but keep behavioral and ransomware prevention on. Document the rationale per slider — auditors and future-you will ask.
3. **Configure sensor update and uninstall protection.** Enable automatic sensor updates with a staged ring (pilot ring gets updates first), and turn on uninstall protection with a maintenance token. An EDR an admin — or malware — can silently remove is not an EDR.
4. **Set up containment and response workflows.** Verify network containment works from the console on a test host (host isolated, console reachable). Pre-authorize SOC analysts to contain without a ticket, and define the escalation path for server containment (which needs change-control awareness). Test the full chain: detect → contain → investigate → release.
5. **Tune detections, don't just suppress them.** Review the top-firing detection types monthly. For each: if it's a true positive pattern (e.g. admin tooling flagged), create a narrowly scoped exception (specific hash + path + user), not a broad disable. Track exception inventory with owners and expiry dates — exceptions are technical debt.
6. **Integrate telemetry into the SOC.** Stream detections to the SIEM with severity mapping, and build the triage runbook: detection → process tree review → prevalence check (how many hosts?) → verdict. Set SLAs: critical detections triaged in 15 minutes, containment decision in 30.
7. **Cover the gaps deliberately.** Deploy to cloud workloads via the cloud sensor, to Linux/macOS fleets with the right sensor variants, and to VDI with non-persistent-mode guidance. Report coverage as a metric (percentage of assets with healthy, reporting sensors) and treat uncovered assets as findings.
8. **Validate with adversary emulation.** Quarterly, run atomic tests or a purple-team exercise against the deployment: confirm prevention fires, containment works, and detections reach the SIEM. A deployment that's never tested is a deployment you hope works.

## Expected outputs

- Tiered prevention policies deployed fleet-wide with 95%+ healthy sensor coverage.
- One-click containment workflows with pre-authorized SOC actions and server escalation paths.
- Monthly detection tuning with a governed exception inventory; quarterly adversary-emulation validation.

## Pitfalls

- "Deploy and forget" — default policies with no tuning generate noise or miss real attacks.
- Broad exceptions ("exclude the whole admin tools folder") that gut prevention.
- No uninstall protection — the first thing sophisticated malware does is kill the sensor.
- Server containment without a plan — isolating a production database at 2 AM needs a pre-agreed process.
- Measuring deployment by "sensors installed" instead of "sensors healthy and reporting" — stale sensors are invisible gaps.

## References

- CrowdStrike Falcon documentation — prevention policies, containment, sensor deployment
- MITRE ATT&CK Evaluations — EDR efficacy testing methodology
- NIST SP 800-53 SI-7 / SI-8 and CIS Benchmarks for endpoint protection baselines
- CISA guidance on EDR deployment for federal and critical-infrastructure networks
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
