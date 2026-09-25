---
skill_id: cyber_implementing_aws_security_hub
name: AWS Security Hub Implementation
description: Centralize AWS security findings in Security Hub with standardized severity and automated response.
risk: low
permissions: []
requires_confirmation: false
tags: [aws, siem]
version: 1.0.0
---
## Purpose
AWS security findings scatter across GuardDuty, Inspector, Macie, IAM Access Analyzer, and partner
products — each with its own console and severity scale. Security Hub aggregates them into one
normalized view (ASFF), so the SOC triages a single prioritized queue instead of five. This playbook
implements Security Hub with proper finding ingestion, severity standardization, and automated
response wiring.

## When to use
- Centralizing cloud security operations for a single- or multi-account AWS estate.
- After incidents where a finding existed in a service console but nobody looked at it.
- Meeting continuous-monitoring requirements (SOC 2, PCI DSS, CIS) with aggregated evidence.
- As the aggregation layer for GuardDuty, Inspector, Macie, and third-party findings.
- Before scaling past a handful of accounts, where per-console triage stops working.

## Prerequisites
- A designated Security Hub administrator account (via Organizations) and member-account enrollment.
- Source services enabled: GuardDuty, Inspector, Macie, IAM Access Analyzer as applicable.
- Defined severity mapping: how your SOC treats Critical/High/Medium/Low, and which severities page
  vs. ticket.
- An EventBridge/SNS/ticketing destination for automated finding routing.
- IAM permissions for the administrator account to manage Security Hub and member associations.

## Procedure
1. **Designate the administrator and enable.** In the Organizations management or delegated admin
   account, designate the Security Hub administrator, then enable Security Hub in each in-scope
   region. Enablement is per-region — document which regions are in scope and why others are
   excluded.
2. **Enroll member accounts.** Invite or auto-enroll member accounts (auto-enrollment for new
   accounts via Organizations prevents gaps). Verify every account shows as associated; unassociated
   accounts are blind spots.
3. **Enable the security standards.** Turn on the standards you will be measured against: CIS AWS
   Foundations, PCI DSS, and/or NIST 800-53. These generate compliance controls findings — the
   continuous-audit feed. Disable individual controls only with documented justification.
4. **Connect finding providers.** Enable integrations for GuardDuty, Inspector, Macie, IAM Access
   Analyzer, and any partner products (Wiz, CrowdStrike, etc.). Confirm findings flow: generate a
   test finding or check the Findings page per provider within 24 hours.
5. **Standardize severity and workflow.** Define: Critical/High findings create tickets with SLAs
   and page for active threats (GuardDuty Trojan/EC2 findings); Medium/Low aggregate into daily
   review. Set Workflow Status conventions (New → Notified → Resolved) so triage state is
   consistent.
6. **Build EventBridge automation.** Create rules on the Security Hub Findings event source: route
   by severity, standard, and resource type. Automate: ticket creation with enriched context
   (account, region, resource, remediation link), Slack/Teams notification for Criticals, and
   auto-remediation triggers for safe fixes (via SSM, as in the Config playbook).
7. **Suppress deliberately, not lazily.** Use suppression rules only for documented false positives
   or accepted risks, with notes explaining why and an expiry. Review suppressions monthly — stale
   suppressions hide real findings.
8. **Tune to kill noise.** Common noise sources: Inspector findings on dev AMIs, Macie findings on
   test buckets, compliance controls not applicable to an account type. Scope standards per OU and
   tune provider severity before the SOC learns to ignore the queue.
9. **Run a daily triage ritual.** SOC reviews New Critical/High findings within the SLA, updates
   Workflow Status, and links tickets. Weekly: review aging findings and suppression list. Monthly:
   trend report — new findings by severity, MTTR, top offending accounts/resources.
10. **Retain and evidence.** Security Hub findings feed audit evidence for continuous compliance.
    Export finding history (or retain via the aggregator) for the audit lookback period, and
    document the triage and remediation process as the control narrative.

## Expected outputs
- Security Hub enabled with administrator/member structure across in-scope regions and accounts.
- Enabled security standards with documented control exclusions.
- Provider integrations verified flowing; severity and workflow conventions documented.
- EventBridge automation: ticketed, paged, and auto-remediated findings by severity.
- Daily triage ritual, monthly trend reporting, and audit-ready finding history.

## Pitfalls
- Per-region enablement forgotten: findings in non-enabled regions never appear. Maintain a
  region-scope list and check it when AWS launches new regions you adopt.
- Member accounts never associated: new accounts via Control Tower/Organizations need
  auto-enrollment or they stay dark.
- Alerting on raw finding volume: hundreds of Medium Inspector findings per day will bury the two
  Critical GuardDuty findings that matter. Severity routing is the whole game.
- Suppression as a noise strategy: suppressing categories instead of tuning scope creates blind
  spots with paperwork.
- Treating compliance-standard findings as incidents: a failed CIS control is a hardening backlog
  item; a GuardDuty finding is a potential incident. Route them differently.

## References
- AWS Security Hub documentation (standards, ASFF, automation with EventBridge)
- AWS Foundational Security Best Practices standard reference
- CIS Amazon Web Services Foundations Benchmark
- NIST SP 800-53 SI-4 (system monitoring) and CA-7 (continuous monitoring)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
