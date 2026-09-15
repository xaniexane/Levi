---
skill_id: cyber_orchestrating_llm_attacks_with_pyrit
name: Adversarial Testing of AI Systems with PyRIT (Defensive)
description: Use PyRIT for authorized adversarial testing of your own LLM systems to harden them.
risk: low
permissions: []
requires_confirmation: false
tags: [ai-security, red-teaming, llm]
version: 1.0.0
---
## Purpose
PyRIT (Python Risk Identification Toolkit) orchestrates adversarial prompts against language models. This playbook uses it strictly defensively: authorized testing of your organization's own AI systems to find jailbreaks, prompt-injection paths, and unsafe outputs before adversaries do — then hardening the system. Never use these techniques against systems you do not own or have permission to test.

## When to use
- Your organization deploys an LLM-powered product, copilot, or agent with tool access.
- You need systematic evidence of AI safety posture for risk review or procurement.
- Validating that guardrails (input filters, output moderation, tool permissions) actually hold.

## Prerequisites
- Written authorization to test the target AI system, including which models, endpoints, and data are in scope.
- A lab or staging instance of the AI system; never run adversarial campaigns against production user traffic.
- Success criteria agreed in advance: what findings count, severity rubric, and reporting channel.

## Procedure
1. **Define scope and rules of engagement.** Document target endpoints, forbidden actions (e.g., no exfiltration of real PII, no disruption), and the test window.
2. **Build a scenario library.** Cover: direct jailbreaks, indirect prompt injection via retrieved content, tool-abuse (the model calling privileged functions), data-extraction attempts, and disallowed-content elicitation.
3. **Orchestrate with PyRIT.** Configure attackers, targets, and scorers; run single-turn and multi-turn conversations, capturing full transcripts for evidence.
4. **Score rigorously.** Use automated scorers plus human review for high-severity candidates; a "jailbreak" that produces no harmful capability is a lower-severity finding than one enabling real abuse.
5. **Trace root causes.** For each confirmed weakness, identify whether the fix belongs in the system prompt, input/output filtering, tool permissioning, or model choice.
6. **Remediate and retest.** Apply fixes, then re-run the same scenarios to verify; track which attack classes are closed vs. mitigated.
7. **Report and monitor.** Deliver findings with transcripts and severity; add regression scenarios to the release pipeline so new model versions get re-tested.

8. **Test the human layer.** Include scenarios where the AI system is used to draft phishing or social-engineering content; the control is often policy and monitoring, not just model refusal.
9. **Track the threat landscape.** Monitor published LLM attack research and update the scenario library; attacker techniques against AI systems evolve as fast as the models.

## Expected outputs
- Authorized test plan with scenario library and severity rubric.
- Finding reports with full transcripts, root-cause analysis, and retest evidence.
- Regression suite integrated into the AI release process.
- Example: a multi-turn prompt-injection scenario tricks the support copilot into revealing another customer's ticket details; the fix restricts the retrieval tool's tenant scoping, verified by re-running the same scenario.

## Pitfalls
- Testing production systems or third-party models without permission.
- Counting automated "jailbreak" scores as real findings without human validation.
- Fixing prompts while leaving the model with excessive tool permissions — the bigger risk.

- Running adversarial prompts against a model that logs to a third party; ensure test transcripts stay within your data boundary.
- Treating a failed jailbreak as proof of safety; attackers iterate, so test across sessions, personas, and encoding tricks.

## References
- PyRIT documentation (github.com/Azure/PyRIT — project docs).
- NIST AI 100-2e2025, Adversarial Machine Learning taxonomy (csrc.nist.gov).
- OWASP Top 10 for LLM Applications (genai.owasp.org) — risk categories for AI systems.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
