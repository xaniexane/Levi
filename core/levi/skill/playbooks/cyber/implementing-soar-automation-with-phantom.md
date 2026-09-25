---
skill_id: cyber_implementing_soar_automation_with_phantom
name: Implementing SOAR Automation with Phantom (Splunk SOAR)
description: Build security orchestration playbooks on Splunk SOAR (formerly Phantom) for automated response.
risk: low
permissions: []
requires_confirmation: false
tags: [soar, automation, incident-response]
version: 1.0.0
---
## Purpose
This playbook covers designing and operating automation on Splunk SOAR (the platform formerly known as Phantom): connecting assets, writing playbooks, and running human-in-the-loop automation that shortens response time without surrendering analyst judgment.

## When to use
- Repetitive triage tasks consume analyst hours (indicator enrichment, ticket creation, user lookups).
- You need consistent, auditable execution of containment steps across shifts.
- Incidents require coordinated actions across many tools (EDR, firewall, identity, ticketing).

## Prerequisites
- Splunk SOAR deployed with admin access and a defined asset inventory (EDR, firewall, IdP, SIEM, ticketing).
- API credentials for each integrated asset, stored in the platform's credential vault.
- A prioritized list of manual workflows to automate, ranked by frequency and time cost.

## Procedure
1. **Connect assets and validate actions.** Configure each integration (e.g., EDR isolate host, firewall block IP, IdP disable user) and test every action in a lab tenant before touching production.
2. **Start with enrichment, not containment.** Automate indicator reputation lookups, WHOIS, passive DNS, and asset context first; these are low-risk and build trust in the platform.
3. **Design playbooks with decision points.** Use conditional branching and explicit approval prompts before irreversible actions (host isolation on a domain controller, account disable for executives).
4. **Standardize inputs and outputs.** Define the artifact schema each playbook expects (e.g., SIEM alert JSON) so playbooks are reusable across alert types.
5. **Add auditability.** Log every automated action with who/what/when, and route playbook results back into the case record so the timeline is complete.
6. **Test with tabletop + live fire.** Run tabletop exercises against the playbook, then execute in a staging environment with real alerts replayed.
7. **Measure and tune.** Track time saved, false automation rate, and analyst override rate; retire playbooks that analysts routinely bypass.

8. **Control the blast radius.** Run playbook actions under per-asset service accounts with minimal scopes, and require re-authentication or step-up approval for actions affecting more than N assets at once.
9. **Plan for platform failure.** Document the manual fallback for each automated containment action so response continues if the SOAR platform itself is down during an incident.

## Expected outputs
- Connected, tested asset integrations with least-privilege API credentials.
- Versioned playbooks with human approval gates on destructive actions.
- Metrics: mean time to enrich, mean time to contain, automation override rate.
- Example: a phishing-alert playbook that enriches 40 indicators, purges the malicious message tenant-wide, and opens a ticket — with analyst approval required before disabling any user account.

## Pitfalls
- Automating containment before enrichment is trustworthy leads to self-inflicted outages.
- Over-privileged service accounts on the SOAR platform become a high-value target; scope them tightly.
- Playbooks that nobody owns rot when APIs change; assign an owner and a review cadence.

- Playbooks that send sensitive case data to third-party enrichment APIs without a data-handling review; check what each integration transmits.
- No rollback plan for automated firewall blocks: a wrongly blocked partner IP needs a one-click revert, not a change ticket.

## References
- Splunk SOAR documentation (docs.splunk.com — Splunk SOAR).
- NIST SP 800-61 Rev. 2, Computer Security Incident Handling Guide.
- SANS SEC504 course materials (sans.org) — incident response automation concepts.
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
