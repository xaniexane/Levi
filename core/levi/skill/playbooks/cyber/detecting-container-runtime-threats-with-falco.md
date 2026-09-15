---
skill_id: cyber_detecting_container_runtime_threats_with_falco
name: Detecting Container Runtime Threats with Falco
description: Operate Falco as a full container runtime threat-detection program: deployment, tuning, response, and metrics.
risk: info
permissions: []
requires_confirmation: false
tags: [containers, falco, detection]
version: 1.0.0
---
## Purpose

Run Falco as a complete runtime threat-detection program — not just escape detection, but the full spectrum: malicious process execution, network anomalies, file integrity, and privilege abuse in containers. This is the operational playbook; the escape-rules playbook covers rule-writing depth.

## When to use

- Standing up container runtime threat detection with Falco.
- Expanding Falco from basic alerting to a SOC-integrated detection program.
- Auditing Falco deployment health and detection effectiveness.
- Integrating Falco alerts into incident response workflows.

## Prerequisites

- Falco (or Falco + falcosidekick) deployed across all clusters with centralized alerting.
- Kubernetes audit logs and image metadata available for enrichment.
- SOC runbooks for container incidents; workload owners identified.
- Baseline of normal runtime behavior per namespace/workload.

## Procedure

1. **Verify deployment completeness.** Confirm Falco runs on every node in every cluster (including new node pools — autoscaling adds nodes Falco must cover). Monitor Falco's own health: is the DaemonSet healthy on all nodes, are rules loading without errors, is the event stream flowing? A Falco that silently stopped on half the nodes is worse than no Falco — it's false confidence.
2. **Organize rules into threat categories.** Structure your ruleset: execution threats (unexpected binaries, shells, package managers), network threats (unexpected outbound connections, connections to private IPs from public-facing pods, port scans), file threats (writes to sensitive paths, binary modifications), and privilege threats (privilege escalation, capability abuse). Category-based organization makes coverage reviews possible.
3. **Build the triage runbook per category.** For each category, define the 10-minute triage: check the pod's image and recent deployments, check Kubernetes audit for `exec`/deployment events, check the process tree, and decide: benign (document and except), suspicious (isolate pod and investigate), malicious (incident). Consistent triage beats brilliant ad-hoc analysis.
4. **Integrate with Kubernetes-native response.** On malicious verdict: quarantine via NetworkPolicy (isolate the pod), capture pod logs and filesystem state, then delete the pod and let the controller reschedule from a clean image. For node-level threats: cordon the node. Pre-authorize these actions so the SOC doesn't wait for permission during an incident.
5. **Tune continuously with metrics.** Track per rule: alert volume, true-positive rate, and mean-time-to-triage. Rules with high volume and zero true positives get tuned or retired; rules with low volume but high fidelity get promoted in priority. Monthly tuning reviews keep the ruleset sharp — Falco rules rot as workloads change.
6. **Correlate Falco with the control plane.** Join Falco alerts with Kubernetes audit logs: a Falco execution alert on a pod that was just deployed by CI is different from one on a pod deployed months ago. Build automated enrichment that attaches deployment age, deployer identity, and image digest to every alert.
7. **Report program health.** Quarterly metrics for leadership: node coverage percentage, ruleset size and true-positive rate, mean-time-to-detect for runtime threats, and incidents first detected by Falco. These numbers justify the program and focus investment on the categories that catch real threats.

## Expected outputs

- Complete Falco deployment with health monitoring and categorized, tuned rulesets.
- Category-based triage runbooks with Kubernetes-native response actions pre-authorized.
- Monthly tuning reviews and quarterly program-health metrics.

## Pitfalls

- Falco on some nodes — autoscaling and new clusters create coverage gaps silently.
- No triage runbooks — every alert becomes a custom investigation and the queue backs up.
- Tuning once at deployment — workload changes rot the ruleset within months.
- Treating Falco alerts as informational — runtime threats need the same urgency as EDR alerts.
- No control-plane correlation — you investigate the alert without knowing the pod was deployed yesterday by an intern.

## References

- Falco documentation (falco.org) — deployment, rules, outputs
- falcosidekick documentation — SIEM and response integrations
- NIST SP 800-190 (Application Container Security Guide)
- MITRE ATT&CK — container and cloud technique mapping
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
