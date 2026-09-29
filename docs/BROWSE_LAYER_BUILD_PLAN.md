# Browse Layer — Strengthened Build Plan

**Status:** PLAN — Chauncey rules on the design (`docs/BROWSE_LAYER.md`)
before any builder starts. No builder begins until Gate 0→1 is met.
**Lineage:** design `89a6f77c9` (architect 🧶) · hunt notes `be870e9e8`
(🪤) · construction skill `core/levi/skill/browse_skills.py` (10
playbooks, `browse.*`).
**Surgeon's mandate:** deterministic. Any competent agent following
this plan plus the skill produces the same structure. Every judgment
call is a labeled decision gate (DG-N) — never improvised, never
papered over.

## How to read this plan

- **File** — the exact path the builder owns. No substitutes, no
  renames without a recorded ruling.
- **Acceptance criteria** — boolean conditions. Each must be true.
  "Mostly" is not true.
- **Tests** — the owned test file(s); every acceptance criterion has
  at least one test.
- **Verification** — the exact commands the builder runs before
  reporting done.
- **DG-N** — an open decision gate. Park dependent work, escalate,
  do not guess.

Conventions inherited from the skill playbooks: the eight laws
(`browse.eight_laws`), deny-closed default, quality gates
(law→guard→prove, tests mandatory, ruff clean), honest claims
(graded per-mechanism only), file ownership (exclusive), phase gates
(exact booleans). Builders read the skill before the plan.

---

## Phase 1 — Sequential foundation (Builder A, alone)

One builder. The plugin API is the contract everything else signs;
two authors produce two contracts. Builder A owns every file below
and every test file below, exclusively.

### Files and acceptance criteria

**`core/levi/browse/__init__.py`**
- Exposes `BROWSE_VERSION` (semver string, starts `"0.1.0"`),
  `get_registry()`, `list_plugins()`.
- Imports nothing heavy: importing `levi.browse` must not import
  network, crypto, or plugin modules (lazy inside functions).
- Test: import works; version matches `^\d+\.\d+\.\d+$`.

**`core/levi/browse/plugin.py`** — declaration, loading, deny-closed boundary
- `validate_declaration(decl)` refuses (raising a named
  `RegistrationRefused` with reason) on: bad `id` format, duplicate
  `id`, unknown hook name, unknown permission name, unconfirmable
  write op, missing/incomplete who-pays card. Six refusal cases, six
  tests — no warn-and-continue path exists in the code.
- Registry: `register` → `grant(all)` → `load`; `revoke`/`expire`
  unload. Partial grants never partially load.
- Execution boundary: a plugin calling past its facade raises a
  receipted `CapabilityDenied` (who, what, when). The denial is
  recorded, not just raised.
- Fault isolation: one plugin's exception is caught, receipted, the
  plugin marked faulted; the pipeline continues.

**`core/levi/browse/permissions.py`** — keeper-held grant ledger
- Store file is created with mode `0o600`; on open, the mode is
  verified and a wrong mode refuses to operate (fail closed, receipted).
- Grants carry plugin id, capability, scope, expiry timestamp.
- `grant`, `deny`, `revoke`, `expire` each append a receipt
  (timestamp, actor="keeper", action, subject, reason).
- An expired grant behaves as no grant: load refused.
- Consent-ledger inversion: the deception-toward-surveillant policy is
  declared in data (a `declared_deceptions` record visible to the
  user), never a hidden code path.
- The ledger seals at rest via the `cybrus/veil.py` binding (bound,
  never reimplemented): no key material in the browse tree — an
  import-graph test asserts veil is the only crypto source.
- The permissions catalog includes the automation/credential
  permissions: `automation_read`, `automation_act`,
  `credential_generate`, `credential_fill`. Each gets
  grant/deny/revoke/use tests in `tests/test_browse_permissions.py` —
  ungranted use is refused, tested per permission.

**`core/levi/browse/page.py`** — page model
- Fields: url, fetched bytes, extracted text/links/images via stdlib
  `html.parser`, claim-graded metadata attached at extraction time.
- Parsing is deterministic: the same bytes produce the same model,
  byte-for-byte, every run (test with a fixture, twice).
- No network, no JS: the module imports neither `socket` nor anything
  executing script.

**`core/levi/browse/pipeline.py`** — fetch → parse → grade → shield → hooks
- Stage order is fixed and tested with stage spies: any reordering
  fails the test.
- Fail-fast: a failing stage stops the pipeline with a receipted
  failure naming the stage and reason. No best-effort continue.
- Fetch re-checks redirects against declared hosts; a redirect to an
  undeclared host stops the pipeline with a receipted refusal.
- `page_loaded` hooks fire in registration order; one plugin's
  exception fails that plugin only (receipted, marked faulted).

**`core/levi/browse/bundle_card.py`** — who-pays validation
- `validate_card(card)`: `payer` in {user, sponsor, data, funnel},
  `note` non-empty, `not` (honesty footer) non-empty. Anything else
  refuses registration with the named missing piece.
- Called by `plugin.validate_declaration`; never bypassable via a
  flag.

**`core/levi/browse/manifest_guard.py`** — CI guard against narrowing
- Compares a capability contract snapshot against the current
  declarations; fails (non-zero exit, named diff) when permissions,
  interception points, or dynamic behavior narrow without a recorded
  ruling file.
- Proof: a fixture with narrowing and no ruling FAILS the guard; the
  same fixture with a ruling file PASSES. A guard with no failing
  fixture is unproven.

**`scripts/check_no_remote_fetch.py`** — no-remote-fetch lint
- Scans the tree for runtime remote-fetch patterns (remote imports,
  URL fetches of libraries/fonts/assets outside declared plugin
  hosts); fails non-zero naming the file and line.
- Proof: a fixture file with a remote import FAILS; the clean tree
  PASSES. Stdlib-only is machine-checked, not promised.

### Tests (all owned by Builder A)

- `tests/test_browse_plugin.py` — 6 registration refusals, load/unload
  lifecycle, facade denial receipted, fault isolation.
- `tests/test_browse_permissions.py` — 0600 enforcement, grant/deny/
  revoke/expiry, receipt completeness, expired-grant refusal.
- `tests/test_browse_pipeline.py` — stage order with spies, fail-fast,
  redirect re-check, one-plugin-fails isolation, determinism (same
  bytes → same model, twice).
- `tests/test_browse_bundle_card.py` — card validation cases, missing
  piece named in the refusal.
- `tests/test_browse_manifest_guard.py` — narrowing-without-ruling
  fails, narrowing-with-ruling passes. *(Strengthening addition: the
  design listed 4 test files for 7 modules; the guard needs its own
  proof.)*

### Verification (exact, before reporting done)

```
pytest tests/test_browse_plugin.py tests/test_browse_permissions.py \
  tests/test_browse_pipeline.py tests/test_browse_bundle_card.py \
  tests/test_browse_manifest_guard.py
ruff check core/levi/browse/__init__.py core/levi/browse/plugin.py \
  core/levi/browse/permissions.py core/levi/browse/page.py \
  core/levi/browse/pipeline.py core/levi/browse/bundle_card.py \
  core/levi/browse/manifest_guard.py scripts/check_no_remote_fetch.py
ruff format --check [same files]
python3 scripts/check_no_remote_fetch.py
python3 -m core.levi.browse.manifest_guard  # or its documented entry point
```

All green, real counts in the receipt. Then Builder A declares the
plugin API **frozen** in the phase-1 receipt.

### Exit: Gate 1→2

The eight booleans in `browse.phase_gates` (Gate 1→2 section). Every
one true, or phase 1 is not done. The frozen API declaration is the
last line of the receipt.

---

## Phase 2 — Parallel (Builders B, C, D, E)

Starts only when Gate 1→2 is fully true. Builder A's API is frozen;
API change requests go through a recorded ruling, never a commit.
Exclusive ownership per the map — no two builders touch the same path.

### Builder B — privacy

**`core/levi/browse/shields.py`**
- Local tracker/ad block lists, versioned (list name + version in
  every receipt). `apply(page)` returns what matched AND what didn't
  (law 7: no simulated success).
- Permission-guard policy: camera/mic/WebRTC prompt shielding toward
  pages; every shielding action declared to the user in the consent
  ledger (law 2 inversion).
- A list that fails to load fails loudly — never silently browsing
  unshielded.
- Tests (`tests/test_browse_shields.py`): match + non-match reporting,
  version stamping, unload-failure loudness, declared-deception
  records visible.

**`core/levi/browse/cookies.py`**
- Tab and global scopes; create/edit/delete; bulk actions with undo;
  import/export in JSON, Netscape, and header-string formats (fixture
  round-trips for all three); reusable profiles stored locally.
- Export is a write op: keeper confirmation required, every time.
- The cookie-sharing warning is structural: the export receipt states
  "cookie profiles are sessions — sharing a profile can share your
  logins." Not a tooltip, not a comment — in the receipt.
- Tests (`tests/test_browse_cookies.py`): scope isolation, bulk+undo,
  all three import/export round-trips, export-refused-without-
  confirmation, warning present in the export receipt.

**`core/levi/browse/attrib.py`**
- X-Posed-pattern attribution cards from the session's own data only.
  No independent geolocation — refused pattern, not deferred.
- Every signal claim-graded via `signals/claim_grade.py`; INFERRED
  signals render the "signal, not verdict" caveat structurally.
- Tests (`tests/test_browse_attrib.py`): grades attached, caveat
  present on INFERRED, no external lookup performed (assert no socket
  use via the facade boundary).

**`core/levi/browse/sessions.py`** — epoch-ratcheted session option
- Sessions for the privacy pipeline with per-session forward
  secrecy, bound to `cybrus/veil.py` (bound, never reimplemented):
  session keys rotate per epoch; rotation destroys old epochs
  (removed from the store, local copies zeroized — mirroring veil's
  honest bounds, which are restated in the module docstring, not
  improved upon).
- The browse layer holds no session key material in cleartext; sealed
  epoch keys only, owner-only store.
- A session created without the veil binding available fails closed
  with a receipted refusal — never a downgrade to unratcheted
  sessions without a recorded ruling.
- Tests (`tests/test_browse_sessions.py`): rotate-then-read-old-epoch
  fails (forward secrecy), sealed-at-rest assertion, no-cleartext-
  key-material scan of the store dir, unavailable-binding refusal.

### Builder C — vault + tools + credential broker

**`core/levi/browse/vault.py`**
- Thin binding to `cybrus/veil` (AES-256-GCM + scrypt + epoch
  ratchet). The crypto lives in veil; this module binds it. Any
  duplicated crypto primitive is a defect — grep must show zero.
- Seal/unseal report actual outcomes (law 7).
- Tests (`tests/test_browse_vault.py`): seal→unseal round-trip,
  failure reported honestly, no crypto reimplementation (import graph
  assertion: veil is the only crypto source).

**`core/levi/browse/credentials.py`** — credential broker binding
- **Generate:** via `cybrus/vault.py::generate_password` (stdlib
  `secrets` CSPRNG, minimum length 12, returned once, never logged).
  A second generator in the browse tree is a defect.
- **Store:** veil-encrypted, keeper-held keys. The module holds no
  key material; it calls the binding.
- **Retrieve:** autofill through the plugin facade. The secret
  travels facade-to-field only — never through plans, previews,
  receipts, or logs. The receipt records *that a fill happened*,
  never the secret (assertion on receipt contents in tests).
- **Bloodline metering:** the generation path calls
  `cybrus/broker_meter.py::entitlement_check` (read-only, never
  consumes quota) before minting. No entitlement → no mint,
  receipted refusal naming the missing entitlement. Fulfillment
  records meter usage; events audit-logged metadata-only. No second
  metering implementation in the browse tree — bound, not rebuilt.
- **Boundary:** `cybrus/broker.py` owns the third-party credential
  lifecycle (provisioning records, OAuth2 state machine, approval
  gates). This module owns the in-layer surface only. They meet at
  `credential_fill` and nowhere else.
- **Claims:** crown-jewels rule (law 11) — no blanket claim on the
  broker, ever; per-mechanism graded claims only; the broker as a
  whole stays UNVERIFIED until a real audit names it.
- Tests (`tests/test_browse_credentials.py`): generate→store→fill
  round-trip, secret-absent-from-receipt assertion,
  entitlement-refused-before-mint (stub meter), no-second-generator
  import assertion, no blanket claim in the module (grep).

**`core/levi/browse/tools/qr.py`** — QR generate/scan as a plugin.
Generation stdlib-only; scan declares `use_camera_frame` and is
honest about needing a camera frame source (no fake scan).
**`core/levi/browse/tools/reader.py`** — clean text extraction
(reader mode) as a plugin, deterministic on fixtures.
**`core/levi/browse/tools/capture.py`** — page capture sealed into a
custody exhibit (`custody/exhibit.py`); the honesty footer
("INTEGRITY IS NOT TRUTH") renders on the card.
**`core/levi/browse/tools/translate.py`** — translation plugin slot.
Offline engine is UNVERIFIED-until-proven: honest "not wired" states,
never fake fluency. A translate call with no engine returns a
receipted UNVERIFIED refusal, not lorem ipsum.
- Each tool ships a valid `BROWSE_PLUGIN` declaration (validated by
  Builder A's registration path — reuse, don't reimplement).
- Tests (`tests/test_browse_tools.py`): one per tool — declaration
  validates, happy path works, dishonest path refused (scan without
  frame source, translate without engine, capture without exhibit
  seal all fail honestly).

### Builder D — sync design

**`core/levi/browse/sync.py`**
- Local-first: bookmarks/history/tabs sync across the keeper's own
  devices with no cloud by default.
- Sovereign-path-default: where a cloud path exists, it is the
  opt-in footnote; the no-cloud path is the default. The default is
  asserted in a test, not documented in a comment.
- Shared-index lookups use hash-prefix (k-anonymous) private lookup:
  the server returns candidates, the client filters locally. The
  exact query never leaves the device (test with a fake server
  asserting the received prefix length).
- The relay is a **spec**, not a server: no network listener is
  built in this phase. Building a server here is scope creep.
- Tests (`tests/test_browse_sync.py`): default-path assertion,
  hash-prefix privacy assertion, local round-trip, relay-spec exists
  and contains no listen/bind code.

### Builder E — automation

**`core/levi/browse/agent.py`** — the agent surface
- Automated browsing, extraction, and form-filling on the keeper's
  behalf, through the facade — never around it.
- **Law 9 protocol on every consequential act:**
  Plan→Preview→Permission→Execute→Verify→Receipt. Each step
  evidenced; a step with no evidence is a step that didn't happen.
  The plan is data (action class, target, parameters); the preview
  renders what *would* happen from the plan; verification reads the
  outcome back and compares it to the plan.
- **Law 10 action classes:** `read_page` / `extract_structured`
  (read-only, `automation_read`, no per-act confirmation);
  `fill_form` / `submit_form` / `navigate` (acting,
  `automation_act`, confirmation per act); `credential_fill`
  (needs `credential_fill`, confirmation per act; the secret never
  touches plan, preview, or receipt).
- **DG-8 default:** acting classes ship as refused-by-default stubs
  raising a named `ActingNotEnabled` that names DG-8 in the refusal.
  The confirmation machinery is fully implemented and tested;
  enablement waits on Chauncey's ruling. No acting capability is
  reachable without it.
- **Local-only (seated-AI ruling):** stdlib heuristics now; the
  native-brain slot is declared as an UNVERIFIED-until-proven
  interface with honest "no brain wired" states. No cloud models —
  a network call to a model provider from this module is a law-3
  violation, not a feature flag.
- **No ambient authority:** there is no "act on my behalf generally"
  grant. Confirmation is per act, per class, at act time.
- **Pipeline relationship:** the agent adds no pipeline stages. It
  invokes facade operations between pipeline runs; a fresh run
  re-fetches, re-grades, and re-shields after every act.
- Tests (`tests/test_browse_agent.py`): read-only classes run the
  full six-step protocol with receipts; acting classes refuse naming
  DG-8; confirmation-per-act enforced (an act without confirmation
  is refused); no-brain state is honest (UNVERIFIED, never fake
  cognition); no network to model providers (facade boundary
  assertion).

### Integration pass (after B, C, D, E are independently green)

One pass, owned by the coordinator (not a builder lane):
pipeline + one plugin from each builder's surface + a read-only
agent run, end to end, with a fixture page. Verifies the frozen API
held: no builder worked around it. If the integration fails, the
failing lane reopens — the API does not bend to fit.

### Verification (per builder, exact)

```
pytest tests/test_browse_<lane>.py   # the builder's owned files
ruff check <owned files> && ruff format --check <owned files>
```

Then the coordinator runs the full browse suite plus the integration
pass. Exit: Gate 2→3 — all booleans true, including the
honest-claims read (grep for blanket secure/private/anonymous) and
Chauncey's explicit phase-3 order (DG-3).

---

## Phase 3 — Native shell (later, separate toolchain)

**Entry conditions:** Gate 2→3 fully true AND Chauncey's explicit
order (DG-3). Green tests do not imply permission.

**Scope:** Android WebView shell in `apps/levi-android` binding the
Python core. The shell is a binding, not a rewrite: the plugin API
(§5 of the design) and pipeline order are reused unchanged. Plugins
observe through the facade — even in the shell, no plugin gets raw
WebView APIs. The credential broker's Android autofill-service
binding lands here (facade autofill in phase 2 was the Python-core
surface; the OS autofill service is the native surface) — still
facade-to-field, still no secret in plans, previews, or receipts.

**Proof (different toolchain, different proof):**
- `./gradlew :app:assembleDebug` succeeds.
- On-device verification: the shell binds the real core against a
  fixture page; the receipt names the device and build.
- Every security-relevant claim re-graded; anything unaudited stays
  UNVERIFIED in the surface. No blanket claims, per
  `browse.honest_claims`.

**Non-scope:** no engine work, no JS bridge beyond the facade, no
Tor client as a claimed virtue (declared slot only, per the design's
teardown disposition).

---

## Decision gates (DG-1…DG-7)

Full text in `browse.decision_gates`. Restated here with what is
parked meanwhile:

- **DG-1 thin/full (Chauncey, PENDING):** build the thin layer exactly
  as phased. No shell-shaped "preparation."
- **DG-2 distribution (Chauncey, PENDING):** side-load only. No
  catalog infrastructure.
- **DG-3 phase-3 timing (Chauncey, PENDING):** no phase-3 work until
  ruled AND Gate 2→3 green.
- **DG-4 name (Chauncey, PENDING):** `browse/` namespace, "browse
  layer" in prose. No invented product names.
- **DG-5 registry wiring (coordinator):** `BROWSE_SKILLS` works
  standalone via direct import; the `SkillRegistry` edit merges after
  the shared index settles.
- **DG-6 primitives adopt/set-aside (Chauncey, PENDING):** if
  set-aside, the seal/grade steps are re-specified — laws 4 and 5
  still need implementations.
- **DG-7 drift watch (ongoing):** thin-layer insufficiency is a DG-1
  re-entry, never a quiet expansion.
- **DG-8 automation acting scope (Chauncey, PENDING):** read-only
  automation first, or acting-on-behalf from day one? Until ruled:
  Builder E implements the confirmation machinery and the read-only
  classes; acting classes exist as refused-by-default stubs naming
  DG-8. No acting capability ships enabled without his word.

## Determinism statement

A reviewer with this plan, the skill, and the design reaches the
same verdicts as the builders: same files, same acceptance
criteria, same gates, same parked gates. Where the plan is silent,
the skill's decision-gates playbook governs: mark it DG-N and
escalate. Silence is never permission.
