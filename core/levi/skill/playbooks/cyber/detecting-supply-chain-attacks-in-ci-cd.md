---
skill_id: cyber_detecting_supply_chain_attacks_in_ci_cd
name: Detecting Supply Chain Attacks in CI/CD
description: Detect compromise of build pipelines: runners, artifacts, and deployment integrity.
risk: low
permissions: []
requires_confirmation: false
tags: [supply-chain, cicd, detection]
version: 1.0.0
---
## Purpose

CI/CD pipelines are trust-concentration points: compromise the pipeline and every artifact it produces is suspect. This playbook covers detecting supply-chain attacks in build systems — runner compromise, pipeline-definition tampering, artifact substitution, and secret exfiltration — using pipeline audit logs, artifact provenance, and runner telemetry.

## When to use

- You operate CI/CD (GitHub Actions, GitLab, Jenkins, Azure DevOps) building production artifacts.
- A pipeline or runner compromise is suspected.
- You need artifact-integrity assurance for releases.
- Compliance (SSDF, SLSA) requires build-integrity controls.

## Prerequisites

- Pipeline audit logs: workflow runs, definition changes, runner registrations, secret accesses.
- Artifact provenance: build attestations, signatures, SBOMs per release.
- Runner inventory: which runners (cloud-hosted, self-hosted) build what, with network/process telemetry where possible.
- Baseline of normal pipeline behavior: triggers, durations, accessed secrets, external endpoints.

## Procedure

1. Monitor pipeline definitions as code under attack. Alert on: workflow/pipeline file changes outside normal PR review (especially direct pushes to main), new workflows added by unusual actors, modifications to jobs that handle secrets or signing, and changes to trigger conditions (e.g., adding pull_request_target to exfiltrate secrets). Pipeline-definition changes deserve the same scrutiny as production code changes.
2. Detect runner compromise and misuse. Alert on: new self-hosted runner registrations (attackers register malicious runners to steal jobs), runners exhibiting unexpected network egress or process behavior, jobs accessing secrets outside their normal scope, and workflow runs triggered by compromised accounts or tokens. Ephemeral, isolated runners limit blast radius — persistent self-hosted runners are the highest risk.
3. Verify artifact integrity end-to-end. For each release: confirm the artifact was built by the expected pipeline (provenance/attestation), verify signatures before deployment, compare artifact hashes against the build record, and alert on deployments of artifacts lacking valid provenance. An artifact that can't prove its build lineage shouldn't reach production.
4. Detect secret exfiltration via pipelines. Alert on: workflows exfiltrating secrets to external endpoints (monitor runner egress), secrets accessed by jobs that don't need them, new outbound connections from runners during builds, and encoded output blobs in build logs (classic exfil channel). Treat CI logs as sensitive — they often contain leaked secrets.
5. Respond to pipeline compromise as supply-chain compromise. Identify all artifacts built during the compromise window, quarantine them, rotate all secrets accessible to affected runners/pipelines, audit deployments of tainted artifacts (including what ran in production), rebuild from clean definitions, and notify downstream consumers if artifacts were distributed externally.
6. Harden the pipeline: require PR review for workflow changes, use OpenID Connect instead of long-lived tokens, pin third-party actions to SHAs, isolate runners per trust level, enforce provenance/signing (SLSA), and scan pipeline definitions for misconfigurations (excessive permissions, unpinned actions).

## Expected outputs

- Pipeline-definition change detections with PR-review correlation.
- Runner anomaly detections: registrations, egress, secret-scope deviations.
- Artifact provenance verification gates before production deployment.
- Pipeline-compromise response: quarantine, secret rotation, rebuild, consumer notification.

## Pitfalls

- Third-party actions auto-updating to latest tags can introduce malicious code — pin to SHAs.
- Self-hosted runners persist across jobs; one malicious PR can poison subsequent builds — use ephemeral runners.
- Build logs containing secrets defeat every other control — mask secrets and audit logs.
- Provenance that nobody verifies is theater — enforce verification gates, don't just generate attestations.
- Long-lived CI tokens are pipeline skeleton keys — replace with OIDC federation.

## References

- NIST SP 800-218 (Secure Software Development Framework); SLSA framework (slsa.dev) for build provenance; MITRE ATT&CK T1195.002, T1552 (Unsecured Credentials) — https://attack.mitre.org/techniques/T1195/002/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
