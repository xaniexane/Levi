# SOURCES.md — LEVI Security Knowledge Index

## Provenance

This index is derived from the **category/topic names only** of the
Awesome-Hacking meta-list:

- Source: `Hack-with-Github/Awesome-Hacking`
  ("A collection of awesome lists for hackers, pentesters & security researchers")
- Read: 2026-09-15 (README table of contents / the two category tables)
- Used: the **81 category names** as reference pointers — nothing else.

The two tables yielded 47 + 34 = 81 categories, each given one entry in
`catalog.json`. Category names are used as pointers only
(e.g. `Hack-with-Github/Awesome-Hacking -> Detection Engineering`).

## Originality rule

**No text was fetched, read, or copied from any linked repository.**
Not the meta-list's descriptions, and not the content of any list it links to.
Every `defensive_summary`, `detection_notes`, `hardening_notes`, and
`key_concepts` entry in `catalog.json` is original prose authored for LEVI.

## Defensive-framing rule

All entries are written for **blue-team defenders**: detection, analysis,
hardening, and incident response. Every domain is covered at full breadth —
nothing is blocked or omitted — including offensive-leaning categories
(password cracking, payload collections, red teaming, social engineering,
kernel exploitation, GTFOBins-style dual-use binaries, etc.).

For the 50 attack-relevant domains, each entry carries an `attack_profile`
field: threat-informed knowledge **of** the attack — what it is, how it works
conceptually, what it targets, and its observable indicators/footprints
(ATT&CK-style technique knowledge). The line is: knowledge of attacks yes,
instructions for attacks no. What stays out, unchanged: procedural execution
instructions (step-by-step how to run an attack), payloads, exploit code,
password-cracking tutorials, and tool usage guides for attacking. No code that
attacks anything.

## Offline guarantee

`catalog.json` ships in the repository. `levi security` works with zero
network access — there is nothing to download, no API to call, and no
telemetry leaves the machine.
