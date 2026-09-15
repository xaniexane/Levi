# Analyzing Campaign Attribution Evidence

## Purpose

Assess whether observed malicious activity can be attributed to a known
threat actor or campaign — weighing infrastructure, tooling, TTP, and
victimology evidence with explicit confidence levels and structured analytic
techniques, and with the discipline to conclude "insufficient evidence" when
that's the honest answer.

## When to use

- Incident response uncovers a toolset or infrastructure pattern resembling
  a named APT or crimeware campaign.
- Threat intel asks you to confirm or refute a vendor's attribution claim
  against your own telemetry.
- Merging seemingly separate incidents: deciding if two clusters are one
  campaign.
- Preparing intelligence products where attribution statements will be read
  by leadership or shared externally.
- Deciding whether to invest in actor-specific detections vs. generic
  technique coverage.

## Prerequisites

- Written authorization where evidence touches user or customer data;
  attribution analysis itself is analytic work, but the underlying telemetry
  inherits its handling restrictions — mark the product accordingly.
- Chain-of-custody notes: record every evidence item's source, collection
  time, and reliability — attribution is only as good as its weakest source,
  and you must be able to show your work.
- A structured evidence store (MISP, OpenCTI, or a case file) to link
  indicators, TTPs, and reports without losing provenance.
- Familiarity with the candidate actors' documented TTPs (see the MITRE
  Navigator companion playbook for building technique profiles).

## Procedure

1. **Define the attribution question precisely.**
   "Who did this?" is too broad. Frame it: "Is cluster A the work of
   GROUP-X, GROUP-Y, or an unattributed actor?"
   Enumerate the candidate set up front, *including the null hypothesis*
   (unattributed / new actor). Attribution without a null hypothesis is just
   confirmation bias with extra steps.
2. **Collect evidence in four pillars.**
   For the incident, document: (a) *Infrastructure* — IPs, domains,
   registrars, certificates, hosting patterns, registration tradecraft;
   (b) *Tooling* — malware families, custom vs. commodity tools, code
   overlaps and compile artifacts; (c) *TTPs* — initial access, persistence,
   lateral movement, and C2 sequences mapped to ATT&CK; (d) *Victimology &
   timing* — targeted sectors/regions, operational hours, language
   artifacts, holiday/observance patterns.
3. **Score each pillar independently.**
   For every candidate actor, rate each pillar as supporting, neutral, or
   contradicting, with a one-line justification and source citation.
   A shared commodity RAT supports nothing; a custom loader with code
   overlap to GROUP-X's 2024 tooling supports strongly.
   Do the scoring per pillar *before* forming an overall judgment.
4. **Weight evidence by forgeability.**
   Infrastructure is cheap to fake (false flags are real and documented);
   custom tooling and long-observed TTP sequences are expensive to fake.
   Explicitly down-weight easily spoofed indicators — an IP previously
   linked to GROUP-X, reused by someone else, is weak evidence.
   Write the weighting down so reviewers can challenge it.
5. **Check for false-flag indicators.**
   Look for deliberate misdirection: language strings inconsistent with the
   rest of the toolchain, infrastructure rented specifically to implicate
   another actor, TTPs copied verbatim from public reports of a different
   group, or timestamps suggesting a staged narrative.
   Document anomalies even if you can't explain them — unexplained anomalies
   cap your confidence.
6. **Apply structured analytic techniques.**
   Run an Analysis of Competing Hypotheses: list evidence rows against
   candidate columns and mark each as consistent, inconsistent, or neutral.
   This forces confrontation with disconfirming evidence instead of
   cherry-picking the favored actor.
   Also pre-mortem your conclusion: "if we're wrong, what would we expect
   to see?"
7. **Assign a confidence level and use analytic language.**
   Use a defined scale (High / Moderate / Low confidence) and phrase
   conclusions as assessments ("We assess with moderate confidence
   that..."), never as proven fact.
   If no candidate clears Low, the answer is "unattributed" — a valid,
   professional conclusion, and overstating is worse than abstaining.
8. **Write the attribution memo.**
   Structure: the question, the executive assessment with confidence,
   evidence by pillar with sources, alternative hypotheses considered and
   why each was rejected, gaps and collection recommendations that would
   raise confidence, and handling caveats.
   Keep raw IOCs in an appendix, not the narrative — decision-makers need
   judgments, analysts need data.
9. **Share responsibly.**
   Before external sharing, verify handling markings (TLP), remove
   victim-identifying details, confirm with legal whether attribution
   statements create liability, and share the confidence level alongside the
   name — a name without confidence is misinformation.
10. **Revisit on new evidence.**
    Attribution is provisional. File the memo where new reporting will find
    it, set a trigger to re-evaluate when new TTP reporting on the
    candidates drops, and update the assessment (including downgrades)
    rather than letting a stale call live forever.

## Key tools & commands

- MISP / OpenCTI — evidence correlation with galaxies/tags for actors and
  campaigns; preserves provenance.
- Passive DNS, WHOIS history, certificate-transparency data — the
  infrastructure pillar.
- Malware repositories and sandboxes (internal or VirusTotal-class) —
  tooling pillar: family classification and code-overlap checks.
- MITRE ATT&CK Navigator layers — the TTP pillar, per the companion
  playbook.
- ACH matrix (a spreadsheet is fine) — the structured technique from step 6
  needs no special software.

## Expected outputs

- An attribution memo with a confidence-graded assessment, explicit
  alternative hypotheses, and handling markings.
- An evidence matrix (pillars × candidates) with sources, forgeability
  weighting, and noted anomalies.
- Collection gaps: what additional evidence would raise or lower
  confidence, and how to get it.
- Properly marked, shareable intelligence — or a documented decision not to
  share, with rationale.

## Pitfalls

- Single-indicator attribution ("the IP was GROUP-X's once") — the most
  common attribution failure. Require convergence across pillars before
  naming anyone.
- Mirror-imaging: assuming the actor shares your constraints, working
  hours, and logic. State your assumptions about their motives explicitly so
  they can be challenged.
- Letting a vendor's attribution do your thinking. Vendor reports are
  inputs; your telemetry is the test. Vendors have marketing incentives you
  don't.
- Overstating confidence to satisfy stakeholders. A wrong High-confidence
  attribution misdirects the whole response; an honest "unattributed,
  here's what would change that" keeps options open.
- Attribution as an end in itself: the operational question is usually "what
  do we block/hunt next," which technique analysis answers even when
  attribution fails.

## References

- MITRE ATT&CK Groups and Campaigns collections (documented TTP baselines
  for candidates)
- ODNI / intelligence-community guidance on analytic confidence levels
  (High/Moderate/Low) and estimative language
- Richards Heuer, "Psychology of Intelligence Analysis" (ACH and cognitive
  bias) — public CIA publication
- CISA / vendor threat reports as primary TTP sources (cite per claim, note
  single-source items)

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
