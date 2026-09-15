---
skill_id: cyber_testing_for_system_prompt_leakage
name: Testing for System Prompt Leakage
description: Authorized testing of your own AI assistants for system prompt extraction, with hardening and detection.
risk: low
permissions: []
requires_confirmation: false
tags: [ai-security, llm, testing]
version: 1.0.0
---
## Purpose
System prompts often contain proprietary instructions, hidden capabilities, and sometimes secrets. Attackers extract them with crafted queries. This playbook covers authorized testing of your organization's own AI assistants for prompt leakage, hardening the prompt architecture, and detecting extraction attempts in logs. Test only systems you own, in non-production where possible.

## When to use
- Pre-release review of a new AI assistant or chatbot.
- After changing system prompts or adding sensitive instructions.
- Validating mitigations for a reported prompt-extraction issue.
- Building detection for prompt-extraction attempts in production logs.

## Prerequisites
- Authorization for the target assistant and its test environment.
- Copy of the system prompt under test (to judge what leaked).
- Understanding of the assistant's tool access and data boundaries.
- Log access for reviewing test conversations.

## Procedure
1. Baseline the assistant's normal refusal and instruction-following behavior.
2. Attempt direct extraction: ask for the system prompt, instructions, or configuration verbatim.
3. Try indirect extraction: ask it to repeat, summarize, translate, or encode its instructions.
4. Try multi-turn and role-play framings that recontextualize the assistant as a different persona.
5. Test whether leaked content includes anything sensitive: credentials, internal URLs, hidden tools.
6. Harden: move secrets out of the prompt entirely, keep instructions minimal, separate system/user channels, and add output filtering for prompt-like content.
7. Build detection: log patterns matching extraction attempts (verbatim requests, encoding tricks) and alert on successes.
8. Re-test after hardening; extraction resistance degrades as models and prompts change.
9. Test whether the assistant reveals tool definitions or hidden capabilities, not just prompt text.
10. Check whether prompt caching or logging stores the system prompt in retrievable logs.
11. Test multi-modal inputs where supported; images can carry extraction instructions too.

## Expected outputs
- Extraction test results: techniques tried, what leaked, severity.
- Hardened prompt architecture with secrets removed.
- Detection rules for extraction attempts.
- Tool and capability disclosure assessment.
- Prompt-storage and log-access review.
- Multi-modal extraction test results.

## Pitfalls
- Anything in the prompt must be treated as potentially public; never put secrets there.
- Refusal training varies by model; re-test on every model or version change.
- Partial leaks (capability hints, tool names) still aid attackers; assess more than verbatim theft.
- Over-aggressive output filters break legitimate use; tune on real conversation data.
- Prompt caching or logging may store the system prompt in retrievable logs; check log access.
- Partial capability disclosure helps attackers plan; assess more than verbatim theft.
- Fine-tuned behaviors can leak training instructions; test beyond the system prompt.
- Error messages from the model backend can leak prompt fragments; review error handling.

## References
- OWASP GenAI Top 10: sensitive information disclosure (genai.owasp.org).
- NIST AI 100-2e, Adversarial Machine Learning taxonomy.
- Model provider documentation on system prompt handling.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
