---
skill_id: cyber_detecting_ai_model_prompt_injection_attacks
name: Detecting AI Model Prompt Injection Attacks
description: Detect direct prompt-injection attempts against LLM deployments with layered input, behavior, and output monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [ai-security, detection, llm]
version: 1.0.0
---
## Purpose

Catch attackers trying to hijack your LLM's instructions — "ignore previous instructions," role-play jailbreaks, and instruction-override payloads — by monitoring inputs, model behavior, and outputs together. No single signal is reliable; the combination is.

## When to use

- Operating a production LLM feature exposed to untrusted users.
- Investigating suspected manipulation of an AI assistant or agent.
- Building detection content for the AI security monitoring program.
- Validating that guardrails are actually catching injection attempts (detection proves the control works).

## Prerequisites

- Logging of prompts, completions, and tool calls from the LLM deployment (with a privacy/retention policy).
- A baseline of normal prompt patterns for the application (lengths, languages, topics).
- SIEM or analytics pipeline that can run pattern and anomaly detection on the logs.
- Defined severity tiers: what counts as a probe versus an active exploitation attempt.

## Procedure

1. **Build the injection signature library.** Maintain patterns for known attack classes: instruction-override phrases ("ignore all previous instructions," "you are now in developer mode"), delimiter attacks (fake system/user role markers), encoding tricks (Base64/leet-speak payloads hiding instructions), and prompt-leak probes ("repeat your instructions verbatim"). Update monthly from published research and your own red-team findings.
2. **Monitor inputs for attack patterns.** Run the signature library against incoming prompts in near real time. Score and alert on matches, but tune for the application's context — a coding assistant legitimately sees "ignore previous" in code comments. Context-aware scoring beats raw pattern matching.
3. **Detect behavioral anomalies in conversations.** Alert on: rapid refusal-then-retry sequences (the attacker iterating on a jailbreak), sudden language or topic shifts mid-session, prompts far outside the length distribution, and sessions with high refusal rates. Aggregate per user and per session — single-turn analysis misses multi-turn jailbreaks.
4. **Watch for prompt-leak and exfiltration signals in outputs.** Scan completions for: verbatim system-prompt fragments, internal hostnames/API keys/PII that shouldn't be in outputs, and tool calls the user didn't request. An injection that succeeds looks like the model doing something it shouldn't — the output is often the clearest signal.
5. **Monitor tool-use anomalies for agentic systems.** Alert when the agent invokes tools outside its normal distribution, chains tools in novel sequences, or attempts privileged operations after a suspicious prompt. Tool-call logs are the audit trail of what the injection actually achieved — prioritize these alerts highest.
6. **Correlate with identity and infrastructure signals.** Join injection attempts with: the user's identity and history (new account? previously flagged?), source IP/ASN reputation, and concurrent suspicious activity (credential stuffing against the same account). A jailbreak attempt from a Tor exit node on a day-old account is a different story than a curious employee.
7. **Respond with graduated actions.** First detection: log and monitor. Repeated attempts: rate-limit or challenge the session. Active exploitation (tool misuse, data exfiltration): terminate the session, revoke tokens, and open an incident. Pre-define these tiers so response is automatic, not debated.
8. **Close the loop with the red team and guardrails.** Every confirmed bypass becomes a new signature, a new red-team test case, and a guardrail improvement ticket. Track injection-attempt volume and success rate over time — a rising success rate means your defenses are decaying.

## Expected outputs

- A maintained injection-signature library with input monitoring and context-aware scoring.
- Behavioral and tool-use anomaly detections with graduated response tiers.
- Correlated identity/infrastructure context on attempts; closed-loop feedback to red-teaming and guardrails.

## Pitfalls

- Relying on input patterns alone — novel injections bypass signatures; behavior and output monitoring catch what patterns miss.
- Alerting on every pattern match without context — false positives train analysts to ignore the feed.
- No output monitoring — you detect the attempt but miss the successful exfiltration.
- Logging prompts without a privacy policy — prompts contain user PII; retention and access need governance.
- Treating blocked attempts as the end of the story — the attacker's next attempt is already being crafted.

## References

- OWASP Top 10 for LLM Applications — LLM01 (Prompt Injection)
- MITRE ATLAS — prompt-injection techniques and mitigations
- NIST AI 600-1 (Generative AI Profile)
- Published jailbreak/prompt-injection research for signature development
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
