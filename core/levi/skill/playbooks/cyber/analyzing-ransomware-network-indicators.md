# Analyzing Ransomware Network Indicators

## Purpose

Extract network indicators from ransomware activity — C2, staging, exfiltration, and victim-notification channels — and convert them into containment blocks and detections, complementing the encryption-mechanism analysis.

## When to use

- Ransomware is detonating or has detonated; you need to cut its network lifelines (key exfiltration, C2, lateral spread).
- Post-incident: building the network timeline of the attack (access → staging → encryption → leak).
- Threat-intel: documenting the actor's infrastructure for sharing.

## Prerequisites

- Written authorization; incident ticket with scope and time window.
- Lab captures of the sample (for pre-detonation intel) and production logs (firewall, proxy, DNS, EDR) for the incident window.
- The encryption-mechanism findings, if available — network and crypto analysis inform each other (e.g., key exfil before encryption).
- Containment authority defined: who approves firewall/proxy blocks.

## Procedure

1. From the lab detonation capture, list every external connection the sample made before encrypting: DNS queries, HTTP(S) posts, and any custom-protocol C2. Timestamp each relative to detonation.
2. Identify key-exfiltration flows: outbound posts occurring between execution and the start of encryption — these carry victim IDs and often the encrypted symmetric key. Block these first; cutting them pre-encryption can strand the attacker's keys.
3. In production logs, search the incident window for the lab-derived indicators: C2 domains/IPs, ransom-note download URLs, and TOR/gateway connections.
4. Hunt the delivery and staging infrastructure: the initial-access vector's URLs/IPs (phishing links, exploited edge device), plus any tooling downloads (PsExec, RDP brute-force sources).
5. Map lateral movement network edges: SMB/RDP/WinRM connections between hosts in the hours before encryption, correlated with authentication logs.
6. Check for pre-encryption exfiltration: large outbound transfers to cloud storage, FTP, or Mega-style services in the days before detonation (double-extortion staging).
7. Identify victim-notification infrastructure only if needed for the investigation (onion addresses from ransom notes) — do not engage.
8. Build the network kill list: domains, IPs, URLs, and ports — push to firewall, proxy, DNS sinkhole, and EDR network rules with ticket references.
9. Verify blocks took effect: fresh captures/DNS logs should show connection failures, not silence from unmonitored paths.
10. Write Suricata/Snort rules for the C2 patterns and test against the lab pcap.
11. Hunt for affiliate infrastructure reuse: the same staging IPs and domains often serve multiple victims — pivot on them in threat intel to warn potential next targets.
12. Check for double-extortion traffic separately: connections to leak-site infrastructure or large uploads to file-sharing services after encryption indicate data publication is in progress.
13. Validate that backup and recovery traffic paths are not on the kill list — blocking your own recovery tooling mid-incident is a real and painful failure mode.
14. Map the affiliate's tooling downloads: RMM tools, PsExec, and credential dumpers fetched from the internet reveal the operator's toolkit.
15. Check for pre-ransom reconnaissance traffic: internal scanning and AD enumeration (LDAP/SMB) in the days before encryption.
16. Document the egress chokepoints observed: which firewall or proxy the traffic left through — this is where future detections belong.
17. Set expiry dates on every kill-list entry: stale blocks accumulate and cause outages.
18. Verify blocks via DNS logs post-deployment: blocked C2 still trying confirms the indicator was right.
19. Check proxy logs for blocked attempts: they reveal infected hosts you haven't found yet.
20. Document residual risk explicitly: which attacker capabilities the blocks don't cover.
21. Produce the network timeline: first access → staging → exfiltration → C2 → encryption, each row tied to a log source.
22. Share sanitized indicators with ISAC/partners per your sharing policy.

## Key tools & commands

- Lab pcap (`dumpcap` during detonation) + `tshark` — pre-encryption network behavior.
- Firewall/proxy/DNS log queries — production-window indicator search.
- `nfdump` / SiLK — lateral-movement edges and exfiltration volumes.
- Suricata/Snort — C2 detection rules tested against the lab pcap.
- EDR network telemetry — per-host connection timelines.
- DNS sinkholing / RPZ — containment of C2 domains.
- MISP — structured sharing of sanitized indicators.
- `whois` / passive DNS — infrastructure attribution and pivoting.
- Backup/recovery traffic allowlist review — avoiding self-inflicted blocks.

## Expected outputs

- Lab-derived network indicator list with first-seen timestamps.
- Production log hits for each indicator (or documented absence).
- Network kill list deployed to firewall/proxy/DNS/EDR with verification.
- Tested IDS rules for the C2 patterns.
- Full network timeline of the attack.
- Affiliate-infrastructure reuse findings (shared staging across victims).
- Double-extortion traffic assessment (leak-site / file-sharing uploads).

## Pitfalls

- Blocking C2 before understanding it — capture the behavior first in the lab, then block in production.
- Missing pre-encryption exfiltration because the window started at detonation — look back days/weeks.
- Treating onion addresses as blockable at the perimeter — focus on the clearnet staging and exfil paths instead.
- Declaring containment while an unmonitored egress path (guest Wi-Fi, cellular) remains.
- Sharing victim-identifying details with indicators — sanitize before external sharing.
- Blocking backup and recovery traffic paths with the kill list — review allowlists first.
- Over-blocking shared-hosting or CDN IPs — collateral damage to legitimate services.
- Kill-list staleness as attacker infrastructure rotates — re-verify hits on a schedule.
- Kill-list entries without expiry dates — stale blocks accumulate and cause outages.
- Blocking at the firewall but not the proxy (or vice versa) — cover all egress paths.
- Forgetting IPv6 egress when writing blocks — dual-stack environments leak around v4-only rules.
- Not informing the SOC of kill-list changes — blocks without context get reverted.
- Assuming encryption-time traffic is the whole story — pre-encryption staging matters more.
- Forgetting to monitor the kill list's effectiveness — blocks need verification.
- Not documenting who approved each block — accountability matters.
- Assuming the affiliate won't retool — schedule re-hunts.
- Missing backup-traffic baselines — restores look like exfiltration.
- Forgetting to remove temporary blocks after the incident — technical debt.
- Not sharing IOCs with the sector ISAC — others are being hit too.
- Ransomware C2 often goes quiet after encryption — hunt the pre-encryption beaconing window.
- Data exfiltration can precede encryption by days — widen the time window backward.
- Legitimate admin tools (RMM, PsExec) serving as the "C2" — do not dismiss signed binaries.
- SMB lateral movement blending with admin traffic — baseline normal admin behavior first.
- DGA domains resolving once — passive DNS history matters more than live resolution.
- Blocking IOCs without removing persistence — the actor re-enters through the same hole.

See also: analyzing-ransomware-encryption-mechanisms.md

## References

- MITRE ATT&CK T1071 (Application Layer Protocol), T1041 (Exfiltration Over C2 Channel), T1021 (Remote Services), T1486 (Data Encrypted for Impact)
- CISA #StopRansomware guidance: https://www.cisa.gov/stopransomware
- CISA Automated Indicator Sharing (AIS) documentation
- MISP documentation — structured indicator sharing
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
