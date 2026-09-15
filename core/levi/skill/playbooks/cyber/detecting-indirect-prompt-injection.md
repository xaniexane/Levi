---
skill_id: cyber_detecting_indirect_prompt_injection
name: Detecting Indirect Prompt Injection
description: Detect prompt injection delivered through retrieved content — documents, web pages, and tool outputs — in RAG and agent systems.
risk: info
permissions: []
requires_confirmation: false
tags: [ai-security, llm, detection]
version: 1.0.0
---
## Purpose

Detect indirect prompt injection — malicious instructions hidden in the content your LLM retrieves (documents, web pages, emails, tool outputs) rather than in user input. This is the dominant real-world LLM attack pattern, and it bypasses every input filter aimed at the user.

## When to use

- Operating RAG systems, AI agents with tool access, or copilots that process external content.
- Investigating suspected manipulation via retrieved documents or web content.
- Building detection for the AI supply chain (poisoned data sources).
- Validating that content-boundary controls actually work.

## Prerequisites

- Logging of retrieved content, prompts (with content delineation), model outputs, and tool calls.
- Inventory of data sources the LLM ingests, with trust levels assigned.
- Baseline of normal tool-call patterns for agentic systems.
- Alerting path with session-termination authority for active exploitation.

## Procedure

1. **Map and trust-tier your content sources.** Inventory every source the LLM can retrieve: internal docs, external web, user uploads, emails, tool outputs. Assign trust tiers — and treat anything below the top tier as untrusted input. Most indirect injections arrive via the sources nobody classified.
2. **Scan retrieved content for injection patterns.** Before content reaches the model (or in parallel for detection), scan for: instruction-like language ("ignore previous instructions," "system:" role markers), hidden text (white-on-white, zero-font, metadata instructions), and multilingual obfuscation. Log matches with the source document — the detection is also the compromised-source identification.
3. **Enforce and monitor content boundaries.** Retrieved content must be structurally delineated from instructions (delimiters, separate roles, or architectural separation). Alert on: model outputs that quote or follow instructions appearing only in retrieved content, tool calls referencing content-derived instructions, and outputs that contradict the system prompt after ingesting external content.
4. **Detect the exploitation, not just the payload.** The injection succeeds when the model acts on it. Alert on: tool calls the user didn't request following content retrieval, data exfiltration patterns (sending retrieved sensitive data to external destinations), privilege-escalation attempts via tool use, and outputs containing content the user shouldn't see (the injection exfiltrating through the model's response).
5. **Monitor data sources for poisoning.** Periodically re-scan high-value sources for newly added injection payloads. Alert on: unexpected modifications to trusted documents, new external sources added to retrieval, and user-uploaded content with injection patterns. The poisoned source is patient — it waits for someone to ask the right question.
6. **Correlate with the attack chain.** Join injection detections with: who triggered the retrieval (compromised account?), the source's provenance (who published the poisoned document?), and what the model did with it (which tools, what data). Indirect injection is often one stage of a larger attack — the document, the trigger, and the exploitation form the incident.
7. **Respond by quarantining the source.** On confirmation: remove or quarantine the poisoned content source, terminate affected sessions, audit what the model did under injection (tool calls, data accessed), and notify users who may have received tainted outputs. Then fix the architecture: stricter source trust tiers, content sanitization, and tool-call confirmation for injection-sensitive operations.

## Expected outputs

- Trust-tiered content-source inventory with injection-pattern scanning on retrieval.
- Content-boundary monitoring with exploitation detection (unauthorized tool calls, exfiltration).
- Source-quarantine response with architecture fixes (sanitization, trust tiers, confirmations).

## Pitfalls

- Filtering only user input — indirect injection bypasses user-input controls entirely.
- Treating internal documents as trusted — insiders and compromised accounts poison internal sources too.
- No content delineation — if the model can't distinguish instructions from data, neither can your filters.
- Detecting the payload but missing the exploitation — the scan caught it but the model still acted.
- One-time source scanning — poisoning is added over time; monitoring must be continuous.

## References

- OWASP Top 10 for LLM Applications — LLM01 (Prompt Injection), indirect variants
- MITRE ATLAS — indirect prompt injection techniques
- Published research on indirect prompt injection (retrieval and agent contexts)
- NIST AI 600-1 (Generative AI Profile)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
