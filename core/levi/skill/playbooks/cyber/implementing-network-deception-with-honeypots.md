---
skill_id: cyber_implementing_network_deception_with_honeypots
name: Implementing Network Deception with Honeypots
description: Deploy honeypots, honeytokens, and decoy credentials to detect lateral movement and reconnaissance with high-fidelity, low-noise alerts.
risk: info
permissions: []
requires_confirmation: false
tags: [deception, detection, honeypot]
version: 1.0.0
---
## Purpose

Turn the attacker's own reconnaissance against them. Deception — honeypots emulating vulnerable services, honeytokens (fake credentials, documents, database rows), and decoy network shares — generates alerts that legitimate users essentially never trigger. A login attempt with a honey credential or a scan hitting a honeypot is not a maybe; it is an adversary (or a badly lost employee) and deserves immediate investigation.

## When to use

- Detecting lateral movement and internal reconnaissance that perimeter controls miss.
- Adding high-fidelity detections to environments with noisy, low-signal alerting.
- Protecting Active Directory: honey accounts and honey SPNs catch Kerberoasting and AS-REP roasting attempts.
- Buying time during incident response by observing attacker tooling in a controlled decoy.
- Meeting detection-in-depth expectations for critical or regulated environments.

## Prerequisites

- Defined deception objectives: which adversary behaviors you want to catch (lateral movement, credential theft, data staging).
- Isolated deployment network or VLAN for honeypots with no legitimate traffic — any interaction is suspicious by design.
- SIEM integration ready before deployment; decoy alerts must reach analysts with context and a runbook.
- Legal/HR review of monitoring and any interactive engagement with intruders (policies vary; some jurisdictions restrict certain active measures).
- Change control for placing honeytokens (fake credentials in LSASS-accessible stores, decoy files on shares) so IT does not "clean up" your canaries.

## Procedure

1. **Start with honeytokens — cheapest, highest value.** Deploy honey credentials: fake service accounts with enticing names in AD, honey API keys in code repos and config shares, decoy AWS keys that alert when used (canary tokens). Instrument each so use triggers an immediate high-priority alert. No legitimate process should ever touch them.
2. **Deploy low-interaction honeypots for breadth.** Stand up emulated services (SSH, SMB, RDP, HTTP, common IoT/OT ports) across subnets using tools like Cowrie, Dionaea, or commercial deception platforms. Low-interaction is safer and sufficient for detecting scanning and automated exploitation — the vast majority of malicious touch.
3. **Add high-interaction systems selectively.** For targeted environments, deploy fully instrumented decoy servers (a fake file server, a decoy Jenkins, a mock OT HMI) with EDR-level telemetry. High-interaction yields attacker TTPs and tooling but needs hardening so it cannot become a launchpad — isolate it at the network layer and snapshot it for reset.
4. **Seed the environment believably.** Decoys must blend in: realistic hostnames, plausible file shares with dated documents, browser history, and credentials cached where attackers look (never real ones). A honeypot named `HONEYPOT-01` in its own VLAN catches only the laziest scanners.
5. **Wire every touch to the SOC with a runbook.** Each decoy type maps to an alert with severity, context (source host, technique attempted), and response steps: isolate the source host, capture memory, hunt for the same indicators elsewhere. Deception alerts should auto-create incidents, not sit in a queue.
6. **Protect the deception infrastructure.** Harden honeypot hosts, monitor them for compromise (they are intentionally attractive targets), and ensure alerts fire if a decoy goes silent — attackers disabling your canaries is itself a signal.
7. **Rotate and refresh.** Change honey credentials periodically, vary decoy placement, and update emulated service banners to match your real fleet's patch levels. Stale deception is fingerprinted and ignored by capable adversaries.
8. **Measure fidelity, not volume.** Track true-positive rate (deception alerts are typically >95% true positive), mean time to detect lateral movement, and attacker dwell time on decoys. Report these as detection-program metrics, not vanity alert counts.

## Expected outputs

- Deployed honeytoken set (AD honey accounts, canary API keys, decoy documents) with alerting.
- Low-interaction honeypot coverage across key subnets; selected high-interaction decoys.
- SOC runbooks per decoy type with auto-incident creation.
- Hardening and monitoring of the deception infrastructure itself.
- Fidelity metrics: true-positive rate, lateral-movement detection time.

## Pitfalls

- **Decoys nobody monitors.** A honeypot whose alerts go to an unmonitored mailbox is an attractive nuisance with no security value. SIEM integration and runbooks come before deployment, not after.
- **Unbelievable decoys.** Default banners, empty file shares, and hostnames like `test-honeypot` only catch automated scanners — which your IDS already catches. Invest in realism proportional to the adversaries you face.
- **Honeytokens in places IT cleans.** Fake credentials in a share that gets wiped quarterly, or honey accounts disabled by the identity team as "orphans," create false negatives and confusion. Coordinate with IT and identity teams.
- **High-interaction without isolation.** A fully exploitable decoy reachable from production can be used as a pivot. Network-isolate high-interaction systems and treat their compromise as an expected event with a reset procedure.
- **Legal overreach.** Interactive engagement (chatting with intruders, hacking back) crosses legal lines in most jurisdictions. Deception for detection is widely accepted; anything beyond observation needs counsel's explicit approval.

## References

- NIST SP 800-53 Rev. 5, SC-36 (Honeypots/Honeyclients) and SC-35 (Honeyclients) — https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final
- MITRE ATT&CK T1595 (Active Scanning) and T1083 (File and Directory Discovery) — adversary behaviors deception catches — https://attack.mitre.org/
- MITRE Engage (adversary engagement framework) — https://engage.mitre.org/
- Cowrie honeypot documentation — https://cowrie.readthedocs.io/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
