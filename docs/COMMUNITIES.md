# COMMUNITIES — Portable Communities

**Remix delta.** Discord/Reddit lock-in works because a community's
structure, history, and governance live on the giant's servers in
proprietary form. Portability removes the lock-in that lets giants neglect
mods and users. LEVI inverts this: the community is a local first-class
data model with one-command export to an open, documented, checksummed
JSON format — and an import that **verifies integrity before accepting
anything**. A community that can leave is a community the platform must
serve.

## Data model

`Community {id, name, created_at}` with `Channel{id,name,kind,topic}`,
`Member{id,name,joined_at}`, `Role{id,name,permissions[],member_ids[]}`,
`Message{id,channel_id,author_id,text,timestamp,edited}`,
`Governance{rules[], moderators[], charter_ref?}`.

Governance is a thin reference: the full versioned governance document
lives in `levi.charters` (see CHARTERS.md); the community stores a
`charter_ref {id, version, checksum}` plus a local rules snapshot so the
export stays self-contained.

## Export format — `levi-community-export/1`

Open JSON: `community` metadata + `sections {channels, members, roles,
messages, governance}` + per-section SHA-256 `checksums` + a `manifest`
(SHA-256 over the sorted checksum table). Import recomputes everything
and **refuses** the file on any mismatch — tampered or corrupt exports
never load silently.

## CLI

```
python -m levi.communities create haven --name "Haven"
python -m levi.communities list | status haven
python -m levi.communities add-channel haven general --name general --topic lobby
python -m levi.communities add-member haven ada --name Ada
python -m levi.communities add-role haven mod --name Moderator --permissions moderate,post
python -m levi.communities grant-role haven mod ada
python -m levi.communities post haven --channel general --author ada --text "hello"
python -m levi.communities set-rules haven "be kind" "no spam"
python -m levi.communities export haven --out haven.levicommunity.json
python -m levi.communities verify --in haven.levicommunity.json
python -m levi.communities import --in haven.levicommunity.json [--as haven2]
```

Import fails closed rather than overwriting an existing community.

## Honest gaps

- Export is a snapshot, not live sync; two forks diverge (documented,
  not hidden).
- Message `edited` flags are carried but edit history is not — a known
  limit of the v1 format.
- Checksums prove the export wasn't altered in transit; they say nothing
  about whether the original history was truthful. Provenance, not truth.
