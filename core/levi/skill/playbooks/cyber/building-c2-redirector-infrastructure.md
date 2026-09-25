---
skill_id: cyber_building_c2_redirector_infrastructure
name: Detecting Command-and-Control Redirector Infrastructure
description: Blue-team playbook for recognizing, analyzing, and dismantling redirector layers used to hide adversary command-and-control servers.
risk: low
permissions: []
requires_confirmation: false
tags: [detection, threat-intel, network]
version: 1.0.0
---
## Purpose
Adversaries commonly place redirectors -- proxy hosts, CDNs, cloud functions, or compromised servers -- between victim implants and their real command-and-control servers to frustrate takedown and attribution. This playbook teaches defenders how to identify redirector behavior in network telemetry, enumerate the infrastructure, and use it to pivot toward the true C2. It covers analysis only, never construction.

## When to use
- Investigating suspected C2 traffic whose destination changes or whose responses look proxied.
- Hunting for infrastructure shared across phishing or malware campaigns.
- Working with a threat-intelligence provider to track a known threat actor's infrastructure.
- Preparing detections that survive simple IP blocking.

## Prerequisites
- DNS logs, NetFlow or equivalent flow records, and TLS handshake metadata.
- Passive DNS and certificate-transparency access for infrastructure pivoting.
- Endpoint telemetry to correlate outbound connections with local processes.
- Defined scope and authorization for any active probing of external infrastructure.

## Procedure
1. Identify redirector candidates. Look for hosts that forward unusual protocols, show many short-lived connections relayed onward, or carry beaconing sessions that terminate elsewhere.
2. Analyze TLS and HTTP characteristics. Record certificate subjects, JA3/JA3S hashes, HTTP header order, server banners, and response sizes; redirectors often add consistent proxy signatures.
3. Pivot on infrastructure. Use passive DNS, certificate transparency, and reverse DNS to find sibling domains and IPs sharing certificates or naming conventions.
4. Correlate with endpoint data. Match outbound connection times and destination IPs to implant processes on hosts; confirm the traffic is malicious rather than legitimate proxying.
5. Map the chain. Document the full path: implant to redirector to suspected origin server, including ports and protocols at each hop.
6. Track over time. Redirectors rotate quickly; maintain a rolling list and watch for infrastructure reuse across incidents to attribute campaigns.
7. Coordinate disruption. Work with hosting providers, registrars, and your threat-intel team to take down confirmed malicious redirectors; block at egress controls in the meantime.
8. Encode detections. Write signatures around certificates, JA3 hashes, and DNS patterns rather than single IPs, since redirectors are ephemeral.

## Expected outputs
- Infrastructure map: redirector hosts, true C2 candidates, and their relationships.
- Reusable detections keyed on certificates, TLS fingerprints, and naming patterns.
- List of affected internal hosts with containment status.
- Takedown requests filed with providers where applicable.

## Pitfalls
- Legitimate CDNs and reverse proxies look similar; attribution needs endpoint corroboration.
- Aggressive active probing of external hosts can alert adversaries or violate acceptable-use policies; stay passive unless authorized.
- Certificate reuse across tenants (for example, default cloud certificates) causes false attribution.
- Blocking a redirector IP may affect unrelated legitimate services sharing the host.

## References
- MITRE ATT&CK: T1090 (Proxy) and T1572 (Protocol Tunneling)
- MITRE ATT&CK: TA0011 (Command and Control)
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- FIRST CSIRT services framework guidance on infrastructure takedown coordination
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
