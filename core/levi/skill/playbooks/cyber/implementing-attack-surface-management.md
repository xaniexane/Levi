---
skill_id: cyber_implementing_attack_surface_management
name: Attack Surface Management
description: Build continuous external attack-surface discovery, inventory, and risk reduction.
risk: low
permissions: []
requires_confirmation: false
tags: [attack-surface, asset-management]
version: 1.0.0
---
## Purpose
Your attack surface is what the internet sees: domains, subdomains, IPs, certificates, exposed
services, and cloud assets — most of it provisioned by teams who never told security. This playbook
implements attack surface management (ASM): continuous external discovery, asset inventory with
ownership, risk assessment of exposures, and a remediation loop that shrinks what attackers can
find.

## When to use
- Standing up external ASM as a program, or replacing periodic manual recon with continuous
  discovery.
- After incidents involving forgotten subdomains, exposed dev environments, or shadow cloud assets.
- During M&A: discovering the acquired company's internet footprint before attackers do.
- Before major launches, or continuously for organizations with heavy cloud/DevOps provisioning.
- As the external complement to internal attack-path analysis.

## Prerequisites
- Seed data: known domains, IP ranges (ARIN/RIPE records), ASNs, cloud accounts, and brand keywords
  for discovery.
- An ASM platform or toolchain (commercial ASM product, or combined open-source recon: subfinder,
  amass, httpx, nuclei — plus process).
- DNS and certificate-transparency access for passive discovery.
- Asset-ownership mapping (CMDB, cloud tagging standards, or a service catalog) to route findings.
- Takedown authority and contacts: domain registrar, hosting providers, and cloud account owners for
  rogue assets.

## Procedure
1. **Seed and discover broadly.** Feed domains, IP ranges, ASNs, and cloud accounts into discovery:
   subdomain enumeration, certificate-transparency logs, DNS datasets, BGP/ASN data, and cloud API
   enumeration. Discovery must run continuously — assets appear daily.
2. **Fingerprint everything found.** For each asset: resolve and banner-grab to identify services,
   technologies, and versions; screenshot web services; check for login pages, admin panels, and
   exposed development artifacts. An IP with no fingerprint is an unknown, not a non-issue.
3. **Inventory with ownership and classification.** Record: asset, exposure (internet-facing?),
   technology, owner team, business purpose, and data handled. Unknown-owner assets get a 30-day
   claim-or-takedown clock — unclaimed internet-facing assets are presumed rogue.
4. **Assess exposure risk.** Flag: end-of-life software, default credentials on login pages, exposed
   databases/admin consoles, dev/staging environments reachable externally, verbose error pages,
   expired or mismatched certificates, and dangling DNS (CNAMEs to unclaimed cloud resources —
   subdomain takeover risk).
5. **Prioritize by exploitability and value.** Rank: internet-facing + known-exploited CVE (check
   CISA KEV) + sensitive data or privileged function first. A marketing blog with an old CMS plugin
   is lower priority than an exposed Jenkins or a takeover-able subdomain.
6. **Drive remediation through owners.** Open tickets with evidence (screenshots, banners, CVE
   references), the required action (patch, take down, restrict, claim DNS), and severity-based
   deadlines. Track MTTR per team; escalate unclaimed assets to takedown.
7. **Hunt the specific high-risk patterns on a cadence.** Weekly automated checks: new subdomains,
   certificate-transparency for lookalike domains (typosquatting), dangling DNS records, newly
   exposed ports on known IPs, and cloud storage buckets with public access.
8. **Integrate with change and cloud governance.** Require new public DNS records and cloud
   deployments to register in the asset inventory (or auto-discover and auto-assign via tagging).
   ASM findings should block or gate risky provisioning where possible.
9. **Measure the surface, not just findings.** Track: total discovered assets, percent with
   confirmed owners, mean time to remediate critical exposures, count of rogue/takedown assets, and
   quarter-over-quarter change in internet-facing services. Shrinking the surface is the goal.
10. **Exercise the takedown muscle.** Maintain runbooks and contacts for: domain registrar
    takedowns, cloud resource deletion, DNS record removal, and abuse reports to hosters. Test with
    a real rogue asset periodically — takedown speed matters during incidents.

## Expected outputs
- A continuously updated external asset inventory with owners, exposure, and technology
  fingerprints.
- Risk-ranked exposure findings with remediation tickets, deadlines, and MTTR tracking.
- Weekly high-risk pattern hunts (dangling DNS, KEV-exposed services, typosquat domains).
- Takedown runbooks with tested contacts and measured response times.
- Trend metrics showing the attack surface shrinking (or why it isn't).

## Pitfalls
- One-time discovery treated as a program: the surface changes daily; snapshots decay immediately.
- Discovery without ownership mapping: thousands of assets and nobody to fix them. Claim-or-takedown
  clocks force resolution.
- Alerting on everything: tune to exploitable exposures or teams will ignore the feed. KEV +
  exposure + sensitivity is the filter.
- Missing cloud and subsidiary assets: seed data must include all cloud accounts, acquired brands,
  and partner-managed domains — attackers don't respect org charts.
- Confusing ASM with vulnerability scanning: ASM answers "what do we expose and who owns it"; vuln
  scanning answers "what's patchable." You need both, in that order.

## References
- CISA Binding Operational Directive 23-01 and KEV catalog (prioritizing known-exploited exposures)
- OWASP Attack Surface Analysis guidance
- NIST SP 800-53 CM-8 (system component inventory) and CA-7 (continuous monitoring)
- MITRE ATT&CK T1595 (Active Scanning), T1596 (Search Open Technical Databases) — the adversary's
  ASM
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
