---
skill_id: cyber_defending_against_subdomain_enumeration_and_osint_exposure
name: Defending Against Subdomain Enumeration and OSINT Exposure
description: Reduce attacker-visible subdomain and OSINT footprint: build an authoritative asset inventory, eliminate dangling DNS records, monitor certificate transparency logs, and detect enumeration activity.
risk: low
permissions: []
requires_confirmation: false
tags: [reconnaissance, dns, asset-management]
version: 1.0.0
---
# Defending Against Subdomain Enumeration and OSINT Exposure

## Purpose

Give defenders a repeatable workflow for shrinking the subdomain and
public-OSINT footprint that reconnaissance tooling (subdomain brute-forcing,
certificate-transparency scraping, search-engine dorking) relies on. Covers
building an authoritative inventory of your own subdomains, removing dangling
and forgotten DNS records that enable subdomain takeover, monitoring
Certificate Transparency (CT) logs for rogue issuance, scrubbing sensitive
details from public sources, and detecting active enumeration against your
domains — all from the defender's side of the wire.

## When to use

- Before or during an external attack-surface review: establish what an
  outsider can discover about your domains.
- After acquiring a company or launching a new brand/domain: inherit and
  tame an unknown DNS footprint.
- When CT-log monitoring alerts on a certificate you did not request.
- When a subdomain-takeover report arrives (bug bounty, researcher, or
  customer) and you need to sweep for siblings of the same flaw.
- As a quarterly hygiene control alongside vulnerability management.
- When threat intel shows your organization in the crosshairs of an
  actor known for infrastructure mapping.

## Prerequisites

- Written authorization from the domain owner to audit DNS zones,
  registrar settings, and public-facing records for the domains in scope.
- Read access to the authoritative DNS zones (or a current zone export)
  and to registrar/CT-monitoring dashboards.
- An inventory baseline to compare against: CMDB, cloud account lists,
  and CDN/WAF configurations.
- Access to DNS query logs (authoritative server or DNS firewall) if you
  intend to detect active enumeration.
- A contact path to the teams that own web, mail, and cloud
  infrastructure so findings can be remediated rather than just reported.

## Procedure

1. **Define scope and pull authoritative data.** List every domain and
   subdomain suffix the organization owns, including defensive
   registrations and legacy brands. Export the current zone files or
   API-listed records from each DNS provider — this is ground truth, not
   what a scanner guesses.
2. **Reconcile records against reality.** For every A, AAAA, and CNAME
   record, confirm the target still exists and is still yours: does the
   host answer, does the cloud resource (bucket, app service, CDN
   distribution) still belong to your account, does the CNAME point at a
   service you still control? Flag anything orphaned or pointing at
   deprovisioned third-party services — these are takeover candidates.
3. **Remove or reclaim dangling records.** Delete DNS records for
   decommissioned services. Where a record must stay for now, re-point it
   at infrastructure you control (a sinkhole page or parking host) and
   open a tracked ticket with the owning team and a deadline.
4. **Harden the DNS control plane.** Restrict zone transfers (AXFR/IXFR)
   to authorized secondaries only, enable DNSSEC signing on the zones,
   lock the registrar account with MFA and registry lock where offered,
   and publish CAA records limiting which certificate authorities may
   issue for your domains.
5. **Stand up Certificate Transparency monitoring.** Subscribe each
   domain (including wildcards) to a CT-log monitor and alert on any
   newly issued certificate you did not request. Treat an unexpected
   certificate as a potential precursor to phishing or interception, and
   investigate issuance through the CA's own transparency and audit logs.
6. **Scrub sensitive OSINT leakage.** Search your domains in public
   code repositories, paste sites, job postings, conference slides, and
   documentation portals for hostnames, internal IP schemes, employee
   names tied to infrastructure, and credentials. Remove or redact what
   you find, and rotate anything that looks like a live secret.
7. **Detect active enumeration.** Baseline normal query volume on your
   authoritative servers, then alert on anomalies: high NXDOMAIN rates
   from single sources (dictionary guessing), bursts of ANY/TXT queries,
   or sequential label probing. Rate-limit or block abusive resolvers at
   the DNS firewall and feed the indicators to the SIEM.
8. **Institutionalize the review.** Put subdomain reconciliation and CT
   review on a recurring schedule (quarterly at minimum), and gate
   decommissioning runbooks on DNS cleanup so new dangling records stop
   appearing. Track mean-time-to-remediate for takeover-class findings.

## Expected outputs

- An authoritative, reconciled subdomain inventory per domain, with
  owner and business justification for each record.
- A remediated list: dangling records removed or re-pointed, with
  tickets for anything deferred.
- Registrar and DNS hardening checklist completed (transfer
  restrictions, DNSSEC, CAA, MFA, registry lock).
- Active CT-log monitoring with alerting wired to the SOC.
- Detection rules for DNS enumeration patterns tuned against your
  baseline, with documented true/false-positive rates.

## Pitfalls

- **Treating scanner output as ground truth.** External enumeration
  finds what is visible, not what is authoritative. Always reconcile
  against your own zone data or you will chase ghosts and miss real
   records.
- **Deleting records without checking mail flow.** MX, SPF, DKIM, and
  DMARC records look like clutter until inbound mail breaks. Verify
  dependencies before touching anything mail-related.
- **Alert fatigue from CT logs.** Large organizations see constant
  issuance (CDNs, SaaS vendors). Tune alerts to unexpected issuers and
  unexpected subdomains rather than every certificate event.
- **Forgetting acquisitions and shadow IT.** Marketing microsites,
  contractor-built landing pages, and acquired-company domains are the
  usual source of forgotten records — include them in scope explicitly.
- **One-time cleanup without process change.** Without a
  decommissioning gate, the footprint regrows within months. Fix the
  runbook, not just the records.

## References

- Certificate Transparency monitoring services and the crt.sh search
  interface for investigating issuance history.
- DNS CAA record specification (RFC 8659) for constraining issuance.
- DNSSEC deployment guidance from your DNS provider and ICANN resources.
- Subdomain-takeover research write-ups (defensive remediation sections)
  for the record types most commonly abused.
- Your DNS firewall / authoritative server documentation for
  query-logging and rate-limiting features.

---
*Original work authored for LEVI. Defensive blue-team playbook — detection, analysis, and hardening guidance only. Topic inspired by a reconnaissance phase script; no content copied from any external source.*
