---
skill_id: cyber_detecting_model_extraction_attacks
name: Detecting Model Extraction Attacks
description: Detect adversaries stealing ML models via systematic API querying.
risk: low
permissions: []
requires_confirmation: false
tags: [ml-security, api, detection]
version: 1.0.0
---
## Purpose

Model extraction (model stealing) attacks reconstruct a proprietary ML model by making large numbers of carefully chosen queries to a prediction API and training a substitute on the responses. This playbook helps defenders of ML-powered services detect extraction campaigns in API telemetry — before the model's intellectual property walks out the door one query at a time.

## When to use

- Your organization serves proprietary ML models via API and needs extraction defenses.
- API analytics show a client with unusual query volume or patterns.
- Threat modeling identified model theft as a business risk.
- Evaluating ML-security controls for a production inference service.

## Prerequisites

- Inference API access logs with per-client identity (API key, IP, account), query payloads or payload hashes, timestamps, and response metadata.
- Baseline of legitimate query patterns: volume, feature-space coverage, and temporal distribution per client type.
- Knowledge of the model's input space and which query patterns are 'informative' for extraction (boundary probing, synthetic distributions).
- Rate-limiting and API-management infrastructure you can act through.

## Procedure

1. Define what extraction looks like in your logs. Extraction campaigns show: high query volume from a single client, systematic coverage of the input/feature space (grid-like or adaptive sampling rather than organic distributions), repeated near-duplicate queries with small perturbations (boundary probing), and queries concentrated on low-confidence regions. Document these as your detection hypotheses.
2. Build volume-and-coverage analytics. Alert on clients exceeding statistical volume thresholds, then weight by feature-space coverage: a client querying uniformly across the input domain is more suspicious than one with clustered, application-like queries. Track unique-input entropy per client — extraction maximizes information per query.
3. Detect adaptive querying patterns. Extraction often proceeds in rounds: an initial broad sample, then focused queries near decision boundaries. Look for sequential patterns where a client's query distribution shifts toward low-margin regions, or where query batches correlate with model-update cycles (re-extracting after retraining).
4. Correlate with account and infrastructure signals. Extraction clients often use newly created accounts, free-tier abuse, multiple API keys from one operator, or distributed IPs to evade per-key limits. Join API telemetry with account-creation data and IP reputation — the campaign view matters more than any single key.
5. Respond with graduated controls. For suspected extraction: tighten rate limits for the client, require stronger authentication or contracts for high-volume access, add query watermarking or perturbation defenses if available, and preserve full query logs for IP/legal action. Avoid tipping off the operator before evidence is preserved.
6. Harden the API against extraction structurally: per-client rate limits and quotas, output perturbation or confidence rounding, query pricing that makes extraction uneconomical, monitoring for substitute-model training signals, and legal/ToS terms prohibiting extraction with a defined enforcement path.

## Expected outputs

- Extraction detection analytics: volume, feature-space coverage, boundary-probing patterns per client.
- Graduated response playbook: rate-limit → challenge → suspend → legal, with evidence-preservation steps.
- API hardening controls: quotas, output perturbation, ToS terms.
- Baseline of legitimate client query patterns for tuning.

## Pitfalls

- High-volume legitimate clients (batch integrations, resellers) look like extraction — baseline per client type.
- Per-IP detection fails against distributed querying; aggregate by account/key and behavioral fingerprint.
- Overly aggressive rate limiting breaks legitimate users — graduate responses, don't nuke on first alert.
- Query payloads may be sensitive — handle logs under the same privacy controls as production data.
- Extraction can be slow (weeks) — detection windows must span long periods, not just hourly spikes.

## References

- NIST AI 100-2e2025 (adversarial ML taxonomy); MITRE ATLAS (Adversarial Threat Landscape for AI Systems) — https://atlas.mitre.org/ (ML attack techniques including extraction); OWASP Top 10 for LLM/ML Applications guidance
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
