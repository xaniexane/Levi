---
skill_id: cyber_performing_cloud_native_forensics_with_falco
name: Cloud-Native Forensics with Falco
description: Use Falco runtime security events for container and Kubernetes forensic timeline reconstruction.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, forensics, kubernetes]
version: 1.0.0
---

## Purpose

Falco observes system calls inside containers and Kubernetes audit events in real time, producing a stream of security-relevant events: unexpected processes, sensitive file writes, outbound connections, privilege escalations. When an incident hits a containerized workload, Falco's event history is often the only record of what happened inside the ephemeral container. This playbook covers using Falco as a forensic source: ensuring the right events are captured, reconstructing container activity timelines, and correlating Falco findings with orchestrator-level evidence.

## When to use

- Investigating a compromised pod, container, or node in Kubernetes.
- Reconstructing what a short-lived container did before it was terminated.
- Validating whether a Falco alert represents real malicious activity or benign behavior.
- Building runtime detection rules informed by forensic findings.
- Auditing container behavior against an expected baseline (which syscalls should this workload ever make?).

## Prerequisites

- Falco deployed with events shipped to durable storage (not just stdout on the node) — forensic value requires history, so confirm retention covers your investigation window.
- Falco configured with the rule set and syscall event capture appropriate to your workloads; default rules catch common cases, custom rules encode your environment's specifics.
- Access to Kubernetes audit logs and container runtime logs for correlation.
- Understanding of the workload's normal behavior: expected processes, file paths, and network destinations per deployment.
- A process for capturing the suspect pod's filesystem/logs before it is rescheduled or deleted.

## Procedure

1. **Verify event availability and integrity.** Confirm Falco events exist for the suspect pod/namespace over the full window, check for gaps (Falco restarts, node reboots, dropped events under load), and note the Falco version and active rule set — findings are interpreted against the rules that were loaded.
2. **Isolate the suspect workload's events.** Filter by pod name, namespace, container image, and node. Build a chronological list: process executions, file writes, network connections, and privilege-related events. This is the raw material of the container timeline.
3. **Classify each event.** For every anomalous event, determine: expected workload behavior (documented in the image's purpose), benign-but-unusual (debugging, init scripts), or malicious (reverse shells, crypto miners, credential access, unexpected package installs). Record the reasoning; Falco alerts are leads, not verdicts.
4. **Trace the entry point.** Work backward from the first malicious event: which process spawned it, what image layer or mounted volume it came from, and which Kubernetes event (pod creation, exec into pod, image pull) preceded it. Correlate with Kubernetes audit logs for `exec`, `attach`, and deployment changes.
5. **Map persistence and lateral movement.** Check for: modified container images pushed to the registry, new CronJobs or DaemonSets, service account token use from unexpected pods, and connections to other pods or the API server. In Kubernetes, persistence often lives in the orchestrator, not the container.
6. **Capture container state.** Before the pod is deleted, collect: `kubectl logs` (current and previous), the container filesystem diff, mounted secrets/configs as referenced, and the image digest. Store these with the Falco event export as the evidence set.
7. **Corroborate with orchestrator evidence.** Join the Falco timeline to Kubernetes audit events (who created/exec'd into the pod), admission controller logs, and image registry pull records. A complete story ties the runtime behavior to a control-plane action.
8. **Convert findings to detection.** For confirmed malicious behaviors, write or tune Falco rules that would fire earlier next time (tighter process allowlists, sensitive-path watches, unexpected egress), and add the indicators to your SIEM.

## Expected outputs

- A container-level timeline built from Falco events, annotated with classifications.
- Entry-point analysis: how the attacker reached the workload (image, exec, vulnerability).
- Persistence and lateral-movement assessment at the orchestrator layer.
- Preserved evidence: event exports, pod logs, filesystem diffs, image digests.
- New or tuned Falco rules encoding the lessons of the incident.

## Pitfalls

- No Falco history because events were only logged to node stdout — ship events to durable storage as a readiness requirement.
- Treating every Falco alert as malicious; noisy default rules need tuning against your workloads or analysts will ignore them.
- Losing the pod before collection: ephemeral containers vanish with their filesystem; capture early.
- Analyzing the container while ignoring the orchestrator — in Kubernetes the interesting persistence is usually a workload object, not a file.
- Rule changes mid-investigation that alter what "no alert" means; document the active rule set per time window.

## References

- Falco project documentation (rules, event sources, outputs)
- Kubernetes audit log documentation
- MITRE ATT&CK containers matrix (T1610, T1611, T1609 — container administration and escape)
- NIST SP 800-190, "Application Container Security Guide"
- CIS Kubernetes Benchmark (for hardening context around findings)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
