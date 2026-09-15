---
skill_id: cyber_red_teaming_llms_with_garak
name: Red-Teaming LLMs with Garak
description: Authorized adversarial testing of your own language models with garak probes to find jailbreak, leakage, and injection flaws.
risk: low
permissions: []
requires_confirmation: false
tags: [ai-security, llm, red-team]
version: 1.0.0
---
## Purpose
Garak is an LLM vulnerability scanner that probes models for jailbreaks, prompt injection susceptibility, data leakage, and harmful-output failures. This playbook covers using it defensively: authorized testing of your organization's own models and AI features in staging, triaging findings, and hardening before release. Testing third-party models or production systems without approval is out of scope.

## When to use
- Pre-release security review of a new LLM-powered feature or chatbot.
- After changing system prompts, guardrails, or model versions.
- Periodic assurance testing of production AI assistants (in a test environment).
- Validating that mitigations for a reported prompt-injection issue actually hold.

## Prerequisites
- Written authorization covering the target model endpoint and test data.
- Garak installed with API access to a staging/test deployment of the model.
- Baseline of expected model behavior and the system prompt under test.
- Triage process for AI-specific findings (prompt issues are fixed differently than code bugs).

## Procedure
1. Confirm scope: test endpoint, allowed probe categories, and any off-limits content areas.
2. Run garak's probe suites relevant to your risk: jailbreak, prompt injection, data leakage, and encoding bypasses.
3. Review hits manually; garak detectors produce false positives, especially on creative or ambiguous outputs.
4. Reproduce confirmed issues with minimal prompts and document the exact system prompt and model version.
5. Classify findings: guardrail bypass, training-data leakage, tool-misuse, or harmful output.
6. Remediate at the right layer: system prompt hardening, input/output filters, tool permission reduction, or model change.
7. Re-run the failing probes after fixes to confirm closure; track regressions across model updates.
8. Report residual risk to product owners; some attack classes (e.g. sophisticated jailbreaks) are mitigated, not eliminated.
9. Include multilingual and encoding-bypass probes if the model serves non-English users.
10. Test the model with tools enabled and disabled separately; tool access changes the risk profile.
11. Archive garak configurations and model versions so results are comparable across runs.

## Expected outputs
- Garak run reports with confirmed vs false-positive findings.
- Remediation list mapped to layers (prompt, filter, tool, model).
- Regression test set re-run on each model or prompt change.
- Per-probe results with tool-enabled vs tool-disabled comparison.
- Versioned garak configuration for repeatable regression runs.
- Residual-risk statement for model classes that cannot be fully fixed.

## Pitfalls
- Testing production models can generate harmful content in logs; use staging and sanitize outputs.
- Detector false positives waste triage time; always manually verify hits.
- Prompt-level fixes are brittle; prefer architectural controls (least-privilege tools, output validation).
- New model versions can regress fixes; re-test on every update.
- Garak probes can be blocked by naive keyword filters; test the real guardrail stack, not a stripped one.
- Nondeterministic models give varying results; run probes multiple times for confidence.
- Red-teaming the base model differs from testing the full product; test the deployed system.
- Probe results are point-in-time; a model fine-tune can undo months of hardening silently.

## References
- Garak project documentation (NVIDIA garak repository).
- OWASP GenAI Top 10 (genai.owasp.org).
- NIST AI 100-2e, Adversarial Machine Learning taxonomy.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
