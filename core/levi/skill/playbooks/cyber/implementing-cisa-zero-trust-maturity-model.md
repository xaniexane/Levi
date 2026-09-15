---
skill_id: cyber_implementing_cisa_zero_trust_maturity_model
name: CISA Zero Trust Maturity Model Adoption
description: Use the CISA Zero Trust Maturity Model to assess, plan, and govern the zero-trust program.
risk: info
permissions: []
requires_confirmation: false
tags: [zero-trust, governance]
version: 1.0.0
---
## Purpose
Zero-trust programs stall without a shared yardstick: teams argue about what "done" means while
identity, device, and network efforts drift apart. CISA's Zero Trust Maturity Model (ZTMM) provides
the federal-standard framework — five pillars (Identity, Devices, Networks, Applications, Data) plus
governance, each with Traditional → Initial → Advanced → Optimal steps. This playbook uses ZTMM to
assess current state, plan the roadmap, and govern progress.

## When to use
- Launching or rebooting a zero-trust program that lacks structure or executive alignment.
- Needing a defensible, standards-based maturity assessment for leadership or regulators.
- Prioritizing across competing zero-trust investments (identity vs. network vs. data).
- Federal agencies or contractors aligning to federal zero-trust mandates and OMB guidance.
- As the governance wrapper around technical playbooks (BeyondCorp access, device posture,
  microsegmentation).

## Prerequisites
- Executive sponsorship: ZTMM assessment exposes gaps that require funding to close.
- Stakeholders per pillar: identity, endpoint, network, application, and data owners willing to be
  assessed honestly.
- Current-state documentation: existing controls per pillar (even if informal).
- A target-state decision: which maturity step per pillar the organization commits to, and by when.
- Familiarity with ZTMM v2 (or current version): pillars, steps, and cross-cutting capabilities.

## Procedure
1. **Learn the model together.** Walk pillar owners through ZTMM: the five pillars,
   visibility/automation/governance cross-cuts, and what each step requires. A shared vocabulary
   prevents "we're already zero trust" misunderstandings.
2. **Assess honestly, pillar by pillar.** For each pillar, score current state against the model's
   steps using evidence (not aspirations): phishing-resistant MFA coverage for Identity, EDR/MDM
   coverage for Devices, segmentation for Networks, SSO/proxy coverage for Applications,
   classification/DLP for Data. Record evidence per rating.
3. **Identify the binding constraints.** The model's value is showing which pillar lags: Advanced
   identity with Traditional devices means compromised endpoints undermine strong auth. Prioritize
   lifting the lowest pillars first — the program is only as mature as its weakest pillar for any
   given workflow.
4. **Set target steps with dates.** For each pillar, commit to a target step and deadline (e.g.,
   Identity → Advanced in 12 months, Networks → Initial in 18). Targets must be resourced: budget,
   headcount, and project slots. Unfunded targets are wishes.
5. **Build the roadmap from the gaps.** Translate each step-up into projects with owners: e.g.,
   Identity Initial→Advanced = phishing-resistant MFA rollout + PIM + conditional access; Devices =
   EDR+MDM coverage + posture signals. Sequence by dependency (identity and visibility usually
   first).
6. **Establish governance.** Quarterly ZTMM review board: pillar owners present evidence of step
   progress, blockers, and metric deltas. Decisions recorded; funding reallocated from stalled to
   progressing efforts. This is the program's steering mechanism.
7. **Measure with pillar metrics.** Per pillar, track 2-3 metrics tied to steps: Identity =
   phishing-resistant MFA %, standing privilege count; Devices = managed/healthy %; Networks =
   segmented workloads %, VPN-dependent apps; Applications = SSO/proxy coverage; Data = classified
   data %, DLP policy coverage. Metrics move only when steps advance.
8. **Re-assess annually.** Repeat the evidence-based assessment yearly (or after major changes).
   Publish the maturity delta per pillar — this is the program's report card for executives and
   auditors.
9. **Align procurement and architecture.** Require new purchases and architectures to state their
   ZTMM contribution (which pillar, which step). This prevents new Traditional-step technical debt
   while you're climbing.
10. **Connect to risk and compliance.** Map ZTMM progress to risk reduction narratives (fewer
    standing privileges, smaller blast radius) and to framework controls (NIST 800-207, OMB M-22-09
    for federal). Maturity steps become audit evidence.

## Expected outputs
- An evidence-based ZTMM assessment across all pillars and cross-cutting capabilities.
- Committed target steps per pillar with dates, owners, and funding.
- A sequenced project roadmap derived from step gaps.
- Quarterly governance reviews and pillar metrics dashboards.
- Annual re-assessment showing maturity deltas.

## Pitfalls
- Self-assessment inflation: rating based on plans instead of deployed evidence. Require artifacts
  for every claimed step.
- Pillar imbalance: advancing one pillar to Optimal while others sit at Traditional wastes money —
  attackers use the weakest pillar.
- Treating the model as a checklist: steps describe capabilities, not products. Buying a "zero
  trust" product doesn't advance a pillar by itself.
- No funding attached to targets: the roadmap dies at the first budget cycle. Secure multi-year
  commitment upfront.
- Ignoring the cross-cutting capabilities: visibility, automation, and governance are what make
  pillar advances stick. Underinvesting here produces unmaintained controls.

## References
- CISA Zero Trust Maturity Model (current version) — pillars, steps, and assessment guidance
- NIST SP 800-207 (Zero Trust Architecture)
- OMB Memorandum M-22-09 (federal zero trust strategy, for federal context)
- CISA/NSA zero trust guidance and reference architectures
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
