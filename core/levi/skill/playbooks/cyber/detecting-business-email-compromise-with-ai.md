---
skill_id: cyber_detecting_business_email_compromise_with_ai
name: Detecting Business Email Compromise with AI
description: Apply ML/NLP models to email content, behavior, and graph signals for AI-assisted BEC detection.
risk: info
permissions: []
requires_confirmation: false
tags: [email, fraud, ai-security]
version: 1.0.0
---
## Purpose

Augment rule-based BEC detection with machine learning: NLP models that catch impersonation language, behavioral models that learn each executive's communication patterns, and graph analysis that spots anomalous sender relationships. AI catches the BEC that follows no known rule — the novel phrasing, the patient attacker, the subtle compromise.

## When to use

- BEC attacks are bypassing existing rule-based email controls.
- Tuning or evaluating an AI/ML email-security product's effectiveness.
- Building in-house ML detection on email telemetry.
- Reducing false positives from broad BEC rules without losing coverage.

## Prerequisites

- Labeled email data: confirmed BEC samples and representative benign mail for training/evaluation.
- Email telemetry: full headers, body text, attachment metadata, sender history, and mailbox audit logs.
- A baseline understanding of current BEC detection performance (precision/recall) to measure improvement.
- Privacy and legal review for ML processing of email content.

## Procedure

1. **Define the ML detection targets.** Separate the problems: (a) impersonation classification — is this message pretending to be someone it isn't? (b) behavioral anomaly — does this deviate from how this sender normally communicates? (c) intent classification — does this message seek a fraudulent payment or credential? Different models, different features, different thresholds.
2. **Engineer features defenders understand.** For NLP: urgency/secrecy language markers, authority-appeal phrases, instruction-change language ("updated bank details"), and stylometric deviation from the purported sender's history. For behavior: sender-recipient graph novelty, time-of-day deviation, first-contact patterns, and reply-chain hijacking signals. For headers: authentication results, infrastructure novelty, display-name mismatches.
3. **Train and validate with realistic data.** Use confirmed BEC samples plus hard negatives (legitimate urgent payment requests — the model's hardest job). Evaluate with precision/recall at the operating threshold, not just AUC; a model with 99% AUC that fires on every urgent invoice is operationally useless. Validate on time-separated data — BEC tactics drift.
4. **Deploy as risk scoring, not binary blocking.** Output a BEC risk score per message feeding the SOC queue and the email gateway (quarantine at high scores, banner at medium). Binary ML blocking on email creates both missed fraud and blocked business — scoring with human review at the top end is the operational sweet spot.
5. **Build the feedback loop.** Every analyst verdict (true BEC, false positive) retrains or re-tunes the model. Track feature drift: when attackers change phrasing, the NLP features decay — monitor model performance monthly and refresh training data quarterly. An unmaintained ML model is worse than rules because its failures are silent.
6. **Combine with non-ML signals.** The strongest BEC detection fuses ML content scores with deterministic signals: mailbox-rule creation, impossible-travel logons, DMARC failures, and payment-process anomalies. No single signal should convict alone — the ensemble is the detection.
7. **Measure business impact, not just model metrics.** Track: BEC attempts caught, false-positive rate on legitimate finance mail, analyst time per verdict, and — most importantly — fraud losses prevented versus the pre-AI baseline. Report these to justify the investment and guide tuning.

## Expected outputs

- ML models for impersonation, behavioral anomaly, and fraud-intent scoring on email.
- Risk-scored email pipeline with quarantine/banner tiers and analyst feedback loop.
- Monthly performance monitoring with quarterly retraining; business-impact metrics reported.

## Pitfalls

- Training on easy negatives — the model learns to flag urgency, not fraud, and finance hates it.
- Deploying binary ML blocking — the false positives will get the model disabled.
- No drift monitoring — attacker phrasing evolves and the model silently decays.
- Ignoring privacy review — ML on email content needs legal sign-off and data handling rules.
- Treating the vendor's "AI" as magic — demand precision/recall numbers on your data, not marketing.

## References

- NIST AI 600-1 (Generative AI Profile) — AI risk management considerations
- FBI IC3 data on BEC losses — the business case for detection investment
- Published research on stylometric and behavioral BEC detection
- Vendor-agnostic ML evaluation guidance (precision/recall at operating thresholds)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
