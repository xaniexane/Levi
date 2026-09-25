---
skill_id: cyber_implementing_gcp_organization_policy_constraints
name: GCP Organization Policy Constraints
description: Apply GCP Organization Policy constraints as preventive guardrails across the resource hierarchy.
risk: low
permissions: []
requires_confirmation: false
tags: [gcp, governance]
version: 1.0.0
---
## Purpose
Detective controls find misconfigurations after deployment; organization policies prevent them from
being created. GCP Organization Policies are hierarchical guardrails (organization → folder →
project) that constrain resource configuration: no public IPs, required CMEK, allowed regions,
domain-restricted sharing. This playbook implements them as the preventive backbone of GCP
governance.

## When to use
- Preventing entire classes of GCP misconfigurations at creation time.
- Meeting data-residency, encryption, and sharing requirements (GDPR, HIPAA, internal policy).
- Governing decentralized GCP usage where teams provision freely.
- After repeated misconfiguration findings that detective controls catch too late.
- As the preventive layer above SCC/CSPM findings.

## Prerequisites
- Resource hierarchy designed: organization → folders (per environment/business unit) → projects,
  with policy inheritance understood.
- Defined guardrail requirements per data classification and environment (prod vs. dev differ).
- Organization admin rights to set policies at the org/folder level.
- Inventory of existing resources that will become non-compliant (the remediation backlog).
- Change communication: policies block provisioning — teams need to know what's constrained and why.

## Procedure
1. **Start with the highest-value boolean constraints.** Priority list: compute.requireOsLogin (or
   disable SA key creation), iam.disableServiceAccountKeyCreation (kills the most abused credential
   type), compute.vmExternalIpAccess (deny public IPs where not needed),
   storage.uniformBucketLevelAccess, sql.restrictPublicIp, iam.allowServiceAccountCredentialLifetime
   (short-lived). Each prevents a well-known misconfiguration class.
2. **Add list constraints for boundaries.** Define: resource locations (allowed regions — data
   residency), trusted image projects (only approved images), domain restricted sharing
   (iam.allowedPolicyMemberDomains — no external sharing outside the org), and allowed ingress
   settings for Cloud Run/functions. Lists encode "where" and "with whom."
3. **Scope by hierarchy deliberately.** Set strict policies at the org root for universal rules (no
   public IPs on databases, domain-restricted sharing); relax or specialize at folder/project level
   where justified (dev folders may allow external IPs for testing — documented). Inheritance means
   one org-level policy covers everything — use that power carefully.
4. **Assess existing-resource impact first.** Use the policy simulator / dry-run to see which
   existing resources violate proposed constraints. Build the remediation or exemption plan before
   enforcing — enforcing blind breaks running workloads and creates emergency exemptions that never
   expire.
5. **Roll out in monitor-then-enforce phases.** Where dry-run is available, measure violations for 2
   weeks; otherwise, announce the policy with an effective date, remediate the backlog, then
   enforce. Each constraint: communicate, remediate, enforce, verify.
6. **Manage exemptions formally.** Project-level policy overrides for genuine needs: documented
   justification, compensating controls, owner, expiry. Review exemptions quarterly — they
   accumulate. Prefer fixing the architecture over exempting it.
7. **Protect the policy administration.** Restrict who can set org policies (organization policy
   admin role, held centrally); log and alert on policy changes. A decentralized ability to relax
   guardrails voids them — centralize with a transparent request process.
8. **Combine with IAM and SCC.** Org policies constrain configuration; IAM constrains who; SCC
   (Security Command Center) detects what slipped through. Report the three together as the GCP
   governance control set, and feed SCC findings back into new constraints (repeat finding classes
   become new policies).
9. **Test constraint effectiveness.** Attempt: creating a public IP where denied, uploading to a
   disallowed region, sharing outside the domain, creating a service-account key where disabled —
   all must fail with clear errors. Document as control evidence for auditors.
10. **Review constraints quarterly.** New GCP services need new constraints (the platform evolves
    monthly); reassess exemptions; verify new folders/projects inherit correctly. Constraints are
    living policy — stale ones miss new service risks.

## Expected outputs
- Prioritized boolean and list constraints enforced across the hierarchy with documented rationale.
- Dry-run impact assessments and remediation of existing violations before enforcement.
- Formal exemption process with expiries and quarterly reviews.
- Centralized policy administration with change alerting.
- Effectiveness tests and quarterly constraint reviews tied to SCC findings.

## Pitfalls
- Enforcing without impact assessment: breaking production workloads on day one destroys the
  program's credibility. Simulate first.
- Overly broad org-level denies: blocking legitimate dev/test patterns creates exemption floods.
  Tier by folder (prod strict, dev pragmatic).
- Exemptions without expiry: temporary overrides become permanent. Every exemption has a date and an
  owner.
- Decentralized policy admin: teams relaxing their own guardrails defeats the purpose. Centralize
  with a fast, transparent request path.
- Set-and-forget: new GCP services launch without constraints covering them. Quarterly reviews must
  include new-service coverage.

## References
- Google Cloud Organization Policy documentation (constraints, hierarchy, dry-run)
- CIS Google Cloud Platform Foundations Benchmark
- NIST SP 800-53 CM-6, CM-7 (configuration settings, least functionality)
- Google Cloud Architecture Framework (governance guidance)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
