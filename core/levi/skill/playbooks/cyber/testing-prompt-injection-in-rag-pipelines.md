---
skill_id: cyber_testing_prompt_injection_in_rag_pipelines
name: Testing Prompt Injection in RAG Pipelines
description: Authorized testing of retrieval-augmented generation pipelines for indirect prompt injection via documents.
risk: low
permissions: []
requires_confirmation: false
tags: [ai-security, rag, testing]
version: 1.0.0
---
## Purpose
RAG pipelines feed untrusted documents into the model's context, enabling indirect prompt injection: instructions hidden in web pages, PDFs, or tickets that hijack the assistant's behavior. This playbook covers authorized testing of your own RAG systems for these flaws and the architectural mitigations that contain them.

## When to use
- Security review of a RAG-based assistant or search product.
- After adding new document sources or tool-calling to a RAG system.
- Validating mitigations for a reported indirect-injection issue.
- Building detection for injection attempts in retrieval logs.

## Prerequisites
- Authorization for the target RAG system and a test deployment.
- Ability to plant test documents in the retrieval corpus.
- Understanding of the pipeline: chunking, retrieval, prompt assembly, and tool access.
- Logging of retrieved chunks per query for analysis.

## Procedure
1. Map the pipeline: which sources are ingested, how chunks are selected, and what the model can do with tools.
2. Plant test documents containing injected instructions (ignore prior instructions, exfiltrate data, call tools).
3. Query the system with benign prompts that retrieve the poisoned chunks; observe whether injected instructions are followed.
4. Test exfiltration paths: can injected instructions cause the model to reveal other retrieved documents or call tools?
5. Test source-based trust: does content from low-trust sources get the same authority as internal docs?
6. Harden: delimit and label retrieved content as untrusted data, apply least-privilege tools, require confirmation for consequential actions, and consider instruction hierarchy enforcement.
7. Build detection: scan ingested documents for instruction-like patterns; alert on tool calls following retrieval of flagged chunks.
8. Re-test after mitigations with fresh injection variants.
9. Test multi-hop exfiltration: an injected document instructing summarization of another sensitive document.
10. Test with realistic chunking and overlap; per-chunk filters can be bypassed at boundaries.
11. Verify that retrieved-document citations do not leak existence of restricted documents.

## Expected outputs
- Injection test results per document source and query type.
- Findings with data-exfiltration or tool-misuse impact.
- Hardened pipeline design and detection rules.
- Multi-hop exfiltration test results.
- Chunk-boundary bypass assessment.
- Citation-leakage review.

## Pitfalls
- Blocking exact phrases is brittle; attackers rephrase. Architectural separation is the durable fix.
- Retrieval ranking can be manipulated (poisoned SEO); treat ranking as attacker-influenced.
- Tool-calling RAG systems turn injection into action; assess tool blast radius first.
- User-uploaded documents are the highest-risk source; apply the strictest handling there.
- Chunk overlap can smuggle injected text past per-chunk filters; test with realistic chunking.
- Citations confirming a restricted document exists are an information leak by themselves.
- Re-ranking models can be manipulated by poisoned content; treat ranking as untrusted.
- Retrieval relevance tuning can be gamed by poisoned documents; monitor ranking shifts.

## References
- OWASP GenAI Top 10: prompt injection (genai.owasp.org).
- NIST AI 100-2e, Adversarial Machine Learning taxonomy.
- Research literature on indirect prompt injection (named).
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
