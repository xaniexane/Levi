---
skill_id: cyber_detecting_container_drift_at_runtime
name: Detecting Container Drift at Runtime
description: Detect runtime drift in containers — unexpected binaries, config changes, and writable-layer abuse — against image baselines.
risk: info
permissions: []
requires_confirmation: false
tags: [containers, detection, runtime]
version: 1.0.0
---
## Purpose

Detect when a running container diverges from its image — new binaries, modified configs, unexpected processes — the drift that signals compromise, misconfiguration, or someone debugging in production. Immutable infrastructure only works if you verify the immutability.

## When to use

- Monitoring Kubernetes and Docker workloads for runtime compromise.
- Enforcing immutable-container policy in production.
- Investigating a container that behaves unexpectedly.
- Validating that CI/CD-deployed images match what's actually running.

## Prerequisites

- Runtime security tooling (Falco, Sysdig, Aqua, or cloud-native options like GuardDuty EKS Runtime Monitoring / Defender for Containers).
- Image baselines: SBOMs or file hashes of deployed images for comparison.
- Baseline of legitimate runtime behavior per workload (some apps legitimately write temp files; know which).
- Alerting path with the workload owner identified.

## Procedure

1. **Define what "drift" means per workload.** Not all change is malicious: some apps write caches and temp files by design. For each workload, document the expected writable paths and processes; everything else is drift. Workloads that should be fully immutable get the strictest policy — drift there is always an incident.
2. **Monitor the writable layer.** Alert on: new binaries appearing in the container filesystem, modifications to system binaries or configs (`/etc/passwd`, `/etc/shadow`, cron files), and unexpected file writes outside the documented writable paths. Compare against the image baseline — the image is the truth, the runtime is the suspect.
3. **Detect unexpected process execution.** Alert on: shells spawned in containers that never run shells (`sh`, `bash` in a distroless app container), package managers running (`apt`, `yum`, `apk` — nobody installs packages in production at runtime legitimately), and binaries executed from `/tmp` or `/dev/shm`. These are the classic post-exploitation patterns.
4. **Watch for privilege and namespace anomalies.** Alert on: processes running as root in containers that should run as non-root, new privileged containers, containers gaining capabilities (`CAP_SYS_ADMIN`), and namespace breakouts (host PID/network namespace joins). These signal escape attempts or misconfigured deployments, both worth immediate attention.
5. **Correlate drift with the deployment pipeline.** When drift is detected, check: was there a legitimate deployment? (compare image digest), did someone `kubectl exec` into the pod? (audit logs), is this a known debugging session? Legitimate drift gets documented; unexplained drift gets investigated. The audit log is the tiebreaker.
6. **Respond by replacing, not repairing.** On confirmed malicious drift: quarantine the pod (network policy isolation), capture forensic artifacts (filesystem diff, process tree, logs), then delete and redeploy from the known-good image — never "clean" a compromised container. Investigate the image and pipeline for how the compromise entered.
7. **Harden against recurrence.** Move toward: read-only root filesystems, non-root users, dropped capabilities, and image signing with admission control (only signed images deploy). Each of these shrinks the drift surface until the detections become confirmations of policy, not discoveries of compromise.

## Expected outputs

- Per-workload drift definitions with writable-layer and process-execution monitoring.
- Image-baseline comparison with deployment-pipeline correlation for triage.
- Replace-not-repair response runbooks and hardening roadmap (read-only FS, non-root, signed images).

## Pitfalls

- One drift policy for all workloads — the noisy app drowns the strict one's signal.
- No image baseline — you can't detect divergence from a truth you never recorded.
- `kubectl exec` treated as normal — it's the interactive backdoor; audit and alert on it.
- Repairing compromised containers — the only trustworthy container is a fresh one from a good image.
- Alerting on drift but not fixing the pipeline — the same vulnerable image redeploys the same compromise.

## References

- NIST SP 800-190 (Application Container Security Guide) — image and runtime controls
- CIS Kubernetes and Docker Benchmarks — runtime security baselines
- MITRE ATT&CK — container techniques (T1610, T1611)
- Falco documentation — runtime drift detection rules
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
