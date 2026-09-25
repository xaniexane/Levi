---
skill_id: web_ops_certificate_management
name: TLS Certificate Management
description: Get, install, renew, and monitor certificates without the 2am expiry panic.
risk: info
permissions: []
requires_confirmation: false
tags: [ops, deployment, security]
version: 1.0.0
---
# TLS Certificate Management
## Purpose
Make certificate expiry a solved problem: automated issuance, tested renewal, and monitored deadlines.
## Key ideas
- Automated CAs (like ACME-based issuers) make certificates free and renewable by software, not by calendar.
- Renewal must be automated AND verified: a cron job that silently fails is the same as no cron job.
- Certificates need the full chain installed; a missing intermediate breaks some clients but not others.
- Wildcard certificates cover subdomains with one cert but concentrate risk; prefer per-service certs where cheap.
- Monitor expiry independently of the renewal automation; two systems must agree the cert is fresh.

## In practice
Automate issuance and renewal from the start, then test renewal in staging by forcing it early; the renewal that has never run is the renewal that fails on expiry day. Alert at 30, 14, and 3 days before expiry through a channel someone reads, independent of the automation's own logs. After installing or renewing, verify the served chain with an external checker, because local tests miss the intermediate-cert issues that break mobile clients. Document where each certificate lives, which service serves it, and how it renews; during an incident, this inventory is worth more than any tool.

```bash
# Issue/renew via ACME (conceptual)
certbot renew --quiet --deploy-hook "nginx -s reload"

# Verify what the server actually serves, including the chain
echo | openssl s_client -connect shop.example.com:443 -servername shop.example.com 2>/dev/null   | openssl x509 -noout -dates -subject

# Alert threshold check (days remaining)
openssl x509 -in /etc/ssl/shop.crt -noout -checkend 2592000 || echo "RENEW SOON"
```

## Common mistakes
- Setting up auto-renewal but never testing it, discovering the failure at expiry.
- Forgetting intermediate certificates, breaking Android and older clients while desktop looks fine.
- Relying on one person's calendar reminder instead of automated monitoring.

## Checklist
- Is renewal automated and has it been tested end-to-end?
- Do independent monitors alert on expiry at 30/14/3 days?
- Is the full chain verified from outside after each renewal?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
