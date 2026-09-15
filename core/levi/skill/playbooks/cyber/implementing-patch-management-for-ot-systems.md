---
skill_id: cyber_implementing_patch_management_for_ot_systems
name: Implementing Patch Management for OT Systems
description: Run patch management in operational technology — risk-based prioritization, vendor-validated testing, maintenance-window deployment, and compensating controls where patching isn't possible.
risk: info
permissions: []
requires_confirmation: false
tags: [ot, ics, patch-management, vulnerability-management]
version: 1.0.0
---
## Purpose

Keep OT systems patched without breaking the process. Unlike IT patching, OT patching contends with vendor certification requirements, 24/7 processes that can't reboot, legacy systems vendors no longer support, and safety implications of every change. This playbook builds a risk-based OT patch program: prioritize by exploitability and process consequence, test in representative environments, deploy in maintenance windows, and apply compensating controls where patching is impossible.

## When to use

- Establishing or maturing OT patch management (a perennial audit finding).
- Meeting NERC CIP-007 R2 (35-day patch evaluation) or IEC 62443 expectations.
- Responding to critical OT vulnerabilities (e.g., advisories affecting your PLC/HMI fleet).
- Reducing the window between vulnerability disclosure and remediation in control networks.
- Justifying compensating controls for unpatchable legacy systems to auditors and leadership.

## Prerequisites

- Complete OT asset inventory with firmware/OS versions, vendor support status, and Purdue-level mapping.
- Vendor patch-validation guidance and support contracts (which patches the vendor has tested against your control system versions).
- Test/staging environment representative of production (or vendor lab access) for patch validation.
- Maintenance window calendar aligned with production schedules and turnaround plans.
- Rollback capability: known-good firmware images, configuration backups, and tested restore procedures.

## Procedure

1. **Build the patch intelligence feed.** Subscribe to vendor security advisories, CISA ICS advisories, and ISAC feeds for your sector. Correlate every advisory against the asset inventory automatically — manual matching doesn't scale and misses affected systems. Track which advisories apply to your fleet and their severity in your environment (a CVSS 9.8 on an air-gapped historian differs from the same score on an internet-facing gateway).
2. **Prioritize by OT risk, not CVSS alone.** Score patches on: exploitability (public exploit? wormable?), exposure (internet-facing, DMZ, control network), and process consequence (safety system vs. monitoring). A remotely exploitable vulnerability in the OT DMZ outranks a local-privilege-escalation on an isolated HMI, regardless of CVSS ordering.
3. **Validate in a representative environment.** Test patches against the actual control system versions in the lab: apply, run through operational scenarios (startup, shutdown, failover, alarm handling), and verify with process engineers. Document vendor-validated vs. organization-validated patches — auditors ask, and untested patches in control networks are how outages happen.
4. **Schedule deployment in maintenance windows.** Bundle patches per system into planned windows, sequenced by dependency (patch the DMZ before the control network; never patch redundant pairs simultaneously — patch A, validate, fail over, patch B). Have the rollback plan staged and tested before the window opens, with defined abort criteria.
5. **Handle the unpatchable deliberately.** For end-of-life systems, vendor-unsupported firmware, or patches that break certification: document the decision, implement compensating controls (network isolation, application allowlisting, enhanced monitoring, removal of unnecessary services), set a replacement or retirement date, and get formal risk acceptance. "Cannot patch" without compensating controls and a plan is negligence, not a strategy.
6. **Patch the IT-adjacent OT first and fastest.** Historians, jump hosts, AV relays, and DMZ systems run standard operating systems — patch these on near-IT timelines. They are the attacker's beachhead into OT; leaving them unpatched while debating PLC firmware is backwards prioritization.
7. **Verify and document.** After each window, verify patch levels across the fleet (scan or agent-reported), reconcile against the plan, and record evidence: advisory evaluated, risk decision, test results, deployment record, verification scan. This evidence package is what NERC CIP-007 and IEC 62443 auditors examine.
8. **Review metrics and improve.** Track mean time to evaluate (target: within 35 days per CIP-007 for applicable systems), mean time to deploy by priority tier, patch compliance percentage, and unpatchable-system inventory with compensating-control status. Report trends to operations and security leadership jointly.

## Expected outputs

- Correlated advisory-to-asset tracking with OT-risk prioritization.
- Validated patch testing process with documented results.
- Maintenance-window deployment plans with sequencing and rollback procedures.
- Unpatchable-system register with compensating controls and risk acceptances.
- Evidence packages per patch cycle; metrics dashboard (MTTR, compliance %).

## Pitfalls

- **Patching redundant systems simultaneously.** Taking down both sides of a redundant pair for patching eliminates the redundancy you paid for. Sequence and validate.
- **Skipping validation for "just an OS patch."** OS patches have broken control applications repeatedly. If it runs in the control network, it gets tested — no exceptions based on patch size.
- **Treating CVSS as the priority order.** CVSS measures vulnerability severity in the abstract; OT prioritization must include exposure and process consequence or you'll patch the wrong things first.
- **No rollback plan.** A patch that breaks a control application with no tested rollback turns a maintenance window into an extended outage. Stage rollbacks before, not during.
- **Infinite deferral of legacy systems.** "We'll replace it next turnaround" for the fifth year running, with no compensating controls, is how unpatchable becomes unprotected. Force the decision annually.

## References

- NIST SP 800-82 Rev. 3, "Guide to OT Security" — https://csrc.nist.gov/publications/detail/sp/800-82/rev-3/final
- NIST SP 800-40 Rev. 4, "Guide to Enterprise Patch Management Planning" — https://csrc.nist.gov/publications/detail/sp/800-40/rev-4/final
- CISA ICS advisories — https://www.cisa.gov/news-events/cybersecurity-advisories
- NERC CIP-007 (system security management, patch provisions) — https://www.nerc.com/
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
