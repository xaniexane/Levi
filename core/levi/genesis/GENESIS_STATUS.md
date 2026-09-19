# Genesis integration status

## Operator-contract seam — LANDED (2026-09-18)

`core/levi/genesis/operators.py` registers every forged variant as a
real ``levi.operator`` Operator (``GenesisVariantOperator``,
kind ``si``) at assembly time via:

```python
from levi.genesis import operators as gen_operators
for v in roster:  # forged variant dicts from levi.genesis.remix
    gen_operators.register_variant(v)
```

- Registration validates the contract (no-mask law enforced at
  register time); re-assembling a pack replaces the earlier entry.
- Turns are served by a backing operator from the default registry
  (default: the local rules engine — teachers stay opt-in per the
  teacher doctrine). Results are stamped with the variant's name.
- `get_variant_registry()` / `resolve_variant(variant_id)` expose the
  process-wide variant registry for seats.
- Dynasty eyes-only upheld: lineage is hashes only, never names.

## Sector editions — referenced, not duplicated

`core/levi/editions/` holds the 11 sector-edition data manifests
(government, schools, universities, corporate, tiny businesses, ...).
Genesis packs reference that path in the buyer README; genesis does not
duplicate edition data.

## Money — paper mode (standing law)

- Quote: `levi.advisor.pricing.advise_price` (flagship tier, volume strategy).
- Checkout: Cybrus gateway only; `levi.cybrus.money` raises/returns
  no-rail → paper receipt. No income is ever recorded here.
- 70/30 split: computed with `levi.income.engine.split_income` as a
  projection on the quote.
