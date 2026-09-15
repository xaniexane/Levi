---
skill_id: cyber_performing_physical_intrusion_assessment
name: Physical Intrusion Assessment
description: Assess facility physical security controls through authorized testing to find gaps before criminals do.
risk: low
permissions: []
requires_confirmation: false
tags: [physical, assessment, hardening]
version: 1.0.0
---

## Purpose
- This playbook covers authorized physical security assessments conducted to harden facilities; it is strictly defensive in intent.
- Test whether locks, badges, cameras, and guards actually stop unauthorized entry.
- Find the human-factor gaps, such as tailgating and social engineering, that technology alone cannot fix.
- Give facilities and security teams a prioritized hardening plan grounded in demonstrated weaknesses.

## When to use
- When a facility houses sensitive data, critical infrastructure, or high-value assets.
- After a physical security incident such as a break-in, tailgating report, or badge misuse.
- When opening a new office or data center, to validate controls before move-in.
- As part of a comprehensive security assessment alongside cyber testing.

## Prerequisites
- Written authorization from facility leadership and legal, with a get-out-of-jail contact available during testing.
- Defined rules of engagement: which areas are off-limits, what techniques are allowed, and how to handle confrontations.
- Coordination with the guard force or monitoring center so testers are not mistaken for real intruders.
- Safety planning: no actions that could cause injury, panic, or property damage.

## Procedure
1. Confirm authorization documents are signed and the emergency contact understands their role.
2. Conduct passive reconnaissance first: observe public areas, visitor flows, and shift changes without interacting.
3. Test perimeter controls: fence lines, gates, loading docks, and after-hours entry points.
4. Test tailgating resistance by attempting to follow authorized entrants, stopping immediately if challenged.
5. Evaluate visitor management: sign-in procedures, badge issuance, escort policies, and badge return.
6. Check sensitive areas: server rooms, network closets, executive floors, and document storage for access controls.
7. Review camera coverage and alarm placement for blind spots, noting where detection failed during the test.
8. Test after-hours controls separately, since staffing and vigilance differ from daytime.
9. Document every finding with time, location, method, and whether detection occurred.
10. Brief stakeholders with findings ranked by risk and remediation sequenced from quick wins to capital projects.
11. Support remediation: retest after fixes to confirm the gaps are actually closed.

## Expected outputs
- An assessment report with demonstrated entry paths, detection gaps, and evidence.
- A prioritized remediation plan covering technology, process, and training fixes.
- Retest results confirming remediation effectiveness.
- A guard-force and staff awareness briefing based on demonstrated social-engineering successes.
- Costed remediation options from procedural fixes to capital improvements.

## Pitfalls
- Testing without airtight authorization; a misunderstanding here can mean arrest or termination.
- Continuing after being challenged or detected; stop, identify, and de-escalate immediately.
- Focusing only on high-tech bypasses while ignoring the propped-open door, which is how most intrusions happen.
- Failing to test the human response: an alarm nobody answers is not a control.

## References
- ASIS Protection of Assets guidance
- ASIS physical security assessment guidance
- NIST SP 800-53 physical and environmental protection control family
- ISC2 physical security domains in the CISSP body of knowledge
- Vendor documentation for the access control and video systems in use
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
