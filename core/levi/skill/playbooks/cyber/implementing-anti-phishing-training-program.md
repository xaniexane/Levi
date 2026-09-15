---
skill_id: cyber_implementing_anti_phishing_training_program
name: Implementing Anti-Phishing Training Program
description: Build an effective anti-phishing program: risk-based training, safe simulated phishing, reporting culture, and measurable behavior change.
risk: info
permissions: []
requires_confirmation: false
tags: [awareness, phishing, training]
version: 1.0.0
---
## Purpose

Technology alone does not stop phishing — user behavior is the decisive
layer. This playbook covers building an anti-phishing program that
actually changes behavior: risk-based training, realistic but safe
simulations, a strong reporting culture, and metrics that measure
outcomes rather than completions.

## When to use

- Establishing or overhauling security-awareness training.
- After phishing-driven incidents revealed user-behavior gaps.
- Meeting compliance requirements for awareness training.
- Reducing click rates and time-to-report across the organization.

## Prerequisites

- Executive sponsorship and HR/legal alignment (simulations need
  policy backing, especially around consequences).
- A phishing-simulation platform with safe, clearly-branded templates.
- Baseline metrics: current click rate, report rate, and reporting
  tooling (phish-alert button) deployed.
- Content covering current threat trends (AiTM, QR-code phishing,
  MFA fatigue).

## Procedure

1. **Segment by risk, not by department.** Prioritize high-risk groups:
   finance (BEC targets), executives and assistants (whaling),
   IT/helpdesk (privileged access), and new hires. Tailor content to
   each group's actual threat exposure.
2. **Teach recognition, not fear.** Training content: how to inspect
   senders and URLs, recognizing urgency and authority manipulation,
   verifying requests through alternate channels, and handling QR
   codes, attachments, and MFA prompts. Keep modules short and
   scenario-based.
3. **Run safe simulations.** Send realistic simulated phishes (never
   using real malware or credential harvesting beyond a safe landing
   page). Vary difficulty: easy lures for baseline, then targeted
   spearphishing-style templates for high-risk groups.
4. **Build reporting culture.** Make reporting one click (email client
   button), acknowledge every report quickly, and publicly celebrate
   reporters — never punish clickers. The goal is fast reporting, and
   punishment destroys it.
5. **Coach, do not shame.** Users who click get immediate, brief,
   constructive coaching (what to look for next time), not
   disciplinary action — except for repeated, willful negligence per
   documented policy. Track improvement per user, not just failures.
6. **Measure what matters.** Primary metrics: report rate, median
   time-to-report, and click rate trend — not training-completion
   percentages. A rising report rate with falling click rate is
   success; 100% completion with no behavior change is failure.
7. **Close the loop with the SOC.** Feed simulation and real-report
   data into detection tuning (which lures evade the gateway?) and
   incident response (fast user reports shorten dwell time — measure
   report-to-containment time).
8. **Refresh continuously.** Update content quarterly with current
   threat trends and lessons from real incidents. Retire stale modules
   — last year's phishing examples teach last year's threats.

## Expected outputs

- A risk-segmented training plan with role-appropriate content.
- A simulation calendar with difficulty progression.
- Reporting tooling deployed with acknowledgment workflows.
- Metrics dashboard: click rate, report rate, time-to-report trends.
- SOC feedback loop documentation.

## Pitfalls

- Punishing clickers — the single fastest way to kill reporting
   culture and drive phishing underground.
- Measuring completions instead of behavior change — compliance
   theater, not security.
- Overly difficult simulations that feel like entrapment — calibrate
   difficulty to the audience's training level.
- One-size-fits-all content — executives and developers face
   different threats; generic training is ignored.
- Simulations without legal/HR review — impersonating internal
   communications needs policy backing.

## References

- NIST SP 800-50: Building an Information Technology Security
  Awareness and Training Program
- CISA: phishing guidance and reporting resources
- Anti-Phishing Working Group (APWG) trend reports
- Academic research on phishing-training effectiveness (for
  program design)
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
