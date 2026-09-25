---
skill_id: utility.toml_to_json
name: TOML to JSON
description: Convert a TOML file into equivalent JSON using the standard library.
risk: moderate
permissions: []
requires_confirmation: true
tags: [toml, json, convert]
version: 1.0.0
---

# TOML to JSON

TOML to JSON parses a TOML document with tomllib and writes the equivalent JSON to a new file - handy for configs moving between ecosystems.

## When to use

- Converting a pyproject-style config for a JSON-only tool.
- Inspecting TOML data with JSON tooling.
- Bridging config formats in a build pipeline.

## Steps

1. Read the TOML file as bytes and parse with tomllib (Python 3.11+).
2. Serialize the resulting structure with json.dump (indent=2) to a new .json file.
3. Load the JSON back and compare key counts against the TOML as a sanity check.
4. Open the JSON and confirm nested tables became objects and arrays stayed arrays.

## Honest limits

- Requires Python 3.11 or newer for tomllib; older versions need the third-party tomli package.
- TOML datetimes become ISO strings in JSON - types narrow, and that is disclosed.
- Comments in the TOML do not survive conversion; JSON has none to hold them.

Original work authored for LEVI - utilities pack.
