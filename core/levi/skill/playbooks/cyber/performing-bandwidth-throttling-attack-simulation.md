---
skill_id: cyber_performing_bandwidth_throttling_attack_simulation
name: Detecting and Mitigating Bandwidth-Throttling Attacks
description: Detect bandwidth-throttling and slow-rate denial-of-service patterns, attribute them, and apply mitigation controls.
risk: low
permissions: []
requires_confirmation: false
tags: [network, dos, detection]
version: 1.0.0
---

## Purpose

Adversaries throttle or degrade a target's bandwidth without taking it fully offline: slow-rate HTTP attacks (slow headers, slow body, slow read), deliberate TCP window shrinking, abusive QoS/dscp manipulation, and volumetric floods that saturate links just enough to starve legitimate traffic. The result is a service that looks "up" to naive health checks while real users time out. This playbook covers detecting those degradation patterns, distinguishing them from benign congestion, and applying defensive controls (rate limiting, connection hygiene, upstream filtering) to restore service quality.

## When to use

- Application or API latency spikes with no corresponding increase in legitimate traffic volume.
- Monitoring shows high connection counts but low completed requests (classic slow-rate signature).
- Health checks pass while end users report timeouts or stalled page loads.
- An incident report mentions "bandwidth throttling" as a suspected attack vector.
- After a volumetric DDoS is mitigated, degradation persists and may indicate a layered slow-rate component.

## Prerequisites

- Access to edge telemetry: web server access logs, load balancer connection metrics, WAF/rate-limiter logs, NetFlow/sFlow or VPC flow logs.
- Baselines for normal connection duration, requests per second, and bandwidth per client profile; without a baseline, "anomalous" is a guess.
- Administrative access to the mitigation stack you plan to tune (WAF rules, web server timeouts, CDN/edge configuration).
- Authorization to apply temporary rate limits or IP blocks during an active event.

## Procedure

1. **Confirm degradation from the user perspective.** Measure p50/p95/p99 response times from synthetic probes and real-user monitoring, segmented by endpoint and geography. If synthetic health checks use tiny payloads, they may miss slow-read attacks; probe with representative payload sizes.
2. **Correlate connection state with request completion.** Pull web server status (e.g., Apache `mod_status`, Nginx stub status) and compare: thousands of connections in `reading`/`writing` state with very few completed requests per second is the hallmark of slow-rate attacks such as Slowloris or R.U.D.Y.
3. **Inspect slow-connection candidates.** From access logs, extract client IPs with long request durations and tiny or incomplete request bodies. Group by IP, ASN, and user-agent. Slow-rate tooling typically reuses a small set of source networks and shows mechanical timing (nearly identical inter-packet gaps).
4. **Check for bandwidth saturation at each layer.** Compare interface/throughput counters (link, load balancer, application). If the link is saturated but the application is idle, you are looking at volumetric or reflection traffic; if the application is saturated with low bandwidth, it is a slow-rate or application-layer problem.
5. **Identify protocol-level manipulation.** Look for TCP sessions with persistently tiny advertised windows, excessive zero-window probes, or fragmented packet streams. Capture with tcpdump or Wireshark during an event and confirm whether window sizes shrink after handshake.
6. **Rule out benign causes.** Cross-check with capacity events: new code deploys, batch jobs, backup windows, CDN cache purges, or upstream provider issues. A throttling pattern that starts exactly at deploy time is usually your own regression.
7. **Apply graduated mitigation.** Start with the least disruptive control that matches the pattern: tighten server request timeouts (header/body read timeouts), lower keep-alive windows, and enforce per-IP connection limits. Then add WAF rules matching the attack's fingerprint (e.g., incomplete POST bodies held open). Use CDN/edge absorption and upstream scrubbing for volumetric components.
8. **Block with care and expiry.** Apply temporary IP/ASN blocks only to sources that meet the attack criteria, with an automatic expiry (e.g., 1–4 hours) and a documented reason. Prefer rate-limiting over blocking where the source set includes shared NAT or cloud egress ranges.
9. **Tune for the long term.** Convert emergency thresholds into standing configuration: request timeouts, body-size limits, slow-client detection in the WAF, and alerting on the ratio of open connections to completed requests. Schedule a review of rate-limit tiers after the event.
10. **Document and hand off.** Record the timeline, indicators (IPs, ASNs, user-agents, packet signatures), controls applied, and residual risk. Feed the indicators into your SIEM and threat-intel platform so repeat campaigns are recognized faster.

## Expected outputs

- An incident timeline distinguishing attack traffic from benign congestion, with evidence for each conclusion.
- Indicator set: source IPs, ASNs, user-agent strings, and packet-level signatures of the throttling behavior.
- Applied mitigations: server timeout changes, WAF rules, rate limits, and blocks, each with expiry and owner.
- Hardened baseline configuration and alerting thresholds for slow-rate and degradation attacks.
- A post-incident summary suitable for stakeholders, including user impact duration and what was changed.

## Pitfalls

- Treating bandwidth graphs alone as diagnostic: slow-rate attacks barely register on throughput charts; connection-state and completion-rate metrics are the signal.
- Blocking cloud provider or corporate NAT ranges wholesale, which punishes legitimate users sharing the same egress IPs.
- Setting request timeouts so aggressively that mobile clients on poor networks are dropped — tune against real client latency distributions.
- Forgetting to expire emergency blocks, leaving stale deny rules that cause mysterious failures weeks later.
- Assuming the event is over when graphs normalize; slow-rate tooling often pauses and resumes. Keep monitoring through at least one full business cycle.

## References

- MITRE ATT&CK T1498, "Network Denial of Service" (includes direct network flood and reflection sub-techniques)
- OWASP guidance on denial-of-service protection for web applications
- Apache and Nginx documentation on request timeouts and connection limits
- NIST SP 800-61, "Computer Security Incident Handling Guide"
- Cloudflare / AWS Shield documentation on DDoS mitigation architecture patterns
