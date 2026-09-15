---
skill_id: cyber_auditing_gcp_iam_permissions
name: Auditing GCP IAM Permissions
description: Audit GCP IAM: over-privileged bindings and primitive-role usage.
risk: moderate
permissions: [cloud.read]
requires_confirmation: true
tags: [cloud]
version: 1.0.0
---
# Auditing GCP IAM Permissions

## Purpose

Systematically audit Google Cloud IAM policies — who can do what, on which resources —
across organizations, folders, and projects to find over-privileged principals, dormant
service account keys, and risky bindings before they are abused.

## When to use

- Periodic cloud security reviews and compliance audits.
- After organization changes, project migrations, or incident response in GCP.
- When onboarding a new organization or folder into the security program.
- Before granting a third party access to a project (verify least privilege after).

## Prerequisites

- Written authorization and a defined scope: organization, folder, and project IDs in
  bounds.
- Read-only audit access (`roles/viewer` plus `roles/iam.securityReviewer` where available)
  on the in-scope hierarchy.
- Inventory of expected break-glass accounts, CI/CD service accounts, and third-party
  access grants.

## Procedure

1. **Map the resource hierarchy.**
   - List organizations, folders, and projects in scope with
     `gcloud projects list` and `gcloud resource-manager folders list`.
   - IAM is inherited downward — a binding at the organization level affects everything
     below it, so start at the top.

2. **Dump IAM policies top-down.**
   - Run `gcloud organizations get-iam-policy <ORG_ID>`,
     `gcloud resource-manager folders get-iam-policy <FOLDER_ID>`, and
     `gcloud projects get-iam-policy <PROJECT_ID>` for each in-scope node.
   - Save every policy JSON with timestamps; these are the audit's primary evidence.

3. **Flag primitive and over-broad roles.**
   - Search policies for primitive roles (`roles/owner`, `roles/editor`, `roles/viewer`)
     — `roles/editor` on a project is effectively full control over its resources.
   - Flag bindings granting powerful predefined roles (`roles/iam.serviceAccountUser`,
     `roles/compute.admin`, `roles/storage.admin`) to broad groups like
     `allAuthenticatedUsers` or `allUsers` (the latter is public access).

4. **Audit service accounts.**
   - List service accounts per project (`gcloud iam service-accounts list`) and review
     which roles each holds.
   - List user-managed keys (`gcloud iam service-accounts keys list
     --iam-account=<SA_EMAIL>`) — flag keys older than the rotation policy, keys owned by
     departed users, and keys on accounts that should use Workload Identity Federation
     instead.

5. **Check service account impersonation chains.**
   - `roles/iam.serviceAccountTokenCreator` and `roles/iam.serviceAccountUser` let one
     principal act as another — map these grants and look for chains that reach a
     highly-privileged service account from a low-privilege starting point.

6. **Review cross-project and external bindings.**
   - Flag members from outside the organization (different domain, `googlegroups.com`
     groups you don't own) holding roles on internal projects.
   - Review VPC Service Controls perimeters and Shared VPC host-project attachments for
     unintended cross-project reach.

7. **Use Policy Analyzer and the IAM recommender.**
   - Run Policy Analyzer queries (via `gcloud policy-intelligence query-activity` or the
     console) to see which granted permissions were actually used in the last 90 days —
     unused permissions are least-privilege violations with evidence.
   - Review IAM recommender output for rightsizing suggestions, but adjudicate each one
     (recommenders miss break-glass and seasonal jobs).

8. **Check organization policies and constraints.**
   - Review `gcloud resource-manager org-policies list` for guardrails like
     `iam.disableServiceAccountKeyCreation`, `compute.requireOsLogin`, and domain
     restriction constraints.
   - Missing preventive guardrails are findings in themselves.

9. **Verify audit logging.**
   - Confirm Cloud Audit Logs (Admin Activity, Data Access where required) are enabled and
     exported to a locked-down sink with adequate retention.
   - Verify alerts on IAM policy changes (`SetIamPolicy`) — privilege changes should page
     someone.

10. **Remediate and verify.**
    - Replace primitive roles with least-privilege predefined or custom roles, rotate or
      delete stale keys, and remove unused bindings.
    - Re-dump the affected policies and diff against the baseline to confirm closure.

## Key tools & commands

- `gcloud organizations|resource-manager folders|projects get-iam-policy <ID>` — the core
  read-only audit primitives.
- `gcloud asset search-all-iam-policies --scope=organizations/<ORG_ID>
  --query="policy:roles/owner"` — hunt a specific role across the whole estate.
- `gcloud iam service-accounts keys list --iam-account=<SA_EMAIL>` — key hygiene.
- `gcloud policy-troubleshoot iam <resource> --principal-email=<E> --permission=<P>` —
  verify what a principal can actually do (useful when adjudicating).
- Policy Analyzer and IAM recommender in the console — usage-based rightsizing evidence.

## Expected outputs

- IAM policy dumps per hierarchy node with timestamps.
- Findings: principal, role, resource, evidence, severity (primitive roles, stale keys,
  impersonation chains, external bindings).
- Policy Analyzer usage evidence supporting least-privilege recommendations.
- Remediation log with before/after policy diffs.

## Pitfalls

- Forgetting inheritance — a clean project policy means nothing under a dirty folder or
  organization policy.
- `allAuthenticatedUsers` is not "authenticated employees" — it includes any Google
  account; treat it as broad external access.
- Dormant bindings on deleted users/groups that silently re-activate if the identity is
  recreated.
- Trusting the recommender blindly — break-glass accounts and annual jobs look "unused"
  and will be wrongly flagged for removal.

## References

- MITRE ATT&CK: T1078 (Valid Accounts), T1552 (Unsecured Credentials), T1134 (Access Token
  Manipulation — cloud IAM analog).
- Google Cloud documentation: "IAM basic and predefined roles", "Service account best
  practices", "Workload Identity Federation", "Policy Analyzer", "Organization policy
  constraints".
- CIS Google Cloud Platform Foundations Benchmark: IAM controls.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
