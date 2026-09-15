---
skill_id: cyber_performing_supply_chain_attack_simulation
name: Supply Chain Attack Simulation
description: Simulate supply chain compromise scenarios in tabletop and controlled exercises to harden vendor and build pipelines.
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, simulation, resilience]
version: 1.0.0
---

## Purpose
- This playbook covers authorized defensive simulation to improve supply chain resilience; it does not cover attacking real suppliers.
- Test how the organization would detect and respond to a compromised vendor or build pipeline.
- Find the blind spots in vendor risk management, SBOM practices, and build integrity.
- Build muscle memory for the decisions a supply chain incident forces.

## When to use
- When supply chain risk is a top concern for leadership or regulators.
- After sector incidents involving compromised vendors or build systems.
- When rolling out SBOM requirements or build-integrity controls.
- As part of enterprise resilience exercises.

## Prerequisites
- Executive sponsorship and written authorization for the simulation scope.
- An inventory of critical vendors, build pipelines, and software distribution paths.
- Participants from security, engineering, procurement, and legal.
- A scenario grounded in realistic supply chain attack patterns.

## Procedure
1. Define objectives: which supply chain stage is under test and what decisions matter.
2. Map the software supply chain: source repositories, CI/CD, artifact registries, and distribution.
3. Build the scenario: compromised build dependency, malicious vendor update, or tampered artifact.
4. Walk through detection: how would anyone notice, and how long would it take.
5. Exercise containment: which products are affected, how are customers notified, how are artifacts revoked.
6. Test vendor coordination: who calls the vendor, what is asked, and what if the vendor is unresponsive.
7. Review build integrity controls: signed commits, reproducible builds, artifact signing, and provenance.
8. Assess SBOM readiness: can the organization list affected products from component data.
9. Discuss legal and communications: disclosure obligations, customer notifications, and regulatory reporting.
10. Capture gaps with owners and deadlines, as with any tabletop.
11. Prioritize remediation: the controls that would have detected or contained the scenario fastest.
12. Schedule the next simulation with a different supply chain stage.

## Expected outputs
- A gap register covering detection, containment, vendor coordination, and communications.
- Prioritized controls for build integrity and SBOM readiness.
- An improved incident playbook for supply chain scenarios.
- A supplier incident communication template ready for real events.
- Procurement contract language on incident notification timelines.

## Pitfalls
- Simulating against real vendor systems; keep the exercise in discussion or lab environments.
- Focusing only on code dependencies while ignoring compromised vendor remote access.
- Ending at detection; the hardest supply chain decisions are containment and disclosure.
- Exercising with vendors who were not informed; coordinate participation in advance.

## References
- NIST SP 800-161 Rev 1 for supply chain control families
- NIST SP 800-161 on supply chain risk management
- CISA guidance on software supply chain security
- NTIA guidance on SBOM
- SLSA framework documentation for build integrity
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
