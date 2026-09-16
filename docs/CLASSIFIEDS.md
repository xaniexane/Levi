# CLASSIFIEDS — Trust-Graph Classifieds

Meta Marketplace's trust story is "trust our graph" — a graph you can't
inspect, scored by an algorithm you can't audit, on a platform that
monetizes every listing with ads and paid boosting. LEVI Classifieds is
the remix: trust you can audit, listings you can take with you, and no
ad layer at all.

## How it works

**Listings** live in `~/.levi/classifieds/listings.json`. Post, browse
(newest first, substring search), mark sold/withdrawn.

**Trust** comes from a contacts file *you* curate
(`~/.levi/classifieds/contacts.json`): your connections and who they
vouch for, with weights you set (0–1). The score formula is published
and every score ships with its explanation:

```
trust(lister) = Σ min(my_vouch[m], their_vouch[m] for lister) / my_connection_count
```

`python -m levi.classifieds trust cara` prints the score, the formula
with real numbers, and every mutual counted. Unknown listers score 0.0
and say so — no fake confidence.

**Portability**: `export` bundles listings plus HMAC-signed trust
attestations into one JSON file (`levi_classifieds_v1`). `import`
brings a bundle into another machine; trust is *recomputed against the
importer's own contacts* (honest: trust is always relative to your
graph). Attestation HMACs prove the bundle wasn't altered after export
— verifiable by the exporter, integrity not identity theater.

## Usage

```bash
python -m levi.classifieds contacts-init --me chauncey --contact ana --contact bob
python -m levi.classifieds vouch ana --for cara --weight 1.0
python -m levi.classifieds add "Road bike" --price '$200' --category sports --lister cara
python -m levi.classifieds browse --query bike
python -m levi.classifieds trust cara
python -m levi.classifieds export --out bundle.json
python -m levi.classifieds import bundle.json
```

## What the giant refuses

- Auditable trust (their formula is the moat; ours is the documentation).
- Portable listings (lock-in is their business model).
- A board with no ad layer and no boosting (their revenue model).

## Open gaps / honesty notes

- **Sybil limit**: the graph trusts your curation. If you vouch for
  everyone, scores mean nothing — the formula is transparent so this
  limit is visible, not hidden.
- No dispute resolution, escrow, or payments — deliberately out of
  scope; this is a trust-signaling board, not a marketplace platform.
- Attestation HMACs verify only against the exporter's own key; a
  recipient can't cryptographically verify someone else's attestations
  (stated in the bundle itself).
