# Analyzing API Gateway Access Logs

## Purpose

Turn API gateway access logs (AWS API Gateway, Azure API Management, Kong,
Apigee, or similar) into security signal: detect abuse, credential stuffing,
scraping, injection probing, and anomalous consumption patterns against your
APIs — and convert validated findings into engineering fixes and durable
detections.

## When to use

- Investigating a suspected API-abuse incident (account takeover waves,
  data scraping, token theft).
- Proactive threat hunting over API traffic for OWASP API Security Top 10
  patterns.
- Post-deploy review of a new endpoint's exposure and error-rate behavior.
- Building baselines and alerting for API-specific detections in the SIEM.
- Validating that rate limits, auth checks, and WAF rules are actually
  effective under adversarial traffic.

## Prerequisites

- Written authorization from the API/platform owner to access production
  access logs (they contain PII, tokens in some configurations, and customer
  data).
- Chain-of-custody notes if logs become incident evidence: record log
  source, time range exported, hash of the export, and collector.
- Access to the centralized log store (CloudWatch, Log Analytics, ELK/Splunk)
  with the gateway's access-log fields parsed — not raw blobs.
- Knowledge of the API surface: route inventory, auth model per route,
  expected client populations, and which endpoints are batch/export (their
  "normal" looks like an attack).

## Procedure

1. **Confirm log completeness.**
   Verify the gateway logs the fields you need: timestamp, source IP, HTTP
   method, path, status code, response size, latency, user-agent, request ID,
   and — critically — the authenticated principal (API key ID, JWT `sub`,
   client ID).
   If the principal is missing, file a logging gap before hunting; without
   it you cannot distinguish an attacker from a legitimate heavy user, and
   every conclusion will be weak.
2. **Baseline normal per route.**
   For each high-value route, compute per-principal request rates, typical
   status-code mix, geographic and user-agent norms, and payload-size norms
   over 2–4 weeks.
   Document batch/export endpoints separately.
   Store baselines where the SOC can reference them during triage.
3. **Hunt authentication abuse.**
   Aggregate 401/403 rates by IP and by principal.
   Signatures: high 401 counts from one IP across many principals
   (credential stuffing, T1110.004); sudden 403 spikes on a previously clean
   principal (token theft or permission change); `invalid_token` errors
   followed by success (token replay testing); password-reset or MFA-bypass
   endpoint abuse preceding account takeovers.
4. **Hunt enumeration and scraping (BOLA/IDOR probing).**
   Look for sequential ID traversal (`/orders/1001`, `/orders/1002`, …) from
   a single principal — classic broken-object-level-authorization probing
   (API1:2023).
   Detect via path-entropy analysis: many distinct object IDs per principal
   per hour far above baseline.
   Also flag large aggregate response sizes per principal (bulk exfiltration
   through individually legitimate reads).
5. **Hunt injection probing.**
   Search request paths, query strings, and logged body snippets for probes:
   `' OR '1'='1`, `<script`, `../`, `${jndi:`, GraphQL introspection queries,
   and mass-assignment attempts.
   A single source generating diverse probe payloads across routes is doing
   vulnerability discovery — block and investigate, and check whether any
   probe succeeded (200s with anomalous response sizes).
6. **Check rate-limit and quota telemetry.**
   Correlate 429 responses with the principals generating them.
   Attackers routinely sit just under limits; look for sustained traffic at
   80–100% of quota from principals that never behaved that way, and for
   distributed low-rate traffic (many IPs, one principal) evading per-IP
   limits.
   Missing 429s where you expect them means the limiter isn't working.
7. **Validate token and key hygiene in logs.**
   Confirm secrets are redacted/masked in stored logs.
   If you find raw API keys or tokens in log fields during this analysis,
   that is a finding in itself — rotate the exposed credentials immediately
   and fix the logging pipeline before continuing.
8. **Trace an incident end to end.**
   For a confirmed abusive principal: extract the full request timeline,
   identify the first anomalous request, enumerate which objects were
   accessed (for BOLA cases, list every object ID touched), determine data
   impact for breach-notification scoping, and check for lateral API abuse
   (did the same principal hit other services?).
9. **Convert to detections.**
   SIEM rules: (a) 401-rate anomaly per IP; (b) object-ID enumeration per
   principal; (c) probe-payload signatures; (d) quota-saturation anomaly;
   (e) new-principal access to sensitive routes.
   Tune thresholds per route using the baselines from step 2, and set review
   SLAs proportional to route sensitivity.
10. **Close the loop with engineering.**
    Findings should produce fixes, not just alerts: enforce per-principal
    rate limits, add object-level authorization checks, strip verbose error
    messages, ensure the gateway emits the authenticated principal on every
    log line, and add schema validation to reject malformed probing traffic
    earlier.

## Key tools & commands

- CloudWatch Logs Insights / Azure Log Analytics / Splunk / ELK —
  aggregation queries over the access logs.
- Example CloudWatch pattern (adapt field names to your log format):
  ```
  fields @timestamp, ip, httpMethod, path, status, principal
  | filter status in [401, 403]
  | stats count() by ip, principal | sort count desc | limit 50
  ```
- `jq` — ad-hoc analysis of exported JSON log samples:
  `jq -r '[.ip, .path, .status] | @tsv' logs.json`.
- API inventory tooling (gateway export, OpenAPI specs) — map observed paths
  against intended routes and spot shadow/undocumented endpoints.
- WAF/gateway analytics dashboards — quick visual triage before deep dives.

## Expected outputs

- A baseline document per critical route: normal rates, status mixes,
  principal populations, with review dates.
- Investigation findings: abusive principals/IPs with timelines, accessed
  objects, and data-impact assessment.
- Deployed SIEM detections with tuned thresholds and measured
  false-positive rates.
- Engineering backlog items: logging gaps fixed, authz gaps closed, rate
  limits tightened — each with an owner.

## Pitfalls

- NAT and egress proxies collapse many users into one IP — never block or
  accuse on IP alone; the authenticated principal is the identity that
  matters.
- Health checks and synthetic monitors generate alarming-looking traffic;
  exclude them by user-agent/principal before hunting.
- Log sampling at high-traffic gateways hides low-and-slow attacks. Know
  your sampling rate and its blind spots, or hunt on unsampled
  security-relevant fields.
- Verbose error messages in responses (stack traces, SQL errors) aid
  attackers and pollute log analysis — treat them as a hardening finding,
  not just noise.
- Time-zone confusion across gateway, application, and SIEM timestamps will
  corrupt timelines — normalize to UTC at ingest and verify.

## References

- OWASP API Security Top 10 (2023): API1 Broken Object Level
  Authorization, API2 Broken Authentication, API9 Improper Inventory
  Management
- MITRE ATT&CK: T1110.004 (Credential Stuffing), T1530 (Data from Cloud
  Storage — adjacent for bulk reads)
- AWS docs: "API Gateway access logging"; Azure docs: "API Management
  diagnostics logs"
- NIST SP 800-95, "Guide to Secure Web Services" (logging considerations)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
