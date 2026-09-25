---
skill_id: cyber_auditing_terraform_infrastructure_for_security
name: Auditing Terraform Infrastructure for Security
description: Static security review of Terraform: tfsec/checkov and state hygiene.
risk: low
permissions: []
requires_confirmation: false
tags: [cloud, supply-chain]
version: 1.0.0
---
# Auditing Terraform Infrastructure for Security

## Purpose

Audit Terraform configurations (`.tf` files, modules, state, and plans) for security
misconfigurations before they are applied — catching open security groups, unencrypted
storage, public buckets, and hardcoded secrets in code review rather than in production.

## When to use

- Security review of infrastructure-as-code pull requests.
- Periodic audits of Terraform repositories and remote state.
- Pre-apply review of plans touching production or regulated data.
- After incidents caused by infrastructure misconfiguration.

## Prerequisites

- Written authorization and a defined scope: repositories, workspaces, and environments in
  bounds.
- Read access to the Terraform repositories, module registry/ sources, and (if in scope)
  remote state backends.
- The ability to run `terraform plan` (init with backend access) or at least static
  analysis on the code.
- Baseline of expected guardrails: which scanners and policy gates already run in CI.

## Procedure

1. **Inventory the Terraform estate.**
   - List repositories, root modules, child modules (local and remote), providers and
     versions, and workspaces/environments.
   - Record provider version pins — unpinned providers make audits non-reproducible.

2. **Run static analysis scanners.**
   - Execute `checkov -d <dir>`, `tfsec <dir>` (or Trivy `trivy config`), and
     `tflint --init` on every root module; save JSON output with versions.
   - Triage findings into true positives, accepted risks, and false positives — do not
     paste raw scanner output into the report.

3. **Review network exposure in code.**
   - Grep for `0.0.0.0/0` and `::/0` in `cidr_blocks`, security group rules, and firewall
     resources; each ingress rule needs a justification.
   - Check for public IPs/subnets on resources that should be private (databases,
     caches, internal load balancers) — verify `associate_public_ip_address` and subnet
     `map_public_ip_on_launch`.

4. **Review data protection settings.**
   - Verify encryption at rest on storage resources (S3 `server_side_encryption_configuration`,
     EBS `encrypted = true`, RDS `storage_encrypted`, GCS/AAD equivalents) and TLS
     enforcement on endpoints.
   - Check key management: customer-managed keys where policy requires, and key rotation
     settings.

5. **Review IAM and access in code.**
   - Inspect `aws_iam_policy_document` / `google_project_iam_*` / `azurerm_role_assignment`
     resources for wildcard actions (`"*"`) and broad principals.
   - Flag IAM resources created with `count`/`for_each` over untrusted input — dynamic
     policy generation is a misconfiguration factory.

6. **Hunt secrets in code and state.**
   - Scan for hardcoded secrets, tokens, and keys in `.tf` files, `.tfvars`, and
     examples (`gitleaks`, `trufflehog`).
   - Review remote state: state files contain secrets in plaintext — confirm the backend
     (S3/GCS/AzureRM) is encrypted, access-logged, and not publicly reachable, and that
     state locking is enabled.

7. **Audit modules and supply chain.**
   - For registry/community modules, pin to a versioned source and review the module code
     — a module is code you run with your credentials.
   - Flag modules fetched from unpinned git refs (`?ref=` missing) or HTTP (not HTTPS)
     sources.

8. **Evaluate policy-as-code gates.**
   - Review Sentinel/OPA/Conftest policies in the pipeline: what do they actually deny,
     and what slips through? Write a test case per critical control.
   - Confirm `terraform plan` output is reviewed (or auto-checked) before every apply —
     an unreviewed plan is an unaudited change.

9. **Check drift and lifecycle hygiene.**
   - Compare `terraform plan` (no-op expected) against reality to find drift; unmanaged
     drift means the code no longer describes the infrastructure.
   - Review `lifecycle` blocks, `prevent_destroy` on critical data stores, and backup/
     retention settings in code.

10. **Report with file-level evidence.**
    - Each finding: file path and line, resource address, current vs. expected
      configuration, severity, and the exact code change to remediate.
    - Provide a prioritized backlog the platform team can work as tickets.

## Key tools & commands

- `checkov -d . --framework terraform -o json` — broad misconfiguration scanning.
- `tfsec .` / `trivy config .` — Terraform-focused scanning with code-line references.
- `tflint --init && tflint` — provider-aware linting (naming, deprecated syntax,
  undocumented variables).
- `conftest test plan.json -p policy/` — policy-as-code evaluation of plan output.
- `gitleaks detect --source .` / `trufflehog filesystem .` — secret scanning.
- `terraform plan -out=plan.out && terraform show -json plan.out | jq` — structured plan
  review.

## Expected outputs

- Scanner outputs (versioned) with triage decisions per finding.
- File-and-line findings register with severity and exact remediation code.
- State backend security review (encryption, access, locking).
- Module supply-chain notes and policy-gate gap analysis.

## Pitfalls

- Reporting raw scanner output — checkov/tfsec false-positive on legitimate patterns
  (e.g., intentionally public CloudFront-backed buckets); adjudication is the audit.
- Auditing code that isn't what's applied — verify the pipeline applies the reviewed
  commit, and check drift.
- Missing secrets in state/history — rotate anything found committed, don't just delete
  the line; git history remembers.
- Remote modules changing under you — unpinned sources make today's audit stale tomorrow.

## References

- MITRE ATT&CK: T1578 (Modify Cloud Compute Infrastructure), T1552 (Unsecured
  Credentials).
- Checkov, tfsec/Trivy, tflint, Conftest documentation.
- Terraform documentation: backend configuration, state security recommendations.
- CIS Benchmarks (AWS/Azure/GCP) — map code findings to the controls they violate.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
