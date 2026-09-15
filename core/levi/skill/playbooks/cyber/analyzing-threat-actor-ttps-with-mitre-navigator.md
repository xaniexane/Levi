---
skill_id: cyber_analyzing_threat_actor_ttps_with_mitre_navigator
name: Analyzing Threat Actor TTPs with MITRE Navigator
description: Visualize TTP overlap across actors with ATT&CK Navigator layers.
risk: low
permissions: []
requires_confirmation: false
tags: [threat-intel]
version: 1.0.0
---
# Analyzing Threat Actor TTPs with MITRE Navigator

See also: analyzing-threat-actor-ttps-with-mitre-attack.md, analyzing-apt-group-with-mitre-navigator.md

## Purpose

Use MITRE ATT&CK Navigator to build visual, shareable technique heatmaps of a threat actor's TTPs:
score techniques by observed frequency or confidence, layer multiple actors or time periods for
comparison, and export the result as an intelligence product or detection-gap briefing. Navigator
turns the technique list into a picture executives and engineers both read instantly.

Navigator is a presentation and comparison layer, not an analysis tool. The quality of every heatmap
is bounded by the quality of the technique mapping underneath it — garbage mappings make pretty
garbage.

## When to use

- You have a completed technique mapping (from the ATT&CK playbook) and need to visualize it for
  stakeholders.
- Comparing two actors' TTPs side by side, or one actor's evolution across campaigns.
- Briefing detection coverage: overlaying "what the actor does" with "what we detect" in a single
  view.
- Preparing purple-team scope: showing exactly which techniques will be emulated.
- Quarterly threat reviews: showing how a tracked actor's profile changed since the last review.

## Prerequisites

- A technique list to visualize: technique IDs with scores, comments, and ideally
  observed/reported/inferred tags from your mapping work. Navigator visualizes data — it does not
  create the mapping.
- Written authorization matching the underlying investigation (the heatmap inherits the sharing
  restrictions of the intel it depicts; mark it TLP accordingly).
- The Navigator instance: the public hosted version (mitre-attack.github.io/attack-navigator) or a
  self-hosted build for sensitive data that should not leave your network. Note which you used.
- The ATT&CK version your technique IDs were mapped against; Navigator layers declare a domain
  (`enterprise-attack`, `mobile-attack`, `ics-attack`) and version compatibility.
- A defined scoring semantic agreed before you start — changing what scores mean mid-project
  invalidates comparisons.

## Procedure

1. Choose the Navigator instance. For internal or sensitive actor profiles, use a self-hosted
   Navigator or the hosted version with no data transmitted beyond the layer JSON you load locally
   in your browser. Record the choice.
2. Create the base layer. In Navigator: New Tab → select the domain (almost always
   `enterprise-attack`) → you have an empty matrix. Alternatively, hand-write the layer JSON (see
   step 4) and open it via "Open existing layer."
3. Encode your technique data as scores. Assign a numeric score per technique reflecting your chosen
   semantics — document the legend explicitly, e.g., 3 = directly observed, 2 = reported by trusted
   source, 1 = inferred, 0 = not observed. Color the gradient from light to dark so density reads at
   a glance.
4. Write or refine the layer JSON. Navigator layers follow this schema: `{"name": "...", "version":
   "5.0", "domain": "enterprise-attack", "techniques": [{"techniqueID": "T1053.005", "score": 3,
   "color": "", "comment": "Observed 2026-03 incident", "enabled": true, "metadata": []}]}`.
   Generate this programmatically from your mapping spreadsheet to avoid transcription errors, then
   load it.
5. Annotate with comments. Every scored technique should carry a comment: the incident or report it
   came from, the date, and the observed/reported/inferred tag. Comments make the heatmap auditable
   months later.
6. Build comparison layers. For actor-vs-actor or then-vs-now analysis, create one layer per subject
   with the same scoring semantics, then use Navigator's multi-layer view or export both and diff
   the technique sets. Divergent techniques are the interesting story.
7. Overlay detection coverage. Create a second scoring dimension or a separate layer where scores
   represent your detection state (e.g., 3 = alerting, 2 = logged, 1 = no visibility). Techniques
   dark in the actor layer but light in the coverage layer are your priority gaps — screenshot this
   for the briefing.
8. Sanity-check the visualization. Before publishing, verify: every dark cell has a comment, the
   legend matches the actual scoring, and no technique was scored from a misread mapping. Have a
   second analyst spot-check the layer against the source mapping.
9. Export and publish. Export as SVG/PNG for slides and as JSON for reuse. Include in the product:
   the scoring legend, the ATT&CK version, the data cutoff date, and the TLP marking. Store the
   layer JSON under version control with the intel report it supports.
10. Maintain on a cadence. For tracked actors, refresh the layer when new reporting arrives or
    quarterly, whichever comes first. Keep prior versions tagged in version control so evolution is
    visible as a diff, not a memory.

## Key tools & commands

- ATT&CK Navigator (hosted at mitre-attack.github.io/attack-navigator, or self-hosted from the
  `attack-navigator` GitHub repository via `npm install` / `ng serve`; a Docker image is also
  published for self-hosting).
- A short Python script to generate layer JSON from a CSV of technique IDs and scores — e.g.,
  `json.dump({"name": ..., "version": "5.0", "domain": "enterprise-attack", "techniques": [...]},
  open("actor.json","w"))`. The layer format version "5.0" with `techniqueID`, `score`, `comment`,
  `enabled` fields is the documented schema.
- `git` for versioning layer JSON alongside intel reports; tag releases per review cycle.
- `diff` on successive layer JSON files to produce the evolution summary for quarterly reviews.
- Screenshot/export: Navigator's built-in SVG/PNG export.

## Expected outputs

- One or more Navigator layer JSON files with scores, comments, and a documented legend.
- Heatmap exports (SVG/PNG) for briefings, with ATT&CK version, cutoff date, and TLP marking.
- An actor-vs-actor or then-vs-now comparison with divergent techniques highlighted.
- A detection-coverage overlay identifying priority gaps.
- A second-analyst spot-check record.
- Version-controlled layer files tied to the supporting intel report, with prior versions tagged.

## Pitfalls

- Scoring without a legend: a heatmap where nobody knows what dark red means is decoration, not
  intelligence. Always publish the legend with the image.
- Mixing scoring semantics across layers (frequency in one, confidence in another) and then
  comparing them as if they were the same.
- Loading sensitive actor data into the hosted Navigator from a network where even the layer content
  is classified — use self-hosted when in doubt.
- Forgetting `enabled: false` vs. omitting techniques: techniques absent from the layer render as
  unscored, which readers may misread as "not used." Be explicit about what absence means in your
  legend.
- Letting the visualization go stale: an actor profile from 2024 presented in 2026 without a cutoff
  date misleads.
- Overloading one layer with two semantics (actor behavior AND detection coverage in the same
  scores) — use separate layers or the overlay view instead.
- Presenting the heatmap without the underlying mapping: executives see the picture, but engineers
  need the technique table with evidence citations.

## References

- MITRE ATT&CK Navigator repository and documentation (layer format specification).
- MITRE ATT&CK enterprise matrix — technique IDs and definitions underlying the layers.
- "Getting Started with ATT&CK" (MITRE) — scoring and heatmap use cases.
- The companion playbook analyzing-threat-actor-ttps-with-mitre-attack.md — the mapping methodology
  that feeds Navigator.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
