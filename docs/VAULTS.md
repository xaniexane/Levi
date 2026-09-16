# VAULTS — per-project memory scopes with explicit retention

## The giant pattern it inverts

Cloud AI memory is one flat, opaque bucket: the user can't see what's
kept, can't scope it per project, can't set retention. Granular controls
would expose how much the giants retain — so they refuse them.

**The remix:** memory is partitioned into vaults. Each vault is an
isolated store with an EXPLICIT retention policy — TTL per entry class,
max entries, auto-purge — stored as readable JSON you can audit and
edit. Isolation is structural (separate directories, per-vault stores),
not a filter flag: a vault's contents can never leak into another
vault's queries.

## Concepts

- **Vault** — `~/.levi/vaults/<name>/` with `entries.jsonl` + `policy.json`.
- **Retention policy** — `{"ttl_by_type": {"working": 86400}, "max_entries": 500}`.
  TTLs in seconds; `0`/missing = keep forever. Enforced on every access:
  expired entries are dropped, then over-cap entries (lowest importance,
  oldest first) are dropped. `purge` reports counts — retention is
  enforced, not advisory.
- **Isolation** — `Vaults` hands you one vault at a time; each vault only
  reads its own directory. There is no cross-vault query path.

Entry shapes reuse `levi.memory.types` (portable with the flat store);
vaults add the scoping + retention the flat store lacks.

## CLI

```
python -m levi.vaults create alpha
python -m levi.vaults policy alpha --ttl working=86400 --ttl episodic=2592000 --max-entries 500
python -m levi.vaults add alpha "deploy checklist" --type procedural --tags ops
python -m levi.vaults search alpha "deploy"     # searches ONLY alpha
python -m levi.vaults purge alpha
python -m levi.vaults export alpha /tmp/alpha.levi-vault.tar.gz
python -m levi.vaults import /tmp/alpha.levi-vault.tar.gz --name alpha-copy
```

## Export format (monopoly-minus-one)

Plain `.tar.gz`: `manifest.json` + `policy.json` + `entries.jsonl`.
Inspectable with system tools; import fails closed on name collision
unless `--merge`.

## Honest gaps

- TTLs are evaluated lazily (on access), not by a background sweeper —
  an untouched vault keeps expired entries on disk until next accessed.
  `purge` is the explicit trigger.
- No encryption at rest yet: vault dirs are 0700 owner-only, but entries
  are plaintext JSON. (Pairs with the existing `levi.vault` seal for
  secrets — a future bridge, not built here.)
- `max_entries` eviction is importance-then-age; a flood of high-importance
  entries can still push out older high-importance ones. Policy, not magic.
