---
skill_id: cyber_performing_threat_emulation_with_atomic_red_team
name: Threat Emulation with Atomic Red Team
description: Emulate adversary techniques with Atomic Red Team in controlled environments to validate detective controls.
risk: moderate
permissions: []
requires_confirmation: true
tags: [emulation, atomic-red-team, detection]
version: 1.0.0
---

## Purpose
- Validate detective controls against specific adversary techniques with minimal operational risk.
- Give defenders a safe way to observe what each technique looks like in their own telemetry.
- Build a repeatable emulation library mapped to the organization's threat model.

## When to use
- When validating new SIEM, EDR, or NDR detections before relying on them.
- When threat intelligence highlights techniques the organization should detect.
- As part of purple team programs and detection engineering workflows.
- After control changes, to confirm coverage did not regress.

## Prerequisites
- Written authorization covering targets, techniques, and time windows.
- Dedicated test systems or an approved lab; avoid production unless explicitly authorized.
- The Atomic Red Team framework with technique packages reviewed for safety.
- SOC coordination with emulation identifiers for alert correlation.

## Procedure
1. Confirm authorization and select techniques mapped to the threat model or new detections.
2. Review each atomic test's commands and prerequisites; skip or adapt anything unsafe for the environment.
3. Prepare the test systems: snapshots or baselines so state can be restored.
4. Notify the SOC with the emulation schedule and correlation identifiers.
5. Execute tests individually, recording precise timestamps for each.
6. Observe which alerts fire and assess their quality: correct technique mapping, useful context, acceptable noise.
7. For techniques with no alert, determine whether the test executed properly before declaring a detection gap.
8. Work with detection engineers to build or tune rules, then rerun the test to validate.
9. Clean up test artifacts and restore systems to baseline.
10. Document results per technique: executed, detected, alert quality, and follow-up actions.
11. Maintain the emulation library with versioning for regression testing.
12. Report coverage trends to security leadership regularly.

## Expected outputs
- Per-technique emulation results with detection verdicts.
- Validated new or tuned detections.
- A maintained emulation library for regression testing.
- A mapping of emulated techniques to the organization's threat model.
- Quarterly emulation calendar aligned with threat-intel priorities.

## Pitfalls
- Running emulations on production without explicit approval; some tests modify system state.
- Skipping the command review; a small number of atomic tests are destructive.
- Confusing test execution failure with detection failure; verify the technique actually ran.
- Letting the emulation library go stale as techniques and tools evolve.

## References
- CISA Known Exploited Vulnerabilities catalog for technique prioritization
- Atomic Red Team project documentation
- MITRE ATT&CK for technique details, https://attack.mitre.org/
- MITRE Caldera for automated adversary emulation
- NIST SP 800-53 control CA-8
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
