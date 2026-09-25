---
skill_id: cyber_hunting_for_domain_fronting_c2_traffic
name: Hunting for Domain Fronting C2 Traffic
description: Detect domain-fronting C2 by correlating TLS SNI, HTTP Host headers, and CDN usage anomalies in network telemetry.
risk: low
permissions: []
requires_confirmation: false
tags: [hunting, network, c2]
version: 1.0.0
---
## Purpose

Domain fronting hides C2 traffic inside TLS connections to reputable
CDNs: the visible SNI names a benign front domain while the encrypted
HTTP Host header addresses the attacker's origin. Though major CDNs have
restricted the technique, variants persist. This playbook covers detecting
fronting-like C2 through SNI/Host discrepancies and CDN-usage anomalies.

## When to use

- Hunting for C2 that evades domain-reputation blocking (traffic to
  reputable CDNs with suspicious characteristics).
- Investigating implants suspected of using CDN-based C2.
- Validating egress monitoring against header-manipulation techniques.
- Threat hunting after intel reports fronting-capable tooling.

## Prerequisites

- TLS handshake logging with SNI (Zeek ssl.log, proxy logs) and, where
  available, decrypted or proxied HTTP Host headers for comparison.
- An inventory of legitimately used CDN-backed services in the
  environment.
- Endpoint telemetry to attribute connections to processes.
- Understanding of your TLS-intercept/proxy architecture and its limits.

## Procedure

1. **Understand the discrepancy to hunt.** Domain fronting's observable
   artifact is a mismatch: the TLS SNI (visible) names an allowed,
   reputable domain while the actual requested host (in the encrypted
   layer) differs. With TLS interception or CDN edge logs, compare SNI
   against Host headers directly.
2. **Hunt SNI/Host mismatches.** Where your proxy or TLS-intercept
   infrastructure logs both values, alert on connections where SNI and
   Host header diverge — legitimate CDN usage occasionally does this
   (domain aliases), so baseline first.
3. **Hunt CDN-usage anomalies without interception.** Without decrypted
   headers, hunt behaviorally: hosts with persistent, periodic
   connections to CDN endpoints that do not match any approved SaaS
   usage; unusual paths or payload patterns to CDN hosts; and beacon-
   like timing over CDN connections.
4. **Profile legitimate CDN traffic.** Build per-host and per-service
   baselines of CDN usage (approved SaaS, software updates, media
   delivery). Fronting hides in legitimate CDN traffic — the baseline
   is what makes the anomaly visible.
5. **Check certificate and connection details.** Examine TLS certificate
   subjects, JA3 fingerprints, and connection persistence for CDN-bound
   sessions that deviate from the legitimate profile (odd certs,
   unusual client fingerprints, extremely long-lived sessions).
6. **Attribute to processes.** Correlate suspicious CDN sessions with
   endpoint data: which process opened them, its parent chain, and
   whether the process legitimately uses CDN services. An unsigned
   binary with persistent CDN connections is a strong signal.
7. **Confirm with controlled observation.** For high-confidence
   candidates, consider targeted packet capture or endpoint network
   tracing (with authorization) to characterize the tunneled protocol
   before acting.
8. **Respond and harden.** Block confirmed C2 origins at egress (note:
   blocking the front domain breaks legitimate services — block the
   true origin), isolate hosts, and deploy detections for the observed
   SNI/Host and behavioral patterns. Review CDN allow-lists.

## Expected outputs

- SNI/Host discrepancy findings and CDN behavioral anomalies with
   evidence.
- Endpoint attribution per suspicious session.
- Confirmed C2 origins blocked; incident handoffs completed.
- Detections for fronting-like patterns with baseline documentation.

## Pitfalls

- Major CDNs have largely disabled classic fronting — but variants
   (domain shadowing, lesser-known CDNs, "fronting-like" header abuse)
   persist; do not dismiss the technique as dead.
- Legitimate CDN aliasing causes SNI/Host mismatches — baselining is
   mandatory before alerting.
- Without TLS interception, detection is behavioral and weaker —
   document the visibility gap honestly.
- Blocking front domains causes collateral damage — always target the
   true origin, and coordinate with service owners.
- Privacy and legal review for TLS interception varies by
   jurisdiction — confirm authority before expanding decryption.

## References

- MITRE ATT&CK: T1090.004 (Domain Fronting), T1573 (Encrypted
  Channel)
- Industry research on domain-fronting detection and CDN abuse
  (defensive summaries)
- Zeek ssl.log documentation (SNI and certificate fields)
- Vendor CDN documentation on Host-header forwarding behavior
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
