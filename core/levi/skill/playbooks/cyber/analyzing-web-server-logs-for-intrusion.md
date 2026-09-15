---
skill_id: cyber_analyzing_web_server_logs_for_intrusion
name: Analyzing Web Server Logs for Intrusion
description: Detect web intrusions: traversal, injection, and webshell indicators.
risk: low
permissions: []
requires_confirmation: false
tags: [network, siem]
version: 1.0.0
---
# Analyzing Web Server Logs for Intrusion

## Purpose

Detect and scope web-layer intrusions from server logs: scanning, exploitation attempts, webshell
activity, and data exfiltration over HTTP/S. Web logs are often the only record of what an external
attacker did before gaining a foothold, so this playbook turns access and error logs into an attack
timeline with attacker IPs, targeted URLs, and successful vs. failed attempts.

Web log analysis is fundamentally a correlation discipline: the access log shows the knock, the
error log shows the stumble, and the application log shows what the code actually did. No single log
tells the story alone.

## When to use

- A WAF or IDS alert indicates possible web exploitation and needs log-level confirmation.
- Post-incident scoping: determining how the attacker got in when the entry point was a web
  application.
- Threat hunting: looking for webshell callbacks, SQLi probing, or credential-stuffing patterns.
- Validating that a patched vulnerability was not exploited before the patch date.
- Retrospective hunting after a new CVE is published against your stack.

## Prerequisites

- Written authorization defining the investigation scope: which virtual hosts, log files, and time
  ranges are covered, and whether log data containing user identifiers may be exported or shared.
- Access to the log files (access_log, error_log, and any application logs) for the full window of
  interest plus a pre-window baseline period. Confirm log rotation hasn't destroyed the window —
  check rotated archives (`access_log.1`, gzipped archives) first.
- Knowledge of the logging format in use (Common, Combined, or custom) — parse accordingly; a
  mismatched format silently drops fields.
- Chain-of-custody notes: source server, file paths, collection timestamps, and hashes of the log
  copies you analyze.
- The application inventory: which apps run on each vhost and their patch levels, so exploit
  attempts can be judged against actual vulnerabilities.

## Procedure

1. Confirm the log format and coverage. Read the server config (`LogFormat` directives in Apache,
   `log_format` in Nginx) and verify the fields present: client IP, timestamp, method, URL, status,
   bytes, referrer, user-agent. List all log files including rotated archives and note any gaps in
   coverage.
2. Establish the baseline. Profile normal traffic for a comparable clean period: top URLs, typical
   status-code distribution, normal user-agent mix, and request-rate per IP. Use `goaccess` for a
   quick visual profile or `awk` summaries. The baseline is what makes anomalies visible.
3. Hunt for reconnaissance. Search for: directory enumeration (many 404s from one IP across varied
   paths), vulnerability scanner user-agents (nikto, sqlmap, nessus signatures), and requests for
   known-sensitive paths (`/.git/HEAD`, `/wp-admin`, `/phpmyadmin`, `/.env`). Aggregate: `awk
   '{print $1}' access_log | sort | uniq -c | sort -rn | head` for top talkers, then inspect their
   URL patterns.
4. Hunt for exploitation attempts. Grep for encoded payloads and attack strings: `%27`/`'` with
   `UNION`/`SELECT` (SQLi), `../` and `%2e%2e` (path traversal), `<script` (XSS probes), `${jndi:`
   (Log4Shell-style), and `;id;`/`|cat` (command injection). Decode URL-encoding before judging —
   attackers nest encodings.
5. Identify successful exploitation. Correlate suspicious requests with response codes and sizes: a
   200 response with an unusual byte count on an attack-shaped request deserves follow-up; a
   subsequent series of POSTs to an odd path (e.g., `/images/logo.php`) with 200s and consistent
   small responses is the classic webshell-callback pattern. Check error logs for application
   exceptions at the same timestamps.
6. Hunt webshell callbacks specifically. Look for POST requests to non-application paths with 200
   responses, requests with no referrer and unusual user-agents hitting the same URL repeatedly, and
   query strings carrying base64-looking blobs. Compare the suspect file's first appearance in logs
   against the file-system creation time.
7. Trace the attacker's full session. For each attacker IP, extract every request in chronological
   order: `grep '<attacker-ip>' access_log | sort -k4`. Annotate: first seen, recon phase, exploit
   attempt, post-exploit activity (webshell use, file downloads), and last seen. Note IP changes —
   attackers rotate.
8. Check for data exfiltration over HTTP. Look for: large outbound byte counts to attacker IPs, GET
   requests for database dumps or backup files, and POSTs with large request bodies to
   external-looking endpoints. Compare byte totals against the baseline profile from step 2.
9. Correlate off the web tier. Match attacker IPs and timestamps against firewall logs (did the IP
   touch other ports), authentication logs (successful logins after web exploitation), and
   file-system timelines (new files under the web root matching webshell timestamps). The web log
   shows the knock; these show what opened.
10. Retrospective-hunt the CVE window. For the vulnerability in question, search the full retention
    window before the patch date for its exploit signatures. A clean result is evidence of
    non-exploitation worth documenting; a hit rewinds the incident timeline.
11. Write the findings. Produce: the attack timeline per attacker IP, the exploited (or attempted)
    vulnerability with evidence, the success/failure determination and its basis, the exfiltration
    assessment, and containment recommendations (block IPs, remove webshells, patch, rotate
    credentials, rebuild if root cause is uncertain).

## Key tools & commands

- `goaccess access_log --log-format=COMBINED -o report.html` for rapid visual profiling (top IPs,
  URLs, status codes, user agents).
- `awk`/`grep`/`sort`/`uniq` pipelines for aggregation, e.g. status distribution: `awk '{print $9}'
  access_log | sort | uniq -c | sort -rn`.
- URL decoding for payload inspection: `python3 -c "import urllib.parse,sys;
  print(urllib.parse.unquote(sys.argv[1]))" '<encoded>'` — repeat until the string stabilizes to
  catch double encoding.
- `zgrep` / `zcat` for searching rotated gzipped archives without decompressing them.
- ModSecurity audit logs (if the WAF was in blocking/detection mode) for the WAF's view of the same
  requests.
- Timeline merge: `grep` attacker IPs across access, error, and application logs, then `sort` by
  timestamp.

## Expected outputs

- Log inventory: files, formats, coverage windows, and gaps.
- A baseline traffic profile for the comparison period.
- Recon, exploitation-attempt, and webshell-callback findings with example log lines.
- Per-attacker-IP chronological timelines with annotated phases.
- Success/failure determination per exploit attempt, with evidence cited.
- Exfiltration assessment with byte counts vs. baseline.
- Off-tier correlation results (firewall, auth, file system).
- Retrospective CVE-window hunt results.
- A findings report with containment recommendations.

## Pitfalls

- X-Forwarded-For vs. direct client IP: behind a CDN or load balancer, the log's first field may be
  the proxy's IP. Confirm which field holds the true client before attributing.
- Log rotation and retention silently truncating your window — always check the oldest available
  entry before scoping conclusions.
- Treating every 404 scan as an incident: internet background noise constantly probes. Require
  progression (recon → exploit-shaped request → anomalous success) before escalating.
- Encoded payloads: single-decoding misses double-encoded attacks; decode iteratively until the
  string stabilizes.
- Missing POST bodies: access logs record the request line, not the body — a 200 on a POST to a
  webshell tells you it was called, not what command ran. Pair with application logs or file-system
  forensics.
- Timezone skew between the web server, the WAF, and the firewall: normalize to one timezone before
  correlating or the sequence will lie.
- Assuming the first exploit-shaped request is the intrusion: attackers often probe for weeks. The
  successful attempt may long predate the noisy one.

## References

- Apache HTTP Server log documentation (`LogFormat`, access/error log reference); Nginx
  `ngx_http_log_module` documentation.
- OWASP Web Security Testing Guide — attack patterns to hunt for.
- OWASP ModSecurity Core Rule Set documentation — WAF-side signatures.
- MITRE ATT&CK T1190 (Exploit Public-Facing Application) and T1505.003 (Server Software Component:
  Web Shell).
- goaccess documentation — log format configuration.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
