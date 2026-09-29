# LEVI Browse Layer — Architecture

**Status:** DESIGN — Chauncey rules before any builder starts. No code ships from this doc.
**Date:** 2026-09-29 · **Architect glyph:** 🧶

## 1. What the layer is

A LEVI-native browsing layer: powered secure browsing with plugins and
extensions, built the LEVI way — stdlib-only, local-first, deny-closed.

Concretely it is three things:

1. **A plugin/extension host** (`core/levi/browse/`) — page tools, privacy
   tools, and utilities as declared, permissioned, keeper-granted plugins.
2. **A privacy pipeline** — fetch → parse → grade → shield, with tracker
   blocking, cookie control, and claim-graded page metadata.
3. **A vault binding** — the keeper-held crypto already in `cybrus/veil`
   (AES-256-GCM + scrypt + epoch ratchet) exposed as the layer's safe
   locker. Not reimplemented. Bound, not rebuilt.

## 2. What the layer is NOT

- **Not a rendering engine.** No Gecko rebuild, no Chromium fork, no JS
  engine. The additions-not-rebuilds law holds: on Android the layer is a
  secure shell over the system WebView; the Python core underneath is
  engine-independent and runs headless.
- **Not a data collector.** No telemetry, no analytics, no account
  required. Sync, where it exists, is local-first with an optional
  self-hosted relay the keeper controls.
- **Not "a secure browser" as a marketing claim.** Security is claimed
  only per-mechanism, each claim graded (see §12). Anything unproven is
  labeled UNVERIFIED, structurally.

## 3. Declared laws (law → guard → prove)

1. **Deny-closed plugins.** A plugin can do exactly what it declared and
   was granted. Undeclared capability use is refused at the boundary, not
   logged-and-allowed.
2. **Keeper-held permissions.** Grants live in the owner-only 0600 store,
   per-plugin, per-capability, with scope and expiry. Every grant, deny,
   and expiry is receipted. The ledger may deceive the *surveillant*
   (spoof or suppress a permission prompt toward a tracker) — but that
   deception is declared to the USER, never hidden from them
   (consent-ledger inversion).
3. **No silent network.** A plugin with network capability declares its
   hosts; anything else is refused. The pipeline never phones home.
4. **Integrity is not truth.** Page captures are sealed as custody
   exhibits (`custody/exhibit.py`); the exhibit proves the bytes didn't
   change, never that the page told the truth.
5. **Signal, not verdict.** All heuristic metadata (tracker verdicts,
   attribution signals) is claim-graded (`signals/claim_grade.py`):
   OBSERVED / INFERRED / UNVERIFIED. Grades never self-upgrade.
6. **Nothing leaves the device ungranted.** Cookies, vault contents,
   history, and profiles stay local unless the keeper explicitly grants an
   export — which is itself a write op requiring confirmation.
7. **No simulated success.** A shield that didn't apply says so. A vault
   that didn't seal says so. Mirrors the connector honesty contract.
8. **No remote fetch at runtime.** Committed code never pulls a library,
   font, or asset from a remote host at runtime — everything vendored or
   stdlib. Machine-checkable via lint (Decentraleyes' surviving rule:
   a dependency fetched from someone else's server is a phone call home).
9. **Consequential acts follow the organism's protocol.**
   Plan→Preview→Permission→Execute→Verify→Receipt on every
   consequential act — anything that changes state on a site, spends
   keeper authority, or moves credentials. A step with no evidence is
   a step that didn't happen.
10. **Acting needs a named grant — never ambient authority.**
    Read-only automation never implies acting authority. Acting
    capability is granted per action class
    (`read_page`/`extract_structured` read-only;
    `fill_form`/`submit_form`/`navigate`/`credential_fill` acting),
    each a separate keeper decision, confirmation per act. Acting
    classes ship refused-by-default (DG-8) until Chauncey rules.
11. **The credential store is the crown jewels.** The credential
    broker generates (via `cybrus/vault.py::generate_password`),
    stores (veil-encrypted, keeper-held), and retrieves (facade
    autofill) site/app credentials. Graded per-mechanism claims
    only — no blanket "secure" until a real audit. Unlimited
    generation is a founder ability per the 2026-09-27 bloodline
    law; other builds get metering hooks bound to
    `cybrus/broker_meter.py`, not the full tap.

## 4. Module map — `core/levi/browse/`

| Module | One-line responsibility |
|---|---|
| `browse/__init__.py` | Public surface: version, registry accessors, `BROWSE_VERSION`. |
| `browse/plugin.py` | Plugin declaration, loading, and the deny-closed execution boundary. |
| `browse/permissions.py` | Keeper-held grant ledger (0600 store): per-plugin, per-capability, scope + expiry, revocable, receipted; consent-ledger inversion declared here. |
| `browse/bundle_card.py` | Who-pays card: every plugin/bundle declares who pays for it (user, sponsor, data, funnel) plus a honesty footer stating what it does NOT do and cannot prove; validated at registration, missing card = refused. |
| `browse/manifest_guard.py` | CI guard: fails when a capability's declared contract narrows (permissions, interception points, dynamic behavior) without a recorded ruling — narrowing is an attributed event, never a silent deprecation (Manifest-V3 lesson). |
| `browse/page.py` | Page model: URL, fetched bytes, extracted text/links/images via stdlib `html.parser`; claim-graded metadata attached. |
| `browse/pipeline.py` | fetch → parse → grade → shield → plugin-hooks, in that order, fail-fast. |
| `browse/shields.py` | Tracker/ad block lists (local lists, versioned), permission-guard policy (camera/mic/WebRTC prompt shielding), declared-deception policy toward surveillants. |
| `browse/cookies.py` | Cookie jar: tab and global scopes, create/edit/delete, bulk actions with undo, import/export (JSON, Netscape, header-string), reusable profiles stored locally. |
| `browse/attrib.py` | X-Posed-pattern attribution cards: account/page metadata from the session's own data only — no independent geolocation; every signal claim-graded. |
| `browse/agent.py` | Agent surface (phase 2, Builder E): automated browsing, extraction, and form-filling on the keeper's behalf. Law 9 protocol on every consequential act; law 10 action classes; stdlib heuristics now, native-brain slot UNVERIFIED-until-proven, no cloud models ever. |
| `browse/credentials.py` | Credential broker binding (phase 2, Builder C): generate via `cybrus/vault.py::generate_password`, store veil-encrypted, retrieve via facade autofill (phase 2) / Android autofill-service binding (phase 3). Bloodline metering bound to `cybrus/broker_meter.py`. |
| `browse/sessions.py` | Epoch-ratcheted session option for the privacy pipeline (phase 2, Builder B): per-session forward secrecy bound to `cybrus/veil.py` — rotation destroys old epochs. |
| `browse/vault.py` | Safe-locker binding to `cybrus/veil` crypto. Thin binding module; the crypto lives in veil and is not duplicated. |
| `browse/tools/qr.py` | QR generate/scan as a plugin (stdlib-only generation; scan is honest about needing a camera frame source). |
| `browse/tools/reader.py` | Clean text extraction (reader mode) as a plugin. |
| `browse/tools/capture.py` | Page screenshot/capture sealed into a custody exhibit as a plugin. |
| `browse/tools/translate.py` | Translation plugin; offline engine is a declared UNVERIFIED-until-proven slot — honest "not wired" states, never fake fluency. |
| `browse/sync.py` | Bookmark/history/tab sync design: local-first, optional self-hosted relay; nothing cloud by default. **Sovereign-path-default:** where two sync paths exist, the no-cloud path is the default and the cloud path is the opt-in footnote — never the reverse. Shared-index lookups use hash-prefix (k-anonymous) private lookup: the server returns candidates, the client filters locally. |
| `browse/plugins/` | Directory where browse plugins live (each a module with a `BROWSE_PLUGIN` declaration). |

Each module ships a `MANIFEST_ENTRY` dict for mechanical merge into
`interop/manifest.py` once the shared index settles (pattern from
pack-to-the-brim runs 30/31).

## 5. Plugin / extension API

A plugin is a Python module under `core/levi/browse/plugins/` (or the
keeper's plugin dir) containing a `BROWSE_PLUGIN` declaration:

```python
BROWSE_PLUGIN = {
    "id": "reader",
    "display_name": "Reader",
    "version": "1.0.0",
    "hooks": ("page_loaded",),          # pipeline hook points it wants
    "permissions": ("read_page_text",), # named capabilities, nothing else
    "write_ops": (),                    # write ops need keeper confirmation
    "who_pays": {"payer": "user",       # required card: user | sponsor |
                 "note": "..."},        # data | funnel — plus a honesty
                                        # footer of what it does NOT do
}
```

**Registration** validates the declaration end to end: every permission
named must exist in the catalog, every write op must be confirmable, and
the who-pays card must be present and complete. A missing or incomplete
card refuses registration — the difference between generosity and
theater is machine-checked.

**Loading.** `browse/plugin.py` keeps the registry. A plugin loads only
after the keeper grants every permission it declares. Grant is
per-plugin, per-capability. No grant, no load — deny-closed.

**Sandbox.** Plugins never get raw stdlib. Each plugin executes against a
capability-limited facade: `page.text()`, `page.links()`, `cookies.read()`,
etc. — exactly the capabilities granted, nothing more. `socket`,
`subprocess`, and file writes are absent from the facade unless the
matching permission was granted AND the keeper confirmed. A plugin that
reaches past its facade fails closed with a receipted denial.

**Write ops.** Any hook that changes state (write cookies, seal to vault,
export a profile) is a write op: it requires an explicit keeper
confirmation at call time, mirroring the connector contract
(`requires_confirmation`, no per-feature override).

**Permissions catalog (initial, deny-closed):**
`read_page_text`, `read_page_links`, `read_page_images`,
`read_cookies`, `write_cookies`, `network_fetch` (declared hosts only),
`vault_seal`, `vault_read`, `export_data`, `use_camera_frame`,
`automation_read`, `automation_act`, `credential_generate`,
`credential_fill`.

## 5b. Agent action classes

The agent surface acts through the facade — never around it. Classes:

- `read_page`, `extract_structured` — read-only; covered by
  `automation_read`, no per-act confirmation.
- `fill_form`, `submit_form`, `navigate` — acting; need
  `automation_act`, confirmation per act.
- `credential_fill` — needs `credential_fill`, confirmation per act;
  the secret never touches the plan, preview, or receipt.

Acting classes ship as refused-by-default stubs naming DG-8 until
Chauncey rules read-only-first vs acting-from-day-one.

## 6. Page pipeline

```
fetch (declared hosts only)
  → parse (stdlib html.parser; no JS execution, ever)
  → grade (claim cards on extracted metadata: OBSERVED/INFERRED/UNVERIFIED)
  → shield (block lists applied; what didn't apply is reported)
  → plugin hooks (page_loaded, in registration order; one plugin's
     exception fails that plugin only, never the page)
```

No JavaScript execution in the Python core — the parse step is static.
Dynamic pages are the WebView shell's job (phase 3), and even there,
plugins observe through the facade.

## 7. Teardown lineage — what was taken, what was refused

Full hunt record: `docs/BROWSER_LAYER_BUILD_NOTES.md` (commit
`be870e9e8`) plus 5 ArchiveRecords under research slug
`browser-hunt-20260929` (Permission Guard, signal-not-verdict, the MV3
platform-API lesson, SponsorBlock crowd labor, Decentraleyes honest
sunset). Disposition of each item, decided here:

**Already implemented — adopted as layer primitives (not rebuilt):**
- Evidence exhibits (`core/levi/custody/exhibit.py`) — page captures seal
  here; the pipeline proves custody integrity, never truth.
- Claim grading (`core/levi/signals/claim_grade.py`) — every heuristic
  signal in the layer carries a grade; INFERRED always renders its
  "signal, not verdict" caveat structurally.

**Adopted into this design:**
- *Who-pays card* → required `who_pays` field on every `BROWSE_PLUGIN`
  declaration (§5), validated by `browse/bundle_card.py` at registration.
- *Manifest-diff guard* → `browse/manifest_guard.py`, phase-1 CI gate
  (Builder A).
- *Hash-prefix private lookup* → `browse/sync.py` shared-index lookups
  (k-anonymous; server never learns the exact query).
- *No-remote-fetch lint* → law 8 (§3), machine-checkable build gate
  (Builder A).
- *Consent ledger* → `browse/permissions.py` (scope + expiry + receipts)
  with the Permission-Guard inversion declared in `browse/shields.py`.
- *Sovereign-path-default sync* → `browse/sync.py` default rule.

**Set aside (noted, not built):** a standalone `levi.economics` shelf
for who-pays cards beyond the browser (future, out of scope); a
community-cache equivalent of X-Posed's 2.5M-profile index (opt-in only,
and only if the keeper ever wants it — not designed here).

**Cybrus lineage — the vault comes in heavy (taken, bound, never
rebuilt):**

- `cybrus/broker.py` — third-party credential provisioning records,
  external API-key records, OAuth2 state machine, approval-gated,
  metadata-only audit. Taken as the credential *lifecycle* owner; the
  browse broker (`browse/credentials.py`) owns only the in-layer
  surface (generate/store/autofill). The agent fills what the keeper
  confirmed; the broker owns the lifecycle. They meet at
  `credential_fill` and nowhere else.
- `cybrus/broker_founder.py` — founder-edition live provisioning
  (L1–L4: secrets-sealed, gate-every-step, terms-are-human,
  no-identity-documents). The browse layer does not drive signups;
  live provisioning stays the cybrus operator channel's job.
- `cybrus/broker_meter.py` — bloodline metering hooks (M1–M5:
  no-self-mint, founder-fulfill, metered, entitlement-before-use,
  audit). The browse broker's generation path calls
  `entitlement_check` before minting; limited instances file tickets,
  the founder fulfills. Bound, not reimplemented — a second metering
  implementation in the browse tree is a defect.
- `cybrus/vault.py::generate_password` — stdlib `secrets` CSPRNG,
  minimum length 12, returned once, never logged. The broker's
  generator. A second generator in the browse tree is a defect.
- `cybrus/veil.py` — AES-256-GCM (stdlib fallback honestly labeled),
  scrypt KDF, keeper-held keys, per-conversation epoch ratchet with
  rotation destroying old epochs. The permission ledger
  (`browse/permissions.py`) seals at rest through this binding; the
  credential store is veil-encrypted; `browse/sessions.py` offers
  epoch-ratcheted sessions to the privacy pipeline. The browse layer
  holds no key material, ever.
- **Refused:** any crypto reimplementation in `core/levi/browse/`;
  any key material outside the keeper's veil store; any metering
  logic not delegated to `broker_meter.py`.

From the specimens themselves:

- **Omni Browser (18 tools):** taken — the *shape* of honest utilities as
  first-class tools (QR, reader, capture, vault, shields). Refused — the
  engine rebuild, the bundled Tor client as a claim (Tor needs its own
  audit; we declare the slot, not the virtue), "100% on-device ML" as a
  marketing line (our translate slot is honestly UNVERIFIED until proven).
- **X-Posed:** taken — "signal, not verdict" as a structural product
  rule (already built as `signals/claim_grade.py`); the hover-dossier
  evidence card (already built as `custody/exhibit.py`: integrity, not
  truth). Refused — independent geolocation (we use only what the
  session's own data attributes); the 2.5M-profile community cache as a
  default-on (ours is opt-in, keeper-controlled, local-first).
- **Cookie-Editor:** taken — tab/global scopes, import/export formats
  (JSON/Netscape/header-string), reusable local profiles, bulk actions
  with undo. Refused — cloud sync as anything but self-hosted and
  optional. Bright line, kept from the original's own warning: **cookie
  profiles are sessions — sharing a profile can share your logins.**
  Export is a write op with confirmation, and the warning is structural,
  not a tooltip.

## 8. What already exists — do not duplicate

- `weblayer/` — Fireworks-canvas hotspots. Name taken; unrelated. New
  namespace is `browse/`.
- `plugins/` (connectors) — third-party *account* connectors with the
  honesty contract. Browse plugins are a different surface (in-layer
  capabilities, not accounts); the write-confirmation pattern is reused,
  the registry is separate.
- `cybrus/veil.py` — AES-256-GCM + scrypt + epoch-ratchet, keeper-held
  keys. `browse/vault.py` binds it; never reimplements it.
- `custody/exhibit.py`, `signals/claim_grade.py` — built by the hunt run;
  the pipeline consumes them.
- `cybrus/broker.py`, `cybrus/broker_founder.py`,
  `cybrus/broker_meter.py` — the credential broker lineage. The
  browse broker binds it (lifecycle, approval gates, bloodline
  metering); it does not duplicate it.
- `cybrus/vault.py::generate_password` — the CSPRNG password
  generator the browse broker calls. No second generator.
- `cybrus/veil.py` — the crypto foundation: sealed permission ledger,
  veil-encrypted credential store, epoch-ratcheted sessions. Bound,
  never reimplemented.
- `honestsearch/` — local index + ranking; becomes a *consumer* plugin of
  the browse layer later, not part of it.
- `clearnet/`, `pwa/`, `videotex/`, `teletext/` — adjacent, not
  overlapping.

## 9. File ownership map (parallel phase)

| Builder | Owns (exclusive) | Tests |
|---|---|---|
| A — foundation | `browse/__init__.py`, `browse/plugin.py`, `browse/permissions.py`, `browse/page.py`, `browse/pipeline.py`, `browse/bundle_card.py`, `browse/manifest_guard.py`, no-remote-fetch lint gate | `tests/test_browse_plugin.py`, `tests/test_browse_permissions.py`, `tests/test_browse_pipeline.py`, `tests/test_browse_bundle_card.py` |
| B — privacy | `browse/shields.py`, `browse/cookies.py`, `browse/attrib.py`, `browse/sessions.py` | `tests/test_browse_shields.py`, `tests/test_browse_cookies.py`, `tests/test_browse_attrib.py`, `tests/test_browse_sessions.py` |
| C — vault+tools+credentials | `browse/vault.py`, `browse/credentials.py`, `browse/tools/*.py` | `tests/test_browse_vault.py`, `tests/test_browse_credentials.py`, `tests/test_browse_tools.py` |
| D — sync+shell | `browse/sync.py`, Android shell binding spec, `apps/levi-android` browse shell | `tests/test_browse_sync.py`, `./gradlew :app:assembleDebug` |
| E — automation | `browse/agent.py` | `tests/test_browse_agent.py` |

Rules of the road: exclusive file ownership (no two builders touch the
same path); temp-index commits with glyph trailers; each module ships
`MANIFEST_ENTRY`; manifest/warehouse wiring merges mechanically after the
index settles — never force it during a hot window.

## 10. Phased plan

- **Phase 0 — design (this doc).** Done. Chauncey rules before builders
  start.
- **Phase 1 — sequential foundation (1 builder).** Builder A: plugin API
  + permissions + page model + pipeline + bundle-card validation +
  manifest-diff guard + no-remote-fetch lint. The permissions catalog
  includes the automation/credential permissions
  (`automation_read`, `automation_act`, `credential_generate`,
  `credential_fill`); the grant ledger seals at rest via the
  `cybrus/veil.py` binding. Everything else hangs off this; it cannot
  be parallelized without divergence. Proof: registry deny-closed
  tests, pipeline order tests, permission grant/deny/revoke/
  expiry tests, who-pays card refusal tests — all green before phase 2.
- **Phase 2 — parallel (4 builders).** B (privacy + epoch-ratcheted
  sessions), C (vault + credential broker + tools), D (sync design),
  E (automation agent surface) build against Builder A's frozen API.
  File ownership per §9. Each builder's tests green independently;
  integration pass at the end (pipeline + one plugin per surface +
  a read-only agent run).
- **Phase 3 — shell binding (later, native).** Android WebView shell in
  `apps/levi-android` binding the Python core. Separate toolchain,
  separate proof (`assembleDebug` + on-device). Credential
  autofill-service binding lands here. Not started until phases
  1–2 are green and Chauncey orders it.

## 11. Thin-vs-full recommendation

**Recommend: thin layer first, designed for a full shell later.**

Reasons:

1. The thin layer (plugin host + privacy pipeline + vault binding +
   honest tools) is genuinely buildable stdlib-only, in this repo, with
   this test suite. Every claim in it can be proven here.
2. The full shell needs the Android WebView native piece — a different
   toolchain, unprovable in pytest, and a real audit before any security
   claim. Starting there puts the hardest, least-provable work first.
3. The thin layer is independently useful on day one (CLI/headless:
   fetch → shield → grade → capture → vault), while the shell binding
   waits for its turn without blocking anything.
4. Team size follows the phase: 1 builder (phase 1) → 3 builders
   (phase 2) → shell team only when ordered (phase 3).

This is not a dodge of the full vision — the API (§5) and pipeline (§6)
are drawn so the WebView shell binds without redesign.

## 12. Honest limits — the security-claims rule

No module may claim "secure", "private", or "anonymous" as a blanket.
Allowed claims are per-mechanism and graded:

- OBSERVED: "tracker list v2026-09-29 applied; 14 of 17 requests matched"
- INFERRED: "page shows no third-party requests (static parse; dynamic
  requests not observed)"
- UNVERIFIED: "Tor routing", "on-device ML translation", anything not
  wired or not yet audited.

A "secure browsing" label on the whole layer is UNVERIFIED until a real
audit exists. Saying less than we can prove is the feature.

**The crown jewels (law 11).** The credential broker is the
highest-value target in the layer: no blanket claim on it, ever — no
"secure password manager", no "military-grade", no "zero-knowledge".
Per-mechanism graded claims only (generation: OBSERVED via stdlib
`secrets`; storage: veil-sealed, keeper-held keys; the whole store:
UNVERIFIED until audited). The grade travels with the claim — in the
API return, the receipt, and the surface.

## 13. Open questions for Chauncey

1. Thin-first phasing (§11) — ruled yes, or full shell now?
2. Plugin distribution: keeper-side-load only, or a signed plugin
   catalog later? (Catalog is phase-3 scope at earliest.)
3. The Android shell (phase 3): WebView binding, or should the shell
   wait until the Python core has shipped and settled?
4. Name: "browse layer" is the working name. Keep it, or give it a
   real name?
5. Automation acting scope (DG-8): read-only automation first, or
   acting-on-behalf from day one? Until ruled, acting classes ship
   refused-by-default.
