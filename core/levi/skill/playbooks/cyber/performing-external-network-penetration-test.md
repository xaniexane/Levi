---
skill_id: cyber_performing_external_network_penetration_test
name: External Network Penetration Test
description: Scope and execute an authorized external network assessment from the defender's view.
risk: low
permissions: []
requires_confirmation: false
tags: [pentest, network, assessment]
version: 1.0.0
---
# External Network Penetration Test

## Purpose

An external network penetration test simulates what an Internet attacker
can reach: exposed services, misconfigurations, and exploitable flaws on
the perimeter. This playbook covers the defender's side of the engagement —
scoping, rules of engagement, and converting findings into lasting
improvements — so the test actually reduces risk.

## When to use

- Annual or compliance-driven external assessments (PCI DSS, SOC 2).
- After major perimeter changes: new VPN, migrated edge devices, cloud
  front doors added.
- Validating that previous critical findings are truly remediated.
- Benchmarking perimeter posture before a red-team exercise.

## Prerequisites

- Signed rules of engagement: in-scope IPs/domains, excluded systems,
  testing windows, and emergency contacts for both sides.
- Written authorization from an asset owner; for cloud assets, confirm
  the provider's penetration-testing policy permits the activity.
- A defined severity model and retest process agreed before testing
  starts.

## Procedure

1. Finalize scope and ROE: explicit IP ranges and domains, what's off-
   limits (production DoS testing, third-party SaaS, social engineering
   unless agreed), and how to pause the test.
2. Verify authorization artifacts: signed engagement letter, emergency
   contact list, and evidence that the client owns or may test every
   in-scope asset.
3. Run open-source reconnaissance first: DNS records, certificate
   transparency logs, exposed repos, and leaked credentials — these often
   reveal the easiest paths and are fully in-bounds.
4. Enumerate the perimeter methodically: port scans of in-scope ranges,
   service fingerprinting, and TLS/certificate review; document every
   exposed service, not just vulnerable ones.
5. Test for the high-value flaws: unpatched Internet-facing services,
   default or weak credentials on management interfaces, exposed admin
   panels, and misconfigured cloud storage reachable from outside.
6. Exploit only within ROE and with care: prefer proof-of-concept
   evidence (a harmless file write, a screenshot) over disruptive
   payloads; stop and notify immediately on unintended impact.
7. Document as you go: for each finding, capture the affected asset,
   reproduction steps, evidence, and business impact — remediation teams
   need the "how to reproduce" to verify fixes.
8. Deliver and retest: walk the report through with defenders, agree
   remediation owners and dates, then retest fixes rather than trusting
   the ticket closure.

## Expected outputs

- A signed ROE and authorization package retained for audit.
- A findings report with reproducible evidence, CVSS/severity ratings,
  and remediation guidance per finding.
- A retest report confirming fixes or reopening failures.
- Perimeter inventory updates: every exposed service now documented.

## Pitfalls

- Scope creep onto out-of-scope or third-party assets — clarify before
  touching anything ambiguous.
- Testing without confirming cloud-provider policy: some providers
  require notification or prohibit certain test types.
- Equating a clean report with a secure perimeter: tests are point-in-
  time; pair with continuous monitoring.
- Disruptive testing in production hours despite an agreed window.

## References

- NIST SP 800-115, Technical Guide to Information Security Testing and Assessment
- PTES (Penetration Testing Execution Standard) technical guidelines
- OWASP Testing Guide (for web-exposed components of the perimeter)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
