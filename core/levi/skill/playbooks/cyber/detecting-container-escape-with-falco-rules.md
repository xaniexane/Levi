---
skill_id: cyber_detecting_container_escape_with_falco_rules
name: Detecting Container Escape with Falco Rules
description: Write and tune Falco rules that detect container-escape techniques with minimal false positives.
risk: info
permissions: []
requires_confirmation: false
tags: [containers, falco, detection]
version: 1.0.0
---
## Purpose

Turn Falco into a precise container-escape detector: custom rules for the escape techniques that matter in your environment, tuned against your workloads so alerts mean something. Generic Falco rules are a starting point; tuned rules are a detection program.

## When to use

- Deploying Falco for container runtime security.
- Tuning noisy default Falco rules into high-fidelity escape detection.
- Writing custom rules for environment-specific escape paths.
- Validating Falco coverage against known escape techniques.

## Prerequisites

- Falco deployed on all Kubernetes nodes (DaemonSet) with rules file management (Helm values or GitOps).
- Baseline of legitimate privileged syscalls per workload for tuning.
- A test cluster for rule validation before production rollout.
- Alerting pipeline from Falco (falcosidekick to SIEM/webhook) with severity routing.

## Procedure

1. **Start from the default rules and inventory what fires.** Deploy Falco with default rules in a staging or canary node pool first. Record every alert for two weeks with its workload context. This inventory separates rules that work as-is from rules that need tuning for your environment.
2. **Write escape-specific custom rules.** Build rules for: `unshare`/`nsenter`/`setns` syscalls from containerized processes, writes to host paths via `/proc/1/root` or similar, `mount` syscalls targeting host devices, access to the Docker/containerd socket, and `ptrace` of host processes. Use Falco's `container` and `k8s` filters to scope rules to container contexts — host processes doing these things are normal.
3. **Tune with workload-aware exceptions.** For each noisy rule, add exceptions keyed to the specific workload that legitimately triggers it (by image, pod label, or namespace) — never broad exceptions like "exclude all of kube-system." Document each exception with owner and justification; review quarterly. An exception is a detection gap with a name on it.
4. **Prioritize by escape severity.** Tag rules with priority: Critical for direct escape mechanics (namespace manipulation, host-path writes, socket access), Warning for precursors (unexpected shells, package managers), Notice for informational (drift indicators). Route Critical to paging, Warning to the SOC queue, Notice to daily review.
5. **Add output enrichment.** Configure Falco outputs to include: pod name, namespace, image, node, and the full parent process tree. An alert saying "unshare syscall detected" is a puzzle; the same alert with pod, image, and "launched from a python process in a nginx container" is an investigation.
6. **Test rules against simulated escapes.** In the test cluster, run controlled escape-attempt simulations (namespace manipulation, host-path access attempts, socket access) and verify each rule fires with correct priority and enrichment. Rules that don't fire on simulation are decoration — fix or remove them.
7. **Version-control and review rules like code.** Store Falco rules in git with PR review, change history, and rollback capability. Quarterly: review exception lists, retire rules with zero true positives, and add rules for newly discovered escape techniques. Detection-as-code is the only sustainable model.

## Expected outputs

- Custom Falco escape rules (namespace abuse, host-path writes, socket access, ptrace) with workload-aware exceptions.
- Priority-tagged alerting with enriched output (pod, image, process tree) routed by severity.
- Version-controlled rules with simulation-tested coverage and quarterly reviews.

## Pitfalls

- Default rules in production without tuning — alert fatigue within days.
- Broad exceptions ("exclude namespace X") that gut the rule.
- Rules scoped without container context — host processes trigger container rules and vice versa.
- Untested rules — the rule you never validated is the rule that fails during the incident.
- Rules in a GUI with no version control — changes are untraceable and unreviewable.

## References

- Falco documentation (falco.org) — rule syntax, macros, lists, outputs
- falcosidekick documentation — alert routing
- MITRE ATT&CK T1611 (Escape to Host) — technique-to-rule mapping
- NIST SP 800-190 (Application Container Security Guide)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
