---
skill_id: cyber_performing_purple_team_atomic_testing
name: Purple Team Atomic Testing
description: Execute controlled atomic adversary tests to validate that detections fire and defenses behave as expected.
risk: moderate
permissions: []
requires_confirmation: true
tags: [purple-team, testing, detection]
version: 1.0.0
---

## Purpose
- Validate that specific detections fire correctly against known adversary techniques.
- Give red and blue teams a shared, low-drama way to test one technique at a time.
- Turn test results directly into detection improvements with clear pass or fail evidence.
- Build a library of validated tests that can be rerun after control changes.

## When to use
- When new EDR, SIEM, or NDR detections need validation before they are trusted.
- After control changes such as EDR policy updates, to confirm coverage did not regress.
- When threat intelligence highlights a technique the organization should be able to detect.
- As the technical engine inside a larger purple team exercise.

## Prerequisites
- Written authorization covering the test systems, techniques, and time windows.
- Isolated or approved test endpoints where atomic tests can run without production impact.
- Coordination with the SOC so test activity is expected and labeled, not investigated as a real incident.
- A test framework such as Atomic Red Team with the relevant technique packages reviewed.

## Procedure
1. Confirm authorization and scope: which hosts, which techniques, and the approved testing window.
2. Notify the SOC with test identifiers so alerts can be correlated to the exercise.
3. Select atomic tests mapped to the techniques under review, preferring the smallest test that exercises the detection.
4. Review each test's commands before execution to confirm they are safe for the target environment.
5. Execute tests one at a time, recording start and end times for alert correlation.
6. Capture the results: which alerts fired, their fidelity, and how long detection took.
7. Investigate misses: was the technique not executed correctly, or did the detection genuinely fail.
8. Tune or create detections for the gaps found, then rerun the same atomic test to confirm the fix.
9. Document each test with technique ID, commands, expected alerts, actual alerts, and the verdict.
10. Archive the test library with versioning so future control changes can be regression-tested.
11. Report aggregate coverage: which techniques are detected, which are not, and the plan for the gaps.
12. Schedule recurring runs so detection coverage is continuously validated, not a one-time snapshot.

## Expected outputs
- Per-test results with pass or fail verdicts and alert evidence.
- New or tuned detections validated by rerunning the atomic tests.
- A coverage map of tested techniques against detection status.
- A versioned atomic test library for regression testing.
- An executive-friendly summary of detection coverage trends over time.
- Integration of atomic tests into CI pipelines for security tooling changes.

## Pitfalls
- Running atomic tests on production systems without explicit approval; some tests alter system state.
- Executing tests the analyst has not read; a few atomic tests are destructive by design.
- Counting a fired alert as success without checking its fidelity; noisy low-quality alerts still need tuning.
- Testing once and declaring victory; detections decay as environments and adversaries change.
- Running tests on a schedule aligned with threat-intel updates keeps coverage relevant.

## References
- Red Canary Atomic Red Team community resources
- Atomic Red Team project documentation
- MITRE ATT&CK techniques pages for the tested techniques, https://attack.mitre.org/
- MITRE Engenuity adversary emulation resources
- NIST SP 800-53 control CA-8 on penetration testing concepts
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
