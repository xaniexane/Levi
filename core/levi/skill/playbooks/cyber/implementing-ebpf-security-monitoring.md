---
skill_id: cyber_implementing_ebpf_security_monitoring
name: eBPF-Based Security Monitoring
description: Deploy eBPF sensors for kernel-level Linux visibility: runtime security without kernel modules.
risk: low
permissions: []
requires_confirmation: false
tags: [linux, monitoring]
version: 1.0.0
---
## Purpose
eBPF lets you run sandboxed programs in the Linux kernel — observing syscalls, network connections,
and file access with near-zero overhead and no kernel modules. For security, that means deep runtime
visibility (process execution, privilege escalation, container escapes, network anomalies) that's
tamper-resistant and performant. This playbook deploys eBPF-based monitoring (Falco, Tetragon,
Tracee, or commercial) with tuned detections feeding the SOC.

## When to use
- Adding runtime threat detection to Linux fleets and Kubernetes nodes.
- After incidents where attackers operated below userspace-visibility (rootkits, container escapes,
  kernel-adjacent techniques).
- Replacing or complementing kernel-module-based agents (stability and security benefits).
- Meeting runtime-monitoring requirements for regulated Linux workloads.
- As the sensor layer for cloud workload protection on Linux.

## Prerequisites
- Linux kernels with eBPF support (4.18+ ideally; verify across the fleet — older kernels limit
  functionality).
- A sensor choice: Falco (CNCF, rule-based), Tetragon (Cilium, enforcement-capable), Tracee (Aqua,
  tracing-focused), or commercial eBPF agents.
- Deployment mechanism: DaemonSet for Kubernetes, systemd/Ansible for VMs.
- SIEM/SOAR destination for sensor events with parsing for the sensor's event format.
- Privilege model: eBPF requires CAP_BPF/CAP_SYS_ADMIN (or privileged DaemonSet) — understand and
  constrain this.

## Procedure
1. **Verify kernel and privilege readiness.** Audit kernel versions across targets; upgrade or
   except hosts that can't support eBPF. Confirm the deployment can obtain necessary privileges
   (privileged DaemonSet, or CAP_BPF with recent kernels) without violating pod-security policies —
   plan the exception deliberately.
2. **Deploy sensors via automation.** DaemonSets for Kubernetes nodes (tolerations for all node
   types), Ansible/systemd for VMs, baked into golden images for new builds. Verify sensor health
   centrally: running version, event throughput, and dropped-event counters — a silent sensor is a
   blind spot.
3. **Start with default rules in alert mode.** Enable the vendor/community default rule sets (Falco
   rules, Tetragon policies) in alert-only. Collect 1-2 weeks of events to learn the environment's
   normal: expected privileged containers, admin tooling, backup agents, and deployment patterns.
4. **Tune ruthlessly.** Write exceptions for legitimate patterns (specific binaries, namespaces,
   users), demote noisy low-value rules, and promote high-fidelity ones. eBPF sees everything —
   untuned, it drowns the SOC. Precision is the deployment's success criterion.
5. **Prioritize the high-value detections.** Ensure coverage for: shell spawned in container
   (possible escape/breakout), privilege escalation (setuid, sudo anomalies, capability use),
   sensitive file access (/etc/shadow, cloud credentials), unexpected outbound connections (C2),
   kernel module loading, and container drift (new binaries in immutable images). Map each to MITRE
   ATT&CK.
6. **Add custom rules for your threats.** Write rules for org-specific concerns: access to
   crown-jewel data paths, execution of banned tooling, or behaviors from past incidents ("never
   again" rules). Version-control custom rules with peer review — detection-as-code.
7. **Integrate with response.** Ship events to the SIEM with full context (process tree,
   container/image identity, pod/node, user). Define playbooks: container escape → isolate node/pod,
   kill workload, investigate image; credential access → rotate, hunt. Where the sensor supports
   enforcement (Tetragon), graduate high-confidence detections to block after tuning.
8. **Monitor sensor health as a control.** Alert on: sensor down/not reporting, event-drop counters
   climbing (overload — tune or scale), policy-load failures, and version drift. An attacker who
   kills the sensor first is the scenario — tamper detection on the sensor itself is mandatory.
9. **Test detection efficacy.** Quarterly: run safe atomic-style tests (spawn shell in test
   container, touch sensitive files, simulate C2-like connections in lab) and verify detection,
   alerting, and (where enabled) enforcement. Untested detections are assumed broken.
10. **Report runtime visibility.** Metrics: sensor coverage percent, detections by severity and
    disposition, rule precision, mean time to triage, and enforcement actions taken. Pair with
    vulnerability and posture metrics for the full Linux-security picture.

## Expected outputs
- eBPF sensors deployed fleet-wide via automation with health monitoring.
- Tuned rule sets: defaults baselined, custom org-specific rules, version-controlled.
- High-value detections mapped to ATT&CK and wired to SOC playbooks.
- Enforcement graduated for high-confidence detections (where supported).
- Quarterly efficacy tests and runtime-visibility metrics.

## Pitfalls
- Kernel version sprawl: old kernels silently limit eBPF features — audit and remediate, don't
  assume.
- Deploying without tuning: eBPF's completeness becomes a firehose. The tune-first discipline makes
  or breaks the deployment.
- Ignoring sensor tamper: privileged attackers kill sensors first. Monitor sensor health and protect
  the sensor's privileges.
- Event drops under load: noisy environments overwhelm sensors — monitor drop counters and
  scale/tune before assuming coverage.
- Treating eBPF as EDR-complete: it's a superb sensor, but needs the SOC workflow (triage, response,
  threat intel) around it to be a capability.

## References
- Falco, Tetragon, Tracee documentation (rules, policies, deployment)
- Cilium / eBPF documentation (kernel requirements, capabilities model)
- NIST SP 800-190 (container runtime security)
- MITRE ATT&CK (technique mappings for runtime detections)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
