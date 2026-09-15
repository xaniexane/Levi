# Auditing TLS Certificate Transparency Logs

## Purpose

Monitor Certificate Transparency (CT) logs for TLS certificates issued for your
organization's domains — catching mis-issued, attacker-controlled, or unexpected
certificates (a classic precursor to phishing sites and adversary-in-the-middle
infrastructure) quickly enough to act.

## When to use

- Continuous monitoring for unauthorized certificates on owned domains.
- Incident response: checking whether an attacker obtained a valid certificate for a
  lookalike or compromised domain.
- Pre-launch verification that only expected CAs issue for your domains (CAA check).
- M&A or brand-protection reviews of newly acquired domains.

See also: analyzing-tls-certificate-transparency-logs.md

## Prerequisites

- Written authorization if this extends beyond your own organization's domains; monitoring
  your own domains needs no external approval.
- The authoritative list of domains and subdomains to watch (from the domain registrar
  inventory and DNS zone data) — you can't detect unexpected certs without knowing what's
  expected.
- A CT data source: crt.sh, a commercial CT feed, or a self-hosted monitor (e.g.,
  certstream client); plus an alerting path (email, SIEM, ticket queue).
- Baseline of legitimate issuance: which CAs, which automation (ACME accounts), and
  typical cadence.

## Procedure

1. **Define the watchlist.**
   - Enumerate owned domains including lookalike-relevant variants you defensively hold;
     decide whether to also watch unowned lookalikes (brand-abuse monitoring is a
     separate, broader feed).
   - Include wildcard scope explicitly — `%.example.com` matching must cover arbitrary
     subdomains.

2. **Set up CT monitoring.**
   - Query crt.sh (`https://crt.sh/?q=%25.example.com&output=json`) for the current
     baseline, or subscribe to a certstream-style live feed filtered on your domains.
   - For continuous coverage, prefer a monitored service over manual queries — CT logs
     append constantly and manual checks miss the window between issuance and abuse.

3. **Establish the issuance baseline.**
   - For each domain record: issuing CA, certificate type (DV/OV/EV), SAN list, validity
     period, and issuance cadence.
   - Note which CAs are authorized via DNS CAA records (`dig example.com CAA`) — any
     issuer not on the CAA list is immediately suspicious.

4. **Triage new certificates.**
   - For each new cert: is the CA expected? Is the SAN list limited to legitimate names?
     Does the timing match automation cadence?
   - Investigate anomalies first: unknown CA, unexpected wildcard, odd SAN entries,
     certificates for hostnames that don't exist in your DNS.

5. **Investigate suspicious certificates.**
   - Check the domain's DNS and hosting: does the cert's SAN resolve to infrastructure
     you control? Look up the IP's ASN and hosting provider.
   - Check whether the hostname is live and what it serves — a valid cert on a phishing
     kit is the scenario this monitoring exists to catch.

6. **Respond to unauthorized issuance.**
   - If a cert was issued without authorization: contact the issuing CA to request
     revocation, investigate how domain validation was passed (compromised DNS, hijacked
     ACME account, mis-issued), and rotate any exposed validation credentials.
   - If it's attacker infrastructure on a lookalike domain: file abuse reports with the
     registrar/hosting provider and consider legal/brand-protection escalation.

7. **Verify CAA and harden issuance.**
   - Publish restrictive CAA records (`0 issue "letsencrypt.org"` style, plus
     `issuewild` and `iodef` for reporting) on every owned domain.
   - Restrict ACME account credentials, require DNS-01 challenges from locked-down DNS
     automation, and alert on CAA record changes.

8. **Tune and document.**
   - Record false positives (new legitimate automation, CA migrations) and encode them
     as allowlist rules.
   - Keep a runbook entry: who gets paged, what evidence to collect, CA contacts, and
     revocation request templates.

## Key tools & commands

- crt.sh web UI and JSON API (`?q=%25.example.com&output=json`) — historical and ad-hoc
  CT search.
- certstream / certstream-python — live CT feed for real-time alerting.
- `dig <domain> CAA` / `nslookup -type=CAA` — verify CAA records authorizing issuers.
- `openssl s_client -connect host:443 -servername <name> | openssl x509 -noout -text` —
  inspect the live certificate on a suspicious host.
- Commercial CT monitoring (e.g., via your CA or brand-protection vendor) for SLA-backed
  alerting at scale.

## Expected outputs

- Domain watchlist with baseline issuance profile per domain.
- Triage log: new certificates seen, disposition (legitimate/expected change/suspicious),
  and investigation notes.
- Incident records for unauthorized issuance with CA correspondence and revocation
  confirmation.
- CAA deployment status and hardening recommendations.

## Pitfalls

- Watching only the apex domain — attackers get certs for subdomains (`login.example.com`
  lookalikes at the subdomain level); wildcard matching is essential.
- CT log delay: there's a lag between issuance and log appearance; combine CT monitoring
  with CA notification services (e.g., CAA `iodef` reports) where available.
- Alert fatigue from legitimate automation churn — baseline ACME renewal cadence before
  writing alert thresholds.
- Assuming a valid certificate means a legitimate site — DV certificates prove domain
  control only, which attackers routinely achieve on lookalike domains.

## References

- RFC 6962 (Certificate Transparency) and RFC 8659 (DNS CAA).
- crt.sh documentation (Sectigo) and the certstream project.
- MITRE ATT&CK: T1583.004 (Acquire Infrastructure: Server — cert-backed phishing infra),
  T1557 (Adversary-in-the-Middle).
- CA/Browser Forum Baseline Requirements: revocation and mis-issuance handling.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
