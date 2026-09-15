---
skill_id: cyber_performing_container_escape_detection
name: Container Escape Detection
description: Detect container breakout attempts and privilege escalation from container to host.
risk: low
permissions: []
requires_confirmation: false
tags: [containers, detection, kubernetes]
version: 1.0.0
---

## Purpose

A container escape turns a compromised workload into a compromised host — and from there, potentially the whole cluster. Escapes exploit privileged containers, exposed host mounts, vulnerable runtimes, or kernel flaws to break namespace and cgroup isolation. This playbook is about detecting escape attempts and successes: the syscall patterns, host artifacts, and orchestrator signals that indicate a container has broken (or is trying to break) its boundaries, and how to respond when it does.

## When to use

- A Falco, EDR, or audit alert suggests container-to-host activity.
- Post-incident review of a compromised pod to determine whether the host was reached.
- Building runtime detection rules for container escape techniques.
- Assessing whether your container hardening (no privileged, read-only root, dropped capabilities) is actually enforced.
- Threat hunting for known escape primitives (hostPath mounts, hostPID, CAP_SYS_ADMIN abuse).

## Prerequisites

- Runtime security telemetry: Falco or equivalent syscall monitoring on nodes, plus Kubernetes audit logs.
- Node-level visibility: host EDR or auditd on Kubernetes nodes, and access to kubelet/containerd logs.
- Baseline of your workloads' legitimate privilege needs: which pods are intentionally privileged and why (the list should be short and documented).
- Incident response authority to cordon nodes and evict pods.
- Knowledge of your runtime version and kernel version for CVE correlation.

## Procedure

1. **Know your escape surface.** Inventory risky configurations: privileged pods, `hostPID`/`hostNetwork`/`hostIPC`, hostPath mounts (especially `/`, `/var/run/docker.sock`, `/proc`, `/sys`), and containers running with `CAP_SYS_ADMIN`, `CAP_SYS_PTRACE`, or as root. Every item on this list is a pre-authorized escape path — document the business justification or remove it.
2. **Monitor for escape syscall patterns.** Alert on: `unshare`/`setns` with host namespaces, `mount` of host devices, `ptrace` across container boundaries, writes to `/proc/sysrq-trigger` or cgroup release_agent paths, and `nsenter`-style behavior. These are the mechanical signatures of breakout attempts.
3. **Watch the host side.** Correlate container alerts with host events: new processes whose parent chain leads into a container runtime shim, unexpected binaries in host paths, modifications to host cron/systemd, and container-runtime socket access from workloads that should never need it.
4. **Detect known exploit primitives.** Match against published escape techniques: CVE-2019-5736 (runc overwrite), CVE-2024-21626 (working-directory escape), cgroup release_agent abuse, and kernel exploits. Correlate your runtime/kernel versions with these CVEs to know which of your nodes are vulnerable in principle.
5. **Investigate the container first, then the host.** When an alert fires: capture the pod's logs and filesystem, identify the triggering process and its ancestry, then examine the node for host-side artifacts. Determine whether the attempt succeeded (host artifacts present) or failed (syscall blocked, no host changes).
6. **Contain at the node level.** For a confirmed escape: cordon the node, evict and delete the offending workloads, snapshot the node for forensics before rebuilding it, and rotate credentials that existed on the node (service account tokens, cloud instance credentials). Treat the node as fully compromised — rebuilding is the only trustworthy remediation.
7. **Eradicate orchestrator persistence.** Check for attacker-created DaemonSets, privileged pods, mutated webhooks, or stolen service account tokens that would re-establish access on fresh nodes. Clean the control plane, not just the node.
8. **Harden based on findings.** Remove the configuration that enabled the escape (drop the capability, remove the hostPath mount, enforce via admission policy), add the observed technique to runtime detection rules, and patch the runtime/kernel.

## Expected outputs

- An inventory of escape-prone configurations (privileged, hostPath, dangerous capabilities) with justifications or removal plans.
- Detection rules for escape syscall patterns and host-side indicators.
- Investigation records distinguishing attempted vs. successful escapes, with evidence.
- Node rebuild and credential rotation records for confirmed escapes.
- Hardening changes: admission policies, capability drops, and patched runtimes.

## Pitfalls

- Allowing privileged pods "temporarily" that become permanent — every privileged workload is a standing escape path.
- Detecting only the container side; a successful escape's most reliable indicators are on the host.
- Rebuilding the node but leaving attacker persistence in the cluster (malicious DaemonSet, stolen tokens).
- Assuming seccomp/AppArmor profiles are applied — verify they are actually attached to running pods, not just defined.
- Missing the cloud layer: a node with an attached instance profile gives an escaped attacker cloud credentials too.

## References

- MITRE ATT&CK T1611, "Escape to Host"
- NIST SP 800-190, "Application Container Security Guide"
- Kubernetes documentation on Pod Security Standards (restricted profile)
- Falco documentation on container-escape detection rules
- CIS Kubernetes Benchmark (privileged and host-namespace controls)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
