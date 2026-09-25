---
skill_id: cyber_implementing_security_chaos_engineering
name: Implementing Security Chaos Engineering
description: Run controlled security chaos experiments — fault injection against security controls — with blast-radius limits and rollback plans.
risk: moderate
permissions: []
requires_confirmation: true
tags: [testing, resilience, devops]
version: 1.0.0
---
## Purpose

Security chaos engineering deliberately injects failures — killing
security agents, simulating control-plane outages, dropping log
pipelines — to prove that security controls actually work under failure
conditions. This playbook covers designing and running these experiments
safely: hypothesis-driven, blast-radius-limited, and fully reversible.

## When to use

- Validating that detections fire when an EDR agent dies or logs stop
  flowing.
- Testing failover of security infrastructure (SIEM ingestion,
  authentication, secrets management).
- Building confidence in incident-response under degraded conditions.
- Maturing a resilience program beyond tabletop exercises.

## Prerequisites

- Explicit authorization for each experiment: scope, blast radius,
  duration, and abort criteria — chaos experiments intentionally
  degrade production-adjacent systems.
- A non-production or carefully ring-fenced environment for initial
  experiments; production only after proven safety.
- Real-time monitoring of both the experiment and business health
  metrics, with automated abort triggers.
- An incident-command structure on standby during experiments.

## Procedure

1. **Start with a hypothesis.** Frame each experiment as falsifiable:
   "If the EDR agent is killed on 5% of workstations, the SOC detects
   the coverage gap within 15 minutes via the health dashboard." No
   hypothesis, no experiment.
2. **Define blast radius and abort criteria.** Limit scope (host count,
   percentage, time window), define steady-state business metrics that
   must not degrade, and set automatic abort triggers (error-rate
   thresholds, manual abort command). Document the rollback procedure
   before starting.
3. **Begin with security-control failures.** High-value first
   experiments: kill EDR agents, block SIEM ingestion, expire
   certificates, revoke secrets-manager access, simulate IdP outage.
   These reveal whether your security posture degrades silently.
4. **Run during business hours with full staffing.** Counterintuitively,
   run when the team is present to observe and abort — not at 2 AM.
   Notify stakeholders in advance; surprise chaos is just an outage.
5. **Observe detection and response, not just recovery.** Measure:
   time to detect the injected failure, whether alerts fired
   correctly, whether runbooks worked under degraded conditions, and
   whether business impact stayed within bounds.
6. **Roll back and verify.** Execute the rollback plan, verify full
   restoration (agents healthy, logs flowing, certs valid), and
   confirm no residual experiment artifacts remain.
7. **Convert findings to improvements.** Every experiment should
   produce: fixed monitoring gaps, improved runbooks, or architectural
   changes (e.g. local log buffering when SIEM ingestion fails).
   Track these to completion — experiments without follow-through are
   risk without value.
8. **Mature the program.** Progress from manual, narrow experiments to
   scheduled, broader ones; build a library of experiment definitions
   under version control; and integrate chaos results into resilience
   metrics reported to leadership.

## Expected outputs

- Experiment definitions: hypothesis, blast radius, abort criteria,
  rollback plan.
- Execution records with detection/response measurements.
- Findings converted to tracked improvements.
- A versioned experiment library and program metrics.

## Pitfalls

- Experiments without abort criteria or rollback plans — this is
   how chaos engineering becomes an actual incident.
- Running in production before proving safety in staging —
   graduate environments deliberately.
- Surprising stakeholders — notify in advance and staff the
   experiment; stealth chaos destroys trust.
- Measuring only recovery time — the security value is in
   detection/response under degradation, not just MTTR.
- Experimenting on compliance-critical controls without assessing
   regulatory impact — some failures must be reported.

## References

- "Chaos Engineering" (O'Reilly) — principles adapted for security
- NIST SP 800-160 Vol. 2: cyber resiliency engineering constructs
- SRE workbook chapters on chaos engineering (Google)
- MITRE: cyber-resiliency and detection-validation methodologies
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
