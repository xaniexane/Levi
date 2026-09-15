---
skill_id: cyber_configuring_host_based_intrusion_detection
name: Configuring Host-Based Intrusion Detection
description: Practitioner guide to deploying and tuning host-based intrusion detection (HIDS) for file integrity, rootkit, and anomaly detection.
risk: info
permissions: []
requires_confirmation: false
tags: [detection, endpoint, hardening]
version: 1.0.0
---
## Purpose
Host-based intrusion detection watches what network controls cannot see: file changes, rootkit indicators, and malicious activity on the endpoint itself. This playbook deploys HIDS agents (such as Wazuh or OSSEC-class tooling), tunes rules to the environment, and integrates alerts into SOC workflows.

## When to use
- Adding endpoint visibility where EDR coverage is incomplete (servers, legacy systems).
- Meeting compliance requirements for file-integrity monitoring.
- Detecting unauthorized changes on critical systems.
- Complementing network IDS with host-level context.

## Prerequisites
- Inventory of hosts to cover, with OS versions and criticality.
- Central manager infrastructure for agent communication and log storage.
- Baseline of normal file and process activity for tuning.
- SOC workflow for triaging HIDS alerts.

## Procedure
1. Define coverage and objectives. Decide which hosts get agents and what each must detect: file-integrity changes, rootkits, log anomalies, or policy violations.
2. Deploy the manager. Install and secure the central manager; configure authentication, log retention, and backup.
3. Roll out agents in phases. Start with a pilot group covering each OS type; verify check-in, log flow, and performance impact before expanding.
4. Configure file-integrity monitoring. Define watched paths (system binaries, configs, web roots); exclude volatile paths that generate noise.
5. Tune rules to the environment. Adjust severity, add local allowlists for known-good applications, and suppress expected administrative changes.
6. Enable rootkit and anomaly checks. Turn on rootkit detection, hidden-process checks, and anomaly detection appropriate to each platform.
7. Integrate with the SOC. Forward alerts to the SIEM with normalized severity; build triage runbooks for the common alert types.
8. Maintain and review. Update agent versions, review rule effectiveness quarterly, and re-baseline after major system changes.

## Expected outputs
- Deployed HIDS with manager and phased agent rollout.
- Tuned file-integrity and anomaly rules with documented exclusions.
- SOC runbooks for HIDS alert triage.

## Pitfalls
- Monitoring everything generates unmanageable noise; scope to what matters.
- Untested agents on production servers cause performance incidents; pilot first.
- Rules never tuned after deployment decay into ignored alerts.
- File-integrity monitoring without a change process flags every legitimate patch.

## References
- Wazuh or OSSEC project documentation
- NIST SP 800-92, Guide to Computer Security Log Management
- CIS Benchmarks for host hardening baselines
- PCI DSS file-integrity monitoring requirements (where applicable)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
