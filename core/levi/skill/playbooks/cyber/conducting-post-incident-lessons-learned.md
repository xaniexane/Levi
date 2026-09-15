---
skill_id: cyber_conducting_post_incident_lessons_learned
name: Conducting Post-Incident Lessons Learned
description: Practitioner guide to running blameless post-incident reviews that convert incidents into concrete security improvements.
risk: info
permissions: []
requires_confirmation: false
tags: [incident-response, governance, improvement]
version: 1.0.0
---
## Purpose
The incident is not over when systems recover; it is over when the organization has learned from it. This playbook structures the lessons-learned review: reconstructing the timeline, identifying what worked and what failed, assigning improvement actions with owners, and tracking them to completion -- all in a blameless culture that encourages honesty.

## When to use
- After every significant security incident or near-miss.
- When the same type of incident recurs, indicating learning failed.
- Building an organizational memory of incidents and improvements.
- Meeting regulatory or contractual requirements for post-incident review.

## Prerequisites
- Complete incident timeline and documentation from the response.
- Participation from responders, affected business units, and relevant third parties.
- Facilitator who was not directly responsible for the response.
- Tracking system for improvement actions.

## Procedure
1. Schedule promptly. Hold the review within two weeks of incident closure while memories are fresh; invite everyone involved plus key stakeholders.
2. Set blameless ground rules. State explicitly that the goal is systemic improvement, not individual blame; enforce it during the session.
3. Reconstruct the timeline. Walk through detection, response, containment, and recovery; identify where time was lost and where things went well.
4. Identify root and contributing causes. Use structured analysis (such as five-whys) to go beyond the proximate trigger to systemic factors.
5. Capture what worked. Document effective detections, procedures, and decisions so they are preserved and repeated.
6. Generate improvement actions. For each gap, define a specific action, owner, and deadline; prioritize by risk reduction.
7. Assign and track. Enter actions into the tracking system; review status in management meetings until closed.
8. Share appropriately. Distribute sanitized lessons to wider teams; feed anonymized insights into training and threat intelligence.

## Expected outputs
- Lessons-learned report with timeline analysis and findings.
- Tracked improvement actions with owners and deadlines.
- Shared knowledge products for training and awareness.

## Pitfalls
- Blame culture produces silence; protect the blameless principle fiercely.
- Reviews held months later rely on faded memories and incomplete notes.
- Actions without owners and deadlines are wishes, not improvements.
- Focusing only on technology while ignoring process and communication failures.

## References
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- ISO/IEC 27035, Information security incident management
- Research on blameless postmortems in reliability engineering
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
