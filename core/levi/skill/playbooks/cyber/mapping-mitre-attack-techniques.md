---
skill_id: cyber_mapping_mitre_attack_techniques
name: Mapping MITRE ATT&CK Techniques
description: Map detections, controls, and incidents to ATT&CK techniques for coverage analysis.
risk: info
permissions: []
requires_confirmation: false
tags: [mitre-attack, detection-engineering, threat-modeling]
version: 1.0.0
---
## Purpose
This playbook standardizes how your organization maps security content to MITRE ATT&CK: detections, preventive controls, threat intel, and incident findings — producing a common language for coverage gaps and investment decisions.

## When to use
- Building a detection coverage heatmap (e.g., ATT&CK Navigator layers).
- Translating threat intel reports into detection requirements.
- Communicating security posture to leadership in a structured way.

## Prerequisites
- Familiarity with ATT&CK Enterprise matrix structure: tactics, techniques, sub-techniques.
- Inventory of detections and controls to map.
- ATT&CK Navigator or equivalent for visualization.

## Procedure
1. **Adopt mapping conventions.** Decide granularity (technique vs. sub-technique), what counts as "covered" (prevent, detect, both), and how to score partial coverage; document it.
2. **Map detections.** For each SIEM/EDR detection, record the technique(s) it genuinely covers — validated against test data, not assumed from the vendor's marketing.
3. **Map preventive controls.** Record which techniques are blocked or mitigated by each control (hardening, EDR prevention, email gateway, segmentation).
4. **Map threat intel.** When CTI describes actor TTPs, translate to technique IDs and overlay on your coverage to find actor-relevant gaps.
5. **Map incidents.** After each incident, record the techniques observed; recurring unmapped techniques indicate detection debt.
6. **Visualize and prioritize.** Produce Navigator layers per stakeholder view (detection coverage, control coverage, actor overlay); prioritize gaps by actor relevance and asset exposure.
7. **Maintain the mapping.** Review mappings when detections change, controls are added, or ATT&CK releases a new version; version-control the mapping data.

8. **Use mappings in procurement.** Ask vendors which techniques their product detects or prevents, and validate the claims against your mapping conventions during evaluation.
9. **Publish a coverage summary.** A one-page tactic-level heatmap for leadership, with the detailed technique data available for engineers — one mapping, two audiences.

## Expected outputs
- Versioned technique-mapping dataset for detections, controls, intel, and incidents.
- Navigator heatmaps showing coverage by tactic with gap analysis.
- Prioritized detection backlog derived from actor-relevant gaps.
- Example: overlaying a ransomware affiliate's TTPs on the detection map reveals no coverage for T1021.004 (SSH lateral movement), generating a top-priority detection backlog item.

## Pitfalls
- Mapping at the tactic level only: too coarse to drive engineering work.
- Claiming coverage from a control that was never tested against the technique.
- Letting the mapping rot while the environment and ATT&CK both evolve.

- Mapping detections to techniques the rule cannot actually distinguish; a generic "suspicious process" alert is not coverage for five techniques.
- Letting the mapping live in one analyst's spreadsheet; store it in version control where the detection code lives.

## References
- MITRE ATT&CK (attack.mitre.org).
- ATT&CK Navigator (mitre-attack.github.io/attack-navigator).
- MITRE D3FEND (d3fend.mitre.org) — countermeasure mapping companion.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
