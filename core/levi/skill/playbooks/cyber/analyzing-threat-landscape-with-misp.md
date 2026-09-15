# Analyzing the Threat Landscape with MISP

See also: analyzing-threat-intelligence-feeds.md

## Purpose

Use MISP (Malware Information Sharing Platform) as your threat-landscape workbench: correlate events
across sources, pivot on attributes to discover actor infrastructure, track campaigns over time, and
produce shared intelligence that other teams can consume. This is the analysis workflow inside MISP,
not the installation guide.

MISP's real power is correlation at scale: a single shared attribute can link your incident to
another organization's event, an actor galaxy, and a year-old campaign. This playbook is about
working those links deliberately instead of hoping the correlation graph does it for you.

## When to use

- An incident produces IOCs and you need to know what they connect to — known actors, prior
  campaigns, other victims.
- Building an actor or campaign profile from multiple intel sources over weeks or months.
- Preparing intelligence to share with an ISAC, peer organization, or law enforcement.
- Reviewing what's known about a sector-wide threat before a briefing or hunt.
- Validating a vendor's attribution claim against the community's collective data.

## Prerequisites

- Written authorization for the intelligence scope: which MISP organizations/communities you may
  share with, the default distribution and sharing-group rules, and TLP handling for your org.
- A MISP instance with user accounts, API keys managed per analyst, and synced feeds/communities
  relevant to your sector. Confirm sync is current — a stale MISP lies by omission.
- An analyst workflow agreement: who creates events, the attribute taxonomy and tagging conventions
  (e.g., `tlp:`, `misp-galaxy:`), and the confidence-tagging scheme, so the instance stays
  consistent.
- Chain-of-custody notes for any forensic-derived attributes added to events (source case ID,
  collection date).

## Procedure

1. Create or locate the event. Search MISP for existing events matching your IOCs (attribute search
   on IP, domain, hash). If one exists and your org has rights, extend it; if not, create a new
   event with a descriptive title, the correct threat-level ID, analysis status ("ongoing" vs.
   "completed"), and a TLP tag.
2. Add attributes with structure. For each IOC add the right attribute type (`ip-dst`, `domain`,
   `md5`/`sha256`, `url`, `email-src`) plus context: first-seen dates, and the `to_ids` flag set
   true only for indicators you would actually detect on. Sloppy `to_ids` usage pollutes everyone's
   IDS exports.
3. Attach objects for complex entities. Use MISP objects (file, url, domain-ip, vulnerability,
   attack-pattern) instead of flat attributes when the IOC has structure — an attack-pattern object
   carrying the MITRE technique ID is far more useful downstream than a bare text note.
4. Tag deliberately. Apply galaxy clusters (`misp-galaxy:threat-actor="..."`,
   `misp-galaxy:tool="..."`) and TLP tags at the event and attribute level. Tags are the pivots — an
   untagged event is a dead end.
5. Pivot on attributes. Click through on each attribute to list every event containing it. A domain
   that appears in three otherwise-unrelated events is a correlation worth investigating; a hash
   shared across events may tie your incident to a known campaign. Record each pivot and what it
   revealed.
6. Build the correlation graph. Use MISP's event graph view to visualize relationships: events
   linked by shared attributes, with galaxies labeling actors and tools. Prune weak links (single
   shared attribute with low confidence) and annotate the strong ones with your reasoning.
7. Track over time. Filter the correlated events by date to see the campaign's evolution: new
   infrastructure, tooling changes, victimology shifts. Add timeline notes to the event so the next
   analyst inherits the narrative, not just the IOCs.
8. Enrich with modules. Run MISP enrichment modules (VirusTotal, Shodan, passive DNS, WHOIS) on key
   attributes and attach the results as objects. Note the enrichment date — passive DNS from six
   months ago is a different fact than from today.
9. Add sightings. Record sightings on attributes your telemetry confirmed (true positives) and on
   ones that proved benign (false positives). Sightings are how the community collectively scores an
   indicator — your sighting data improves everyone's expiration and confidence decisions.
10. Publish and share. Set the final analysis status, verify distribution and sharing-group settings
    match the intel's sensitivity, then publish. Notify the relevant community or ISAC channel with
    a summary: what it is, confidence, recommended actions, and the event UUID for reference.

## Key tools & commands

- MISP UI: event search, attribute pivot, correlation graph view, galaxy tagging, sighting buttons.
- PyMISP for automation: `from pymisp import PyMISP; misp = PyMISP(url, key)`; search attributes
  with `misp.search(controller='attributes', value='<ioc>')`; add events with
  `misp.add_event(event)`; add sightings with `misp.add_sighting(...)`.
- MISP feed and sync configuration (Administration → Sync) to keep community data flowing; verify
  with the feed preview's last-sync timestamps.
- Enrichment modules (configured under Administration → Module Settings): VirusTotal, Shodan,
  passive DNS, WHOIS.
- `misp-modules` service health check when enrichment results stop arriving.
- MISP dashboard widgets for tracking your org's event, attribute, and sighting counts over time.

## Expected outputs

- A MISP event (new or extended) with typed attributes, correct `to_ids` flags, TLP tags, and galaxy
  clusters.
- MISP objects for structured entities (files, attack patterns with technique IDs).
- A pivot log: which attributes were pivoted, what correlated events were found.
- A correlation graph showing event relationships with annotated strong links.
- A campaign timeline narrative attached to the event.
- Enrichment results attached as objects with dates.
- Sightings recorded for confirmed and refuted indicators.
- A published event with correct distribution, shared to the appropriate community with a summary.

## Pitfalls

- `to_ids=true` on everything: context attributes (victim hostnames, analyst notes) exported to IDS
  rules create false positives across every consumer of your feed.
- Correlating on weak attributes: a shared public DNS resolver IP or a common user-agent string is
  not an actor link. Require multiple independent pivots.
- Publishing with the wrong distribution: one mis-set sharing group can leak victim-identifying data
  to the wrong community. Double-check before publishing.
- Letting events rot at "ongoing" analysis status: stale in-progress events erode trust in the
  instance. Close or update them.
- Trusting synced community data blindly: verify high-impact correlations against your own telemetry
  before acting.
- Galaxy over-tagging: tagging an event with three different threat actors "just in case" destroys
  the galaxy's analytical value. Tag what the evidence supports.
- Forgetting sightings: an event full of IOCs with no sightings tells consumers nothing about which
  indicators actually fired anywhere.

## References

- MISP documentation (misp-project.org) — events, attributes, objects, galaxies, correlation,
  sightings, and sharing groups.
- PyMISP documentation — API automation patterns including sightings.
- MISP galaxy and taxonomy repositories — the standard tagging vocabularies.
- FIRST TLP 2.0 — handling rules for shared intelligence.

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
