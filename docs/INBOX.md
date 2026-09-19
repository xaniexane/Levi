# Inbox — companion analytics + request box

`core/levi/inbox/` — the user-facing side of the companion: what the
user uses, and what the user asks for. Both halves are **local-first
and user-owned**: data lives under `~/.levi/inbox/` (override with
`LEVI_INBOX_DIR`), owner-only (`0o700` dir, `0o600` files). Nothing
leaves the machine. No external telemetry, ever.

## Canon: analytics is a founder composite

Analytics is the **DemandPulse + Omnipulse + CyberPulse** composite —
not a standalone instrument:

- **DemandPulse** senses demand patterns: which capabilities the user
  actually reaches for is where the need is.
- **CyberPulse** feels the organism's telemetry: the pulse of what runs,
  the health of the body.
- **Omnipulse** tracks lifecycles: usage across the cycle clock — what
  persists, what decays, what is reborn.

`levi.inbox.analytics` is their joint instrument: the recording surface
and aggregate views through which the three founders' signals become
readable to the user.

## Analytics (`levi.inbox.analytics`)

Usage events — *which* capability ran, *when* — aggregated into
daily/weekly views and per-capability counts. An event records the
capability name and a short label (e.g. the chat session name); it
**never** records message content, arguments, or secrets.

- `record(capability, detail="")` — append one event; never raises
  into callers. Set `LEVI_ANALYTICS_OFF=1` to disable.
- `Analytics().daily()` / `.weekly()` / `.top(n)` — aggregate views.
- Corrupt lines are skipped individually; one bad line never aborts
  a query.

CLI: `levi inbox analytics [today|week|top]`.
Chat box: `/analytics`, `/analytics week`, `/analytics top`.

## Request box (`levi.inbox.requests`)

Drop a request in anytime: `/request <text>` in the companion chat
box, or `levi inbox request "..."`. Stored locally with timestamp.

Statuses move forward only: `open → considered → building → done`.

- `RequestBox().add(text)` → `Request(id, text, status, ts)`
- `.list(status=None)`, `.get(id)`, `.set_status(id, status)`

CLI: `levi inbox requests`, `levi inbox request "..."`,
`levi inbox request-status <n> <status>`.
Chat box: `/requests`, `/requests <status>`, `/requests <n> <status>`.

## Honest limits

- Analytics is aggregate counts, not insight: it tells you *what* you
  use and *how often*, not why. It records only events the REPL and
  `record()` callers emit — CLI organs that never call `record()` are
  invisible to it.
- The request box is a list, not a promise: requests are stored and
  triaged, nothing auto-builds from them.
- This is the user's own data on their own machine. There is no sync,
  no export, no dashboard — just the box and the views.
