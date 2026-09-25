# Legion — the monetizable bot product

**Canon (Chauncey, 2026-09-18):** *"The monetizable bot product is named
Legion (Legion bot)… one face the customer talks to, the legion
(tailored team of agents) behind it doing the work. 'For we are many.'"*

## The product

- **One face.** Every Legion install presents a single conversational
  face to the customer. The face greets, answers identity questions
  honestly, and routes every intent it can't answer itself to a named
  crew member (`legion/product.py` — `RouterConfig`, `build_router`).
- **The legion behind it.** The tailored crew is assembled from the
  existing agent population: one seat per crew role, resolved through
  the hive adapter (`levi.hive.orchestrate.seats_for`), with each seat
  mapped to an operator through the universal operator registry
  (`levi.operator.registry.resolve_for_seat` — any operator swappable
  into any seat by config). Responsibilities and handoff rules ship
  with the team (`legion/team.py`).
- **White-labeled per business.** Name, tone, greeting, brand colors,
  domain vocabulary — validated, never guessed (`legion/product.py` —
  `WhiteLabel`). The install wears the business's own brand.
- **Specialist add-on packs.** Restaurant, salon, shop, generic:
  domain vocabulary, FAQs, tasks, and escalation rules as data, no
  hardcoded business names (`legion/packs.py`).
- **Tailored team = Site Lift analysis + installed crew.** A Site Lift
  report's failed measured checks map to crew needs; the proposal
  carries the gaps, the unmapped checks (never dropped), the detected
  business type, the suggested pack, and the assembled team
  (`legion/sitelift_link.py`).

## The money shape

Genesis-style: **lifetime one-copy buy**, one price, one business. Add-on
packs at a labeled fraction of the base. Optional care/hosting plans
only if Chauncey wants recurring — nothing recurring is built or quoted
now.

The seam is **paper-only** (`legion/sale.py`):

- Quote via the founder price advisor (`levi.advisor.pricing`) —
  flagship tier, ~30-60% below the giant when a giant price is known,
  lifetime = recommended monthly × 24 months, stated plainly. A quote
  moves nothing.
- Checkout record via the Cybrus money gateway — **PLAN and PREVIEW
  only**. The rail is labeled "paper" (a label, not a rail); authorize
  and execute are never called. The gateway stays fail-closed.
- The 70/30 split is computed as a labeled paper ledger line
  (`levi.income.engine.split_income`) — never recorded income.
- The license is issued **paper-unpaid**, buyer blank until a real
  sale. This seam cannot mark a license paid; only a real
  Chauncey-authorized Cybrus settlement can, and no rail exists for that.

## CLI

`levi legion configure|team|pack|quote` — see `CLI_WIRING_NOTES.md` for
the three minimal hooks in `core/levi/cli/main.py` (sibling-owned;
wired once the sibling merge lands).

## What Legion is NOT (honest limits)

- Not the full LEVI organism. A Legion install is one white-labeled
  bot with a small crew — it doesn't carry LEVI's memory, growth loop,
  cyber suite, or finance brain.
- Not live commerce. Until Chauncey deliberately registers a money
  rail, every price is a quote, every checkout a plan, every license
  unpaid. The repo contains zero payment rails, by design.
- Not a mask. The face never wears another provider's brand and never
  claims to be another company's product (`check_no_mask` runs on the
  face copy at configure time). The business's own white-label brand is
  the only brand it wears.
- The operator registry integration is config-driven: seats resolve to
  operator names from the registry's seat map; the roster adapter
  remains the crew source.
