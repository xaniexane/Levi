# Applying the Cyber Kill Chain

## Purpose

Use the Cyber Kill Chain model (Reconnaissance → Weaponization → Delivery →
Exploitation → Installation → Command & Control → Actions on Objectives) as
an analytic framework to structure intrusion investigations, identify the
earliest phase where defenses could have broken the chain, and prioritize
improvements by phase. A communication and prioritization tool — pair it with
technique-level analysis for detection engineering.

## When to use

- Structuring an incident timeline so each adversary action maps to a phase
  and a defensive opportunity.
- Post-incident reviews: finding the earliest phase where detection or
  prevention could have stopped the intrusion.
- Threat modeling a new system: walking the chain to enumerate required
  attacker steps and existing controls per step.
- Communicating intrusions to non-technical stakeholders — the chain is an
  intuitive narrative spine.
- Tabletop exercises: walking a hypothetical intrusion through current
  controls phase by phase.

## Prerequisites

- Written authorization is not needed for the analytic exercise itself; the
  underlying evidence (logs, images, testimony) carries its own
  authorizations and chain-of-custody requirements — keep evidence
  references attached to each phase mapping.
- Assembled incident evidence: timelines, IOCs, TTP observations, and
  control-performance data to map.
- Awareness of the model's limits (documented below) — the kill chain
  describes a specific intrusion archetype well and others poorly.
- Stakeholder context: know whether the audience needs a narrative
  (executives), actions (engineering), or both.

## Procedure

1. **Lay out the seven phases as your working scaffold.** Create a table with one row per phase: Reconnaissance, Weaponization, Delivery, Exploitation, Installation, C2, Actions on Objectives. Every row gets four columns: evidence, timestamp, defensive controls present, and whether each control worked. Empty rows are findings about visibility, not failures of the model.
2. **Populate from your evidence, earliest first.** Map each observed adversary action to its phase: domain registration and scanning → Reconnaissance; phishing email arrival → Delivery; malicious macro/document execution → Exploitation; persistence mechanism → Installation; beaconing → C2; data staging and theft → Actions on Objectives. Leave phases empty rather than inventing entries — gaps reveal where your telemetry is blind.
3. **Identify the earliest breakable link.** For each populated phase, ask: which control, if it had worked, would have stopped everything after it? Rank candidate improvements by (a) how early in the chain they act and (b) implementation cost. Early-chain wins (email filtering catching the phish, patching the exploited vulnerability) usually beat late-chain ones (better DLP) on cost-effectiveness.
4. **Give Weaponization special handling.** This phase happens on adversary infrastructure and is rarely directly observable — note what you *infer* (e.g., "payload built to exploit CVE-XXXX, likely weaponized days before delivery based on compile timestamps") vs. what you *observed*. Don't let inference masquerade as evidence; mark it clearly.
5. **Map defenses per phase, not just detections.** For each phase record preventive, detective, and corrective controls. The kill chain's value is showing *layered* defense: if Delivery prevention failed, did Exploitation detection catch it? If Installation detection fired, did anyone respond? Empty defensive columns reveal single points of failure; full columns with failures reveal control-effectiveness problems.
6. **Account for non-linear reality.** Real intrusions loop: initial access → discovery → lateral movement → privilege escalation cycles through Exploitation/Installation/C2 repeatedly, sometimes over months. Note iterations explicitly rather than forcing a single pass — and recognize the model's bias toward the perimeter-breach, malware-delivery intrusion archetype it was built from.
7. **Supplement where the model is blind.** The kill chain underplays insider threats (they start at Installation or later), supply-chain compromise (Weaponization/Delivery collapse into the vendor), cloud control-plane attacks, and ransomware double-extortion business models. Where your incident doesn't fit, say so explicitly and pair the analysis with ATT&CK mapping (technique-level) or the Diamond Model (adversary/victim/infrastructure/capability relationships).
8. **Produce the phase-by-phase narrative.** Write the incident as a chain story for stakeholders: what happened at each phase, what saw it, what missed it, and the one-line lesson per phase. This becomes the executive summary and a reusable training artifact. Keep it to one page for executives; the full table is the appendix.
9. **Convert to prioritized actions.** Each failed or missing control becomes a backlog item tagged with its phase, owner, and date. Prioritize by earliest-phase coverage per unit cost. Present the backlog as "where we break the chain next time" — that framing gets funded more reliably than "control gaps."
10. **Reuse the scaffold proactively.**
    Apply the same table to threat scenarios you *haven't* suffered yet: in
    tabletop exercises, walk a hypothetical intrusion (ransomware via
    phishing, supply-chain update compromise, insider data theft) through
    your current controls per phase and find the gaps before an adversary
    does.
    Record the exercise the same way you'd record an incident.

## Key tools & commands

- Your SIEM/timeline tool — evidence assembly per phase (no special tooling
  required; the kill chain is analytic, not technical).
- MITRE ATT&CK mapping — technique-level detail beneath each phase, which is
  where detection engineering actually happens.
- Timeline analysis tools (Plaso/log2timeline, Timesketch) — order evidence
  chronologically before phase-mapping.
- Tabletop exercise templates and scenario libraries — for the proactive
  application in step 10.
- A simple spreadsheet — the phase table needs no specialized software;
  rigor comes from the mapping, not the tool.

## Expected outputs

- A phase-mapped incident table: evidence, timestamps, controls, and
  control effectiveness per phase, with gaps marked.
- An "earliest breakable link" analysis with prioritized, cost-ranked
  improvements.
- A one-page stakeholder narrative plus the full table as appendix.
- A corrective-action backlog with phase tags, owners, and dates.
- Documented model limitations where the incident didn't fit, with
  supplementary framework mappings.
- Tabletop exercise records reusing the same scaffold.

## Pitfalls

- Treating the chain as a literal sequence: insiders start at Installation;
  supply-chain attacks compress Weaponization/Delivery into a trusted
  update. Force-fitting distorts the analysis — note the misfit instead.
- Filling Weaponization with speculation presented as fact — mark inferences
  clearly or drop the row.
- Using the kill chain *instead of* technique-level analysis: it's a
  communication and prioritization framework, not a detection-engineering
  tool. Always pair it with ATT&CK.
- Analysis without action: a beautiful phase map that produces no backlog
  items is theater. The deliverable is the prioritized actions, not the
  diagram.
- Applying only to external intrusions: run the model against insider and
  supply-chain scenarios too, noting where it strains — the strain points
  are themselves useful findings about your mental models.

## References

- Lockheed Martin Cyber Kill Chain (Hutchins, Cloppert, Amin) — the
  original model and its intended scope
- MITRE ATT&CK Enterprise matrix (technique-level companion mapping)
- The Diamond Model of Intrusion Analysis (Caltagirone, Pendergast, Betz) —
  for relationship-centered cases the chain handles poorly
- NIST SP 800-61 (incident handling phases, for structuring response around
  the analysis)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
