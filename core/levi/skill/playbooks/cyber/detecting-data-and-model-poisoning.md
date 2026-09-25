---
skill_id: cyber_detecting_data_and_model_poisoning
name: Detecting Data and Model Poisoning
description: Detect training-data and model poisoning with provenance tracking, statistical validation, and behavior monitoring.
risk: info
permissions: []
requires_confirmation: false
tags: [ai-security, mlops, detection]
version: 1.0.0
---
## Purpose

Detect poisoning of AI training data and models — malicious samples inserted to plant backdoors, skew behavior, or degrade performance — through data provenance, statistical validation, and post-deployment behavior monitoring. Poisoning is subtle by design; detection must be systematic.

## When to use

- Operating ML pipelines that ingest third-party, crowdsourced, or web-scraped data.
- Validating models before production deployment (model acceptance testing).
- Investigating unexpected model behavior (targeted misclassifications, bias shifts).
- Building MLOps security controls for regulated AI deployments.

## Prerequisites

- Data lineage tracking: every training sample traceable to its source.
- Baseline model performance metrics and behavioral test suites.
- Access to training data and pipeline logs for forensic analysis.
- A model registry with versioning and approval gates.

## Procedure

1. **Enforce data provenance.** Record the source, collection method, and timestamp for every training sample. Data without provenance doesn't enter training — this single rule eliminates the easiest poisoning vector (anonymous bulk submissions). Maintain an allowlist of trusted data sources with integrity checks.
2. **Validate data statistically before training.** Run automated checks on each data batch: label distribution vs. historical norms, feature-value outliers, duplicate/near-duplicate clusters (poisoning often injects many similar samples), and embedding-space anomalies. Flag batches that deviate — investigate before they enter the training set, not after the model misbehaves.
3. **Scan for known poisoning patterns.** Check for: trigger-pattern samples (identical patches/watermarks across many samples — the backdoor signature), label-flipping clusters (many samples of class A labeled as class B), and samples crafted to sit near decision boundaries. Maintain a library of published poisoning techniques and test each new dataset against them.
4. **Test the trained model adversarially.** Before deployment, run: backdoor trigger tests (does a specific pattern cause targeted misclassification?), performance on clean holdout data vs. training data (large gaps suggest memorized poison), and behavioral probes for the threat model (targeted errors an attacker would want). A model that fails these doesn't deploy — it gets investigated.
5. **Monitor deployed models for poisoning symptoms.** Alert on: sudden accuracy drops on specific classes or slices, predictions that correlate with suspicious input patterns, and user reports of targeted bad behavior. Log prediction inputs (with privacy controls) so you can forensically examine what triggered the anomaly.
6. **Investigate with data forensics.** When poisoning is suspected: identify the suspicious samples via influence analysis (which training samples most affected the bad behavior?), trace them to their source via provenance records, and check whether the source is compromised or malicious. Remove the poisoned samples, retrain, and re-run the adversarial tests.
7. **Harden the pipeline.** Implement: signed datasets with integrity verification, access controls on training data (who can add samples?), anomaly detection as a permanent pipeline stage, and model signing so deployed models are traceable to validated training runs. Poisoning defense is supply-chain defense applied to data.

## Expected outputs

- Provenance-tracked training data with statistical validation gates before training.
- Pre-deployment adversarial testing (backdoor, performance-gap, behavioral probes).
- Deployed-model behavior monitoring with data-forensic investigation procedures.

## Pitfalls

- Training on unprovenanced data — you can't investigate poisoning you can't trace.
- Validating only aggregate accuracy — poisoning targets specific behaviors that aggregates hide.
- No holdout data — without clean test data, you can't measure the damage.
- Treating data pipelines as non-security infrastructure — the pipeline is the attack surface.
- Deploying without adversarial testing — the backdoor ships to production silently.

## References

- NIST AI 600-1 (Generative AI Profile) — data integrity and poisoning risks
- MITRE ATLAS — ML attack techniques including data poisoning
- Published research on backdoor and data-poisoning attacks for test design
- OWASP Top 10 for LLM Applications — LLM03 (Training Data Poisoning)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
