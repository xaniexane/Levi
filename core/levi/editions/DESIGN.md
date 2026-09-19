# LEVI Editions — Design Doc

All under OMEGA Powered by Alpha. Levi heads all; Levi is the blueprint
that outlives them.

## 1. What an edition is

An edition is a **built domain instrument**: specially created tools,
skills, and agents that automate and refine the workflow of one division
of the economy. It arrives as a team template — a curated roster of
AI/SI operators, sector workflows, a data-handling posture, and a
compliance stance — but the roster is only the crew. The tools, skills,
and agents they wield, purpose-built for the domain's stated work, are
the edition's real body. A complete edition also carries the domain's
courses, classes, and certifications; virtualizes the domain's
paperwork; and lessens the keeper's workload the way interns do —
training, virtual paperwork, and offload are the full proposition.

### Administration add-ons

Editions are sold to administrations — the institutions that run them.
Side to every edition, switched on when the purchasing administration
requests it: specialized assistants for its people (a teacher's aide
for every teacher, and the equivalent in every sector); a time clock
for the agents and staff working inside the edition; and the
coordination layer — meeting briefs, newsletters, meeting updates,
training updates.
Editions are not separate products.
They are pre-built monthly rosters a keeper, institution, or sovereign
adopts inside the roster/tier game: tiers determine how many operators
you combine as a team; an edition tells you *which* operators, *why*,
and *under what law*.

There is nothing that can be taught that can't be assisted through AI
or SI — so every sector gets an edition: education, law enforcement,
military, government, hospitals, first responders, law, nonprofits,
business, enterprise, industrial, plus the open creational edition
(the mold, not the cast).

## 2. The manifest model (`manifest.py`)

- `EditionManifest`: id, name, sector, ring, tagline, description,
  roster, ai_si_mix, workflows, data_posture, compliance, excluded,
  tier_fit, pricing_note.
- `RosterSlot`: selects agents **by category** (optional subcategories),
  with a side (`ai`/`si`/`either`), a count, and a purpose. Category
  selection — never raw agent ids — so catalog re-stamping never breaks
  an edition. Resolution is deterministic: matches sorted by id, first
  `count` taken (`resolve_roster`).
- `DataPosture`: residency, retention, audit, and `trains_on_data`,
  which is always `False` — enforced in validation, sold as the feature.
- `excluded`: deliberate refusals, each with a *why*. An edition's
  refusals are as much the product as its roster.
- `validate_manifest`: every slot must resolve to agents; every refusal
  must carry a reason; training on sector data is a validation failure.

## 3. The AI/SI mix (the twin theme, applied)

The conventional side (AI) does procedure: grading rubrics, report
formats, compliance checklists, retention rules. The improvising side
(SI) does purpose: detective theories, course design, pattern discovery,
creative variation. Most sector editions are **Hybrid by nature** — the
pairing is the product, and sector editions are where the catch
compounds: neither side alone is whole for real institutional work.

## 4. The three rings (`rings.py`)

Distribution architecture, not product lines:

- **Open creational** — structure + architecture only. Ships: `schema/`
  (edition template, ring policy), `manifest.py`, `rings.py`,
  `DESIGN.md`, the lexicon. Outside minds author editions, propose
  rosters, build integrations, send plans upstream. Never ships: agent
  implementations, curated rosters, sector workflows, prompts, weights.
- **Closed** — diehard developers + the keeper. Full source: `catalog.py`,
  the 471-agent catalog, the original stack. The crown jewels never leave.
- **Government** — closed contents + the twelve-gate hardening checklist:
  reproducible builds, signed sealed receipts, append-only audit trails,
  sovereign deployment (zero external calls, air-gap capable), enforced
  data residency, no-training attestation, supply-chain pins,
  deny-closed HITL, penetration review, sovereign off-switch, provenance
  on everything, personnel-as-process. The bar is public; the builds that
  clear it are not.

The boundary is mechanical: `ring_for_path()` classifies any
repo-relative path by prefix rules. Unknown paths default to CLOSED
(deny-open). Any packager, CI gate, or release script can enforce it.

## 5. The eleven editions (`catalog.py`)

| Edition | Sector | Ring | Roster heart |
|---|---|---|---|
| education | universities, schools | closed | Learning & Notes + Communication; course production, assistants, grading |
| law-enforcement | police | closed | Security & Privacy + Travel & Local; paperwork, detective analysis, forensics support, simulation, theories, pattern/heat maps |
| military | defense, worldwide | government | Security & Privacy + System & Device Care; sovereign, air-gappable |
| government | political/admin | government | Communication + Productivity; audit trails, sealed receipts |
| healthcare | hospitals | closed | Health & Fitness + Communication; assists clinicians, never decides |
| first-responders | emergency services | closed | Communication + Travel & Local; offline/degraded-mode capable |
| legal | law firms, counsel | closed | Productivity + Learning & Notes; privilege-aware, assists counsel |
| nonprofit | charities, NGOs | closed | Productivity + Communication; appeal pricing, volume |
| business | companies | closed | Productivity + Finance & Money; the working edition |
| industrial | plants, field ops | closed | System & Device Care + Smart Home & IoT; fail-closed, HITL on physical actions |
| open-creational | everyone | open | the template and schema only — the mold, not the cast |

## 6. Safety boundaries (absolute)

- Defensive / authorized purple-team only, in every ring, forever.
- Law-enforcement tooling assists with **lawful evidence analysis**:
  chain-of-custody honesty (analysis never alters source evidence; copies
  marked as copies), every finding receipted with provenance. No
  surveillance automation, no dragnet identification, no predictive
  policing of persons — patterns on places and cases, not people.
- Military edition: no autonomous targeting, no weapons direction, no
  offensive cyber. Defensive and authorized only. Absolutely.
- Healthcare: assists clinicians, never diagnoses, no triage automation.
- Legal: assists counsel, never practices; review gates on all output.
- First responders: assists; humans dispatch.
- Industrial: fail-closed; HITL on any physical-world action; no
  autonomous control of safety-critical systems.
- Nothing in any edition evades the proving bar.

## 7. The roster/tier game

Editions plug into monthly roster selection as **team templates**: adopt
the education edition and your month's roster is its curated operators;
the roster IS your environment. `tier_fit` on each manifest suggests the
roster size (e.g. education → 4, law-enforcement → 6+, military and
government → Prime/Supra sovereign). Templates respect monthly lock-in:
adopt mid-cycle and it takes effect next season, like every roster change.

## 8. Pricing (per the doctrine)

No free core. ~30–60% below giants where comparable; **premium where
incomparable** — and sector editions are incomparable surfaces: no giant
sells a forensics-assistant edition, a sovereign government ring, a
no-training guarantee, or a monthly operator roster. Charge for what they
don't offer; undercut where they do. Nonprofit carries appeal pricing
(volume over margin). Government ring is the highest rentable power
below Supra: sovereign deployment is the product.

## 9. Build order

1. Skeleton + design (this wave).
2. `catalog.py`: the 11 manifests as data.
3. Validation tests: every slot resolves, every refusal reasoned, no
   training flags, ring boundaries hold.
4. Government-ring scaffolding: hardening manifest + sovereign profile
   (after the 471-agent enterprise waves land).
5. Generation 2 of the dynasty builds on editions, not before them.

## 10. Open questions for the keeper

1. Edition premium shape: flat edition license atop the roster tier, or
   editions as their own tier band? (Proposed: license atop tier —
   the roster is the seat, the edition is the playbook.)
2. Law-enforcement edition: ship the theory workbench in the closed
   ring at launch, or hold it for government-ring review first?
3. Military/government editions: which sovereign deploys first — is
   there a pilot institution in mind, or do we harden on speculation?
4. Open creational: do we accept outside edition submissions into the
   closed catalog, and under what review?
5. Nonprofit appeal pricing: how deep — and does the keeper want a
   tithe/grant mechanism in the pricing notes?
