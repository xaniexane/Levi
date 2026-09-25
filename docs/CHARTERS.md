# CHARTERS — Community Charters

**Remix delta.** Reddit's mods are captive: they govern inside a platform
that can overrule, replace, or ignore them, and their governance has no
existence outside Reddit's servers. LEVI inverts this: the charter is a
**versioned, founder-signed artifact the community owns**; the mod action
log (warnings, removals with reasons, appeals) is local and auditable;
the whole thing exports to an open checksummed format. Founder-held
keys, real mod tooling, governance that can leave.

Not to be confused with `levi.identity.charter` — LEVI's own identity
constitution. This package is *community* governance.

## Data model

Charter: `{id, community_id, version, rules[{id,text,added_in_version,
retired_in_version}], roles[{id,name,permissions}], succession{founder,
successors[], trigger}, amendment{procedure, quorum}, history[]}`.
`community_id` matches `levi.communities` ids by convention.

Mod log: actions `(warn | remove | ban | unban | note |
appeal-decision)` — every action **requires a non-empty reason** (no
silent moderation). Appeals move `open → upheld | overturned`, decided
by a named moderator with a decision note.

## Signatures — honest scope

HMAC-SHA256 over canonical JSON with a per-charter founder key
(`~/.levi/charters/<id>.key`, owner-only 0o600). A valid signature
proves the artifact came from the key holder and is unaltered since
signing. It does NOT prove the founder's real-world identity, that the
rules are just, or that the community consented. Amendment
`approvals_claimed` are **recorded claims, not cryptographic proofs**.
The founder key never leaves the founder's machine: charter *exports*
carry no key, so imports are **re-keyed locally** and the history entry
says so explicitly — `verify()` after import attests the local key.
`rotate-key` re-signs under a new key and records the rotation (the
trust gap during rotation is documented, not hidden).

## Interop with communities (B6)

`charters attach <charter-id> --community haven` writes
`charter_ref {id, version, checksum}` into the community's governance
block (`levi.communities`), so the community export carries its
governance pointer — governance travels with the community.

## Export format — `levi-charter-export/1`

Sections `{charter, mod_log, appeals}` + per-section SHA-256 checksums +
manifest. Import verifies everything and **fails closed**; it also
refuses to overwrite an existing charter.

## CLI

```
python -m levi.charters new haven-c --community haven --founder ada --rules "be kind" "no spam"
python -m levi.charters show haven-c | verify haven-c | list
python -m levi.charters add-rule haven-c --text "no ads"
python -m levi.charters retire-rule haven-c r2
python -m levi.charters add-role haven-c mod --name Moderator --permissions warn,remove,ban
python -m levi.charters set-succession haven-c --successors grace --trigger "absence > 90 days"
python -m levi.charters set-amendment haven-c --procedure "proposal + 72h discussion" --quorum 2
python -m levi.charters amend haven-c --changes "added rule r3" --approvals ada grace
python -m levi.charters rotate-key haven-c
python -m levi.charters mod haven-c --moderator ada --action warn --target mallory --reason "spam x3"
python -m levi.charters appeal haven-c --action-id <id> --appellant mallory --text "..."
python -m levi.charters decide-appeal haven-c --appeal-id <id> --by grace --decision overturned --note "..."
python -m levi.charters modlog haven-c
python -m levi.charters attach haven-c --community haven
python -m levi.charters export haven-c --out haven-c.levicharter.json
python -m levi.charters import --in haven-c.levicharter.json [--as haven-c2]
```

## Honest gaps

- Amendment approvals are claimed identities, not proofs — a dishonest
  founder can fabricate the quorum. The log makes fabrication auditable;
  it does not make it impossible.
- No multi-signature support yet: one founder key per charter (v1 limit).
- Succession `trigger` is a documented human process; LEVI does not
  detect "founder absence" — claiming otherwise would be dishonest.
