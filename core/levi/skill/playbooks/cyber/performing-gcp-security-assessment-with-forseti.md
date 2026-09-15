---
skill_id: cyber_performing_gcp_security_assessment_with_forseti
name: GCP Security Assessment with Forseti
description: Audit GCP projects against policy with Forseti Security scanners.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, gcp, compliance]
version: 1.0.0
---
# GCP Security Assessment with Forseti

## Purpose

Forseti Security scans GCP organizations against policy rules — IAM
bindings, firewall rules, bucket ACLs, BigQuery datasets — and reports
violations. This playbook runs a Forseti-based assessment and converts
scanner violations into prioritized remediation.

## When to use

- Periodic compliance checks of GCP organizations and folders.
- Post-migration validation that cloud guardrails actually landed.
- Detecting configuration drift between audits.
- Pre-audit evidence gathering (SOC 2, ISO 27001 cloud controls).

## Prerequisites

- Forseti Security deployed with a service account holding
  organization-level read rights (roles/browser, security reviewer).
- Scanner rules defined for your policy baseline (whitelists,
  blacklists, required constraints).
- A notification pipeline: Forseti violations exported to Pub/Sub,
  email, or the SIEM for tracking.

## Procedure

1. Confirm the inventory pipeline is healthy: the Forseti server should
   have a current model of the organization — stale inventory produces
   stale findings.
2. Review and version-control the scanner rules: firewall rules that
   must not exist, IAM members that must not be granted, required
   labels or encryption settings.
3. Run the scanners: `forseti scanner run` (or wait for the scheduled
   run) and export violations to the notification sink.
4. Triage by blast radius: org-level IAM grants and 0.0.0.0/0 firewall
   rules first, then project-level drift, then labeling hygiene.
5. Investigate each violation's provenance: who made the change, via
   which API call, and whether it was an emergency break-glass or
   routine drift — Admin Activity logs answer this.
6. Remediate in the source: fix Terraform/modules or deployment
   pipelines, not just the live resource, or drift returns on the next
   apply.
7. Convert repeated violations into guardrails: Organization Policies
   that prevent the misconfiguration beat scanners that merely report
   it.
8. Archive scanner outputs with hashes as audit evidence and trend
   violation counts across runs to show improvement.

## Expected outputs

- A violation report mapped to the organization's policy baseline.
- Remediation actions with root-cause fixes in IaC.
- New or tightened Organization Policies for repeat findings.
- Trend data showing violation reduction over time.

## Pitfalls

- Scanning with an outdated inventory model and chasing ghosts.
- Fixing live resources while the Terraform still encodes the bad
   configuration.
- Overly broad whitelist rules that silently exempt whole projects.
- Treating scanner output as the control: Forseti detects, Org Policy
   prevents — you need both.

## References

- Forseti Security documentation (forsetisecurity.org)
- Google Cloud documentation: Organization Policy Service
- CIS Google Cloud Platform Foundations Benchmark
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
