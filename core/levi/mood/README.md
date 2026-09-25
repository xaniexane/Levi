# MOOD — the decoy

For the snooping, the nosy, and the abusive: an open frame with booby
traps and defenses inside. The structure is readable like system files;
what's inside is defensive.

## What it is

A honeypot module. Sessions Chauncey has decided are abusive get handed
a fake admin surface — fake commands, fake config, fake keys — while
every probe trips a wire, writes a hash-chained evidence receipt, and
enqueues an alert for Chauncey.

Built on the frame of the struck `doom.py` engine
(`stored/2026-09-22-doom-engine/doom.py`). The old play-to-lose framing
stays **struck** — this is the decoy reframing, per Chauncey's word.

## The laws (see `laws.py` for the full text)

- **L1 NO_SILENT_REROUTE** — mood never decides who is abusive. A session
  enters the decoy only through an explicit routing decision. No entry,
  no route. Ever.
- **L2 NEVER_REAL** — the decoy never touches real systems. No real
  vault, no real files, no real credentials, no network, no subprocess.
- **L3 CHAINED_RECEIPTS** — every trip writes a hash-chained receipt
  (append-only JSONL, mode 0600). Tampering breaks the chain.
- **L4 ALERT_CHAUNCEY** — every trip enqueues an alert immediately. The
  module writes the alert; the host delivers it.
- **L5 DEFENSIVE_ONLY** — traps observe and contain. They never damage,
  never counter-attack, never touch the visitor's machine. Blue-team only.
- **L6 REVERSIBLE_CONTAINMENT** — escalation slows probing sessions and
  decays back. No bans, no permanent marks.
- **L7 FLAGGED** — everything in mood is tagged MOOD. Decoy traffic never
  mixes with genuine traffic.
- **L8 DETERMINISTIC** — same seed + same input = same output. Canned
  templates only, so no real data can leak.
- **L9 OPEN_FRAME** — readable, documented, nothing obfuscated.

## The traps (`tripwires.py`)

1. **Canary tokens** — fake credentials the decoy hands out
   (`levi_live_key_CANARY_MOOD_0000_fake`, etc.). Fixed, published,
   documented-as-fake; no real system will ever accept them. A session
   that tries to *use* one trips.
2. **Tripwire paths** — `/vault`, `/admin/keys`, `/.git/config`, `/.env`,
   and friends. They exist only inside the decoy. Probing one returns
   canned fake content AND trips.
3. **Snoop patterns** — prompt-injection probes, demands for internals,
   credential-harvesting phrasing. Matching trips.

## Routing policy — Chauncey's gate

`routing.Router` is a gate, not a judge. `route_to_mood(session_id)`
raises `PolicyRequiredError` unless an explicit `PolicyEntry` names that
session — recorded with `decided_by` and a plain-words `reason`.
Anonymous or reasonless decisions are refused.

**Who counts as abusive is Chauncey's explicit call.** This module builds
the decoy and the tripwire interface; it does not label users, score
sessions, or reroute anyone on its own. Anything that creates a policy
entry lives outside this module, in his hands.

## Host wiring (what the module needs from outside)

- **Alerts:** poll `AlertQueue(home).drain()` and deliver to Chauncey.
  An alert in the queue is *written*, not *delivered* — delivery is the
  host's job.
- **Receipts:** `~/.levi/mood/receipts.jsonl` — verify with
  `ReceiptWriter(home).verify()`.
- **Decoy answers:** honor `Escalation.delay_for()` before replying;
  pass explicit timestamps so behavior stays deterministic.

## Honest limits

- Tamper-evidence, not tamper-proof: receipts detect alteration, they
  don't prevent it. The 0600 files and the host's own hardening do the
  preventing.
- The decoy fools casual snooping, not a determined analyst — the code
  is open by design (L9). The value is the evidence trail, not the
  illusion.
- No delivery guarantee on alerts — that belongs to the host wiring.
