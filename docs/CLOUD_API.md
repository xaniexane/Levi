# LEVI Cloud API — `levi agent serve` as a multi-user API

LEVI can be its own cloud provider: run `levi agent serve` on one
machine and call it like an API from anywhere (your phone, another
computer, a script). Two credential kinds exist:

| Credential | Who | Powers |
|---|---|---|
| Owner master token (`LEVI_AGENT_TOKEN`) | you, the server operator | full tool registry, no rate limit; manages API keys |
| Per-user API keys (`levi_sk_…`) | other users / devices | cloud-safe tool profile, 60 req/min |

## Quickstart

```bash
# 1. On the server machine, set a long random owner token and serve:
export LEVI_AGENT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
levi agent serve --host 127.0.0.1 --port 8765

# 2. Create a key for another user (prints ONCE — copy it now):
levi cloud keys create alice
# levi_sk_...

# 3. From anywhere that can reach the server:
curl -s http://SERVER:8765/v1/agent/run \
  -H "Authorization: Bearer levi_sk_..." \
  -H "Content-Type: application/json" \
  -d '{"task": "What are the latest tech headlines?", "max_steps": 6}'

curl -s http://SERVER:8765/v1/agent/chat \
  -H "Authorization: Bearer levi_sk_..." \
  -H "Content-Type: application/json" \
  -d '{"session_id": "alice-1", "message": "hello, what can you do?"}'

curl -s http://SERVER:8765/v1/tools \
  -H "Authorization: Bearer levi_sk_..."
```

`/healthz` is public (no auth): `{"status": "ok", "service": "levi-agent", "version": "…"}`.

## Key lifecycle

```bash
levi cloud keys create <name> [--no-learn]  # prints the key once; only a SHA-256 hash is stored
levi cloud keys list             # name, prefix, created, active/revoked, learn flag (hashes never shown)
levi cloud keys revoke <name|prefix>
levi cloud keys learn <name|prefix> on|off   # toggle growth-learning consent for a key
levi cloud usage [--key <name>] [--limit 20]
```

- Keys live in `~/.levi/cloud/keys.json` (`0o600` file, `0o700` dir).
  The raw key is **never stored** — only its SHA-256 digest — and never
  logged; logs and metering record only the public prefix (`levi_sk_…`).
- Verification is constant-time over the stored digests.
- Revoked keys stay in the store as `revoked: true` (audit trail) and
  can never authenticate again.

## Auth scheme

`Authorization: Bearer <credential>` on every `/v1/*` route. The
server checks the owner token first (constant-time compare), then the
API-key store. Anything else → `401 {"error": "unauthorized"}`.

## Rate limits

- API keys: token bucket, **60 requests/minute** per key
  (override with `LEVI_CLOUD_RATE_PER_MIN`). Exceeding it returns
  `429 {"error": "rate limit exceeded"}` with a `Retry-After` header
  (seconds).
- Owner token: not rate-limited.
- Buckets are in-memory; a server restart resets them.

## Cloud-safe tool policy

An API key's agent runs a **default-deny** subset of the tool
registry, enforced server-side by key type — a client cannot claim a
wider profile. The exact allowlist lives in
`core/levi/cloud/profile.py` (`CLOUD_SAFE_TOOLS`):

**Allowed** (read-only, no host state, no owner data):
`affect_detect`, `affect_state`, `capabilities`, `course_brief`,
`course_search`, `lab_footprint`, `lab_scenario`, `news_latest`,
`news_search`, `skill_list`, `skill_load`, `web_search`.

**Denied to API keys** (owner token only):
- `shell_exec` — arbitrary host command execution
- `file_write`, `file_edit` — arbitrary file write
- `file_read` — reads the server owner's files
- `memory_read`, `memory_write` — the owner's private memory
- `schedule_add`, `schedule_list`, `schedule_remove` — the owner's schedule
- `delegate` — spawns subagents outside the restricted profile
- `http_request`, `web_fetch` — arbitrary network egress (SSRF surface)

Chat sessions for API keys are namespaced per key
(`cloud_<prefix>_<session_id>`), so users cannot read each other's
sessions. `/v1/tools` lists exactly the tools *your* credential may
use.

## Usage metering

Every `/v1/` call appends one JSONL record to
`~/.levi/cloud/usage.jsonl`: timestamp, key name, key prefix,
endpoint, steps, outcome. Read it with `levi cloud usage`. Only the
key prefix is recorded — never a raw key.

## Growth: learning from cloud usage

When your LEVI serves other users, their sessions can teach LEVI new
*techniques* — how another model decomposed a task, chained tools, or
structured an answer. This is **cross-user distillation**, and it is
consent-gated and privacy-scrubbed by design.

**What is learned.** Only generalized *techniques*, as procedural
memory tagged `learned_from: <source>` — e.g. "when gathering
information, issue several focused searches before composing the
answer". A learning is distilled only when heuristic good-outcome
signals hold: the user kept the conversation going (or explicitly
approved), tool calls succeeded, and no correction/retry language
appeared. These are heuristics, not truth — documented as such in
`core/levi/growth/reflect.py`.

**What is never learned or stored.**

- Never another user's verbatim output, facts, or preferences.
- Never secrets or PII: a redaction gate (`core/levi/growth/redact.py`)
  scrubs API keys, tokens, `password=` assignments, emails, phone
  numbers, and card/SSN-like digit runs *before* reflection, and user
  speech is generalized to short pattern stubs.
- Cloud experiences are never sent to the model-assisted reflector
  (a third-party provider must not receive another user's content);
  distillation is rules-only.
- Only persistent `/v1/agent/chat` sessions are harvestable. One-shot
  `/v1/agent/run` calls leave no session record — nothing to learn from.

**Consent.** Per-key opt-out: `levi cloud keys create <name> --no-learn`,
or `levi cloud keys learn <name> off` later. Opted-out keys are skipped
*entirely* — their session files are never opened. Global kill switch:
`LEVI_GROWTH_CLOUD_LEARN=0` disables cloud harvest for all keys.
Consent defaults to opt-in for new keys (a missing `learn` field on
older records also means opted in); the flag is shown in
`levi cloud keys list`.

**Observability.** `levi growth status` shows pending experiences by
source (`local` vs `cloud`, per provider). Journal entries carry source
provenance (`sources.by_origin`, `sources.cloud_providers`).

**Residual risk, stated plainly.** Regex redaction is heuristic — an
unusually phrased secret or PII the patterns miss can slip through.
The gate reduces exposure; it is not a proof of absence. If a key's
sessions must never touch the growth loop at all, use `--no-learn`.

## Honest limits

- **Single machine.** No clustering, no failover; if the server box
  sleeps, the API sleeps.
- **No billing.** Metering is honest accounting for the owner, not a
  payment rail.
- **Keys are bearer secrets.** Anyone holding a key *is* that user
  until the key is revoked. Send keys over TLS (serve behind
  nginx/Caddy with HTTPS for anything beyond localhost).
- **No per-key scopes.** An API key gets the whole cloud-safe profile
  or nothing.
- **The cloud-safe profile is read-only by design.** An API-key agent
  cannot write files, run shell commands, or touch your memory and
  schedule — that is the point. The owner token keeps full power.
- **Body cap 1 MiB; max 50 steps per run** (`MAX_STEPS_CAP`).
