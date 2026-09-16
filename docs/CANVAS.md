# CANVAS — local workbench canvas

## The giant pattern it inverts

Anthropic's canvas splits chat from work-product — but the artifacts live
on their servers, in their format, under their retention. The pattern:
your work product is a hostage of the platform that helped you make it.

**The remix:** the same chat/work-product split, with artifacts versioned
locally — every edit appends an immutable version (history is never
rewritten), diffs via stdlib difflib, and full export (every version plus
a manifest) as a first-class operation. The work can leave LEVI any time,
in open formats.

## Model

- **Artifact**: id, type (`doc` | `code` | `plan`), title, ordered versions.
- **Version**: immutable `{n, created_at, content, note}`. Edit = append v(n+1).
- Storage: `~/.levi/canvas/<id>/` with `meta.json` + `v0001.md`, ... —
  raw content files any tool can read.

## CLI

```
python -m levi.canvas new essay --type doc --title "My essay" --text "..."
python -m levi.canvas edit essay --text "revised..." --note "tightened intro"
python -m levi.canvas show essay --version 1
python -m levi.canvas diff essay 1 2
python -m levi.canvas versions essay
python -m levi.canvas export essay /tmp/essay.levi-canvas.tar.gz
```

## Export format (monopoly-minus-one)

`.tar.gz` with `manifest.json` + `versions/v0001.md`... — plain tar and
JSON, inspectable with system tools.

## Honest gaps

- No collaborative editing / merge: versions are linear appends. Two
  writers editing "at once" just interleave versions; last-writer-wins
  per version, full history preserved.
- No rich-text rendering: artifacts are plain text/markdown. A viewer is
  the web app's job, not the store's.
- Diffs are line-based (difflib unified); binary artifacts are out of
  scope by design.
