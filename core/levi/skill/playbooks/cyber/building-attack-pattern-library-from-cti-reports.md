---
skill_id: cyber_building_attack_pattern_library_from_cti_reports
name: Building an Attack Pattern Library from CTI Reports
description: Distill CTI reports into reusable ATT&CK-mapped detection patterns.
risk: low
permissions: []
requires_confirmation: false
tags: [threat-intel]
version: 1.0.0
---
# Building an Attack Pattern Library from CTI Reports

## Purpose

Turn unstructured cyber threat intelligence reports (vendor blogs, government advisories,
ISAC bulletins) into a structured, queryable attack pattern library — TTPs mapped to
MITRE ATT&CK, with detection and mitigation notes — so CTI actually drives detection
engineering instead of piling up as PDFs.

## When to use

- Maturing a CTI program from "report inbox" to operationalized intelligence.
- Feeding detection engineering with actor- and campaign-specific behaviors.
- Preparing threat-informed risk assessments or purple-team scenarios.
- Onboarding new analysts with a searchable history of relevant adversary behavior.

## Prerequisites

- Written authorization is generally not needed for processing *public* CTI; define
  handling rules for reports under TLP:AMBER/RED or NDA (store, don't republish).
- A canonical schema decision up front: ATT&CK technique/sub-technique IDs as the spine,
  plus your own fields (report source, actor, campaign, first seen, detection notes).
- Tooling for extraction and storage: even a structured spreadsheet beats PDFs, but plan
  to graduate to STIX 2.1 / a TIP (MISP, OpenCTI).
- Prioritized intelligence requirements — which actors, sectors, and technologies matter
  to your organization — so extraction effort goes where it matters.

## Procedure

1. **Define the schema.**
   - Minimum fields per pattern: ATT&CK technique ID, procedure description (what the
     actor *actually did*, quoted or paraphrased), actor/campaign, report source + URL,
     date, confidence, detection opportunities, and mitigation notes.
   - Keep procedure-level detail — "uses PowerShell" is a technique; "obfuscated
     PowerShell downloading from a newly registered domain via BITS" is a pattern.

2. **Set up the intake pipeline.**
   - Collect reports from trusted sources (vendor research blogs, CISA advisories, ISAC
     feeds) into a single intake queue with metadata (source, date, TLP).
   - Deduplicate: the same campaign gets reported by five vendors — link, don't
     quintuplicate.

3. **Extract TTPs per report.**
   - Read for behavior, not IOCs: walk the report's kill chain and note each technique
     with the concrete procedure.
   - Map to the most specific ATT&CK sub-technique justified by the evidence; mark
     ambiguous mappings as such rather than forcing a fit.

4. **Write detection notes at extraction time.**
   - For each pattern, note *where it would be visible*: which log source, which fields,
     what a true positive looks like, and known benign mimics.
   - Patterns without a detection note rot — the note is what makes the library
     operational.

5. **Normalize and store.**
   - Enter patterns in the canonical schema (STIX 2.1 Attack Pattern objects if using a
     TIP; structured rows otherwise).
   - Tag by actor, campaign, sector, and technology so hunts can slice the library
     ("show me ransomware-affiliated patterns against our VPN vendor").

6. **Quality-review extractions.**
   - A second analyst spot-checks technique mappings and detection notes; common failure
     modes are over-mapping (every report becomes T1059) and copying vendor marketing as
     procedure.
   - Track mapping disagreements — they reveal where your ATT&CK fluency needs work.

7. **Publish to consumers.**
   - Detection engineers: prioritized pattern lists mapped to uncovered log sources
     (gap analysis input).
   - Hunt teams: campaign pattern packs for threat hunts.
   - Risk/leadership: trend views (which techniques are rising against our sector).

8. **Maintain and expire.**
   - Re-verify patterns annually against current ATT&CK versions (techniques get renamed,
     split, and deprecated).
   - Archive patterns superseded by better reporting; keep the history — old patterns
     resurface when actors regress to proven tradecraft.

## Key tools & commands

- MISP / OpenCTI — structured storage, STIX 2.1 export, and sharing.
- MITRE ATT&CK Navigator — visualize library coverage against your detection posture.
- `attackcti`-style Python libraries or plain spreadsheets for lightweight extraction
  workflows.
- Simple ETL scripts (Python) to normalize vendor report formats into the canonical
  schema.

## Expected outputs

- Attack pattern library: technique-mapped, procedure-level, detection-noted entries.
- Coverage map (ATT&CK Navigator layer) showing library vs. deployed detections.
- Consumer packs: detection-engineering backlog, hunt packages, trend briefs.
- QA log and schema documentation.

## Pitfalls

- Extracting IOCs instead of behaviors — IOCs expire in weeks; patterns last years.
- Forcing ambiguous behavior into a specific sub-technique — wrong precision is worse
  than honest generality.
- No detection notes — a library nobody can act on is a museum.
- Ignoring TLP: republishing TLP:AMBER/RED report content into shared tooling burns
  source trust.

## References

- MITRE ATT&CK framework and STIX 2.1 specification (OASIS).
- MISP and OpenCTI documentation.
- NIST SP 800-150 (Guide to Cyber Threat Information Sharing).
- CISA advisories and vendor research as source material (cite per entry).

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
