---
skill_id: cyber_securing_agentic_ai_tool_invocation
name: Securing Agentic AI Tool Invocation
description: Harden AI agent tool use: least-privilege tools, human approval gates, and audit logging of invocations.
risk: info
permissions: []
requires_confirmation: false
tags: [ai-security, agents, hardening]
version: 1.0.0
---
## Purpose
AI agents that can call tools (run code, query databases, send messages) turn prompt injection into real-world impact. This playbook hardens the tool-invocation layer: least-privilege tool design, confirmation gates for consequential actions, and complete audit logging, so a manipulated agent cannot silently cause harm.

## When to use
- Designing or reviewing an AI agent with tool-calling capabilities.
- After a prompt-injection incident or red-team finding against your agent.
- Procurement review of third-party agentic AI products.
- Defining AI security standards for development teams.

## Prerequisites
- Inventory of tools exposed to the agent with their permissions and side effects.
- Classification of actions by consequence (read-only vs state-changing vs external).
- Human-in-the-loop workflow capability in the agent framework.
- Centralized logging for agent decisions and tool calls.

## Procedure
1. Catalog every tool: what it does, what credentials it holds, and what damage misuse could cause.
2. Apply least privilege: narrow tool scopes, read-only variants where possible, and short-lived credentials.
3. Require explicit human approval for consequential actions (payments, data deletion, external sends, privilege changes).
4. Validate tool arguments server-side; never trust the model's parameter choices blindly.
5. Separate tool results from instructions: treat retrieved content as untrusted data, never as new directives.
6. Log every invocation with the prompt context, arguments, approver (if any), and outcome; retain for investigation.
7. Rate-limit and anomaly-monitor tool usage: bursts, unusual tools, or off-hours activity trigger review.
8. Test with adversarial prompts regularly; confirm that injection attempts cannot bypass approval gates.
9. Maintain an allowlist of tools per agent role; new tools require security review before enablement.
10. Scope and expire agent memory; long-lived memory can be poisoned across sessions.
11. Test the approval gate under adversarial prompts, not just happy-path flows.

## Expected outputs
- Tool inventory with privilege ratings and approval requirements.
- Approval-gate design for consequential actions.
- Audit logging specification and monitoring rules for agent tool use.
- Per-role tool allowlist with review records.
- Agent memory scoping and expiry policy.
- Adversarial approval-gate test results.

## Pitfalls
- Prompt-level instructions ('never do X') are not security boundaries; enforce in code.
- Overly broad tools (e.g. 'run any SQL') defeat least privilege; split into narrow tools.
- Approval fatigue leads to rubber-stamping; reserve gates for truly consequential actions.
- Tool output containing injected instructions is the top bypass vector; sanitize and delimit.
- Long agent memory can be poisoned across sessions; scope and expire stored context.
- Tool descriptions themselves can contain injected instructions; treat them as untrusted.
- Multi-agent handoffs multiply the injection surface; validate at each boundary.
- Shadow AI agents built by business units bypass every control here; discover them through network and SaaS monitoring.

## References
- OWASP GenAI Top 10 and Agentic AI guidance (genai.owasp.org).
- NIST AI 100-2e, Adversarial Machine Learning taxonomy.
- Anthropic/industry guidance on agent safety (named, vendor docs).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
