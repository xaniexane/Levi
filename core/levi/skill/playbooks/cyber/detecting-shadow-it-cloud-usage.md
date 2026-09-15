---
skill_id: cyber_detecting_shadow_it_cloud_usage
name: Detecting Shadow IT Cloud Usage
description: Detect unsanctioned cloud service and SaaS usage (shadow IT).
risk: low
permissions: []
requires_confirmation: false
tags: [shadow-it, casb, cloud]
version: 1.0.0
---
## Purpose

Employees adopting SaaS and cloud services without IT approval creates unmanaged data flows, unmonitored access, and compliance gaps. This playbook covers detecting shadow IT with CASB/proxy/DNS telemetry, assessing the risk of discovered services, and building a sanctioned-alternative program rather than a whack-a-blocklist.

## When to use

- Leadership asks 'what SaaS are we actually using?' and nobody knows.
- A breach or leak involved an unsanctioned service.
- You need CASB use cases beyond malware blocking.
- Compliance (SOC 2, HIPAA, GDPR) requires knowing data processors.

## Prerequisites

- CASB (or proxy/firewall/DNS logs) with application identification for cloud/SaaS traffic.
- Identity provider logs to map SaaS usage to users.
- An approved-service catalog (even a starter list) for comparison.
- Data-classification policy to assess what's at stake in each service.

## Procedure

1. Measure from multiple vantage points. Aggregate CASB/proxy logs for distinct cloud applications by user and data volume; supplement with DNS query analysis for SaaS domains and IdP logs for SSO-bypassed services (services where users authenticate directly, not via SSO). No single source sees all shadow IT — triangulate.
2. Categorize discovered services by risk. For each unsanctioned service assess: data types uploaded (PII, source code, financials), authentication strength (SSO support? MFA?), the vendor's security posture (SOC 2, encryption, data residency), user count and business criticality, and whether corporate credentials are reused. Risk-rank; don't treat a team meme generator like an unsanctioned CRM holding customer data.
3. Investigate the high-risk subset deeply. For top-risk services: determine what data was uploaded (DLP/proxy inspection where lawful), who the admin users are, whether data can be exported/deleted, and whether the service suffered known breaches. Check for OAuth grants to unsanctioned apps in your IdP — shadow IT often arrives via 'Sign in with Google/Microsoft'.
4. Respond with sanction-and-substitute, not just block. For each service decide: sanction (add to approved catalog, negotiate DPA/SSO, bring under management), substitute (migrate users to an approved equivalent), or prohibit (block with a clear explanation and an approved alternative). Blocking without alternatives drives users to worse options — the program fails without the substitute path.
5. Build the intake and monitoring loop. Create a lightweight service-request process (fast enough that users actually use it), publish the approved catalog where users look, run shadow-IT discovery monthly, and track metrics: unsanctioned-service count, high-risk service count, mean time to disposition. Report trends to leadership, not just block counts.
6. Address the identity angle: enforce SSO for sanctioned services, monitor OAuth consent grants continuously, and run credential-hygiene checks for corporate passwords reused on external services.

## Expected outputs

- Shadow-IT inventory: services by user count, data volume, and risk rating.
- Disposition tracker: sanction / substitute / prohibit per service with owners.
- Lightweight intake process and published approved-service catalog.
- Monthly discovery cadence with trend metrics.

## Pitfalls

- Blocking without approved alternatives just pushes users to less-visible options.
- DNS-only discovery misses SaaS accessed via IPs/CDNs — combine with proxy/CASB app-ID.
- Personal-use SaaS on corporate networks isn't automatically a finding — scope to corporate data.
- OAuth-granted shadow apps bypass network detection entirely — monitor IdP consent grants.
- A heavyweight approval process nobody uses is worse than none — keep intake fast.

## References

- NIST SP 800-53 CM-8 (system component inventory), CM-10; CSA guidance on shadow IT and CASB; MITRE ATT&CK T1530 (Data from Cloud Storage) for exfiltration via unsanctioned services — https://attack.mitre.org/techniques/T1530/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
