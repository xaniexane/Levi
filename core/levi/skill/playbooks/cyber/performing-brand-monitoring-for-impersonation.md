---
skill_id: cyber_performing_brand_monitoring_for_impersonation
name: Brand Monitoring for Impersonation
description: Detect typosquat domains, lookalike social accounts, and phishing kits abusing your brand, and drive takedowns.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intel, phishing, brand-protection]
version: 1.0.0
---

## Purpose

Attackers register lookalike domains, clone login pages, and create social media profiles that impersonate your organization to phish customers and employees. Brand monitoring is the defensive discipline of finding that abuse early, assessing which instances are actively malicious, and getting them taken down. This playbook covers building a watchlist, choosing detection sources, triaging hits, preserving evidence, and executing takedowns through registrars, hosts, and platform abuse channels.

## When to use

- Standing always-on brand protection for an organization with a public customer base.
- A phishing report references a domain or page that looks like yours.
- Before a major product launch, funding announcement, or event that increases your phishing appeal.
- After a breach or public incident, when opportunistic impersonation typically spikes.
- Evaluating a brand-protection vendor or building the capability in-house.

## Prerequisites

- A canonical list of brand assets: primary domains, product names, executive names, trademarks, logos, and official social handles.
- Access to monitoring sources: certificate transparency logs, newly-registered-domain feeds, a typosquat generation capability, and social platform search/API access.
- Documented takedown contacts or accounts: registrars, hosting providers, and abuse desks for relevant social platforms.
- A triage owner and SLA definitions (e.g., active phishing kit: hours; parked lookalike: days).

## Procedure

1. **Build the watchlist.** Enumerate exact brand strings plus generated variants: typosquats (character omission, substitution, transposition, doubling), homoglyphs, hyphenation, added keywords (login, verify, support, secure), and alternate TLDs. Include executive names and product names, not just the corporate domain.
2. **Monitor certificate transparency.** Stream CT logs for certificates issued to any watchlist variant. A freshly issued certificate on a lookalike domain is often the earliest signal of an impending phishing campaign — frequently hours before the first victim report.
3. **Monitor domain registrations and DNS.** Subscribe to newly-observed-domain feeds and check watchlist variants for recent registration, parking pages that change to login forms, and MX records (suggesting email-based abuse is coming). Prioritize domains with brand-plus-keyword combinations.
4. **Scan social and app platforms.** Search major social networks, messaging channels, code repos, and mobile app stores for brand names, logos, and executive identities. Fake support accounts and "airdrop/claim" pages are common pretexts.
5. **Triage each hit.** Classify: benign (fan, reseller, defensive registration by you), suspicious (parked, for sale), or malicious (credential harvesting, malware, investment scam). For malicious sites, capture screenshots, HTML, and headers as evidence before any takedown request; note the hosting provider, registrar, and name servers.
6. **Assess active harm.** Check whether the phishing page is live and collecting credentials (test with dummy credentials only where lawful and safe), whether it is being distributed (search for the URL in phishing feeds and your email telemetry), and whether any of your users have visited it (proxy/DNS logs).
7. **Execute takedowns.** File abuse reports in parallel: registrar (phishing/impersonation), hosting provider (ToS violation), and, for lookalike domains, consider UDRP or registrar dispute processes for the highest-value cases. Use platform-specific impersonation report flows for social accounts. Track ticket IDs and follow up on SLA.
8. **Protect users during the window.** While takedown is pending, block the malicious domains and URLs at your email gateway, web proxy, and DNS filtering; publish an internal alert with the exact lure so helpdesk staff recognize victim reports; and consider a customer-facing notice if the campaign is broad.
9. **Close the loop.** Confirm the takedown (site unreachable, domain suspended, account removed), watch for re-registration or infrastructure reuse by the same actor (same kit, same name servers, same favicon hashes), and log the full lifecycle for metrics: time-to-detect, time-to-takedown, and victim exposure estimates.

## Expected outputs

- A maintained watchlist of brand variants across domains and platforms.
- Triaged hit log with benign/suspicious/malicious classifications and evidence captures.
- Takedown case files: abuse tickets, correspondence, and confirmation of removal.
- Defensive blocks deployed at email, proxy, and DNS layers during active campaigns.
- Program metrics: detection latency, takedown latency, and repeat-offender tracking.

## Pitfalls

- Alert fatigue from raw typosquat feeds — tune with certificate issuance and content analysis, not domain registration alone.
- Filing takedowns without preserving evidence first; once the site is down you lose the kit sample and attribution details.
- Ignoring social and messaging platforms while focusing only on domains; much modern impersonation never uses a domain you can seize.
- Treating parked lookalikes as harmless forever — re-check them, since attackers often park then weaponize.
- Forgetting defensive registrations: owning the most obvious variants yourself is cheaper than chasing takedowns for them.

## References

- Certificate Transparency (RFC 6962) and public CT log monitors
- ICANN UDRP policy documentation for domain dispute processes
- CISA guidance on phishing and brand-impersonation reporting
- NIST SP 800-177, "Trustworthy Email" (for related sender-authentication context)
- Platform-specific impersonation reporting flows (document the ones you use in runbooks)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
