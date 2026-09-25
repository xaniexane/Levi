# Dual-Reality Files

One file, two sides — adapted from the OMEGA Canon's Feature 8
(Dual-Reality File System) and the Alpha & Omega meta-doctrine M-01:
every canon is simultaneously a written declaration AND a physical
engine. LEVI-native original implementation.

- **SIDE A (PHYSICAL)** — what it does: automations, flows, device logic.
- **SIDE B (CANON)** — what it is: architecture, identity, theory, purpose.

The two sides update together, evolve together, stay in sync.

## Format

A `.dual.md` markdown file with two fenced sections:

```markdown
<!-- dual-reality:1 -->
# Engine X

## SIDE A — PHYSICAL

runs the nightly scan and writes receipts

## SIDE B — CANON

Engine X exists so the nightly scan is receipted
```

## CLI

```bash
PYTHONPATH=core python -m levi.dual create --path x.dual.md --title "Engine X" \
  --physical "..." --canon "..."
PYTHONPATH=core python -m levi.dual read --path x.dual.md
PYTHONPATH=core python -m levi.dual verify --path x.dual.md     # sync report
PYTHONPATH=core python -m levi.dual seal --path x.dual.md       # identity-lock
PYTHONPATH=core python -m levi.dual verify-seal --path x.dual.md # drift check
```

## Rules

- Both sides are required; a half file is refused at creation.
- `verify` checks presence, non-emptiness, and shared vocabulary
  (canon must describe the physical in its own words).
- `seal` refuses out-of-sync files. Sealing writes a sha256 digest to
  `~/.levi/dual/seals.jsonl`; `verify-seal` detects later drift.
