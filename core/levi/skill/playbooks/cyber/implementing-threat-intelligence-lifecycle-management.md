---
skill_id: cyber_implementing_threat_intelligence_lifecycle_management
name: Implementing Threat Intelligence Lifecycle Management
description: Run the full threat intelligence lifecycle from requirements to feedback and retirement.
risk: info
permissions: []
requires_confirmation: false
tags: [threat-intelligence, lifecycle, program-management]
version: 1.0.0
---
## Purpose
This playbook establishes the threat intelligence lifecycle as a managed process: requirements drive collection, analysis produces finished intelligence, dissemination puts it to work, and feedback improves the next cycle. It turns ad-hoc intel consumption into a measurable program.

## When to use
- Threat intel exists but nobody can say what questions it answers or whether it changed any decision.
- Stakeholders (SOC, IR, executives, engineering) each want different intelligence products.
- You are building or maturing a CTI function and need an operating model.

## Prerequisites
- Identified stakeholders and their priority intelligence requirements (PIRs).
- Access to collection sources: internal telemetry, commercial feeds, open sources, sharing communities.
- An analyst workflow tool (TIP, wiki, or tracker) to manage requirements and products.

## Procedure
1. **Capture requirements.** Interview stakeholders and write PIRs as answerable questions with deadlines and the decisions they support; review them quarterly.
2. **Plan collection.** Map each PIR to sources and collection methods; identify gaps where no source answers a requirement and either acquire coverage or downgrade the PIR.
3. **Process and normalize.** Deduplicate, translate, and structure raw data into a common model so analysts work from one consistent picture.
4. **Analyze and produce.** Apply structured analytic techniques (analysis of competing hypotheses, kill-chain mapping); write finished intelligence at the right level: tactical indicators for the SOC, operational TTP assessments for IR, strategic briefs for leadership.
5. **Disseminate with purpose.** Deliver each product through the channel its consumer actually uses (SIEM feed, ticket, briefing, dashboard), with handling markings and expiry.
6. **Collect feedback and measure.** Track which products were used, which PIRs were answered, and what changed as a result; feed misses back into requirements.
7. **Retire stale holdings.** Expire indicators and archive reports on schedule so the knowledge base stays trustworthy.

## Expected outputs
- Documented PIRs linked to stakeholders and decisions.
- Dissemination matrix (product, audience, channel, cadence).
- Program metrics: PIR satisfaction rate, product usage, time from requirement to delivery.

## Pitfalls
- Collecting without requirements: a feed firehose that answers nobody's question.
- Writing only tactical indicators while leadership gets no strategic context.
- No feedback loop, so the program optimizes for volume instead of usefulness.

## References
- NIST SP 800-150, Guide to Cyber Threat Information Sharing.
- CISA Cyber Threat Intelligence resources (cisa.gov).
