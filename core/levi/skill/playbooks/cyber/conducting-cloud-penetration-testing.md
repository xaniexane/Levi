---
skill_id: cyber_conducting_cloud_penetration_testing
name: Conducting Authorized Cloud Penetration Testing
description: Practitioner guide to planning and executing authorized cloud penetration tests within provider policies and defined scope.
risk: info
permissions: []
requires_confirmation: false
tags: [cloud, assessment, pentest]
version: 1.0.0
---
## Purpose
Cloud penetration testing assesses the customer's configuration and applications, not the provider's infrastructure -- and each provider has policies defining what is allowed. This playbook structures an authorized cloud pentest: provider-policy compliance, scoping, methodology across IAM, storage, compute, and networking, and reporting that drives remediation.

## When to use
- Assessing cloud configuration and application security before or after migration.
- Meeting compliance or customer requirements for periodic cloud testing.
- Validating that cloud hardening efforts are effective.
- Testing detection and response in cloud environments (purple-team style).

## Prerequisites
- Written authorization from the asset owner defining accounts, regions, and resources in scope.
- Provider testing policy reviewed and complied with (most major providers allow customer testing within published boundaries without pre-approval).
- Test identities with defined privilege levels; production data handling agreements.
- Rules of engagement: prohibited actions (DoS, data exfiltration beyond proof, provider-infrastructure testing).

## Procedure
1. Confirm authorization and policy compliance. Document scope, get sign-off, and verify planned techniques comply with the provider's penetration-testing policy.
2. Reconnoiter the cloud footprint. Inventory accounts, regions, storage buckets, exposed services, and DNS records within scope.
3. Assess identity and access. Review IAM policies, roles, and trust relationships for excessive privilege, wildcard actions, and confused-deputy risks.
4. Test storage and data exposure. Check bucket and share permissions, encryption settings, and public exposure of sensitive data.
5. Assess compute and networking. Review security groups, network ACLs, instance metadata protections, and container configurations.
6. Test application layers. Assess deployed applications for injection, broken access control, and misconfigured APIs per the agreed scope.
7. Attempt controlled privilege escalation. Within scope, demonstrate impact of misconfigurations (for example, reaching sensitive data via over-permissive roles) without disrupting services.
8. Report and retest. Document findings with evidence and remediation guidance prioritized by exploitability; retest after fixes.

## Expected outputs
- Assessment report with evidenced findings and remediation priorities.
- Confirmation of provider-policy compliance.
- Retest results.

## Pitfalls
- Testing provider infrastructure instead of customer configuration violates policy and law.
- Exfiltrating real customer data as proof goes beyond authorization; use canary data.
- Ignoring the provider's policy updates can invalidate your authorization mid-test.
- Findings without business context get deprioritized; tie each to data or access impact.

## References
- AWS, Microsoft Azure, and Google Cloud penetration testing policies
- CIS Benchmarks for cloud platforms
- NIST SP 800-53 cloud-relevant control families
- MITRE ATT&CK cloud matrices
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
