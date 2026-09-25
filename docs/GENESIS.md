# Genesis package

**Canon (the keeper's word):** a genesis pack is a *fully basic* variant of
the LEVI system — **lifetime, 1-copy buy** (one-time purchase, yours
forever). It ships with a few agents as **renamed / remixed / recycled /
mutated variants — never the raw originals.**

The step-up above genesis is the tailored-edition line: government,
schools, universities, corporate, and tiny businesses each get their own
edition — those live as data manifests in `core/levi/editions/` and are
*referenced* by genesis packs, not duplicated.

## How assembly works

1. **Parts bin** (`core/levi/genesis/parts.py`) — a static catalog of the 11
   capability families from `core/levi/dynasty/wave/` (read-only; genesis
   never edits it). Parsed with `ast`, never imported, so no heavy dynasty
   dependencies load at catalog time.
2. **Forge** (`core/levi/genesis/remix.py`) — forges variants in four modes:
   - `rename` — new name, same capability domain
   - `remix` — new name, traits blended across two crafts
   - `recycle` — same craft, reworked presentation, new name
   - `mutate` — traits recombined across crafts, new name

   Every forge run is **deterministic**: the same (source, mode, seed)
   always forges the same variant. Lineage travels as a sha256 hash of the
   source modules — never as a name.
3. **Assembler** (`core/levi/genesis/assemble.py`) — spec → pack directory:
   `manifest.json` (pack id, variant roster with lineage hashes, license
   terms "lifetime single-copy", build receipt hash-chain), one
   self-describing module per variant, `license.json` (buyer UNASSIGNED),
   `quote.json` (paper price), `install.py` (copies into a target
   LEVI_HOME, verifies the hash-chain first, `--dry-run` supported),
   buyer `README.md`.
4. **License** (`core/levi/genesis/license.py`) — terms as data:
   one-time purchase, 1 copy on machines you own, transferable once with
   the license file, no resale, no redistribution.

## Forge rules (enforced in code, not just documented)

- **No outside brands.** Every forged name and description passes
  `levi.bot.persona.check_no_mask` — a violation raises `ForgeError`.
- **No dynasty-internal IP on user-facing output.** Raw agent proper names,
  Section 0 material, provenance, and playbook references never appear in
  variant names, descriptions, README, docs, or manifests. Forge material
  is generic paraphrase; tests assert the absence of raw names across
  every family × mode × seed combination.
- **Deterministic.** Seeded RNG only; no wall-clock, no uuid in forged
  identities.

## Money (paper mode — standing law)

- Quotes come from the keeper's price advisor (`levi.advisor.pricing`);
  the advised flagship band is quoted as the one-time lifetime price.
- Checkout goes through the Cybrus gateway **only** — and with no payment
  rail registered it returns a paper receipt saying exactly that. Nothing
  is charged, nothing is recorded.
- The 70/30 split is computed with `levi.income.engine.split_income` and
  shown as a projection on the quote. No income is ever recorded here.
- The license buyer field is filled by the sale step, never faked.

## Operator-contract seam

`core/levi/operator/registry.py` is still being built by a sibling worker.
Assembly tries a lazy import and registers each forged variant if present;
otherwise it records the integration as PENDING (`GENESIS_STATUS.md`
holds the exact call). The build never fails on its absence.

## What a genesis pack is NOT (honest limits)

- **Not the full organism.** Variants are remixes — capability cards with
  trait behavior — not live agents with persistent memory, the growth
  loop, the daemon, or the native brain.
- **Not the editions line.** Sector-tailored editions (government, schools,
  universities, corporate, tiny business) are separate manifests in
  `core/levi/editions/`; the genesis README points buyers there.
- **Not a live purchase.** Everything money is paper until the keeper
  registers a real rail with Cybrus and authorizes the sale step.

## CLI

```
levi genesis assemble --spec pack-spec.json [--out packs-root]
levi genesis assemble --spec-json '{"name": "...", "variants": [...]}'
levi genesis list
levi genesis inspect <pack-id-or-dir>
levi genesis parts
```

Spec shape: `{"name": "...", "variants": [{"source": "<family>",
"mode": "rename|remix|recycle|mutate", "seed": <int>}, ...]}`.
The 11 families are the capability sources listed by `levi genesis parts`.
