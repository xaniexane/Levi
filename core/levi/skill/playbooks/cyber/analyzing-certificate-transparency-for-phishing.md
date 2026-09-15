# Analyzing Certificate Transparency Logs for Phishing

## Purpose

Use Certificate Transparency (CT) logs to detect phishing infrastructure
early — spotting fraudulently or lookalike-issued certificates for your brand
*before* the phishing campaign mails its first lure. Certificates are
typically issued days before a campaign launches, giving defenders a rare
head start.

## When to use

- Brand/domain protection: continuous monitoring for certificates issued for
  your domains or lookalikes.
- Incident response: a phishing report arrives and you want the full set of
  related malicious certificates and infrastructure, not just the one URL in
  the ticket.
- Threat hunting: finding phishing kits staging on newly certified domains.
- Pre-attack warning: certificates issued but domains not yet live indicate
  staging — prepare takedowns in advance.
- Post-takedown verification: confirming the actor didn't simply re-certify
  under a new lookalike.

See also: analyzing-tls-certificate-transparency-logs.md, analyzing-typosquatting-domains-with-dnstwist.md

## Prerequisites

- Written authorization is not required for querying public CT logs, but any
  follow-on action against third-party infrastructure (takedown requests,
  registrar complaints) needs legal/brand-owner approval — define the
  approval workflow before your first find.
- Chain-of-custody notes: record query times, data sources, and certificate
  details (serial, issuer, SANs) for any cert that becomes incident evidence.
- A defined watchlist: your exact domains, common misspellings, brand
  keywords, executive-name domains, and product names.
- Access to a CT search interface (crt.sh, Censys, or a CT-log streaming
  API) and your SIEM or ticketing system for the triage queue.

## Procedure

1. **Build the watchlist.** Include: exact brand domains, IDN/homoglyph variants, `brand-keyword` combos (e.g., `brand-support`, `brand-secure`, `brand-verify`), and TLD-swapped variants of your primary domains. Document the generation logic so gaps are visible and auditable. Review the list quarterly — brands launch products, and each product name is a new lure keyword.
2. **Query CT logs for exact-domain issuance.** On crt.sh, search `%.example.com` (the `%` wildcard covers subdomains) and review recent issuances. Any certificate for your domain you did not request is an incident — investigate issuance via your CA's validation logs immediately; it may indicate DNS or validation compromise, not just phishing.
3. **Hunt lookalike domains.** Search CT logs for certificates containing your brand keywords issued in the last 7–30 days. Filter out your legitimate issuances (known CAs, known ACME automation accounts) and triage the remainder:
   ```bash
   # Pull recent certs matching a keyword via crt.sh JSON, then inspect
   curl -s "https://crt.sh/?q=%25brandkeyword%25&output=json" \
     | jq -r '.[].name_value' | sort -u
   ```
   Tune the window: too wide and you're triaging history; too narrow and you miss slow-burn staging.
4. **Enrich each suspect certificate.** For every candidate: resolve the domain (does it point at a live host?), fetch the site safely (sandboxed browser or `curl` — never a production browser), screenshot it, and compare against your brand assets. Note the issuing CA, issuance date, and full SAN list — phishing kits often bundle multiple lure domains in one certificate, giving you the campaign's domain list for free.
5. **Pivot to infrastructure.** From confirmed phishing domains, pivot on: shared IP/hosting ASN, reused certificates covering multiple phishing domains, name-server patterns, registrar, and creation-time clustering. This turns one phish into the campaign's infrastructure map — and often reveals sibling campaigns impersonating other brands on the same kit.
6. **Assess campaign readiness.** A certificate issued but a domain not yet resolving or serving content = staging. Prioritize monitoring; prepare takedown evidence packages (screenshots, cert details, brand-impersonation comparison, WHOIS) so the takedown request fires the moment the lure goes live rather than after victims report it.
7. **Initiate takedowns through proper channels.** Submit abuse reports to the hosting provider and registrar with your evidence package, and notify the issuing CA of brand impersonation. Track ticket IDs, response times, and outcomes — measure which providers act fastest so future playbooks route to the effective channels first.
8. **Automate the watch.** Deploy continuous CT monitoring (scheduled crt.sh/Censys queries or a CT-streaming service) feeding a triage queue with auto-suppression of known-legitimate issuances. Alert SLA: review within one business day; certificates age into campaigns fast, and a week-old unreviewed queue is just a slower way to learn about incidents from victims.
9. **Feed the SOC and the brand team.** Confirmed phishing domains become blocklist entries (proxy, DNS firewall, email gateway) and the infrastructure pivots become hunt queries. Verify blocks are actually effective (test resolution through your own resolvers). Brief brand/legal on active impersonations for customer-communication decisions.
10. **Measure and improve.**
    Track metrics: time from certificate issuance to detection, to takedown
    request, to takedown completion; false-positive rate of the triage
    queue; campaigns caught pre-launch vs. reported by victims.
    Use these to justify the program and tune the watchlist.

## Key tools & commands

- crt.sh — free CT search with JSON output for automation
  (`?q=...&output=json`); the workhorse for ad-hoc hunting.
- Censys / commercial CT APIs — higher-volume querying, certificate-field
  search, and alerting for continuous monitoring.
- `openssl s_client` / `curl` — safe certificate and content retrieval
  during enrichment (never open suspected phish in a production browser).
- Screenshot/sandbox tooling — visual comparison of phishing pages vs.
  legitimate brand pages for evidence packages.
- Your SIEM/ticketing integration — turning the CT feed into an assigned,
  SLA-tracked queue.

## Expected outputs

- A documented brand watchlist with generation logic and review cadence.
- Triage queue output: suspect certs classified legitimate / staging /
  active phish, with evidence per item.
- Infrastructure pivot map per confirmed campaign, including sibling-brand
  findings worth sharing.
- Takedown tickets with IDs, response times, and outcomes; blocklist
  additions verified effective.
- Program metrics: issuance-to-detection and issuance-to-takedown times,
  pre-launch catch rate.

## Pitfalls

- Let's Encrypt and other free CAs issue to anyone — a valid certificate on
  a phishing domain means nothing about legitimacy. Never treat "has HTTPS"
  as trust, and train the helpdesk out of that reflex.
- Wildcard CT queries are noisy; without suppression lists for your own
  automation (renewals, CI pipelines) you'll drown in your own certificates.
- Acting on lookalikes that are legitimate (partners, resellers, fan sites,
  security researchers) creates legal exposure — confirm impersonation
  intent before takedown, and keep legal in the loop on borderline cases.
- CT logs have propagation delay (typically minutes to hours); a brand-new
  phish may not appear yet. Pair with domain-registration feeds for the
  freshest signal.
- Attackers watch for takedowns and re-certify under new lookalikes within
  hours — post-takedown monitoring of the same infrastructure pivots catches
  the sequel.

## References

- RFC 6962 (Certificate Transparency) — log mechanics background
- crt.sh documentation (query syntax, JSON output, wildcard behavior)
- MITRE ATT&CK: T1583.004 (Acquire Infrastructure: Server), T1566
  (Phishing), T1583.001 (Acquire Infrastructure: Domains)
- CA/Browser Forum Baseline Requirements (issuance validation context —
  what a CA should have checked)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
