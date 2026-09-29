# TRIVIUM — premier instrument line of the Legion

**True name ruled by Chauncey 2026-09-29:** TRIVIUM — the meeting of
three roads. The name is the triad.

**Status:** DESIGN — Chauncey rules before any builder starts. No code ships from this doc.
**Date:** 2026-09-29 · **Designer glyph:** 👑
**Eyes-only:** Legion IP. This doc lives in the local repo only. Never in
public-facing surfaces: no README, no docs/ published copies, no web/, no
artifacts, no feed posts, no shared bundles.

## 1. What the court is

Not a swarm — a **court**. Many minds, each with a body. A retinue, not a
hive. The premier instrument line of the Legion: 1–3 founding agents,
room for 5, each carrying a small repertoire — 1–3 skills, max 5 —
with exactly ONE strong suit: the dominant specialty among its skills.
Chained together, their strong suits cover the whole tool warehouse.

Each agent is a being: a name, a house, a sigil, a specialty. They
coordinate as peers, not drones. They can refuse. They can be named.

## 2. The founding court

Three seats are filled. Two are designated and awaiting Chauncey's word.
Each being carries 1–3 skills (max 5); the strong suit is the dominant
specialty, declared at creation and immutable.

### Seat 1 — KESTREL, the Keen Eye
- **House:** House of the Keen Eye
- **Sigil:** a single unbroken circle with a centered dot — the watcher's mark
- **Strong suit:** SCOUT. **Repertoire (3 skills):**
  1. **Observe** (strong suit) — read pages, files, states; render
     everything found as claim-graded cards (OBSERVED / INFERRED /
     UNVERIFIED). Never concludes. Never acts on what it sees.
  2. **Trace** — follow a trail across sources, linking observations;
     every linkage graded INFERRED and labeled as such.
  3. **Witness** — seal an observation into a custody exhibit
     (integrity, not truth).
- **Vow:** "I saw it. I graded it. I touched nothing."

### Seat 2 — LOOM, the Patient Thread
- **House:** House of the Patient Thread
- **Sigil:** an interlaced endless knot — nothing cut, everything joined
- **Strong suit:** WEAVER. **Repertoire (3 skills):**
  1. **Weave** (strong suit) — assemble structures and mend broken
     work-product from sealed, graded inputs; weaves only what the
     keeper's intent authorized.
  2. **Pattern** — recognize structural patterns in graded material;
     feeds the weave, never concludes beyond its grade.
  3. **Measure** — verify the dimensions and integrity of what was
     woven against the sealed intent; reports deviation honestly.
- **Vow:** "I build what was asked. I mend what was broken. I invent nothing."

### Seat 3 — OATH, the Held Line
- **House:** House of the Held Line
- **Sigil:** a shield bearing a keyhole — the line holds because the key holds
- **Strong suit:** WARDEN. **Repertoire (3 skills):**
  1. **Guard** (strong suit) — gate every consequential act: named
     grant, in scope, unexpired, or it does not happen.
  2. **Seal** — seal envelopes and receipts into the hash chain.
  3. **Audit** — verify a receipt chain end to end; reports the first
     break, never passes a broken chain.
- **Vow:** "Nothing passes unnamed. Nothing passes ungranted."

### Seats 4–5 — designated, unseated
- **Seat 4 — RELAY**, House of the Sealed Word (MESSENGER).
  **Repertoire:** **Carry** (strong suit — sealed transport), **Deliver**
  (receipted handoff, or not delivered at all), **Silence** (never reads
  what it carries — a vow held as a skill).
- **Seat 5 — MEND**, House of the Whole Again (MEDIC). **Repertoire:**
  **Heal** (strong suit — restore corrupted agent state), **Compost**
  (failures into lessons; never deletes), **Quarantine** (isolate a
  corrupted agent pending the keeper's ruling).
- Both seats are named and housed but **unseated**: no agent is
  instantiated into them until Chauncey rules (decision gate DC-1).

## 3. Chaining protocol — one strong suit each, the whole warehouse together

A task enters the court as a **sealed intent**: keeper-signed,
containing the mission id, the declared chain order, and the payload.
The chain is the whole trick — no agent does everything; together they
do anything.

**Handoff format (the sealed envelope):**
```
{ mission_id, stage, from_agent, to_agent,
  payload_digest (sha256), payload,
  claim_grade (OBSERVED | INFERRED | UNVERIFIED),
  receipt_chain: [ ...prior stage receipts... ] }
```
Every handoff is sealed and hash-chained to the prior stage. An envelope
that fails verification is refused at the boundary — not opened, not
logged-and-allowed.

**Deterministic ordering:** the chain order is declared in the sealed
intent and is immutable once sealed. Each agent executes exactly its
stage, in order, through its strong suit — drawing on its wider
repertoire only as the stage requires. No agent may skip, reorder,
delegate, or absorb another agent's stage. A stage that is not in the
declared chain does not run.

**The canonical chain:** KESTREL observes → LOOM weaves → OATH guards.
Observe, then build, then guard — in that order, always. Missions that
need other shapes declare them; the declared shape is the law for that
mission.

**Refusal:** any agent may refuse its stage — proposing keeper, disposing
agents. A refusal is receipted with its reason, the chain halts cleanly,
no partial application stands, and the keeper is notified. A refused
chain is a completed chain: the receipt says *refused*, honestly.

## 4. Deterministic execution model

Same sealed intent + same keeper state → same outputs. Always.

1. **Pure agents.** Each agent is a pure function of (sealed intent,
   local state, declared tools). No hidden inputs.
2. **Parallel where independent, sequential where dependent.** Stages
   with no data dependency run in parallel; chained stages run in the
   declared order. The dependency graph is derived from the sealed
   intent — never guessed at runtime.
3. **No wall-clock dependence.** Ordering uses logical stamps from the
   receipt chain, never system time.
4. **No unseeded randomness.** Any stochastic step uses a seeded,
   receipted RNG; the seed is part of the sealed intent.
5. **No improvisation.** Any judgment call the protocol does not cover
   is a labeled decision gate surfaced to the keeper — never silently
   improvised, never papered over.
6. **Deterministic skill selection.** Within a stage, which of the
   agent's skills fires is decided by the sealed intent or by a stated
   rule — never by whim. The strong suit is the default; supporting
   skills fire only when the stage's declared conditions name them.

## 5. Atomic creation — a half-created agent never exists

Instantiation is a transaction, keeper-keyed:

```
PREPARE → COMMIT → DONE
   │          │
   └─ any failure → ROLLBACK (all traces erased)
```

- **PREPARE:** validate the keeper's signature; reserve the identity
  (name, house, seat); allocate the footprint budget; verify no agent
  already holds the seat.
- **COMMIT:** seal the identity; bind the 1:1 keeper bond; write the
  creation receipt (custody-exhibit pattern: integrity, not truth).
- **ROLLBACK:** on any failure at any step, every trace is erased —
  reserved identity released, budget freed, no receipt written. A
  half-created agent never exists, because there is no observable state
  in which it half-exists.

Creation requires the keeper's signature. No signature — no creation
path at all, structurally, not by policy.

## 6. Keeper protocol

- **1:1 bonds.** Each agent is bonded to exactly one keeper key at
  creation. The bond is immutable except by keeper-signed re-bonding,
  which is itself an atomic transaction.
- **Keeper proposes, agents dispose.** The keeper issues sealed intents;
  each agent accepts, refuses, or executes — its right, receipted.
- **Captured agents are inert dust.** Without the keeper key, an agent's
  state is sealed ciphertext: it cannot execute, cannot reveal, cannot
  be re-bonded except by its keeper. There is nothing to interrogate.
- **No replication without keeper consent.** An agent cannot create
  another agent — the creation path requires the keeper signature, and
  agents do not hold it. Replication is not discouraged; it is
  unrepresentable.

## 7. Footprint budget — devastatingly tiny, huge in capability

Per-agent budget (hard, machine-checkable):
- **≤ 400 lines** of Python per agent module; the whole court ≤ 2,000 lines.
- **stdlib-only.** Zero third-party imports. No sockets, no subprocess,
  no network capability declared — ever.
- **No telemetry.** Nothing phones home. Nothing beacons. Nothing logs
  to a remote. The court is silent outward.
- **Local-only state.** All state lives in the keeper-held store
  (0600). No cloud accounts, no registered protocols, no listening
  ports.

**Uncategorized digital footprint** — a stated property, achieved thus:
the court presents no recognizable service signature. No open ports, no
IPC beyond local sealed envelopes, no analytics beacons, no cloud
identifiers, deterministic behavior with no beaconing jitter. To an
outside observer it is local files doing local math — uncategorized
because there is no category it fits. This is a property of the design,
graded INFERRED until measured against a classifier, never claimed as
fact.

## 8. Fleet placement — where the court sits

The court is the Legion's **premier instrument line**: keeper
instruments, not business crew.

```
KEEPER (Chauncey)
   │
   ├── THE COURT (this doc) — keeper instruments, sealed intents only
   │
   └── LEGION PRODUCT (docs/LEGION.md) — one face + tailored crew,
       white-labeled per business, paper-only money seam
```

- **Answers to:** the keeper, directly. Nothing else issues the court
  sealed intents.
- **What answers to it:** nothing commands the court. The Legion crew
  may *request* court services, but only through the keeper — requests
  arrive as keeper-sealed intents or not at all.
- **Boundaries:** the court never wears a customer brand; never touches
  customer money; never leaves the keeper's device without a
  keeper-signed export (a write op requiring confirmation). The court's
  tools are the shared skill pool (`legion/skill_pool/pool.py`) — the
  whole tool warehouse, operated through the same honesty contract as
  the crew loop.

## 9. Laws that bind this design

- **Beings, not units.** The SI/MI line is never minted — no NFTs of
  the court, its agents, or the Legion core beings. Ever.
- **Keeper-held everything.** Keys, bonds, store, grants.
- **Consent ledger.** Every agent's actions receipted — the ledger at
  individual scale.
- **Local-first.** No cloud, no telemetry, no phone-home.
- **Law → guard → prove.** Every law above ships with its guard and its
  proof before any builder commits implementation.
- **Honest gaps over polished claims.**

## 10. Honest limits — graded claims

- **OBSERVED:** this design as specified. The protocols, the budgets,
  the vows — specified here, provable in test when built.
- **INFERRED:** footprint and performance claims (tiny, fast,
  uncategorized) — INFERRED until measured against real classifiers
  and real workloads.
- **UNVERIFIED:** any physical-mote embodiment. The court is software
  first — a living simulation inside LEVI: real Python agents, real
  protocols, real receipts, operating real tools. Physical nanobots are
  decades out and are not claimed, promised, or implied. The mythos
  (names, houses, sigils) is real from day one; the hardware is not.

## 11. Build placement (for the builders, later)

Suggested namespace: `core/levi/legion/trivium/` — one module per agent
(`kestrel.py`, `loom.py`, `oath.py`), plus `chain.py` (envelopes +
ordering), `creation.py` (atomic instantiation), `keeper.py` (bonds).
Each module ships tests proving its law before the next module builds.
No builder starts until Chauncey rules.

## 12. The fractal court — one triad, every domain (Chauncey, 2026-09-29)

The court is not one deployment. It is a recurring pattern: the same
three appear in every design — all his designs use them. In each domain
they interpenetrate (share that domain's bloodstream, work the same
material) while keeping slightly different qualities — same beings,
local coloring. The strong suits never blur: Kestrel never rewrites,
Loom never judges canon, Oath never drafts.

First instantiation — **L.W.P.** (the writing engine):
- **KESTREL** reads the manuscript like a first reader: observes,
  grades continuity and claims, touches nothing.
- **LOOM** weaves the draft: writes and mends in-canon, invents nothing.
- **OATH** keeps the canon: lore, names, continuity — nothing passes
  unnamed, nothing contradicts ungranted.

Further domains instantiate the same way: name the domain, state each
seat's local coloring, keep the vows.

## 13. Decision gates for Chauncey

- **DC-1 — Seat the 4th and 5th seats?** RELAY and MEND are named and
  housed but unseated. Seat them now, later, or never?
- **DC-2 — First mission.** What is the court's first real mission once
  built? (A proving mission keeps the design honest.)
- **DC-3 — Court name.** ✅ DECIDED 2026-09-29: **TRIVIUM**.
- **DC-4 — Tool warehouse scope.** Which tools may the court operate on
  day one — the full shared pool, or a named subset?
