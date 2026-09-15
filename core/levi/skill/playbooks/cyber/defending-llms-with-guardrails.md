---
skill_id: cyber_defending_llms_with_guardrails
name: Defending LLMs with Guardrails
description: Layer input/output guardrails, tool-use controls, and monitoring around LLM deployments to contain abuse.
risk: info
permissions: []
requires_confirmation: false
tags: [ai-security, llm, defense]
version: 1.0.0
---
## Purpose

Build defense-in-depth around your LLM deployment: input validation, output filtering, tool-use constraints, and behavioral monitoring — so a successful prompt injection meets five more walls before it can cause harm. Guardrails don't make the model safe; they make the system survivable.

## When to use

- Shipping any LLM feature that processes untrusted input (chatbots, agents, RAG, copilots).
- Responding to a red-team finding or real incident involving prompt injection or jailbreak.
- Defining the security architecture for agentic systems with tool access.
- Auditing an existing deployment's controls before expanding its permissions or data access.

## Prerequisites

- A clear inventory of the LLM system's capabilities: tools it can call, data it can read, actions it can take.
- Defined policy: what the system must never do (exfiltrate, execute unapproved actions, reveal secrets).
- Logging pipeline for prompts, completions, tool calls, and guardrail decisions.
- Authority to block or degrade functionality when guardrails trigger — a guardrail that only logs is a suggestion.

## Procedure

1. **Map the trust boundaries first.** Draw the data flow: untrusted user input, semi-trusted retrieved documents (RAG), trusted system instructions, and the tools/actions the model can invoke. Every crossing point gets a control. Retrieved content is the most underestimated attack vector — treat it as untrusted input.
2. **Deploy input guardrails.** Filter and sanitize before the model sees input: blocklist/allowlist patterns for known injection phrases, maximum input lengths, and structural validation (JSON schema for tool inputs). For RAG, delimit retrieved content with clear boundaries and strip or neutralize embedded instructions before insertion into context.
3. **Constrain the model's capabilities, not just its words.** Limit tool access to an explicit allowlist with parameter validation; require human confirmation for irreversible or high-impact actions (deletes, sends, purchases, privilege changes). An agent that can only read tickets can't be tricked into wiping a database.
4. **Deploy output guardrails.** Scan completions before delivery: PII/secret patterns (API keys, SSNs, internal hostnames), policy classifiers for disallowed content, and structural checks (did the output contain a tool call that wasn't authorized?). Quarantine or redact on trigger, and log the full context for review.
5. **Add behavioral monitoring.** Alert on: repeated refusal-then-retry patterns (jailbreak attempts), sudden topic shifts mid-conversation, tool calls outside the normal distribution, and prompt lengths or structures matching known attack templates. Aggregate per user/session to catch slow, multi-turn attacks.
6. **Isolate and rate-limit.** Run the LLM service with least-privilege credentials, network egress restricted to required endpoints, and per-user/per-tenant rate limits. A compromised agent session should not be able to enumerate your internal network or exfiltrate at line speed.
7. **Test the guardrails adversarially.** Run the red-team suite (see the promptfoo playbook) against the full system with guardrails enabled. Every bypass becomes a guardrail improvement ticket. Re-test after each guardrail change — filters interact in surprising ways.
8. **Plan the guardrail-failure response.** Define what happens on trigger: block, redact-and-continue, or step-up authentication. Log every trigger with the input, output, and decision. Review triggers weekly — a guardrail that fires constantly on legitimate use is misconfigured and will be disabled by frustrated users.

## Expected outputs

- A trust-boundary map with controls at each crossing: input filters, tool allowlists, output scanners.
- Human-confirmation gates on irreversible actions; rate limits and least-privilege service credentials.
- Guardrail trigger logging with weekly review and adversarial regression testing.

## Pitfalls

- Guardrails only at the model layer — the system prompt is not a security control; assume it can be bypassed.
- Treating retrieved/RAG content as trusted — indirect prompt injection is the dominant real-world LLM attack.
- Output filters with no human review loop — false positives train users to work around the guardrails.
- Unbounded tool access "for now" — the agent's capabilities are the blast radius; scope them first.
- Logging prompts without a data-retention and privacy policy — prompts contain user PII and secrets.

## References

- OWASP Top 10 for LLM Applications — guardrail-relevant risks (LLM01–LLM10)
- NIST AI 600-1 (Generative AI Profile) — risk management for GenAI systems
- MITRE ATLAS — mitigations mapped to AI attack techniques
- Anthropic / OpenAI system-card and safety documentation for layered-defense patterns
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
