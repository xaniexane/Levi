---
skill_id: cyber_building_soc_metrics_and_kpi_tracking
name: Building SOC Metrics and KPI Tracking
description: Practitioner guide to selecting, measuring, and reporting SOC metrics that drive operational improvement rather than vanity statistics.
risk: info
permissions: []
requires_confirmation: false
tags: [soc, metrics, operations]
version: 1.0.0
---
## Purpose
SOCs drown in data but starve for insight. This playbook selects a focused set of metrics -- detection coverage, response times, alert quality, analyst workload -- builds reliable measurement, and turns the numbers into a reporting rhythm that improves operations instead of just filling slides.

## When to use
- Standing up SOC performance measurement for the first time.
- Replacing misleading metrics (like raw alert counts) with meaningful ones.
- Justifying SOC staffing, tooling, or budget changes to leadership.
- Diagnosing whether the SOC is getting better or just busier.

## Prerequisites
- Ticketing and SIEM data with consistent severity, status, and timestamps.
- Agreed definitions for each metric (what counts as acknowledged, resolved, true positive).
- Baseline period of data before setting targets.
- Stakeholders who agree on what good looks like.

## Procedure
1. Choose outcome-oriented metrics. Start with mean time to detect, mean time to respond, true-positive rate, and alert-to-ticket conversion; add coverage metrics next.
2. Define each metric precisely. Document numerators, denominators, time windows, and exclusions so the numbers are reproducible.
3. Automate collection. Pull metrics from the ticketing system and SIEM via API; avoid manual spreadsheets that drift and lie.
4. Establish baselines. Measure for four to eight weeks before setting targets; targets without baselines are guesses.
5. Build tiered reporting. Give analysts operational views, managers trend views, and executives a small set of KPIs tied to risk reduction.
6. Review metrics in operations meetings. Discuss what changed, why, and what action follows; metrics without decisions are decoration.
7. Guard against gaming. Watch for behaviors like premature ticket closure; pair efficiency metrics with quality metrics.
8. Evolve the set. Retire metrics that no longer drive action; add new ones as the threat landscape and tooling change.

## Expected outputs
- Documented metric definitions with baselines and targets.
- Automated dashboards for analysts, managers, and executives.
- Monthly review cadence with action tracking.

## Pitfalls
- Vanity metrics (total alerts handled) reward volume over quality.
- Manually compiled metrics get quietly abandoned within quarters.
- Targets set without baselines are either trivial or demoralizing.
- Measuring individuals punitively destroys trust; measure the process.

## References
- NIST SP 800-61 Rev. 3, Computer Security Incident Handling Guide
- SANS guidance on SOC metrics and maturity
- ISO/IEC 27004, Information security measurement
---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
