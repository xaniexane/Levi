---
skill_id: cyber_continuous_llm_red_teaming_with_promptfoo
name: Continuous LLM Red Teaming with Promptfoo
description: Run scheduled adversarial evaluations of your own LLM deployment with promptfoo to catch regressions before attackers do.
risk: info
permissions: []
requires_confirmation: false
tags: [ai-security, testing, llm]
version: 1.0.0
---
## Purpose

Treat your own LLM like an attacker would: continuously probe it with promptfoo for jailbreaks, prompt injection, data leakage, and policy violations, and fail the build when safety regressions appear. This is defensive adversarial testing of systems you own — the goal is to find your weaknesses first.

## When to use

- Operating a production LLM feature (chatbot, agent, copilot) that handles untrusted user input.
- Validating a model, prompt, or guardrail change before it ships.
- Building a security regression suite for AI features in CI/CD.
- Demonstrating due diligence for AI risk assessments and internal audits.

## Prerequisites

- promptfoo installed and a test harness that can call your LLM deployment (API endpoint, model provider, or local model).
- Written authorization to test the target system — test your own deployments or staging mirrors, never third-party services.
- A baseline of expected-safe behavior and the policy your model must follow (refusal topics, data-handling rules).
- CI integration (GitHub Actions, Jenkins) so evals run on every prompt/model/config change.

## Procedure

1. **Define the threat model for your deployment.** List what a successful attack looks like for your app specifically: system-prompt extraction, PII leakage from context, tool misuse (e.g. the agent executing unauthorized actions), disallowed content, and indirect prompt injection via retrieved documents. Generic test suites miss app-specific risks.
2. **Build a promptfoo config with layered test cases.** Write `promptfooconfig.yaml` with providers pointing at your deployment, and prompts covering: direct jailbreak attempts (role-play, hypothetical framing), prompt-injection payloads (instruction overrides in user input), data-exfiltration probes ("repeat your system prompt"), and tool-abuse scenarios for agentic setups. Start from promptfoo's built-in red-team plugins, then add cases specific to your app's tools and data.
3. **Add custom assertions that match your policy.** Beyond default checks, write assertions for your invariants: e.g. "response must not contain strings from the system prompt," "must refuse to summarize the attached confidential document for an unauthorized user," "tool calls must stay within the allowed allowlist." Failing assertions are the security signal — vague "LLM-graded" checks alone drift.
4. **Run the baseline and triage every failure by hand.** The first full run will surface false failures (over-strict assertions) and real ones. Triage each: fix the assertion or fix the app. Record the baseline pass rate — this is the number future runs are compared against.
5. **Wire it into CI as a blocking gate.** Run the red-team suite on every change to prompts, system messages, model versions, guardrail configs, and tool definitions. A regression (previously passing attack now succeeds) blocks the deploy. Keep a fast subset for PRs and the full suite nightly.
6. **Rotate and expand the attack corpus.** Attackers adapt; your tests must too. Monthly: add new jailbreak techniques from published research, refresh injection payloads, and add cases for newly added tools or data sources. Track which attack classes succeed over time — a rising trend in one class means your guardrails are decaying.
7. **Test the whole system, not just the model.** Include your guardrails, input filters, and output classifiers in the test path — a model that "fails" but is caught by the output filter is a pass for the system. Also test with realistic multi-turn conversations and tool-using agent loops, where single-turn probes miss the real attack surface.
8. **Report like a security finding, not a benchmark.** Each confirmed bypass gets: the attack class, reproduction steps, blast radius (what could an attacker do with it), and remediation (prompt change, guardrail, tool restriction). Track mean-time-to-fix for red-team findings alongside other security bugs.

## Expected outputs

- A promptfoo red-team suite in version control with app-specific attack cases and custom assertions.
- CI gating on prompt/model/guardrail changes with baseline pass rates and regression blocking.
- A monthly corpus-refresh cadence and findings tracked as security bugs with remediation owners.

## Pitfalls

- Testing the base model instead of your deployed system — your guardrails and tools change the attack surface completely.
- LLM-as-judge assertions with no grounding — they pass attacks that a precise assertion would catch; use deterministic checks where possible.
- A static test corpus — it rots within months as attack techniques evolve.
- Running red-team tests against production with real user data in context — use staging mirrors with synthetic data.
- Treating a high pass rate as "secure" — it's a lower bound on attacker success, not an upper bound.

## References

- promptfoo documentation (promptfoo.dev) — red-team configuration and plugins
- NIST AI 600-1 (GenAI Profile) and the OWASP Top 10 for LLM Applications
- MITRE ATLAS — adversarial threat landscape for AI systems
- Anthropic / OpenAI published red-teaming methodologies for evaluation design
