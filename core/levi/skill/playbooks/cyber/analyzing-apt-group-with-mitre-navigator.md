# Analyzing APT Groups with MITRE Navigator

## Purpose

Use MITRE ATT&CK Navigator to build, compare, and operationalize technique
profiles of APT groups — turning threat-intel reporting into prioritized
detection and hardening work for your environment, and giving leadership a
coverage picture they can actually read.

## When to use

- A new threat-intel report names an APT group targeting your sector and you
  need to translate it into defensive action.
- Prioritizing which ATT&CK techniques to build detections for given limited
  analyst capacity.
- Comparing two groups' toolkits to assess whether separate incident
  clusters are one actor or two.
- Briefing leadership: showing detection coverage of relevant APT techniques
  as a heatmap.
- Planning adversary-emulation (red team) scenarios scoped to a realistic
  group profile.

## Prerequisites

- Written authorization is generally not needed for this analytic work, but
  note: if you enrich profiles with your own incident data, that data
  inherits its handling restrictions — mark accordingly.
- Chain-of-custody notes: record report sources, dates, and confidence
  levels feeding each technique mapping — intel degrades, and you need to
  know what a layer was built from when it goes stale.
- A current ATT&CK Navigator instance (public hosted or self-hosted) and
  the current ATT&CK Enterprise matrix data.
- Source reporting: vendor threat reports, CISA advisories, or ISAC
  bulletins naming the group's TTPs — aim for 2–4 independent sources.

## Procedure

1. **Collect source reporting.**
   Gather 2–4 reputable reports on the target group.
   Record for each: publisher, date, and which TTP claims are directly
   observed vs. inferred.
   Discard single-source, low-confidence claims from your defensive profile
   or mark them clearly — they don't earn detection-engineering hours.
2. **Map reported behaviors to technique IDs.**
   For each observed behavior, assign the most specific ATT&CK
   technique/sub-technique (e.g., spearphishing attachment → T1566.001, not
   just T1566).
   Where reports disagree, keep both mappings and note the conflict rather
   than forcing a false consensus.
   Precision here determines whether your detections match reality.
3. **Build the Navigator layer.**
   In ATT&CK Navigator, create a new layer on the Enterprise matrix and
   enable techniques per your mapping.
   Use scores or color gradients to encode confidence: red = directly
   observed in multiple reports, orange = single-report, yellow = inferred.
   Add comments on each enabled technique citing the source report — future
   you will thank present you.
4. **Overlay your defensive coverage.**
   Create a second layer scoring your detection coverage per technique:
   green = production detection with alerting, yellow = partial/log-only,
   red = no coverage.
   Be honest: a log source that exists but nobody queries is yellow at best.
   Navigator's layer-compare makes the gap between "what the group does"
   and "what you'd see" visually obvious.
5. **Prioritize the gap.**
   Sort uncovered techniques by two axes: how central the technique is to the
   group's operations (their "can't-operate-without-it" techniques like
   their preferred persistence or C2) and how detectable it is in your
   telemetry.
   Build detections for high-centrality, high-detectability techniques
   first — best return on analyst hours.
6. **Compare groups when attribution is ambiguous.**
   Load two groups' layers and use Navigator's comparison view.
   Shared tooling (same custom malware, infrastructure patterns) supports a
   single-actor hypothesis; divergent initial-access and persistence choices
   argue for separate actors.
   Document the comparison with specifics, don't just eyeball it.
7. **Translate into hunt hypotheses.**
   Each red/orange technique in the group's profile becomes a hunt: "If
   GROUP-X were in our environment, we'd expect to see <technique> as <log
   evidence>."
   Run the top 3–5 hunts and record negative results too — confirmed absence
   is intelligence, and it validates your coverage scores.
8. **Scope adversary emulation.**
   Hand the layer to your red team (or use it to scope a purple-team
   exercise): emulate the group's top techniques and verify the
   green/yellow/red coverage scores empirically.
   Adjust the layer based on what the emulation actually evaded.
9. **Brief and publish.**
   Export the layer (Navigator's JSON/SVG export) into your threat-intel
   repository with the source list and date.
   Brief stakeholders with the heatmap plus the top-5 prioritized gaps and
   the detection work they generated.
   Keep the briefing to decisions and actions, not technique trivia.
10. **Maintain the profile.**
    Revisit the layer when new reporting drops or every 6 months at minimum.
    Groups evolve toolkits; a 2023 profile driving 2026 detections is a
    liability.
    Version your layers (v1.0, v1.1…) so consumers know what they're
    looking at.

## Key tools & commands

- MITRE ATT&CK Navigator (web) — layer creation, scoring, color gradients,
  layer comparison, JSON/SVG export.
- ATT&CK Enterprise matrix and STIX/TAXII feeds — canonical technique
  definitions and group profiles (the ATT&CK "Groups" pages pre-map many
  reported techniques — use as a starting point, then validate against
  primary reporting).
- Your SIEM/EDR — score actual detection coverage honestly per technique;
  query each before claiming green.
- Threat-intel platform (MISP, OpenCTI, or vendor feed) — store the
  finished layer with its sources and version.

## Expected outputs

- A Navigator layer per analyzed group: techniques enabled,
  confidence-scored, source-cited, versioned.
- A coverage-gap heatmap: group techniques vs. your honest detection
  posture.
- A prioritized detection/hunt backlog derived from the gap analysis, with
  owners.
- Emulation validation results adjusting the coverage scores.
- A versioned intel package (layer JSON + source list + briefing) stored in
  your intel repository.

## Pitfalls

- Treating ATT&CK group pages as complete: they summarize public reporting
  and lag real operations. Always supplement with recent vendor reports.
- Mapping too coarsely (everything becomes T1078 or T1059) destroys the
  value — the sub-technique is where detection engineering lives.
- Confusing tool overlap with actor identity: many groups buy the same
  crimeware. Technique *sequences* and infrastructure are stronger
  attribution signals than shared commodity tools.
- Letting the layer go stale. Date-stamp prominently and set a review
  reminder — calendar it, don't just intend it.
- Scoring coverage aspirationally ("we'll have logs next quarter") — score
  what exists today; maintain a separate roadmap layer for planned coverage.

## References

- MITRE ATT&CK: Enterprise matrix, Groups collection, Navigator
  documentation
- MITRE ATT&CK Navigator usage docs (layers, scoring, comparison, export)
- CISA advisories and vendor threat reports (primary sources for group
  TTPs — cite per claim)

See also: analyzing-threat-actor-ttps-with-mitre-navigator.md

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
