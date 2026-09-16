# LEVI Sentinel — defensive host tooling

Executable blue-team tooling for systems you own or are authorized to
protect. Original LEVI-native implementation; concepts adapted from
legacy LEVI August-lineage defensive scripts (source-sync entry
`the-pack`), rewritten from scratch — no source text copied.

## What it is

| Command | What it does |
|---|---|
| `levi sentinel watch` | Read-only detection: failed-login scan, suspicious process markers, listening-ports inventory |
| `levi sentinel integrity create/verify` | SHA-256 file-integrity baselines for a directory tree (create now, verify later, get added/removed/changed) |
| `levi sentinel triage --path DIR` | Defensive file triage: SHA-256 "DNA" fingerprint + signature leads (reverse-shell idioms, miner tokens, obfuscation, credential-access markers) |
| `levi sentinel case create/log/hash/summary` | Forensic case tree with append-only chain-of-custody log and markdown summary |
| `levi sentinel contain block-ip/terminate` | HITL-gated defensive containment — dry-run preview by default |

## The binding law

**Detection is read-only. Containment never runs automatically.**

Every containment action follows Plan → Preview → Permission → Execute
→ Verify → Receipt. Without `--confirm`, `contain` prints a plan and
changes nothing. A plan for one IPv4 address or one PID is the maximum
blast radius: temporary iptables INPUT drops and SIGTERM only.

This module never scans anyone else's systems, never exfiltrates data,
and never "heals" files on its own (restoring from an integrity diff
is a human decision, not an automated one).

## Related systems

- `levi security` — the offline defensive *knowledge* index (playbooks, topics).
- `core/levi/security/integrity.py` — FNV-1a pack-manifest tamper-refuse
  (guards what LEVI loads, not your host's files — different job).
- `levi surgeon` — code snapshots and the sandbox HITL gate (the same
  human-confirmation philosophy applied to code changes).

## Storage

- Integrity manifests: wherever you put `--manifest` (operator-owned).
- Forensic cases: `~/.levi/sentinel/cases/`.
- Nothing leaves the machine.
