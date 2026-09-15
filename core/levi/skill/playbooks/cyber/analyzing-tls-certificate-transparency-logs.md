# Analyzing TLS Certificate Transparency Logs

See also: auditing-tls-certificate-transparency-logs.md, analyzing-certificate-transparency-for-phishing.md

## Purpose

Monitor Certificate Transparency (CT) logs — the public, append-only records of issued TLS certificates — to detect certificates issued for your domains (or lookalike domains) that you did not authorize. Unauthorized issuance is an early warning of phishing infrastructure, subdomain takeover preparation, or a compromised certificate authority process.

CT monitoring is one of the cheapest high-value detective controls available: the data is public, the queries are free, and a single alert can precede a phishing campaign by days.

## When to use

- Continuous monitoring: catching misissued or attacker-requested certificates for your brand domains.
- Incident response: checking whether an attacker obtained a valid certificate for a lookalike domain during a phishing campaign.
- Pre-deployment validation: confirming the certificates currently issued for your domains match your inventory.
- M&A or rebrand: discovering certificates issued for newly acquired domains you now own.
- Third-party risk: spotting certificates issued for your domains by SaaS vendors or partners outside your process.

## Prerequisites

- Written authorization from the domain owner or security leadership to monitor the specified domains; include the exact domain list and the response procedure for hits.
- An authoritative inventory of your legitimate certificates: issuing CAs, issuance dates, and the process that requests them, so you can distinguish authorized issuance from rogue issuance.
- A designated response contact (PKI team, domain registrar liaison) for revocation requests.
- Data-handling notes: CT data is public, but your monitoring queries and alert logic are internal — store them accordingly.
- A list of authorized third-party issuers (CDNs, SaaS platforms that issue certs for your domains) to suppress expected hits.

## Procedure

1. Define the watchlist. List every domain and wildcard you own, plus high-value lookalikes (common typosquats, hyphenated variants, IDN homographs of your brand). Store it as a versioned file — the watchlist is a living document.
2. Choose the log sources. Query the major CT logs via an aggregator: crt.sh (web UI and JSON API: `https://crt.sh/?q=%25.example.com&output=json`), the Cert Spotter API, or a certstream feed for real-time issuance. Using at least two sources guards against aggregator gaps.
3. Pull historical issuance. For each watched domain, fetch all logged certificates: `curl -s "https://crt.sh/?q=%25.example.com&output=json" | jq '.[] | {issuer: .issuer_name, not_before, name_value}'`. Reconcile against your inventory — every entry should map to a known issuance event.
4. Check CAA records as context. Query DNS CAA records for your domains (`dig example.com CAA`): they declare which CAs may issue. A certificate from a CA not in your CAA set is either a CAA violation worth reporting or a sign your CAA records need updating — determine which.
5. Set up continuous monitoring. Subscribe to a real-time feed (certstream) filtered on your watchlist patterns, or poll the aggregator APIs on a schedule (hourly is typical). Alert on: any new certificate for an exact owned domain not in the inventory pipeline, and any new certificate for a lookalike domain regardless of issuer.
6. Triage each alert. For a hit, collect: the full certificate (crt.sh provides download links), issuer CA, issuance timestamp, SAN list, and whether the private key could plausibly be attacker-held. Check the domain's DNS and hosting — an issued certificate plus active phishing content is a confirmed hostile use.
7. Investigate misissuance. If a certificate was issued for your exact domain outside your process: determine which CA issued it, whether domain validation was abused (DNS hijack, compromised validation endpoint), and whether the certificate has been used (check your TLS logs and CT "seen" timestamps). Treat this as a potential CA-process compromise, not just a bad cert.
8. Respond. For attacker lookalike domains: request takedown via the hosting provider and registrar, submit the certificate to your threat-intel platform, and consider a CA revocation request if the cert impersonates your brand. For misissued certs on your own domains: request revocation from the issuing CA, rotate any exposed material, and fix the validation weakness.
9. Report CA problems upward. For genuine misissuance or CAA violations, file a report with the issuing CA and consider reporting to the CA/Browser Forum or Mozilla's bug tracker (for publicly trusted CAs). CAs are required to investigate misissuance reports — your report improves the ecosystem.
10. Review and tune. Weekly, review false positives (authorized issuances the inventory missed — usually a process gap, not a tool gap) and update the inventory and watchlist. Monthly, verify the monitoring pipeline itself is healthy: inject a test pattern and confirm the alert fires.

## Key tools & commands

- crt.sh: `curl -s "https://crt.sh/?q=%25.example.com&output=json"` for historical issuance; the web UI for interactive review and certificate download.
- certstream-python: `from certstream import listen_for_all_certs; listen_for_all_certs(callback)` for real-time issuance monitoring with a domain-match callback.
- Cert Spotter API (sslmate) for monitored-domain alerting with a dashboard.
- `openssl x509 -in cert.pem -noout -text` to inspect a downloaded certificate's issuer, SANs, and validity window.
- `dig <domain> CAA` for checking Certificate Authority Authorization records.
- `jq` for filtering aggregator JSON by issuer or date.

## Expected outputs

- A versioned domain watchlist (owned + lookalike patterns).
- A reconciled issuance inventory: every logged certificate mapped to authorized or unauthorized.
- CAA record review with violations or gaps noted.
- A continuous-monitoring configuration (feed subscriptions, poll schedule, alert rules).
- Per-alert triage records: certificate details, DNS/hosting findings, disposition.
- Revocation/takedown requests filed, with ticket references.
- CA misissuance reports filed where applicable.
- A weekly tuning log and monthly pipeline health-check record.

## Pitfalls

- Alerting on your own CDN or SaaS vendors: many providers issue certificates for customer domains legitimately — inventory them or drown in false positives.
- Watching only exact domains: attackers register lookalikes, not your domain. The lookalike pattern list is where the value is.
- Assuming CT coverage is instant: there is a lag between issuance and log inclusion, and a lag between inclusion and aggregator indexing. State your detection-delay assumption.
- Treating a logged certificate as proof of active attack: issuance is preparation. Confirm hostile use (DNS, hosting, content) before escalating.
- Forgetting precertificates: CT logs contain precertificates that may never become final certificates — dedupe by serial/issuer before counting "issuances."
- Wildcard certificates hiding subdomains: a `*.example.com` cert won't name the phishing subdomain. Pair CT monitoring with DNS monitoring for full coverage.
- Alert fatigue from certificate renewals: automated renewals (Let's Encrypt, ACM) generate constant "new certificate" events — baseline the renewal cadence and alert only on out-of-pattern issuance.

## References

- RFC 6962 (Certificate Transparency) — the log protocol and Merkle-tree auditability.
- RFC 8659 (DNS CAA) — Certificate Authority Authorization records.
- crt.sh documentation and JSON API usage.
- certstream project documentation — real-time CT feed consumption.
- CA/Browser Forum Baseline Requirements — issuance and revocation expectations for CAs.
- MITRE ATT&CK T1583.004 (Acquire Infrastructure: Server) and T1598 (Phishing for Information) for the attacker-use context.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
