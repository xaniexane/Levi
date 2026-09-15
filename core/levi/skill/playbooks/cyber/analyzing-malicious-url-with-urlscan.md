# Analyzing Malicious URLs with urlscan.io

## Purpose

urlscan.io detonates a URL in an instrumented browser and records everything:
the DOM, network transactions, screenshots, downloaded files, and verdicts.
This playbook shows how to submit URLs safely, read a scan report like an
analyst, pivot on infrastructure, and automate lookups — without ever visiting
the malicious URL yourself.

## When to use

- A suspicious URL arrived via phishing email, chat, or user report.
- Triage of URLs extracted from malware, PDFs, or macro documents.
- Pivoting from one malicious URL to related infrastructure (shared IPs,
  certificates, ASNs).
- Checking whether a URL is already known before submitting (avoid tipping
  off attackers with a fresh scan of a targeted phish).

## Prerequisites

- Written authorization for the investigation; note that submitting a URL
  creates a **public** scan by default — never submit URLs containing
  credentials, session tokens, or internal hostnames. Use unlisted/private
  scans (requires an API key and appropriate plan) for sensitive URLs.
- A urlscan.io account and API key for submissions and higher rate limits.
- Operational caution: a fresh scan notifies the site operator via the visit;
  for highly targeted phishing, search existing scans first.

## Procedure

1. Search before submitting: on urlscan.io, query the domain, URL, or hash
   (`domain:example.com`, `page.url:"..."`, `filename:*.exe`). An existing
   recent scan may answer your question with no new footprint.
2. If no usable scan exists, submit via the API:
   `curl -X POST https://urlscan.io/api/v1/scan/ -H "API-Key: <key>" \
   -H "Content-Type: application/json" -d '{"url":"<url>","visibility":"unlisted"}'`
   Record the returned scan UUID and poll `https://urlscan.io/api/v1/result/<uuid>/`.
3. Read the report top-down:
   - Verdicts and tags (phishing, malware) — treat as triage hints, not truth.
   - Screenshot and DOM snapshot: does the page impersonate a brand (login
     form, logo)? Compare against the legitimate site.
   - Transactions: list every request — look for credential POSTs, secondary
     payload downloads, and requests to unrelated malicious domains.
4. Analyze the page's behavior: JavaScript that harvests form input, redirects
   through multiple hops, or fingerprints the visitor (these show in the DOM
   and transaction list).
5. Pivot on infrastructure: from the report's IPs, ASNs, and certificate
   hashes, search urlscan for other pages on the same infrastructure
   (`ip:<ip>`, `asn:<asn>`). Shared infrastructure reveals campaigns.
6. Extract IOCs: final URLs, redirect chain, IPs, domains, file hashes of
   downloads, and certificate fingerprints. Feed them into your IOC workflow.
7. For credential-phishing pages, capture which brand is impersonated and the
   form field names — this informs user-warning and detection content.
8. Decide disposition: block at proxy/DNS, submit to takedown via the hosting
   provider or registrar, and notify affected users if credentials were entered.
9. For pages that cloak, compare the urlscan DOM/screenshot against an
   independent fetch (proxy logs, second scanner) — serving different content
   to the scanner confirms cloaking and is itself IOC-worthy behavior.

## Key tools & commands

- urlscan.io search syntax: `domain:`, `page.url:`, `ip:`, `asn:`,
  `filename:`, `hash:`.
- Submission API: `POST https://urlscan.io/api/v1/scan/` with `API-Key` header;
  result API: `GET https://urlscan.io/api/v1/result/<uuid>/`.
- `urlscan` CLI / Python wrappers — scripted submission and result polling.
- Companion: VirusTotal URL analysis for a second verdict source.

## Expected outputs

- Scan report interpretation: malicious/benign verdict with evidence
  (screenshot description, transaction anomalies, verdicts).
- IOC set: URLs, redirect chain, IPs, domains, cert hashes, downloaded files.
- Campaign pivots: related scans on shared infrastructure.
- Disposition: blocks placed, takedown requested, users notified.

## Pitfalls

- Public scans leak the URL to the world — including any tokens in it. Default
  to unlisted/private for anything sensitive.
- A "clean" verdict on a fresh scan may mean cloaking (the site served benign
  content to the scanner's IP/ASN) — re-scan from different settings or treat
  with suspicion if other evidence says malicious.
- Scanning a targeted phish tips off the attacker that you are investigating;
  search first, submit second.
- Verdicts are automated and occasionally wrong in both directions — always
  read the transactions and DOM yourself.
- Short-lived phishing pages may be dead by scan time; a dead page is not
  proof the URL was benign.
- Submitting the same targeted URL repeatedly burns the investigation — each
  scan is another visit the attacker can see; batch your questions into as few
  scans as possible.

## References

- urlscan.io documentation and search API reference (urlscan.io/docs)
- MITRE ATT&CK: T1566.002 (Phishing: Spearphishing Link),
  T1204.001 (Malicious Link)
- APWG / brand-impersonation reporting guidance for takedowns

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
