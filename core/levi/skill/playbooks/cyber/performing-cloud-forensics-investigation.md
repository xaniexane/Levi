---
skill_id: cyber_performing_cloud_forensics_investigation
name: Cloud Forensics Investigation
description: Conduct forensically sound investigations in cloud environments across compute, storage, and identity evidence.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, forensics, incident-response]
version: 1.0.0
---

## Purpose

Cloud incidents do not leave a disk you can pull: evidence lives in API logs, snapshots, ephemeral instance storage, and provider-side telemetry, and it can vanish when an autoscaling group terminates or a log retention window expires. This playbook provides the general methodology for cloud forensics: preserving volatile evidence fast, establishing timelines from distributed log sources, analyzing compute and storage artifacts, and producing defensible findings. Provider-specific techniques are covered in companion playbooks; this one is the overarching investigation discipline.

## When to use

- A cloud workload is suspected compromised and you must determine scope and impact.
- An alert implicates a cloud identity, instance, container, or storage resource.
- You need a defensible timeline of attacker activity across multiple cloud services.
- Preparing cloud forensic readiness before an incident (far better than during one).
- Coordinating with a provider or law enforcement where evidence handling matters.

## Prerequisites

- Predefined forensic readiness: centralized logging enabled (management-plane and data-plane), adequate retention, and snapshots/versioning on critical storage — verify these before you need them.
- An isolated forensic account or subscription with no trust to production, for holding evidence copies.
- IAM permissions for evidence collection: snapshot creation, log export, instance stop (not terminate), and memory capture where supported — granted to responders under break-glass procedures.
- Chain-of-custody documentation process adapted for cloud artifacts (snapshot IDs, log export hashes, API call records).
- Legal/privacy review for multi-tenant or cross-border data, especially for storage containing customer data.

## Procedure

1. **Triage and scope in minutes, not hours.** Identify the suspected resources (instances, identities, buckets, keys) and the blast radius: which accounts, which roles the suspect identity can assume, which data stores are reachable. Freeze the scope in writing before collecting.
2. **Preserve volatile evidence first.** Snapshot disks of suspect instances, capture memory where the platform supports it, and export relevant logs immediately. Disable termination protection gaps: apply "do not terminate" safeguards to suspect instances and suspend autoscaling or lifecycle policies that could delete evidence.
3. **Isolate without destroying.** Prefer containment that preserves state: revoke/suspend suspect credentials, attach restrictive security groups, detach public IPs, or move instances to a quarantine subnet. Avoid rebooting or reimaging until acquisition is complete — volatile state is evidence.
4. **Build the timeline from multiple sources.** Correlate: management-plane API logs (who did what, from where), OS-level logs from the instance, VPC/flow logs (network conversations), application logs, and identity provider sign-in logs. Normalize to UTC, and treat clock skew between sources as a documented assumption.
5. **Analyze compute artifacts.** Mount snapshots read-only in the forensic account and examine: persistence mechanisms (cron, systemd units, startup scripts, container entrypoints), recently modified binaries and configs, shell histories, and credential material. Compare against a known-good baseline or gold image.
6. **Analyze storage and identity artifacts.** Check bucket/object versioning for planted or exfiltrated objects, review access logs for anomalous reads, and audit the suspect identity's policy attachments, access-key age, and recent `AssumeRole` chains. Attackers in cloud environments live in the identity plane as much as the OS.
7. **Determine impact and eradication requirements.** Conclude: initial access vector, persistence established, data accessed or exfiltrated (with evidence, not speculation), and which credentials, keys, and resources must be rotated or rebuilt. Distinguish confirmed from suspected in the report.
8. **Document chain of custody for cloud artifacts.** Record snapshot IDs, AMI IDs, log export locations with hashes, the exact API calls used for collection, who performed each step, and timestamps. Cloud evidence is defensible when the collection process is reproducible from your notes.

## Expected outputs

- A scoped incident record: affected accounts, resources, identities, and time bounds.
- Preserved evidence set: snapshots, memory captures, and exported logs with hashes, held in the forensic account.
- A correlated UTC timeline of attacker and responder activity.
- Findings on initial access, persistence, and data impact (confirmed vs. suspected).
- Eradication and recovery recommendations: rotations, rebuilds, and control gaps to close.

## Pitfalls

- Letting autoscaling, spot termination, or short log retention destroy evidence before you collect — readiness is the real playbook.
- Rebooting or reimaging a suspect instance as a "quick fix," wiping memory and ephemeral storage.
- Collecting evidence into the same compromised account, where the attacker may observe or tamper with it.
- Building a timeline from a single log source; cloud attacks span services, and one source always has gaps.
- Stating exfiltration as fact without log evidence — "data was accessible" and "data was exfiltrated" are different claims with different consequences.

## References

- NIST SP 800-61, "Computer Security Incident Handling Guide"
- NIST SP 800-86, "Guide to Integrating Forensic Techniques into Incident Response"
- AWS, Azure, and GCP documentation on forensic snapshot and log export capabilities
- SANS cloud forensics posters and evidence-collection guidance
- Cloud Security Alliance, "Security Guidance for Critical Areas of Focus in Cloud Computing"
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
