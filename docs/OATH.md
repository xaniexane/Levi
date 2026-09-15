# LEVI Oath — the trust-bound mission plane

> *"The agent itself holds zero authority; every signing ceremony is sudo for agents."*

LEVI Oath is a clean-room, LEVI-native recreation of the **trust model** behind
[Beadle](https://github.com/punt-labs/beadle) *(inspiration reference only — not a source;
no Beadle code was read or copied)*. Beadle's trust architecture was tested but never
shipped a working daemon. **Oath ships one.**

The idea: signed instructions arrive over ordinary email. Every message is classified
into a four-level trust ladder. Nothing executes unless the sender is a known contact,
their signature verifies, their explicit grants cover the requested command, and the
command tier sits under their risk ceiling. The agent can never grant itself anything —
authority flows only from the owner's signing ceremonies.

## The zero-authority principle

This is the whole design in one sentence: **the agent holds zero authority**.

- Commands do not exist until the *owner* reviews canonical JSON and signs it with
  their own GPG key (`oath command define` → review → `oath command sign`). The loader
  **refuses** any definition with a missing, bad, or expired signature — there is no
  trust-on-first-use.
- Contacts, grants, fingerprints, and rate limits are owner-managed data edited through
  the CLI. Mail can never modify them.
- Mission creation requires `VERIFIED` or `TRUSTED` mail. There is deliberately **no
  override flag** — not even the owner can bypass it from the mail path (the local
  console path, `oath run`, acts with owner authority by construction).
- Deny-closed permissions: anything not explicitly granted is denied.

## Architecture

```
email (Maildir / IMAP)
   │  inbox.py — parse, extract PGP/MIME parts, classify, match contact
   ▼
mission {contact, trust, pipeline_text, stages}
   │  daemon.py — gates in order, rate limit, run, audit, mark seen
   ▼
policy.py   1. trust gate (VERIFIED/TRUSTED hard requirement, no override)
            2. permission check (deny-closed rwx + explicit d grants)
            3. risk-ceiling inheritance (never above contact's ceiling)
   ▼
pipeline.py  cmd:name k=v | ai:"prompt" | reply:…
   │  stdout chains left-to-right; permissions checked BEFORE each stage;
   │  --dry-run previews without executing
   ▼
audit.py  append-only JSONL hash chain + GPG-clearsigned checkpoints
```

### Trust levels (`trust.py`)

| Level | Meaning |
|---|---|
| `TRUSTED` | Valid signature **and** the signing fingerprint is pinned to the contact — the fully-validated chain |
| `VERIFIED` | Valid PGP signature from an unpinned key |
| `UNTRUSTED` | A signature was present but verification failed |
| `UNVERIFIED` | No signature at all |

Verification runs `gpg --verify` against an **isolated keyring** (`$LEVI_OATH_GNUPGHOME`
or `<oath home>/gnupg`), never the user's `~/.gnupg`.

**Honest note on Proton:** Proton's proprietary end-to-end encryption is not verifiable
by third-party tooling — there is no way to prove a "Proton-to-Proton" claim without
Proton's own stack. The implemented path is **PGP/MIME** (`multipart/signed`), which is
exactly what Proton Bridge produces for signed mail (plus clear-signed bodies as a
convenience). `TRUSTED` here means *signature verifies + fingerprint pinned to a known
contact* — that pinned chain is what stands in for the fully-validated claim.

### Keys (`keys.py`)

GPG wrapper: isolated GNUPGHOME (mode 0700), key import, fingerprint pinning helpers,
batch key generation (`gpg --batch --quick-generate-key`) for tests and the owner.

### Contacts (`contacts.py`)

Address book at `<oath home>/contacts.json`:

- `fingerprints` — pinned keys; a pinned valid signature upgrades `VERIFIED` → `TRUSTED`
- `trust_floor` — `VERIFIED` or `TRUSTED` (can be raised, never lowered below `VERIFIED`)
- `tier_ceiling` — highest command risk tier the contact may run
- `grants` — per-command letters: `r` (read-only commands), `w` (state-changing),
  `x` (pipeline execution). `d` is the explicit dangerous-tier grant, never inherited.
- `max_missions_per_hour` — rate limit enforced at mission intake

### Commands (`commands.py`)

Canonical JSON definitions `{name, argv template, arg schema, risk tier, description}`,
stored as `name.json` + detached signature `name.json.sig` in `<oath home>/commands/`.
Risk tiers: `read` / `write` / `execute` / `dangerous`.

argv templates carry `{placeholders}`; arguments are validated against the schema
(types, required, patterns, enums, min/max, max_length) and **shell metacharacters are
rejected outright**. Execution uses `subprocess.run(argv, shell=False)` — `shell=True`
never appears anywhere in this codebase.

Two builtins ship in code (they are code, not email-controlled data, so they need no
signature — but they pass through the same policy gates): `ai` (reasoning stage, tier
`execute`) and `reply` (mail-reply stage, tier `write`).

### Policy (`policy.py`)

Enforcement order: **trust gate → permission → risk ceiling**. A denial at any gate
stops the mission and is written to the audit trail.

### Pipelines (`pipeline.py`)

```
cmd:disk-usage path=/tmp | ai:"summarise the usage" | reply:body="{stdin}"
```

- `cmd:<name> k=v …` — a signed command definition
- `ai:"prompt"` — AI reasoning stage. Runs through LEVI's real agent runtime
  (`levi.agent.loop.run_subtask`), imported **lazily inside the stage function** so this
  module imports clean standalone. If the agent runtime is unavailable, a deterministic
  offline rules engine responds — its output is honestly labeled `[offline-fallback]`
  and it never invents a model call.
- `reply:subject="…" body="…"` — auto-reply is a *pipeline stage*, not daemon I/O.
  The daemon only provides the SMTP transport the stage calls into.

`--dry-run` previews the plan (rendered argv, policy decisions) without spawning any
subprocess or sending any mail.

### Audit (`audit.py`)

Append-only JSONL at `<oath home>/audit.jsonl`: `{seq, ts, prev_hash, payload, sha256}`
chained entries. `oath audit verify` replays the chain; any payload edit breaks it.
`oath audit checkpoint` writes a GPG-clearsigned checkpoint binding `seq` to the head
hash; verification checks every checkpoint signature against the owner's fingerprint.

### Inbox (`inbox.py`)

Maildir (`<oath home>/maildir/{new,cur,tmp}`) + IMAP intake using **stdlib only**
(`imaplib`, `email`, `smtplib`). Extracts PGP/MIME signed parts, classifies trust,
matches the sender to a contact (by email, else by signing fingerprint), and builds a
mission. The pipeline text always comes from the **verified signed content** — unsigned
mail yields an `UNVERIFIED` mission with no pipeline, which the trust gate refuses.

No raw shell anywhere: commands execute only via signed definitions with argv
templates.

### Daemon (`daemon.py`)

The working unattended daemon Beadle never shipped: poll loop + `--once` mode for
cron; enforces gates and rate limits; runs missions; sends result/error replies via
SMTP (stdlib `smtplib`). Every decision is audited.

## What's real vs. stubbed

| Real | Stubbed / honest limits |
|---|---|
| GPG verification, keygen, signing via the system `gpg` | Requires `gpg` installed (tests skip without it) |
| PGP/MIME + clear-sign classification, all four levels | Proton-proprietary E2EE claims are not verifiable (see note above) |
| Signed command registry with refuse-unsigned loader | The owner must complete the sign ceremony by hand (by design) |
| Policy gates, deny-closed grants, risk ceilings, rate limits | — |
| Pipeline chaining, dry-run, per-stage policy checks | AI stage needs LEVI's agent runtime or it honestly falls back |
| Hash-chained audit log + signed checkpoints | Checkpoint signing needs the owner's key in the oath keyring |
| Maildir + IMAP intake, SMTP replies | No POP3; no automatic key discovery (pins are owner-managed) |

## Email setup (IMAP/SMTP + GPG only)

1. `python -m levi.oath init --email you@example.com`
2. `python -m levi.oath key gen --uid "Owner <you@example.com>"` (or import your key),
   then paste the fingerprint into `<oath home>/owner.json`.
3. Fill in `<oath home>/mail.json` (IMAP for intake, SMTP for replies) — or drop mail
   into `<oath home>/maildir/new/`.
4. Add contacts: `oath contact add alice --email alice@example.com`,
   `oath contact pin alice <fingerprint>`, `oath contact grant alice disk-usage r`.
5. Define commands: `oath command define disk-usage --tier read --argv du -sh {path} --arg path:string:true`,
   review, then `oath command sign disk-usage`.
6. `python -m levi.oath daemon --once` (cron) or `python -m levi.oath daemon` (loop).

A contact then emails a signed pipeline, e.g. a clear-signed body containing:

```
cmd:disk-usage path=/tmp | ai:"summarise this" | reply:body="{stdin}"
```

## CLI

`python -m levi.oath` with subcommands: `init`, `doctor`, `key`, `contact`, `command
define|sign|list|show`, `run`, `inbox poll`, `daemon`, `audit verify|checkpoint|tail`.

**Note:** the `levi oath` wiring into the main LEVI CLI follows after the hardening
pass — `core/levi/cli/main.py` is intentionally untouched by this build.
