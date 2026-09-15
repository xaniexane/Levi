---
skill_id: cyber_configuring_suricata_for_network_monitoring
name: Configuring Suricata for Network Monitoring
description: Deploy Suricata with EVE JSON logging, TLS/DNS protocol logging, and curated rules for full-fidelity network visibility.
risk: low
permissions: []
requires_confirmation: false
tags: [ids, network, detection]
version: 1.0.0
---
## Purpose

Use Suricata as more than an IDS — as the network-monitoring layer that feeds everything else: flow, DNS, TLS, HTTP, and file-extraction metadata in structured EVE JSON, plus tuned alert rules. If Zeek is the microscope, Suricata is the wide-area sensor grid.

## When to use

- Building or upgrading network visibility on perimeters, data-center cores, and cloud VPC mirrors.
- Replacing Snort with a multi-threaded engine, or running both for coverage comparison.
- Feeding a data lake / SIEM with structured protocol metadata for threat hunting.
- Compliance-driven continuous network monitoring (e.g. PCI DSS traffic logging).

## Prerequisites

- Sensors with sufficient CPU/RAM for multi-threaded capture; confirm packet loss is zero under peak load before tuning.
- Traffic feeds: SPAN/tap for on-prem, VPC traffic mirroring or packet-mirror agents for cloud.
- Rule sources: Emerging Threats (free) and/or a commercial feed; an update mechanism (suricata-update).
- Storage planning: EVE JSON at scale is voluminous — size retention before enabling everything.

## Procedure

1. **Validate lossless capture first.** Deploy with AF_PACKET (or DPDK for very high throughput), then check `stats.log` for drops. Any `capture.kernel_drops` > 0 means your sensor is blind during peaks — fix worker-thread count, ring sizes, or offload settings before trusting any alert.
2. **Configure EVE JSON outputs deliberately.** Enable `flow`, `dns`, `tls`, `http`, `alert`, and `fileinfo` outputs; keep `payload` and full `packet` capture off by default (enable selectively for hunting, with retention limits). Ship EVE to your log pipeline with the sensor's identity attached.
3. **Set HOME_NET precisely and define ports.** Correct `HOME_NET` makes rules and anomaly thresholds meaningful; also review the `port-groups` so service-specific rules match your actual services. Mis-scoped HOME_NET is the number-one Suricata tuning failure.
4. **Curate rules with suricata-update.** Enable Emerging Threats plus your commercial feed; disable categories for services you don't run and noisy deprecated rules. Use `disable.conf`/`modify.conf` so tuning survives rule updates — manual GUI edits get overwritten on the next pull.
5. **Tune stream and defrag engines.** Review `stream` memcap, `defrag` settings, and the `app-layer` protocol parsers for your traffic mix. Anomalies like `stream.reassembly` failures in eve.json often reveal evasion attempts — alert on them, don't just ignore.
6. **Turn on file extraction for the DMZ/web tier.** Enable `file-store` with a hash-and-drop policy (extract, hash, log, then age out), feeding hashes to your malware-sandbox or threat-intel lookups. This gives you "what binary did that HTTP flow carry" without full pcap retention.
7. **Build the analyst views.** In the SIEM, pre-build dashboards for: alerts by signature/severity, TLS JA3 anomalies, DNS query volume by client, HTTP user-agent anomalies, and extracted-file hash reputation. Provide analysts a runbook linking each Suricata event type to triage steps.
8. **Automate rule updates and regression-test.** Run suricata-update on schedule, reload rules without dropping capture, and run a synthetic malicious-traffic test (e.g. a known EICAR download in a lab feed) after each update to prove the pipeline still fires end to end.

## Expected outputs

- Lossless multi-threaded sensors emitting curated EVE JSON (flow/dns/tls/http/alert/fileinfo) to the SIEM.
- A documented, update-resilient rule policy with per-category enable/disable rationale.
- Analyst dashboards and a triage runbook; automated updates with synthetic regression tests.

## Pitfalls

- Packet drops under load — every alert you don't get is invisible, and Suricata won't warn you loudly.
- Keeping full payload/packet capture on everywhere — disk exhaustion kills the sensor.
- Manual rule edits outside suricata-update — wiped on the next update, tuning lost.
- Ignoring anomaly events (`event_type: anomaly`) — they carry the evasion attempts the rules missed.
- Letting EVE retention silently expire before an investigation needs it — size it from real traffic first.

## References

- Suricata User Guide (docs.suricata.io) — configuration, EVE JSON, rule management
- Emerging Threats ruleset documentation
- NIST SP 800-94 (Guide to Intrusion Detection and Prevention Systems)
- MITRE ATT&CK — signature-to-technique mapping for coverage reviews
