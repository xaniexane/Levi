---
skill_id: cyber_performing_wifi_password_cracking_with_aircrack
name: Auditing Wireless PSK Strength with Aircrack-ng
description: Authorized audit of your own WPA2/WPA3 passphrase strength using Aircrack-ng, plus detection of handshake-capture attacks.
risk: low
permissions: []
requires_confirmation: false
tags: [wireless, audit, authentication]
version: 1.0.0
---

## Purpose
Weak Wi-Fi pre-shared keys fall to offline dictionary attacks in minutes. This playbook describes how a defender audits passphrases on wireless networks they administer: capturing your own handshake and testing it against wordlists to prove whether the PSK policy holds. It also covers detecting when someone else attempts handshake capture or deauthentication against your network. Only test networks you own; capturing handshakes on third-party networks is unauthorized interception.

## When to use
- Periodic wireless security audit or compliance review.
- After a suspected PSK compromise or staff turnover involving shared keys.
- When evaluating migration from WPA2-PSK to WPA3-SAE or 802.1X.
- When wireless IDS reports deauthentication floods or unknown monitor-mode clients.

## Prerequisites
- Written authorization from the network owner covering the target SSIDs and BSSIDs.
- A wireless adapter supporting monitor mode and packet injection, with Aircrack-ng suite installed.
- The current PSK policy and an approved wordlist for testing (never use breach-compilation lists containing real user passwords beyond scope).
- A maintenance window if any active deauthentication is planned; prefer passive capture.

## Procedure
1. Put the adapter in monitor mode and confirm the target BSSID, channel, and encryption with a passive survey.
2. Capture the 4-way handshake passively by waiting for a legitimate client to associate; avoid forced deauthentication unless explicitly authorized.
3. If authorized and necessary, perform a minimal targeted deauthentication to trigger re-authentication, then immediately stop.
4. Run `aircrack-ng` against the capture with your approved wordlist and document whether the PSK falls, and how fast.
5. If the PSK cracks: rotate it immediately, enforce a generated high-entropy passphrase, and consider WPA3-SAE or 802.1X/EAP to eliminate PSK attacks entirely.
6. For detection: monitor the wireless IDS for deauthentication/disassociation floods, EAPOL handshake captures by unknown stations, and evil-twin SSIDs.
7. Record results, rotate any tested credentials used during the audit, and brief network owners on findings.
8. Document the approved wordlist and capture window so the audit is reproducible and its limits are clear.
9. Schedule re-audits after any PSK change and annually; treat the PSK policy as a living control, not a one-time test.
10. Verify PMF (protected management frames) status on the target; its absence enables the deauth capture path.
11. Test whether the PSK appears in common breach compilations before dictionary testing concludes.
12. Document the approved wordlist and capture window so the audit is reproducible.

## Expected outputs
- Audit report: PSK crackable (yes/no), time-to-crack, wordlist used.
- Remediation actions taken (rotation, policy change, migration plan).
- Wireless IDS tuning notes for handshake-capture detection.
- Re-audit schedule tied to PSK rotation events.
- PMF and management-frame protection status per SSID.
- Breach-compilation check result for the current PSK.
- Re-audit schedule tied to PSK rotation events.

## Pitfalls
- Deauthentication disrupts legitimate users; treat it as a disruptive action needing approval.
- Testing with weak wordlists and declaring victory creates false confidence; use a serious list.
- WPA3-SAE resists offline dictionary attacks but downgrade attacks exist; verify PMF and transition-mode settings.
- Never retain captured handshakes longer than the audit; delete captures after reporting.
- Capturing on channels with heavy legitimate traffic increases accidental collection of unrelated client data; minimize capture scope.
- PMKID attacks harvest hashes without any client present; monitor for PMKID harvesting attempts.
- Transition-mode WPA2/WPA3 networks are only as strong as their weakest allowed mode.
- Shared PSKs posted in offices or emails defeat even strong passphrases; audit distribution too.

## References
- Aircrack-ng official documentation (aircrack-ng.org/documentation.html).
- NIST SP 800-153, Guidelines for Securing Wireless Local Area Networks.
- Wi-Fi Alliance WPA3 specification guidance.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
