---
skill_id: cyber_performing_red_team_phishing_with_gophish
name: Red Team Phishing with Gophish
description: Conduct authorized red-team phishing operations with Gophish to test email defenses and user reporting behavior.
risk: low
permissions: []
requires_confirmation: false
tags: [red-team, phishing, gophish]
version: 1.0.0
---

## Purpose
- This playbook covers authorized adversary simulation to test and improve defenses; every campaign requires written authorization.
- Test whether email gateways, SOC triage, and users detect and report realistic targeted phishing.
- Measure the full defensive chain from delivery through user report to SOC response.
- Produce findings that improve technical controls and awareness training together.

## When to use
- During authorized red team engagements where initial access via phishing is in scope.
- When validating improvements to email security controls after tuning.
- When the organization wants realistic adversary simulation beyond routine awareness campaigns.
- After threat intelligence shows phishing as the top initial-access vector for relevant actors.

## Prerequisites
- Written rules of engagement authorizing phishing, including target scope and any forbidden lure types.
- Gophish infrastructure separated from corporate systems, with operational security appropriate to the exercise.
- Coordination boundaries: typically the SOC is not pre-briefed in red team exercises, but safety contacts must exist.
- Legal review of lure content, especially for campaigns targeting executives or using sensitive pretexts.

## Procedure
1. Confirm written authorization and the exact scope: who may be targeted and what is off-limits.
2. Perform authorized reconnaissance on public sources to build realistic, targeted lures.
3. Set up Gophish infrastructure with proper mail authentication and domains that will not harm deliverability of real mail.
4. Craft lures matching the emulated threat actor's style, avoiding pretexts that could cause real harm or panic.
5. Launch in a controlled manner, monitoring for unintended consequences such as help-desk overload.
6. Track the full kill chain: delivery, open, click, credential submission, and user reporting.
7. Measure defensive response: did the gateway block it, did users report it, how fast did the SOC triage the reports.
8. Stop immediately if the campaign causes operational disruption or targets someone in distress.
9. Debrief targets sensitively; red team phishing should educate, not humiliate.
10. Report findings as defensive gaps with recommendations for gateway tuning, detection, and training.
11. Support remediation and offer to rerun the scenario after fixes to validate improvement.

## Expected outputs
- A red team phishing report with delivery-to-report metrics and defensive gaps.
- Recommendations for email gateway, SOC, and awareness improvements.
- Validation reruns after remediation where agreed.
- A comparison of red-team bypass rates against routine awareness campaign metrics.
- Infrastructure teardown procedures so exercise domains cannot be abused afterward.

## Pitfalls
- Blurring into real harm with aggressive pretexts; red team realism must stay within ethical and legal bounds.
- Targeting individuals known to be vulnerable or in crisis; screen target lists with HR guidance.
- Failing to distinguish red-team results from awareness metrics; they measure different things.
- Neglecting operational security of the phishing infrastructure itself, which can burn domains or leak exercise details.
- Reusing exercise infrastructure across engagements, which lets defenders fingerprint it.

## References
- SANS SEC565 red team operations methodology
- Gophish official documentation
- MITRE ATT&CK phishing techniques, https://attack.mitre.org/techniques/T1566/
- NIST SP 800-53 control CA-8 on penetration testing
- CISA red team and assessment methodology resources
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
