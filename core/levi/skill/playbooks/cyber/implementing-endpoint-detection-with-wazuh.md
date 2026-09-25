---
skill_id: cyber_implementing_endpoint_detection_with_wazuh
name: Endpoint Detection with Wazuh
description: Deploy Wazuh for open-source endpoint detection, FIM, and log analysis with tuned rules.
risk: low
permissions: []
requires_confirmation: false
tags: [endpoint, edr]
version: 1.0.0
---
## Purpose
Commercial EDR is powerful but expensive — and many environments (labs, subsidiaries, legacy fleets,
budget-constrained orgs) need solid endpoint detection without the per-seat cost. Wazuh provides
open-source XDR: endpoint agents, file-integrity monitoring, log analysis, vulnerability detection,
and a detection engine — free to run, with the tradeoff being operational effort. This playbook
deploys Wazuh with tuned rules and SOC integration.

## When to use
- Building endpoint detection on open-source where commercial EDR isn't funded or feasible.
- Covering Linux/server fleets, lab environments, or subsidiaries outside the main EDR deployment.
- Meeting log-analysis and FIM requirements (PCI DSS 11.5, 10.x) with one platform.
- As a complement to commercial EDR: Wazuh's log/FIM/vuln-detection strengths fill gaps.
- When data-sovereignty or air-gap constraints favor self-hosted detection.

## Prerequisites
- Infrastructure for the Wazuh manager (and cluster for scale), indexer (OpenSearch), and dashboard
  — sized for event volume.
- Agent deployment mechanism: Ansible, GPO, MDM, or golden images.
- Defined detection priorities: which threats matter most (mapped to ATT&CK) to guide rule tuning.
- SIEM/SOAR destination or the Wazuh dashboard as the SOC's working console — decide the triage
  home.
- Time budget: Wazuh trades license cost for engineering time. Staff it honestly.

## Procedure
1. **Size and deploy the manager tier.** Single manager for small fleets; multi-node cluster for
   scale or HA. Deploy the indexer (OpenSearch/Wazuh indexer) and dashboard with TLS,
   authentication, and restricted network access. Harden the manager like production infrastructure
   — it's the detection brain.
2. **Roll out agents in waves.** Deploy via automation (Ansible/GPO/MDM); verify enrollment
   centrally and reconcile against the asset inventory — unenrolled endpoints are the gap. Start
   with servers and high-value workstations, then the general fleet.
3. **Enable the core modules.** Turn on: syscheck (FIM) for critical paths, rootcheck
   (rootkit/anomaly detection), log analysis (auth, sudo, application logs), vulnerability detection
   (inventory vs. feeds), and SCA (security configuration assessment against CIS-like policies).
   Each module needs its tuning pass.
4. **Tune rules before trusting alerts.** Run 2-4 weeks in monitor mode: triage the alert firehose,
   write local rules and decoders for your environment, suppress known-benign patterns with
   documented justification, and escalate rule levels for your crown-jewel scenarios. Default rules
   are a starting point, not a finished product.
5. **Build the high-value detections.** Ensure coverage for: brute-force authentication, privilege
   escalation (sudo/su anomalies), new listening ports, malware-adjacent behaviors (from rootcheck
   and syscheck), and vulnerability-detection criticals on internet-facing hosts. Map each to ATT&CK
   and to a response playbook.
6. **Integrate with the SOC workflow.** Forward alerts to the SIEM with context, or operate from the
   Wazuh dashboard with defined triage SLAs. Configure active response (firewall-drop, account lock)
   carefully — only for high-confidence scenarios after tuning, with manual override available.
7. **Maintain the vulnerability-detection feed.** Keep the vulnerability detector updated (feed sync
   monitored); triage findings into the patch process. Alert on feed-sync failures — stale feeds
   mean missed CVEs.
8. **Manage FIM deliberately.** Scope syscheck to paths that matter (binaries, configs, startup
   locations) with appropriate frequencies; realtime for critical files, periodic for the rest.
   Alert on: unexpected binary changes, new setuid files, and startup-persistence modifications. FIM
   noise from package managers needs whitelisting, not disabling.
9. **Monitor platform health.** Alert on: agents not reporting, manager/indexer resource exhaustion,
   rule-load errors, and dashboard access anomalies. A detection platform that silently degrades is
   worse than none — it suppresses the instinct to check.
10. **Report and mature.** Metrics: agent coverage, alerts by severity and disposition, rule
    precision, vulnerability MTTR, and FIM change dispositions. Quarterly: review rule
    effectiveness, add detections for new threats/incidents ("never again" rules), and assess
    whether the operational cost still beats commercial alternatives.

## Expected outputs
- Wazuh manager/indexer/dashboard deployed, hardened, and sized, with agents enrolled fleet-wide
  (verified coverage).
- Core modules enabled and tuned: FIM, rootcheck, log analysis, vulnerability detection, SCA.
- Custom rules/decoders for the environment, mapped to ATT&CK with response playbooks.
- SOC-integrated alerting with triage SLAs; cautious active response for high-confidence cases.
- Health monitoring, feed-sync monitoring, and quarterly detection reviews.

## Pitfalls
- Underestimating operational cost: Wazuh is free like a puppy. Budget engineering time for tuning,
  upgrades, and rule maintenance.
- Default rules in production: the out-of-box rule set is noisy and generic. The tuning phase is
  mandatory, not optional.
- Unscoped FIM: monitoring everything generates unmanageable noise. Scope to security-relevant paths
  with sane frequencies.
- No agent-coverage reconciliation: the endpoints without agents are where incidents start. Verify
  coverage continuously.
- Active response without tuning: auto-blocking on noisy rules causes self-inflicted outages.
  High-confidence only, after burn-in.

## References
- Wazuh documentation (deployment, rules, decoders, active response)
- CIS Benchmarks (SCA policy content)
- NIST SP 800-53 SI-4, SI-7 (monitoring, software integrity — FIM mapping)
- MITRE ATT&CK (detection mappings for custom rules)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
