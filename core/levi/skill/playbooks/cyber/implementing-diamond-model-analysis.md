---
skill_id: cyber_implementing_diamond_model_analysis
name: Diamond Model Analysis for Intrusions
description: Apply the Diamond Model to intrusion analysis: adversary, capability, infrastructure, victim relationships.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, analysis]
version: 1.0.0
---
## Purpose
Incident reports often list indicators without understanding: who attacked, with what, through which
infrastructure, against whom — and how those relate. The Diamond Model of Intrusion Analysis
structures every intrusion as relationships between four vertices (Adversary, Capability,
Infrastructure, Victim), revealing pivots: shared infrastructure linking incidents, capabilities
suggesting adversary identity, victimology suggesting targeting. This playbook operationalizes the
model for SOC and threat-intel teams.

## When to use
- Analyzing intrusions beyond IOC lists: understanding the adversary and their operation.
- Pivoting from one incident to related activity (shared infrastructure, reused capabilities).
- Building threat-intel products that inform defense (detections, hunting hypotheses) rather than
  just reporting.
- Attributing campaigns internally (which incidents belong together) without overclaiming external
  attribution.
- Training analysts in structured analytic thinking for intrusions.

## Prerequisites
- Incident data: forensic artifacts, logs, malware samples, and infrastructure observables from at
  least one intrusion.
- An analytic workspace: link-analysis tool, threat-intel platform, or even a structured case file —
  somewhere relationships are recorded, not just lists.
- Access to infrastructure context: passive DNS, WHOIS, certificate transparency, and internal
  asset/victim data.
- Defined confidence levels and analytic standards (e.g., ICD 203-style estimative language) to
  avoid overstating.
- Time boxed for analysis: the model rewards depth; scope each diamond to the investigation's
  questions.

## Procedure
1. **Frame the event.** Write the single-sentence intrusion event: "Adversary X used capability Y
   against victim Z via infrastructure W" — with placeholders for unknowns. This sentence is the
   hypothesis the diamond will fill in and refine.
2. **Populate the four vertices.** Adversary: who (even if just "unknown actor with these TTPs").
   Capability: malware, tools, exploits, techniques (map to ATT&CK). Infrastructure: domains, IPs,
   email accounts, C2. Victim: targeted organizations, people, assets, and why they're interesting
   (victimology). Record confidence per vertex.
3. **Draw the edges as relationships.** For each pair, document the relationship with evidence:
   adversary–capability (actor uses tool X — "used by" with sample evidence),
   capability–infrastructure (malware beacons to domain Y), infrastructure–victim (phish sent from Z
   to victim), adversary–victim (targeting motive). Edges carry the analytic weight, not the
   vertices alone.
4. **Add the meta-features.** For each edge, record: phase of the intrusion (recon, exploitation,
   C2, actions — kill-chain mapping), direction, and timestamps. Then classify activity threads:
   which edges belong to the same operational thread vs. separate threads. Threads reveal the
   operation's structure.
5. **Pivot deliberately.** From each vertex, pivot: infrastructure → other victims (who else
   resolved that domain?), capability → other incidents (where else did this tool appear?), victim →
   other adversaries (who else targets this sector?). Each pivot is a hunting hypothesis or a link
   to another case.
6. **Group with activity threads and activity groups.** Cluster related diamonds into activity
   threads (one operation) and activity groups (persistent actor campaigns). This is internal
   attribution done right: grouping by shared infrastructure/capability/victimology with stated
   confidence — not naming nation-states on thin evidence.
7. **Extract defensive value.** From each diamond, derive: detection opportunities (capability →
   signatures/behaviors; infrastructure → blocks/hunts), victimology lessons (who's targeted → who
   gets hardened and warned), and intel requirements (what's unknown → collection tasking). Analysis
   that doesn't improve defense is trivia.
8. **Write the diamond as a product.** Document: the event sentence, the four vertices with
   confidence, key edges with evidence, pivots performed and results, activity-group placement, and
   defensive actions taken. Future analysts should be able to reuse every vertex and edge.
9. **Maintain the diamond library.** Store diamonds in the threat-intel platform with searchable
   vertices. When a new incident arrives, search infrastructure and capability vertices first — the
   fastest attribution is finding you've seen this diamond before.
10. **Review analytic quality.** Periodically review diamonds for: confidence inflation (assertions
    beyond evidence), missing victimology (the "why them" question unanswered), and un-pivoted
    vertices (lazy analysis). Quality review keeps the library trustworthy.

## Expected outputs
- Diamond-model analyses for significant intrusions: vertices, edges with evidence, meta-features,
  confidence levels.
- Documented pivots linking incidents into activity threads and groups.
- Defensive extractions: detections, hunts, hardening actions, and intel requirements per diamond.
- A searchable diamond library in the threat-intel platform.
- Analytic tradecraft standards (confidence language, quality review).

## Pitfalls
- IOC lists masquerading as analysis: vertices without edges are just lists. The relationships are
  the analysis.
- Attribution overreach: claiming specific actors on shared-tooling evidence. State what's
  evidenced; group internally with confidence.
- Skipping victimology: "why this victim" often reveals targeting logic that predicts the next
  victim. Always ask it.
- Analysis without defensive extraction: brilliant diamonds that change no detection or hardening
  are academic. Every diamond owes defensive output.
- One-and-done diamonds: intrusions evolve — update diamonds as new evidence arrives, and link
  follow-on activity.

## References
- Caltagirone, Pendergast, Betz: "The Diamond Model of Intrusion Analysis" (the foundational paper)
- MITRE ATT&CK (capability/technique taxonomy for the capability vertex)
- ICD 203 (analytic standards — confidence and estimative language)
- CISA / threat-intel community guidance on structured intrusion analysis
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
