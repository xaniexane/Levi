---
skill_id: cyber_forensic_case_management_workflow
name: Forensic Case Management Workflow
description: Run a defensible digital-forensics engagement end to end: case intake and authorization, evidence handling with chain of custody, hashing, analysis coordination, and reporting.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, incident-response, procedure]
version: 1.0.0
---
# Forensic Case Management Workflow

## Purpose

Give defenders a repeatable, defensible workflow for managing a digital
forensics engagement from intake to report. Covers case creation and
authorization records, evidence handling with chain of custody, hashing
and integrity verification, coordinating analysis across disk, memory,
and mobile artifacts, and producing a report that survives scrutiny —
whether the audience is your incident commander, your legal team, or a
courtroom.

## When to use

- Opening any forensic examination: suspected compromise, insider
  activity, malware triage, or data-theft allegation.
- When evidence must be preserved in a defensible state from the first
  touch (litigation hold, HR investigation, regulatory inquiry).
- Coordinating multiple analysts or tool outputs (disk images, memory
  dumps, mobile extractions, log bundles) without losing track of what
  came from where.
- Before running any acquisition or analysis tool, to make sure
  authorization, scope, and handling rules are settled first.
- When handing a case to external counsel or law enforcement, to show
  a clean, documented trail.

## Prerequisites

- Written authorization stating what you may examine, what you may
  not, and who approved it — signed before acquisition begins, not
  after.
- A designated case directory with access controls limited to the
  investigation team; evidence must not sit on shared drives.
- Write-blocking (hardware or software) for original media, and
  sufficient storage for forensic images plus working copies.
- Hashing tools available (SHA-256 at minimum) and a case log
  (notebook or ticketing system) for the chain of custody.
- Clarity on the questions the examination must answer — "find
  everything bad" is not a scope.

## Procedure

1. **Open the case and record authorization.** Create the case
   directory with a unique case ID and subfolders for evidence,
   working images, exports, logs, reports, memory, and mobile
   artifacts. File the written authorization, the scope (systems,
   accounts, time ranges), the investigation questions, and the names
   of everyone with access. Nothing is collected before this exists.
2. **Plan acquisition before touching anything.** Decide the order of
   volatility: memory first on live systems, then disk images, then
   logs and cloud artifacts. Prefer dead-box imaging with a
   write-blocker where the system can be taken offline; document why
   if live acquisition is the only option.
3. **Acquire with integrity built in.** Image through a write-blocker,
   hash the source and the image immediately (SHA-256), and record
   both hashes plus tool, version, operator, and timestamp in the case
   log. Verify the image hash matches before the original media is
   released. Every handoff of evidence — analyst to analyst, team to
   counsel — gets a dated, signed chain-of-custody entry.
4. **Work only on copies.** All analysis happens on working copies of
   the image, never on originals. Mount read-only or use forensic
   suites that enforce it. If a working copy is altered during
   analysis, re-hash and note the deviation rather than hiding it.
5. **Coordinate analysis by artifact type.** Run disk, memory, and
   mobile/log analysis as tracked workstreams feeding one timeline:
   filesystem timelines, process and network artifacts from memory,
   app data from mobile extractions. Correlate across workstreams
   (a file creation time, a process launch, a log entry) instead of
   letting each become its own island.
6. **Document findings as you go, not at the end.** Log every tool
   run with command line, version, input hash, and output location.
   Separate observed facts ("process X launched at T") from analyst
   inferences ("consistent with initial access via...") — conflating
   them is how reports get discredited.
7. **Write the report and close the case.** Structure it for the
   audience: executive summary, scope and authorization, methodology,
   findings with artifact references, limitations (what you could not
   examine and why), and appendices with hashes and tool logs. Have a
   second analyst review for accuracy. Archive the case with its
   retention policy, and revoke access for anyone who no longer needs
   it.

## Expected outputs

- A case directory with segregated evidence, working copies, logs,
  and reports, access-controlled to the investigation team.
- A complete chain-of-custody log from acquisition through every
  handoff.
- SHA-256 hashes for every source and image, verified at acquisition
  and re-verified on demand.
- A correlated timeline across disk, memory, mobile, and log
  workstreams.
- A reviewed final report distinguishing facts from inferences, with
  documented limitations.

## Pitfalls

- **Collecting before authorizing.** The most common way to poison a
  case is to image first and get permission later. Authorization
  precedes acquisition, always.
- **Analyzing the original.** One write to original media — a mount
  without read-only, an antivirus scan — and your hashes no longer
  match. Work on copies, every time.
- **Hash theater.** Hashing the image but never verifying, or hashing
  with MD5 alone in 2026, gives the appearance of integrity without
  the substance. Hash at acquisition, verify before analysis.
- **Timeline islands.** Disk, memory, and logs each tell part of the
  story. Findings that are never correlated across workstreams miss
  the attack chain.
- **Facts vs. inferences.** "The log shows X" is a fact; "the
  attacker did Y" is an inference. Reports that blur them lose
  credibility under review — label each.

## References

- NIST SP 800-86 (Guide to Integrating Forensic Techniques into
  Incident Response) for the end-to-end process model.
- NIST SP 800-101 (mobile forensics) and SP 800-72-era guidelines
  where applicable to device handling.
- Your forensic suite's documentation (Autopsy, Volatility 3, ALEAPP/
  iLEAPP) for tool-specific acquisition and analysis steps.
- Organization's evidence-retention and legal-hold policies — they
  govern the archive step, not your preferences.
- Chain-of-custody templates from your legal team or certifying body.

---
*Original work authored for LEVI. Defensive blue-team playbook — detection, analysis, and hardening guidance only. Topic inspired by a forensic orchestration script; no content copied from any external source.*
