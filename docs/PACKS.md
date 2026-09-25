# PACKS — Scoped Knowledge Packs

Anthropic's project-knowledge pattern (folder + instructions as
persistent context) is a cloud feature: your context lives on their
servers, under their retention policy, inside their product. LEVI Packs
is the remix: the pack is a folder on your disk in an open format, and
assembly happens locally.

## The format

```
~/.levi/packs/<name>/
    manifest.json      # format, name, version, description, scope, priority
    instructions.md    # standing instructions (any top-level *.md counts)
    instructions/      # more instruction files (optional)
    content/           # reference material: md / txt / json
```

`manifest.json` scope rules (user-editable):

```json
"scope": {
  "always": false,
  "projects": ["levi"],
  "paths": ["*/workspace/*"],
  "tags": ["ops"]
}
```

## Scoping

`python -m levi.packs assemble [--project SLUG] [--cwd PATH] [--tag T]`
attaches only packs whose rules match. Precedence: tags > projects >
paths > always; within the match set, lower `priority` assembles first.
Every section carries a provenance header (`# pack: <name> (matched by:
<rule>)`) so the model always knows which pack said what.

A byte budget truncates *content first* — instructions are never
silently truncated, and any truncation is named in the assembly header.

## Usage

```bash
python -m levi.packs init research --scope-always --description "background reading"
python -m levi.packs list
python -m levi.packs show research
python -m levi.packs assemble --project levi
python -m levi.packs validate
python -m levi.packs delete research
```

## What the giant refuses

- Context as portable files (their context is a SaaS feature you rent).
- User-visible, user-editable assembly order and scoping (theirs is
  opaque prompt-stuffing).
- Provenance headers on context (theirs arrives unattributed).

## Open gaps

- No pack signing/sharing registry yet — packs move as folders (tar
  them); a future `packs export/import` could bundle them.
- No conflict detection when two packs give contradictory instructions
  (both assemble; provenance headers make the conflict visible to the
  model instead).
