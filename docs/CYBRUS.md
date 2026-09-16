# CYBRUS — Founder-Grade Identity Vault (Security Layer)

Cybrus is LEVI's **Security Layer**: the founder-grade identity vault,
policy engine, human-approval gate, tamper-evident audit log, device
trust registry, and the **sole gateway** through which anything inside
LEVI may reach the outside world.

> **Canonical spec placement.** Cybrus sits in the Security Layer
> alongside **UniForge** (per the SER-13/18/21 master spec, 2026-07-05/06).
> **UniForge is not built in this increment — Cybrus only.**

Defensive blue-team only. Local-first. Stdlib-only, no network calls, no
telemetry. State lives under `~/.levi/cybrus/` (the `LEVI_HOME` convention),
owner-only (`0o600`), atomic writes. No hardcoded secrets.

---

## Canonical spec

### Internal API surface (`core/levi/cybrus/gateway.py` → `CybrusGateway`)

| Method | What it does |
|---|---|
| `auth(identity, credential)` | Authenticates an identity (constant-time password check) → issues a session token (`kind="session"`, 12h TTL). Failures never distinguish "unknown identity" from "bad password". |
| `generate_account(name, tier)` | Thin wrapper over the account factory. The plaintext password exists only in the return value — never in the audit log. |
| `create_api_key(name, scopes)` / `get_api_key(name)` / `validate_api_key(name, presented)` / `list_api_keys()` / `revoke_api_key(name)` | Named API keys. Secrets live in the encrypted vault (`cybrus.apikeys` service); only names/scopes are listed. Distinct from session tokens. Constant-time validation. |
| `route_internal(qid_or_target, payload_meta)` | Internal routing decision. Accepts a `QID` ("QID = address of thought") or a named internal target. **Logged with metadata only — never full payloads.** |
| `route_external(destination, actor, purpose)` | **THE sole external gateway** (see below). |
| `authorize_execution(actor, action, resource)` | The execution-authorization path: **policy check → approval check → audit append → decision**. High-risk requires an approved HITL record; policy `deny` always wins, even with an approval in hand. Approvals are single-use. |

Supporting engines: `policy.py` (default-deny, deny-wins, strictest-risk ceiling),
`approval.py` (the user's **HITL gate**: pending → approved/denied/expired, 24h TTL),
`audit.py` (append-only JSONL, SHA-256 hash chain), `devices.py`
(`untrusted < known < trusted`), `identity.py` / `factory.py` / `tokens.py` /
`vault.py` (sibling-built), `qid.py` (QID addressing).

### The sole-external-gateway rule

> **Omega never touches external APIs directly — Cybrus does.**

`route_external` is the authorization / routing-**control plane**, not an
HTTP client: this build performs **no network calls**. A grant requires ALL
four, in order:

1. **(a) Authenticated identity** — a live session from `auth()` for `actor`.
2. **(b) Policy-engine `allow`** — evaluated as `(actor, external.<destination>, route)`.
3. **(c) HITL approval when high-risk** — a human-approved record matching (actor, destination, purpose); raises `ApprovalRequired` carrying the pending approval id otherwise.
4. **Short-lived signed routing grant** — a token bound to (actor, destination pattern, scope, expiry, purpose; default 5-minute TTL), plus a **full audit record**.

**No grant without all four. No bypass path exists.** `PolicyDenied` is
raised on policy deny regardless of any approval on record.

### QID addressing (`qid.py`)

`QID` is a frozen dataclass — `shell.form.logic_state.recursion`, e.g. `"3.42.7.0"`:

- `shell`: 1..21 · `form`: 1..315 · `logic_state`: 1..13 · `recursion`: 0..10³⁰
- `QID.parse("s.f.l.r")`, `str(qid)` round-trips, out-of-range → `ValueError`.

The **18 SER-18 phase names** and **13 SER-13 state names** live in the
canonical master spec, which is not present in this build. The module
deliberately does **not** invent them: `PHASE_NAMES` / `STATE_NAMES` are
empty by default and `phase_name()` / `state_name()` return `None` until
`register_spec_tables(phases, states)` (or `load_spec_tables(path)`) loads
them — with the exact counts (18 / 13) strictly validated. Numeric range
validation always applies.

### HITL execution authorization

`authorize_execution(actor, action, resource)`:

1. Policy evaluates. `deny` → audited `execution.denied`, blocked. **Deny wins over any approval.**
2. `allow` at high/critical risk → looks for a matching **approved** HITL record; none → creates a pending approval, audited `execution.approval_required`, blocked with the approval id.
3. Approved record found → marked **consumed** (single-use), audited `execution.authorized`, allowed.
4. `allow` at low/medium risk → audited `execution.authorized`, allowed.

`approval.py` is explicitly the user's HITL gate: `approve` / `deny`
semantics are "high-risk execution requires explicit human approval" —
`check()` is true only for approved, non-expired, non-consumed records.

---

## Architecture & module map

```
core/levi/cybrus/
├── gateway.py      # CybrusGateway — canonical internal API surface (this spec)
├── qid.py          # QID addressing: shell.form.logic_state.recursion
├── policy.py       # PolicyEngine — default-deny, deny-wins, risk ceiling
├── approval.py     # ApprovalEngine — the HITL gate (pending/approved/denied/expired)
├── audit.py        # AuditEngine — append-only JSONL, SHA-256 hash chain
├── devices.py      # DeviceTrust — enroll / trust levels / revoke
├── identity.py     # identity accounts (sibling-built)
├── factory.py      # account factory: generated names + passwords (sibling-built)
├── tokens.py       # TokenEngine — kinds: session | api | revenue (paper-only)
├── vault.py        # encrypted credential vault (sibling-built)
├── _paths.py       # state paths under ~/.levi/cybrus (sibling-built)
└── __main__.py     # python -m levi.cybrus  /  levi cybrus
```

Token kinds: `session` (gateway auth, 12h), `api` (general bearer; routing
grants are short-lived `api` tokens), `revenue` (**paper-only** value
tracking — requires `memo` + `basis` notes, labeled `paper=True`; no real
money is ever represented).

CLI (`levi cybrus …` / `python -m levi.cybrus …`):

- `status` — policy / approvals / audit / devices / identities overview
- `account create <name> [--tier]`, `account list`,
  `account set-password <name>` — set/change a password (prompted twice,
  never argv; changing an existing credential requires proving the current
  one first). Only the PBKDF2 hash reference is stored.
- `vault store|get|list` (master password and secrets via `getpass`, never argv)
- `token issue --scope <s> [--scope …] [--ttl]`, `token rotate <id>`,
  `token revoke <id>` (`--scope` is required: the engine rejects empty
  scope lists, so the CLI fails at parse time instead)
- `apikey create <name> --scope <s> [--scope …]` (shown once; `--scope`
  required), `apikey list`, `apikey revoke <name>`
- `route grant <destination> --purpose "…" --actor <name>` (password prompted;
  full authz path; prints the pending approval id when HITL is required)
- `qid parse <qid>`
- `approve <id> --identity <name>`, `deny <id> --identity <name> [--reason]`,
  `approvals pending` — **authenticated**: the password is prompted (never
  argv) and verified through `gateway.auth()`; the verified identity is
  recorded in the decision's `by` field and in the audit log (`approval.approved`
  / `approval.denied`). There is no anonymous path to decide a pending approval.
- `audit tail [-n]`, `audit verify`
- `device enroll <id> <name>`, `device trust <id> <level>`, `device list`

---

## Plan → Preview → Permission → Execute → Verify → Receipt

Every consequential act through the gateway follows the organism's binding
law:

- **Plan** — the caller decides actor/action/resource (or destination/purpose).
- **Preview** — `authorize_execution` / `route_external` evaluates policy first; the decision (allow/deny, risk, reason) is computed before anything happens.
- **Permission** — high/critical risk requires the HITL gate: an explicit human `approve`.
- **Execute** — the grant is issued / the action authorized (single-use approvals can't authorize twice).
- **Verify** — grants validate via `validate_grant` (binding + expiry checked); tokens validate via the token engine.
- **Receipt** — every step appends to the tamper-evident audit log (`auth.*`, `execution.*`, `route.*`, `apikey.*`).

---

## Threat model

- **Assumes the local machine is the trust boundary.** State files are owner-only; the vault is encrypted at rest; tokens/API keys are never logged or re-readable (plaintext shown exactly once).
- **Default-deny everywhere.** Unknown actors, resources, and actions are denied; deny rules beat allow rules; the strictest matched risk applies.
- **No confused-deputy external access.** There is exactly one external gateway, and it is fail-closed on four independent checks.
- **No silent high-risk acts.** High/critical risk cannot execute without a recorded human approval.
- **No anonymous HITL decisions.** `levi cybrus approve` / `deny` require `--identity` plus a password verified through `gateway.auth()` — the verified identity is recorded in `decided_by` and in the audit log (`approval.approved` / `approval.denied`). Programmatic `ApprovalEngine.approve()` keeps its `by=` parameter for in-process callers; the CLI path cannot self-approve anonymously.
- **Single-use approvals are atomic.** The gateway consumes approvals with an atomic match-and-mark under an advisory file lock (`fcntl.flock` on POSIX; threading fallback elsewhere), so two concurrent processes cannot both spend one approval or both rotate one token into two successors.
- **Audit is tamper-evident, not tamper-proof.** The SHA-256 chain detects modification/deletion after the fact; it does not prevent a root-level attacker from rewriting history — `audit verify` is the check.
- **Local-shell threat model, stated plainly.** Cybrus defends the *integrity* of identity, policy, and audit records against buggy or racing local processes. But a local attacker who holds the user's shell **and** the user's credentials (vault master password, identity passwords) is out of scope — no local software gate can distinguish that attacker from the user. The vault's encryption-at-rest raises the bar for offline disk theft, not for a live compromised session.
- **Out of scope:** remote identity federation, hardware-backed keys, device attestation, recovery service, network transport, intrusion detection. This build is the local control plane.

## Defensive-only law

Cybrus is blue-team tooling: authentication, authorization, audit, and
trust management. It contains **no attack tooling, no exfiltration
helpers, and no bypass paths** — high-risk actions require explicit human
approval and there is deliberately no flag, env var, or backdoor to skip
it.

## Cryptography

- The vault uses **Fernet** (`cryptography` package) when available.
- Otherwise it falls back to a clearly-labeled **stdlib-only cipher**
  (documented in the vault module as a fallback, not equivalent to Fernet).
- Password hashing: PBKDF2-HMAC-SHA256, 600,000 iterations (stdlib
  `hashlib`; no Argon2 path in this build — the earlier doc line claiming
  Argon2id was wrong and has been corrected).
- Token/API-key comparison: `hmac.compare_digest` (constant-time). Password
  verification (`factory.verify_password`) is also constant-time.

## Local tier policy — no payments

Everything here is local and free to produce: stdlib plus the one
already-accepted optional pip dep (`cryptography`, with a labeled stdlib
fallback). **Revenue tokens are paper/simulated only** — ledger
entries with a `memo` and an honest `basis` note, labeled `paper=True`.
No payment rails, no real money, no pricing.

---

## Honest gaps (what this build does NOT do)

- **Routing is control-plane only.** `route_external` authorizes and issues
  short-lived grants; it performs **no network calls** in this build. The
  actual HTTP transport is a future increment.
- **UniForge is not built.** The Security Layer's sibling from the canonical
  spec is explicitly out of scope for this increment.
- **Revenue tokens are paper/simulated only.** No real value is represented
  or moved.
- **Receipts are not yet automatic everywhere.** The audit engine exists and
  the gateway emits receipts for its own flows, but policy/approval/device
  mutations made directly against the engines don't yet auto-emit receipts.
- **QID name tables not loaded.** The 18 SER-18 phase names and 13 SER-13
  state names are validated-but-empty until the master spec file is
  provided; only numeric ranges are enforced.
- **Sessions are in-memory.** A gateway restart requires re-authentication;
  there is no persistent session store yet.
- **No remote anything.** No federation, no hardware keys, no attestation,
  no recovery service, no telemetry (by design).

## Round-3 adversarial review — found and fixed (2026-09-16)

Severity key: **H** = exploitable hole · **M** = hardening gap · **L** = hygiene.

1. **[H] Anonymous CLI approve/deny.** `levi cybrus approve <id>` defaulted
   `by="owner"` with no authentication — anyone with a local shell could
   self-approve any pending HITL entry. **Fix:** `approve`/`deny` now require
   `--identity` plus a `getpass` password verified through `gateway.auth()`
   (fail-closed on unknown/suspended identity, empty or wrong password); the
   verified identity is recorded in `decided_by` and in the audit log
   (`approval.approved` / `approval.denied`). Added `account set-password`
   so identities can hold credentials (changing an existing credential
   requires proving the current one). Programmatic
   `ApprovalEngine.approve()` keeps its API. Tests: anonymous/wrong-credential/
   unknown-identity approve rejected; authenticated approve+deny record the
   real identity; double-decide fails closed.
2. **[M] Approval double-consume race.** `authorize_execution` /
   `route_external` matched an approved entry and annotated it consumed in
   two steps — two concurrent processes could both spend one approval and
   mint two grants. **Fix:** `ApprovalEngine.consume_approved()` matches and
   marks `consumed_at` atomically under an advisory `fcntl` store lock
   (`_paths.store_lock`); the gateway uses it in both paths. Thread-race
   test asserts exactly one winner out of 8.
3. **[M] Token double-rotate race.** Two concurrent `rotate()` calls could
   both mint a live successor. **Fix:** issue/rotate/revoke/purge run under
   the store lock with a fresh reload; the loser sees `revoked` and fails
   closed. Thread-race test: 1 winner, 5 fail-closed.
4. **[M] Read-modify-write entry loss.** Concurrent writers to the grants,
   apikey-registry, identity, device, policy, and vault-entry stores could
   silently drop each other's entries (shared fixed `.tmp` name in
   `atomic_write_bytes` compounded it). **Fix:** all mutating paths take the
   store lock with reload; temp files now have unique per-write names and
   `fchmod` re-asserts `0o600`.
5. **[L] Dead `except TypeError` fallback in `_open_vault`.** The fallback
   called a nonexistent `master_password=` kwarg and masked real `TypeError`s
   from inside the constructor. **Fix:** removed; direct construction.
6. **[L] `--scope` argparse/engine mismatch.** The CLI advertised `--scope`
   as optional (default `[]`) while the engine/gateway reject empty scopes —
   a confusing runtime error. **Fix:** `--scope` is now `required=True` for
   `token issue` and `apikey create` (clear parse-time failure).
7. **[L] Docs overclaim: Argon2id.** The docs claimed Argon2id "when present";
   no argon2 code path exists — password hashing is PBKDF2-HMAC-SHA256 at
   600k iterations. **Fix:** docs corrected.

**Verified clean (no change needed):** no `bypass`/`backdoor`/`master key`/
hardcoded-credential strings anywhere in `core/levi/cybrus/` or the cybrus
tests (grep sweep; only "no bypass path" / "no hardcoded" assertions remain);
no plaintext passwords, tokens, or secrets in any audit/log/print path
(plaintext is printed exactly once at issuance/rotation/get by explicit user
request, never audited); all secret comparisons use `hmac.compare_digest`;
PBKDF2 at 600,000 iterations (not lowered); every state write path is
atomic + `0o600`, every dir `0o700` (verified in tests).

## Residual risks (honest)

- The store lock is **advisory**: it serializes cooperating cybrus processes
  (the TOCTOU races above). A non-cooperating process editing the JSON
  directly, an NFS-mounted home (where `flock` semantics are unreliable), or
  a root attacker is not stopped by it. On non-POSIX platforms it degrades
  to a per-path threading lock (same-process threads only).
- **Local shell + credentials = game over** (see threat model). Cybrus cannot
  distinguish the user from an attacker holding their passwords on a live
  session; the vault's encryption protects offline disk theft, not a live
  compromise.
- The audit log is **tamper-evident, not tamper-proof**: a root attacker can
  rewrite history. `audit verify` detects it after the fact; there is no
  remote witness or append-only hardware in this build.
- `--purpose` on `route grant` and free-text `reason` on `deny` are written
  to the audit log — do not put secrets in them.
- Sessions live in gateway process memory; a restart drops them (by design,
  fail-closed toward re-authentication).
