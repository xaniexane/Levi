---
skill_id: cyber_implementing_api_threat_protection_with_apigee
name: API Threat Protection with Apigee
description: Deploy layered API threat protection on Apigee: policies, quotas, threat detection, and anomaly response.
risk: low
permissions: []
requires_confirmation: false
tags: [api, gateway]
version: 1.0.0
---
## Purpose
An API gateway is the enforcement point where contract-level promises become runtime reality. This
playbook implements threat protection on Google Cloud's Apigee: request validation, quota and
spike-arrest policies, threat-detection rules, and analytics-driven anomaly response — turning the
gateway from a router into a security control. The policy patterns generalize to any API gateway.

## When to use
- Hardening an existing Apigee deployment that currently proxies traffic with minimal policy.
- Ahead of exposing partner or public APIs where you cannot trust client behavior.
- After incidents involving API abuse: credential stuffing, scraping, parameter injection, or DDoS
  via expensive endpoints.
- As the runtime enforcement arm of the API posture and testing playbooks.
- When compliance requires centralized authentication, audit logging, or traffic controls at the API
  tier.

## Prerequisites
- An Apigee organization/environment with administrative access and a non-production environment for
  policy testing.
- The API inventory and risk ranking from posture management — protect highest-risk APIs first.
- Authentication infrastructure to integrate: OAuth2/OIDC provider, API key management, or mTLS PKI.
- A logging/SIEM destination for Apigee analytics and audit events, with retention defined.
- Change control for gateway policy: who approves, how rollback works, and maintenance windows for
  enforcement changes.

## Procedure
1. **Map and prioritize API proxies.** Inventory every Apigee proxy: upstream target, exposure
   (internal/partner/public), auth model, and traffic volume. Rank protection rollout by exposure x
   sensitivity — public partner APIs first.
2. **Enforce authentication at the edge.** Apply VerifyAPIKey or OAuthV2 policies on every proxy; no
   anonymous passthrough for non-public endpoints. For partner APIs, prefer OAuth2
   client-credentials or mTLS over static keys; rotate keys on a schedule and on personnel changes.
3. **Validate every request against the contract.** Add JSONThreatProtection / XMLThreatProtection
   policies (depth, array/object counts, string lengths) and schema validation where contracts
   exist. Reject malformed payloads at the gateway — malformed input should never reach upstream.
4. **Apply quotas and spike arrest.** Set Quota (per developer/app, per day/hour) and SpikeArrest
   (burst smoothing) on all proxies, tightest on expensive or sensitive operations (search, export,
   auth endpoints). Quotas are both a cost control and an abuse control.
5. **Enable threat-detection rules.** Turn on Apigee's threat detection for anomalous patterns
   (unusual error rates, traffic spikes, suspicious geography) and route alerts to the SOC. Tune
   baselines per API — a batch-export endpoint has a different normal than a login endpoint.
6. **Add targeted protection policies.** For login/token endpoints: brute-force protection
   (failed-attempt throttling, CAPTCHA handoff). For all proxies: CORS policies restricted to known
   origins, response-cache controls for sensitive data, and masking of sensitive fields in
   trace/debug and analytics.
7. **Centralize logging and audit.** Ship proxy access logs, policy violations, and admin audit
   events to the SIEM. Ensure logs capture: client identity, API key/app, source IP, request path,
   response code, and latency — enough to reconstruct abuse timelines.
8. **Test policies in shadow before enforcing.** Deploy new policies in a non-production environment
   first; use Apigee trace sessions to verify legitimate traffic passes and attack samples are
   blocked. Promote with a rollback plan — a bad regex in a threat policy can block all traffic.
9. **Run a pre-launch abuse review for new APIs.** Before any new proxy goes live: confirm auth,
   quotas, validation, and logging are in place; run a light abuse test (fuzzed inputs, auth bypass
   attempts) against staging. No proxy ships with "we'll add policies later."
10. **Review and tune quarterly.** Analyze blocked-request logs for false positives (legitimate
    clients throttled) and false negatives (abuse that passed). Adjust quotas, validation limits,
    and detection thresholds; retire policies for decommissioned proxies.

## Expected outputs
- All prioritized proxies protected: edge authentication, request validation, quotas/spike arrest,
  CORS, and logging.
- Threat-detection alerts flowing to the SOC with per-API baselines.
- A tested change/rollback procedure for gateway policy.
- SIEM dashboards for API abuse: top blocked clients, error-rate anomalies, quota exhaustion.
- A launch checklist enforced for every new API proxy.

## Pitfalls
- Policies that exist but are not attached to all proxies: audit proxy-to-policy mapping, not just
  policy existence.
- Overly aggressive validation breaking legitimate clients (especially mobile apps on old versions)
  — phase in with monitoring, communicate changes to consumers.
- Logging that captures tokens or PII in cleartext: mask sensitive data in analytics and debug
  sessions.
- Quotas set from guesses instead of traffic analysis: too loose and they don't protect; too tight
  and they cause outages. Base them on measured p99 traffic.
- Forgetting the admin plane: Apigee management access needs MFA, IP restrictions, and audit logging
  too — a compromised gateway admin bypasses every proxy policy.

## References
- Google Cloud Apigee documentation (policies, threat detection, analytics)
- OWASP API Security Top 10 (threats the gateway layer must mitigate)
- NIST SP 800-204B (API gateway security patterns)
- MITRE ATT&CK T1190 (Exploit Public-Facing Application), T1110 (Brute Force)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
