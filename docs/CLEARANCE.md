# CLEARANCE.md — who may see what

This is a **design document**, not an enforcement claim. It records the
keeper's access tiers for LEVI: who may see what, who may never see what,
and how clearance is granted and revoked. Enforcement (keys, ledgers,
revocation plumbing) is future work; the law below is what that work
must implement.

## The standing law

**Clearance is granted, never bought.** No paid tier, no bundle, no
purchase buys clearance — the same pattern as the legion law (the united
legion belongs to the keeper; select users receive it only by his grant;
it is never purchased through a tier). A higher-paying customer is not a
higher-cleared person. Clearance moves one direction only: the keeper's
explicit grant, and his revocation ends it immediately and totally.

Least privilege throughout: every tier sees the minimum it needs, and
no tier implies any other.

## Tier 0 — The Keeper's Eyes Only

**Who:** Chauncey. Nobody else, ever, for any reason, at any price.

**May see:** everything — vault bundles and passphrases, crown jewels
(SI closed source, signing and grant keys, the legion's control plane),
keeper personal data, the clearance ledger itself, break-the-code stage
selection and the unreleased pool.

**Never sees anyone else:** there is no one else at this tier.

**Grant/revoke:** he is the keeper. There is no grant process and no
revocation — Tier 0 is identity, not permission.

## Tier 1 — Trusted Developers

**Who:** individual developers the keeper names, one by one. No teams,
no companies, no roles — persons.

**May see:** the working-copy source they are assigned to, docs, tests,
the issue tracker, build tooling. Scoped per person, per area, recorded
in the clearance ledger.

**Never sees:** vault bundles and passphrases; crown-jewel sources (SI
core, vault crypto internals beyond the labeled interface, grant/signing
keys); the keeper's personal data; production secrets; other developers'
scopes; Tier 0 material of any kind.

**Grant:** the keeper's explicit per-person grant — named, scoped,
dated, written in the clearance ledger. **Revoke:** the keeper's word,
instantly: access cut, credentials rotated, sessions ended, their scope
re-audited. Revocation needs no reason and no notice.

## Tier 2 — Investors

**Who:** capital partners under NDA, named by the keeper.

**May see:** sanitized briefs, receipts, roadmap summaries, published
metrics — the story of the work, never the work itself.

**Never sees:** source code, vault bundles, internal docs, unreleased
designs, keeper personal data, anything Tier 1 sees.

**Grant:** NDA signed + the keeper's explicit grant, recorded in the
ledger. **Revoke:** access cut on the keeper's word or when the
relationship ends; materials already shared under NDA stay under NDA,
but no new material flows.

## Tier 3 — Admins / Special-Clearance Employees

**Who:** operators the keeper hires or appoints for specific duties
(support, dispatch ops, community care). Roles, not persons, define the
scope — but the grant is still per person.

**May see:** only the operational tooling their role requires, and only
the user data that role is authorized to touch. Nothing else.

**Never sees:** vault bundles and passphrases; crown jewels; grant
authority itself (admins never grant clearance); other tiers' material;
the keeper's personal data.

**Grant:** the keeper's grant only — attached to the person *and* the
role, recorded in the ledger. It is never bundled with employment by
default and never purchased. **Revoke:** immediate and total the moment
the role ends or the keeper says so: credentials dead, sessions ended,
a handover audit of what they touched.

## The clearance ledger (design)

A keeper-held, append-only record: every grant and revocation, named,
scoped, dated, signed by the keeper's key. It is Tier 0 material. It
exists so that "who can see this?" always has one true answer, and so
that a revocation can be proven complete. The ledger's implementation
(signing, storage, audit) is future work — the requirement is not.

## What this doc does not claim

- No enforcement exists yet: there is no login system, no key server,
  no automated revocation in this repo today. Anyone with the working
  copy has the working copy.
- The vault bundles (`vault/`) are Tier 0 by law; their actual
  protection today is the passphrase + owner-only perms + physical
  control of the drives. That is real, and it is the keeper's hands,
  not this document, that hold it.
- Break-the-code sweep material is public-by-design (that is the point
  of the sweeps); stage *selection* and the unreleased pool are Tier 0.
  See `docs/BREAK_THE_CODE_SWEEPS.md`.
