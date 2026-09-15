---
skill_id: cyber_performing_subdomain_enumeration_with_subfinder
name: Subdomain Enumeration with Subfinder
description: Enumerate subdomains with Subfinder to map attack surface and find forgotten or exposed assets.
risk: low
permissions: []
requires_confirmation: false
tags: [recon, subfinder, attack-surface]
version: 1.0.0
---

## Purpose
- Build a complete picture of the organization's external subdomain footprint.
- Find forgotten, misconfigured, or takeover-vulnerable subdomains before attackers do.
- Feed the asset inventory that vulnerability management and monitoring depend on.

## When to use
- During authorized external assessments and attack-surface reviews.
- Continuously, to catch new subdomains as teams deploy them.
- After acquisitions, to discover the inherited external footprint.
- When hunting for subdomain takeover opportunities defensively.

## Prerequisites
- Written authorization covering the target domains.
- Subfinder installed with API keys configured for passive sources.
- A process for validating results: DNS resolution checks and ownership verification.
- Coordination with asset owners for follow-up on findings.

## Procedure
1. Confirm authorization for the target domains and any rate-limit considerations.
2. Configure Subfinder with API keys for passive sources to maximize coverage.
3. Run enumeration against each in-scope domain, saving raw output with timestamps.
4. Supplement with certificate transparency logs and DNS dataset queries for additional names.
5. Resolve all discovered names and record which ones are live.
6. Fingerprint live hosts: web servers, cloud services, and exposed applications.
7. Check for subdomain takeover: dangling CNAMEs pointing to unclaimed cloud resources.
8. Reconcile findings against the official asset inventory to find shadow IT.
9. Report unknown or vulnerable subdomains to owners with remediation guidance.
10. Take over or remove dangling records immediately; claim the cloud resource or delete the DNS entry.
11. Schedule recurring enumeration so new subdomains are caught quickly.
12. Trend the external footprint size over time as an attack-surface metric.

## Expected outputs
- A validated subdomain inventory with live-host status.
- Subdomain takeover findings with remediation.
- Attack-surface trend metrics.
- An external asset inventory reconciled with internal CMDB records.
- Automated alerting when new subdomains appear.

## Pitfalls
- Enumerating domains without authorization; passive sources still constitute reconnaissance.
- Reporting raw tool output without validation; many enumerated names do not resolve.
- Finding takeovers but not fixing the DNS; the window stays open until the record changes.
- Ignoring wildcard DNS responses that make every name appear live.

## References
- ProjectDiscovery documentation for Subfinder configuration
- Subfinder project documentation
- OWASP guidance on subdomain takeover
- NIST SP 800-53 control CM-8 on system component inventory
- CISA guidance on attack surface management
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
