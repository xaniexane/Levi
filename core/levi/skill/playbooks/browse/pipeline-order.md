---
skill_id: browse.pipeline_order
name: Pipeline Order
description: fetch to parse to grade to shield to plugin hooks — the fixed order, fail-fast, no JavaScript, one plugin's failure never takes the page.
risk: info
permissions: []
requires_confirmation: false
tags: [browse, pipeline, order, fail-fast]
version: 1.0.0
---

# Pipeline Order

The page pipeline runs in exactly this order, every time. The order
is the contract — reordering stages is an API change, which needs a
recorded ruling.

```
fetch (declared hosts only)
  → parse (stdlib html.parser; no JS execution, ever)
  → grade (claim cards on extracted metadata: OBSERVED/INFERRED/UNVERIFIED)
  → shield (block lists applied; what didn't apply is reported)
  → plugin hooks (page_loaded, in registration order)
```

## Stage rules

- **fetch:** declared hosts only (law 3). A fetch to an undeclared
  host is refused before any byte moves. Redirects are re-checked
  against the declaration — a redirect to an undeclared host stops the
  pipeline with a receipted refusal.
- **parse:** stdlib `html.parser`, static. No JavaScript execution in
  the Python core, ever. Dynamic pages are the WebView shell's job
  (phase 3); the core parses what it can see and grades the rest
  UNVERIFIED.
- **grade:** every piece of extracted metadata that is not a direct
  byte observation gets a claim card. The grade is attached to the
  page model, not computed later by consumers.
- **shield:** local block lists, versioned. What applied is reported;
  what didn't apply is reported too (law 7: no simulated success).
  A shield list that failed to load fails the stage loudly — never
  silently browsing unshielded.
- **plugin hooks:** `page_loaded` fires in registration order. One
  plugin's exception fails **that plugin only** — the exception is
  receipted, the plugin is marked faulted, the page continues. A
  faulted plugin does not retry mid-pipeline.

## Fail-fast

A stage that fails stops the pipeline. There is no "best effort
continue" — a half-fetched, half-graded page is worse than no page,
because downstream stages would grade guesses as observations. The
failure is receipted with the stage name and the reason.

## Agent acts (no new stages)

The agent surface (`browse/agent.py`) does not add pipeline stages.
It invokes facade operations *between* pipeline runs: an act
completes its Plan→Preview→Permission→Execute→Verify→Receipt chain,
then a fresh pipeline run re-fetches, re-grades, and re-shields the
result. Acting never happens mid-pipeline — a page mid-pipeline is
not a page the keeper previewed.

Consequence: the pipeline order above is unchanged by automation.
The agent is a privileged consumer of the pipeline, not a stage in
it.

## What this is not

Not a browser engine pipeline. No layout, no rendering, no script
runtime. The Python core is a fetch-grade-shield machine; pixels are
phase 3's problem.
