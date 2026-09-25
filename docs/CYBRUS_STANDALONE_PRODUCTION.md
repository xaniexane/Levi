# Cybrus standalone — production document

**Product:** Cybrus — Security & Identity, standalone customer edition.
**Status:** built and locally tested; NOT released, NOT published.
**Pricing:** UNDECIDED. The provisional tier ladder in this document is
Chauncey's to change. Nothing here is a promise to a customer.
**Release:** no authorization. Local commits only; nothing pushes.

## 1. Product definition

Cybrus is one of the dynasty's standalone products, on the same footing
as DemandPulse: a customer-facing Security & Identity layer anyone can
run on their own machine. Three jobs, one sealed box:

1. **Vault** — encrypted local storage for passwords, tokens, keys.
2. **Generator** — cryptographically strong passwords on demand.
3. **Broker** — third-party account provisioning, external API-key
   storage/retrieval, and OAuth2 authorization-code + PKCE flows through
   platform OAuth layers — an automated vault that can create and fetch
   credentials for third-party sites on the user's behalf, always through
   approval gates and tier quotas.

The vault is local-first: state under `~/.levi/cybrus/` (or `CYBRUS_HOME`),
Fernet-sealed when `cryptography` is present, honestly labeled
`stdlib-fallback` when it is not. The broker prepares and stores; the
operator/browser layer performs live web interaction. The broker never
impersonates a human and never skips an approval gate.

## 2. User onboarding

Entry point: `python -m cybrus quickstart` (master password via explicit
input, `CYBRUS_MASTER_PASSWORD`, or `getpass` — never argv or logs).
It initializes and unlocks the vault, generates a first password, stores
a first credential, verifies the round-trip, and returns a receipt.

Support surface: `python -m cybrus status` (vault health + backend),
`python -m cybrus limits` (policy table + personal usage),
`python -m cybrus broker` (provision/list/keys/oauth commands),
`python -m cybrus sheet` (customer sheet), `python -m cybrus price`
(pricing: currently unset — says so honestly).

Support doctrine: everything reversible, receipts for everything
consequential, and the honest-limits list is part of the product, not a
footnote.

## 3. Packaging and distribution

Distribution: `packaging/cybrus/` — a local-only `cybrus` wheel built
with `pip wheel .`, console entry point `cybrus = "cybrus.__main__:main"`.
Core dependencies are empty; `cryptography` is an optional accelerated
backend. Do NOT publish — the package is deliberately local-only until
Chauncey orders otherwise.

Build validation (before any release conversation): build the wheel in a
clean temporary environment, install it, and run
`python -m cybrus quickstart` + the standalone test suite against the
installed copy.

Gate run 2026-09-22 (BLUE-2 🪖): wheel `cybrus-0.1.0-py3-none-any.whl`
built in a clean temp venv, installed into a fresh venv from the wheel
alone (no repo on `sys.path`). `python -m cybrus quickstart` passed
against the installed copy (stdlib-fallback backend — `cryptography` was
deliberately absent from the fresh env). Standalone suite
(`test_cybrus_standalone.py`, `test_cybrus_rate_limits.py`): 25 passed;
the packaging-manifest test was deselected in the gate run (it reads the
repo tree) and its version-sync assertion was checked instead against the
installed wheel's METADATA — 0.1.0 == `product.PRODUCT_VERSION`.
Nothing published, nothing uploaded — build+install+test only.

## 4. Rate-limit policy (anti-spam)

The broker is automated access to third-party sites. That power gets a
ladder, not a leash:

- **FREE ($0)** — vault + password generation only. Zero automated
  retrieval, zero account creation.
- **STARTER ($6/mo — PROVISIONAL)** — 20 automated retrievals/day,
  5 account creations/day (per-hour ceilings beneath those).
- **PRO ($18/mo — PROVISIONAL)** — 200 automated retrievals/day,
  50 account creations/day.
- **PLATFORM (custom)** — uncapped, still audited.

Mechanical rules:

- Per-action per-hour and per-day sliding windows (OAuth initiation
  tighter per hour than OAuth refresh).
- Burst rule: more than 10 retrievals in 5 minutes triggers a 15-minute
  cooldown plus an audit flag.
- One in-flight OAuth flow per user at a time; the reservation releases
  on completion, abandonment, or initialization failure.
- Every allow, deny, and bypass is audit-logged.
- Account creation is individually human-approved even when quota allows;
  admin bypass covers quotas only, never approval or security gates.
- Chauncey (founder) is quota-exempt; every attempt still logged.
- Tier assignment is a local stub (`rate_limits.set_tier`) with a
  documented billing-entitlement seam — real billing owns the source of
  truth when it exists.

Quotas are enforced inside the broker itself (`broker.py` calls
`rate_limits.check/acquire_flow/release_flow`), so no consumer can
accidentally skip them.

## 5. Pricing decisions — gated on Chauncey

Explicitly unset: the standalone product price, and the final values of
the tier ladder above. DemandPulse's price does not transfer
automatically. Do not quote, publish, or promise any price without his
word.

## 6. Honest limits

- The OAuth engine runs the protocol state machine; the human operator
  completes external logins.
- The vault is as strong as its master password — no backdoor, no
  recovery without it.
- `stdlib-fallback` vaults are labeled; treat them as weaker than
  Fernet-sealed ones.
- Tier assignment is a local stub until billing exists.
- Nothing leaves the machine. That is the point.

## 7. Test surface

`tests/test_cybrus_standalone.py` (product sheet, quickstart lifecycle,
vault store/retrieve/delete, CLI, manifest, broker hookup),
`tests/test_cybrus_rate_limits.py` (hour/day quotas, window reset,
burst cooldown, audit entries, admin bypass, in-flight OAuth, tier
assignment, usage summary, broker wiring). Plus the sibling-owned
`tests/test_cybrus_broker.py`. All must be green before any release
conversation.
