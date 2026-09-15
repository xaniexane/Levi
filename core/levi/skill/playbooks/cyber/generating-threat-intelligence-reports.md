---
skill_id: cyber_generating_threat_intelligence_reports
name: Generating Threat Intelligence Reports
description: Produce clear, actionable threat intelligence reports — strategic, operational, and tactical — with proper handling markings and dissemination.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, reporting, analysis]
version: 1.0.0
---
## Purpose

Threat intelligence only has value when it reaches the right consumer in
a form they can act on. This playbook defines how to produce finished
intelligence reports at three levels — strategic (for leadership),
operational (for campaign tracking), and tactical (IOCs and detections
for defenders) — with consistent structure, confidence statements, and
handling markings.

## When to use

- After completing an investigation, hunt, or malware analysis that
  produced shareable findings.
- When leadership needs a threat briefing (strategic level).
- When peer teams or the community need campaign context (operational)
  or IOCs (tactical).
- As the output stage of your intel-requirements cycle: every priority
  intelligence requirement should eventually produce reporting.

## Prerequisites

- Finished analysis with validated findings — reports must not
  speculate beyond the evidence.
- Defined consumers and their classification/handling constraints.
- Your reporting templates and handling-marking scheme (TLP).
- A dissemination process: who approves release, and through which
  channels (intel platform, email, community sharing groups).

## Procedure

1. **Identify the consumer and level.** Executives get strategic
   reports (threat landscape, business risk, recommended posture
   changes); campaign trackers get operational reports (actor TTPs,
   infrastructure, timeline); SOC and detection engineers get tactical
   reports (IOCs, behaviors, Sigma/YARA content). One report rarely
   serves all three — write for one audience.
2. **Lead with the bottom line.** Every report opens with: what happened
   or what is the threat, why the consumer should care, and the
   recommended actions. Details follow; the executive summary must stand
   alone.
3. **State confidence explicitly.** Use standardized estimative language
   (high/moderate/low confidence) for each key judgment, and separate
   facts (observed) from assessments (inferred). Note collection gaps
   that limit confidence.
4. **Structure the body consistently.** Recommended sections: summary,
   background/context, detailed findings (with MITRE ATT&CK mapping),
   IOCs/observables, detection guidance, recommended actions, and
   sources/gaps. Consistent structure lets consumers skim reliably.
5. **Make IOCs machine-readable.** Include IOCs in an appendix or
   companion STIX package with confidence, first/last seen, and expiry —
   never bury them only in prose. Mark handling (TLP) per section where
   sensitivity varies.
6. **Sanitize for the audience.** Remove victim-identifying details,
   internal hostnames, and sensitive sources before wider release.
   Apply TLP markings correctly: TLP:RED stays with named recipients,
   TLP:AMBER within the organization/community, and so on.
7. **Disseminate and track.** Release through approved channels, log
   distribution, and set a review date — intelligence decays, and stale
   reports mislead.
8. **Collect feedback.** Ask consumers whether the report drove action;
   feed that back into collection priorities and template improvements.
   Unused reporting is a signal to adjust, not to produce more.

## Expected outputs

- Finished reports at the appropriate level(s) with executive summary,
  confidence statements, ATT&CK mapping, and handling markings.
- Machine-readable IOC appendices (STIX) with expiry dates.
- A dissemination log and review schedule.
- Consumer feedback captured for process improvement.

## Pitfalls

- Writing for everyone produces reports useful to no one — pick one
  audience per report.
- Confidence inflation ("we assess with high confidence" on thin
  evidence) destroys trust; be honest about gaps.
- Leaking victim or source identities through careless detail —
  sanitize systematically, not from memory.
- TLP mismarking either over-shares (leak) or under-shares (intel dies
  in a drawer) — train authors on the markings.
- Producing reports nobody reads: tie every report to a consumer need
  or an intelligence requirement.

## References

- NIST SP 800-150: Guide to Cyber Threat Information Sharing
- STIX 2.1 / TAXII 2.1 specifications (OASIS)
- FIRST: TLP (Traffic Light Protocol) version 2.0
- Sherman Kent-style estimative language guidance (ODNI analytic
  standards)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
