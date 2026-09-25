# LEVI Security Knowledge Index

An offline-first, stdlib-only catalog of **81 security domains**, derived from
the *category names only* of the Awesome-Hacking meta-list
(`Hack-with-Github/Awesome-Hacking`). Full breadth — every category is covered,
including the offensive-leaning ones. Nothing is blocked or omitted.

## What's in each entry

| Field | Meaning |
|---|---|
| `id` / `name` | Kebab-case id and the original category name (a reference pointer) |
| `defensive_summary` | What the domain covers and why a defender cares |
| `attack_profile` | **Attack-relevant domains only (50 of 81).** Threat-informed knowledge *of* the attack: what it is, how it works conceptually, what it targets, and its observable indicators/footprints. ATT&CK-style technique knowledge. |
| `detection_notes` | What to watch for in logs and telemetry |
| `hardening_notes` | How to defend: controls, configuration, process |
| `key_concepts` | Core terms for the domain |
| `reference` | Upstream pointer, e.g. `Hack-with-Github/Awesome-Hacking -> YARA` |

## The line: knowledge OF attacks, not instructions FOR attacks

The index covers attack techniques as **knowledge** — what they are, how they
work conceptually, what they target, and what footprints they leave. That is
threat-informed defense: you cannot detect what you do not understand.

What stays **out**, deliberately and permanently:

- step-by-step instructions for running an attack
- payloads, exploit code, or weaponized samples
- password-cracking tutorials or tool usage guides for attacking
- any code that attacks anything

Every entry carries `detection_notes` and `hardening_notes` — the
defensive-framing structural guarantee enforced by the test suite.

## Originality

No text was fetched, read, or copied from any linked repository. Category names
are reference pointers only; all prose is original LEVI-authored content. See
`core/levi/knowledge/security/SOURCES.md` for provenance.

## CLI usage (zero network required)

```bash
levi security list                  # all 81 domains (id + name)
levi security search <query>        # match name / summary / notes / concepts
levi security show <id>             # full entry incl. attack profile + detection + hardening
```

Examples:

```bash
levi security search ransomware
levi security show password-cracking
levi security show detection-engineering
```

## Offline guarantee

`core/levi/knowledge/security/catalog.json` ships in the repo. Queries read the
local file only — no downloads, no APIs, no telemetry leaves the machine.
