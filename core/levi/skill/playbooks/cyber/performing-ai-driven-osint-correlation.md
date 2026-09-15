---
skill_id: cyber_performing_ai_driven_osint_correlation
name: Performing AI-Driven OSINT Correlation (Defensive)
description: Correlate open-source intelligence with AI assistance for threat intel and investigations.
risk: low
permissions: []
requires_confirmation: false
tags: [osint, threat-intelligence, investigations]
version: 1.0.0
---

## Purpose
This playbook uses AI-assisted correlation of open-source intelligence for defensive purposes: enriching threat intel, supporting investigations, and monitoring exposure of your organization's assets — with strict handling of privacy, verification, and data-protection obligations.

## When to use
- Triaging large volumes of OSINT (breach dumps, social posts, code repos) for relevant threats.
- Enriching incident investigations with public context on infrastructure and actors.
- Discovering your organization's unintended public exposure (leaked credentials, exposed services).

## Prerequisites
- Defined intelligence requirements: what questions the OSINT effort answers.
- Legal/privacy review: what may be collected and stored under applicable law.
- An AI/ML correlation environment with no sensitive case data in prompts to public models.

## Procedure
1. **Scope the collection.** Define targets (your assets, relevant actors, technologies) and explicitly out-of-scope areas; unfocused OSINT collection creates legal and storage risk.
2. **Collect from legitimate sources.** Use public APIs, threat-intel feeds, certificate transparency, code repositories, and reputable monitoring services; respect terms of service and robots directives.
3. **Correlate with AI assistance.** Use models to cluster related entities, resolve aliases, summarize reporting, and surface contradictions — always keeping source links for verification.
4. **Verify before acting.** AI correlation proposes hypotheses; every operational decision (blocking, attribution statements, victim notification) requires human verification against primary sources.
5. **Protect privacy.** Minimize collection of personal data, redact where possible, and apply retention limits; document the lawful basis for processing.
6. **Sanitize AI inputs.** Never feed victim PII, credentials, or non-public case details into public AI services; use internal or contracted models with data protections for sensitive work.
7. **Produce and archive.** Write finished OSINT assessments with confidence levels and full source citations; archive the underlying collection per retention policy.

8. **Handle disinformation risk.** OSINT includes deliberate deception; apply source-reliability and information-credibility ratings before any assessment cites a source.
9. **Brief consumers on confidence.** Every OSINT product states what is known, what is assessed, and what is unknown — decision-makers need the gaps, not just the findings.

## Expected outputs
- Scoped OSINT collection plan with legal/privacy sign-off.
- Correlated entity graphs with verified assessments and confidence ratings.
- Handling procedures for AI tooling and personal data.
- Example: AI correlation links a new ransomware leak-site post to a previously reported intrusion set via shared infrastructure; human verification against primary sources confirms the link before it is briefed.

## Pitfalls
- Acting on AI-generated correlations without primary-source verification.
- Pasting sensitive investigation data into public AI chatbots.
- Mission creep: collecting personal data "just in case" without a requirement.

- Using OSINT to investigate individuals without authorization; employee and third-party investigations need legal review first.
- Storing raw scraped datasets indefinitely; apply the same retention discipline as any other personal-data processing.

## References
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
- OSINT ethics and tradecraft references (e.g., Bellingcat's online investigation toolkit guidance).
- SANS SEC487 (sans.org) — open-source intelligence methods.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
