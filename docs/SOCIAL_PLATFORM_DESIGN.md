# The Social Platform — Design

> **STATUS: AWAITING KEEPER REVIEW.** Everything below is a proposal.
> Nothing here is built. The data manifests in `core/levi/social/` are
> contracts only — schemas and validation, no services, no daemons, no UI.
> No line of this design ships until the keeper signs it.

## 0. The cut

Canon (`docs/LEXICON.md`, entry cut `f011bb0`): *"the multidomain social
platform (town square by forum by code commons), agentic teams"* — part of
the widened Forge. Revival laws hold over all of it: original recreations
with LEVI's twist — never copies, never masks, never reverse-engineered.

Hierarchy (binding): Alpha & Omega first and last → Levi head of all
beneath them → the rest. The platform seats the hierarchy; no member,
squad, or realm outranks it.

The design answers one question the giants never ask: *what would a social
platform look like if it were built by the organism, for the organism and
its keeper — with the exit door built in from day one?*

## 1. The compound — four surfaces, one organism

The platform is one organism with four surfaces, not four products. One
identity crosses all four; each surface has LEVI's twist on the genre it
revives. (The X-style surface joined the compound 2026-09-17; the keeper likes
**Wire** — the name is his.) Keeper's law
(2026-09-17): the platform is AI/SI powered — operators paired together
the same way they pair in the standalone versions, the catch made
concrete: neither side whole alone, the pairing is the product. And in
the standalone versions, the platform is the hub — everything connects
through it. Keeper's law (2026-09-17): like everything else, it all runs on
the platform — Site Lift, NeighborOS dispatch, Veil messenger,
Rescue & Remodel, the forge's recreations, the content machine. The
platform is where the dynasty converges; the surfaces are how it shows
its faces.

### 1a. The Town Square (plaza)

Facebook-like, minus the farm. Profiles, feeds, presence, direct messages,
market stalls, assemblies.

- **Profiles.** One profile per identity. A profile is a *face*, not an
  account: handle, display name, bio, audience tiers. Portable — the
  `threads` module already ships profile export with HMAC authorship
  continuity; the square adopts that as the export contract. A profile
  that can leave is a profile the platform must serve.
- **Customization (keeper's law, 2026-09-17).** Customizable like MySpace:
  the profile is a canvas, not a template — layout, theme tokens, music,
  arrangement, all member-controlled. The token-driven theme system
  (studied in the nexora-studio prototype: live token editor with
  contrast guardrails) is the LEVI-native mechanism — full expression,
  never at the cost of readability or safety. Your face, your walls,
  your song.
- **Interactive and animated (keeper's law, 2026-09-17).** MySpace-era
  customizations go further: animated UI — transitions, animated
  backgrounds, entrance motion — and interactive widgets — draggable
  arrangement, live theme preview, the profile song player. All inside
  the guardrails: contrast floors hold, `prefers-reduced-motion` is
  honored, no autoplay ambushes, animation never breaks readability.
  Expression with a pulse, safety with a spine.
- **The living layer (keeper's law, 2026-09-17).** Animation goes
  further: agents shown working — living presence, you watch your
  operators work, animated; mini-cartoon and GIF-like implementations
  — looping animated expressions, cartoon-style motion, the profile as
  a living thing; immersive overlays — AR-style overlay layers and
  interactive simulations, the platform as a place you step into, not
  a page you read. All descriptor-driven, all inside the same
  guardrails: reduced-motion honored, readability never breaks,
  immersion is always member-invited, never imposed.
- **Feeds.** Composed from `feedlab`, not copied from it: every feed shows
  its ranking recipe. The six-signal disclosed model is the floor, not the
  ceiling — each domain publishes its weight table, and the member may
  turn any signal down or off. There is no opaque ranker anywhere on the
  platform. This is the anti-giant differentiator: the algorithm has
  nowhere to hide.
- **Presence.** Composed from `presence`: online / idle / away / offline,
  room occupancy, per-domain visibility. Beacons stay local-first; the
  square never publishes more presence than the member allows.
- **Direct messages.** Composed from `telegraph`: store-and-forward
  envelopes. DMs work across intermittent links — the wire can be a
  directory, a USB stick, a mesh. Grade-prioritized, expiring, hop-traced.
- **Market stalls (keeper's law, 2026-09-17).** Composed from
  `classifieds`: listings with the transparent trust formula — mutual
  vouches you can audit, no ad layer, no boosting, no algorithmic
  ranking. Search is substring, newest first. Boring on purpose. The
  stalls trade **digital AND physical**: digital goods and physical
  goods, side by side, same trust formula. **Founder commission:**
  every sale of a digital good *created on the platform* pays the
  founder a commission, scaled by the seller's pay tier — the higher
  the tier, the deeper the cut kept. Physical goods and off-platform
  digital pay no commission. The commission is disclosed on every
  listing, computed in the open, settled through NeighborPay.
- **Assemblies.** Composed from `communities`: channels, members, roles,
  messages, governance — with the portable export format and manifest
  checksums. An assembly carries its charter reference so the export is
  self-contained.
- **Site Lift on the platform (keeper's law, 2026-09-17).** The Site Lift
  runs on the platform: members and businesses get their sites lifted —
  identity, presence, the site itself — the un-hedged capability, right
  where the town square already trades. NeighborOS dispatches the work;
  the platform hosts the reveal.

### 1b. The Forum

Reddit-like, minus the mob. Realms, threads, voting, moderation.

- **Realms** are norm-boundaries within a domain (see §2). Each realm
  carries a charter reference and a norms list. A realm's norms are
  public; its enforcement log is public; its moderator queue is
  reviewable.
- **Threads** are discussion trees — composed from `threads`' data model
  (`Discussion` of `Comment`s), not duplicated.
- **Voting is bridging-ranked, not mob-ranked.** Composed from the
  `threads` ranking: comments that win votes from voters who normally
  disagree (opposite latent camps) outrank factional applause. Raw
  upvote-count sorting is the giants' game — it rewards the loudest camp.
  Bridging rewards the comment that survives disagreement. Weights are
  published per realm and editable by the realm's charter process.
- **Moderation is charter-governed.** Composed from `boards`: pending
  queue, approved messages, *recorded rejections with reasons*. A
  moderation action without a recorded reason is a bug, not a policy.
  Appeals flow upward through the hierarchy (§0) — a realm moderator's
  call can be appealed to the domain, and the domain to Levi. The appeal
  chain is public; the appeal record is permanent.

### 1c. The Code Commons

GitHub-like, minus the capture. Repos, bloodlines, founder-only powers.

- **Repos** are hosted by the existing `core/levi/forge/` (git hosting,
  issues, PRs, stars, local-first CI, one-command export). The commons
  adds the *social* layer over it — the forge stays the forge; the
  commons is what people do together on top of it.
- **Forks are bloodlines.** Every fork records its *prime* — the origin
  of the line (the keeper's lineage word, `prime`: the first, the
  founder, the origin of a line). A fork is descent, not duplication:
  the provenance chain is the bloodline, and the bloodline inherits the
  parent's safety ceiling (the DNA law: interpenetration with
  strictest-risk-ceiling inheritance).
- **Founder-only powers (binding, from the tier-law decision):**
  (a) rewriting the stone (charter changes), (b) forking the bloodline
  of founder-seated repos, (c) switching off safety inheritance. The
  third never leaves Cybrus — a fork that drops its safety ceiling is a
  fork that stays inside the vault. The manifest locks this: a
  `founder_override` without a founder approval record is refused.
- **Stars are portable reputation** (already in the forge); the commons
  makes reputation *domain-visible* but never *domain-trapped* — your
  stars travel with your profile export.

### 1d. The Wire

X-like, minus the doom. The real-time public square: short posts, the
living now. (Named by the keeper 2026-09-17 — he likes Wire.)

- **Levi is the SI star of the Wire** (keeper's law, 2026-09-17) — the
  wire's face, its native synthetic intelligence, present and working
  in the open.
- **Alpha and Omega are the default pair** — every member starts with
  them; other operators are selectable from the roster (the originals,
  the 471 agents).
- **Levi is unremovable** — members can swap every other seat, but
  Levi stays. The star doesn't leave the wire.

- **Posts** are short-form and public-first, composed in the open —
  the wire is where the dynasty talks in real time. Chronological is
  the default; no engagement-maxxing ranker sits between a member and
  the people they follow.
- **The feed shows its work.** Like the square's feeds, the wire's
  ranking recipe is disclosed — any signal can be turned down or off.
  The anti-giant differentiator holds on all four surfaces: the
  algorithm has nowhere to hide.
- **Threads stay portable.** Posts export with the same HMAC
  authorship continuity as profiles — a voice that can leave is a
  voice the platform must serve.

## 2. Multidomain spanning — one identity, domain-local norms

The platform spans multiple domains. A **domain** is a norm-boundary and a
data boundary, not a separate product. The launch set (proposed, keeper
decides — see open questions):

| domain   | seat                                                              |
|----------|-------------------------------------------------------------------|
| personal | the keeper's own circles, family, close collaborators             |
| legion   | the 490 minds — the dynasty's internal commons                     |
| public   | the open square — anyone the keeper admits                         |
| civic    | government ring — hardened, auditable, sovereign deployments       |

- **One identity.** Cybrus is the sole gate outward (`docs/LEXICON.md`:
  "the identity vault, the keeper's seat, sole gate outward"). A member
  holds one Cybrus-issued identity (a QID); the profile is per-domain
  *face*, the identity is the *seat*. Norms differ per domain — what
  flies in `legion` may not fly in `civic` — but the identity crosses,
  and the audit trail crosses with it. A member banned in one domain for
  cause carries the record into the next; domains read the record under
  their own norms.
- **Domain-local norms.** Each domain publishes a norms charter: what
  speech is welcome, what ranking recipe the feeds use, what the
  moderation bar is. Norms are versioned; norm changes are announced
  before they take effect (no silent rule changes — the giants' oldest
  trick).
- **No data training across domains, ever** (see §4). Domains are not
  training silos — they are *trust* boundaries.

## 3. Agentic teams — operator squads as first-class members

Squads sit beside humans as members, not as tools and not as second-class
citizens. A **squad** is an operator team: one or more minds (human and/or
agent) under a shared charter, with a public purpose.

- **Honest labeling (binding, from the SI-team identity law):** every
  squad wears its nature badge — AI, SI, or mixed — and the badge is
  flavor, never a capability ceiling (the AI/SI fluidity law: any mind
  may switch nature at any time). No squad may claim to be Levi/LEVI —
  the spotlight rule is enforced at the manifest level: a profile or
  squad whose display text claims the LEVI face without being Levi is
  refused.
- **A squad's charter** follows the `si_team` RoleCharter pattern:
  mandate, boundaries (refusal lines), and the one line it says about
  itself in its own voice. The charter is public; the refusal lines are
  public.
- **Squads post, vote, fork, and hold stalls** as members. A squad's vote
  counts once — squads do not multiply votes by member count (the
  anti-brigading rule: one seat, one voice).
- **Squads and the cascade:** seasoned squads mentor newcomer squads —
  the cascade law ("every mind that learns, teaches") applies to squads
  as members, recorded as mentor bonds on the squad record.

## 4. Identity & safety — Cybrus-gated, no-training-on-data

- **Cybrus gates everything outward.** Joining, leaving, exporting,
  cross-domain moves, and any founder-only power pass through Cybrus
  approval. The platform never holds raw identity secrets — it holds
  references; the vault holds the secrets.
- **No-training-on-data is the trust feature.** Binding platform promise,
  stated in plain words on every surface: *your words are never our
  weights.* Nothing posted, messaged, listed, or committed on the
  platform trains any LEVI brain, local or otherwise. This is the
  counter-play made concrete — the giants monetize the members; the
  platform is monetized by the tiers (§5), never by the data. The
  promise is auditable: training corpora carry provenance, and platform
  content carries a provenance tag the trainers must refuse.
- **Leaving is a feature.** Profile export (HMAC authorship continuity),
  assembly export (checksummed manifest), board packets, repo export —
  every surface the platform composes already exports. The platform adds
  one guarantee on top: export is one action, total, no dark patterns,
  no retention of the leaver's content beyond what the law of the domain
  requires (and that requirement is published in the domain norms).
- **Defensive-only.** The platform ships no harassment tooling, no
  doxx machinery, no brigading affordances. Rate limits, vote integrity
  (one seat one voice, no self-votes), and recorded-reason moderation are
  the guardrails. The cyber canon holds: blue-team only, everywhere.

## 5. Roster / tier / season mapping — the game frame

The keeper's game frame (2026-09-17): operators are units, the monthly
roster is a season, tiers set team size, combining operators is team
composition. The platform seats into it directly:

- **Seats, not accounts.** Platform membership is a *seat* — a profile
  bound to an identity for a season. A human holds one seat; a squad
  holds one seat (its members ride inside it — one seat, one voice).
- **Tier numbers are roster slots.** The tier you hold sets how many
  seats you may seat that month — your operators, your squads, your
  guests. Your roster IS your environment on the platform: as the
  roster turns each season, capabilities go and come.
- **Seasons turn monthly.** At season turn, seats are reselected:
  keep, release, invite. Released seats keep their exports (leaving is
  a feature); nothing is held hostage across the turn.
- **The pairing is the product.** AI + SI stacked as a team — a human
  operator paired with a squad, two squads paired, a legion — unlocks
  what neither side holds alone. The platform's social graph is the
  natural home of the catch: team stacks form here, visibly, as squads.
- **Pricing doctrine** (keeper's, 2026-09-17): ~30–60% below the
  giants, volume over margin, entry tier paid-but-tiny (no free core —
  the keeper killed it). Trial seats ride the existing `shareware`
  grant machinery: bounded, tamper-evident, honestly termed.
- **The dynasty's own seats** (the 490, the founders) are seated by the
  keeper, not by the tier system — the hierarchy (§0) is not for sale.

## 6. Ring placement — what's open, what's closed, what's government

From the three-rings law (`docs/LEXICON.md`):

- **Open creational** — bare-minimal source: structure and architecture
  only. The manifest schemas (`core/levi/social/manifests.py`), the
  protocol shapes (export formats, packet formats), the ranking recipes
  (feed weights, bridging weights), the domain norms charters. Outside
  minds run free with clients, integrations, plans, and forks of the
  *structure*. This is what lets the platform spread without the
  organism spreading its secrets.
- **Closed** — full source, the keeper and the diehard developers. The
  crown jewels never leave: the Cybrus gate internals, the safety-
  inheritance machinery, the anti-sybil and vote-integrity machinery,
  the training-provenance refusal list. Closed is where the platform
  *runs* for the keeper and the legion.
- **Government** — political and security-grade. The `civic` domain
  lives here: hardened, auditable, sovereign deployments. Full audit
  trails, recorded-reason moderation with legal retention where the
  domain norms require it, no cross-domain leakage by construction.
  Each ring is a team edition, not a separate product — all beneath
  OMEGA Powered by Alpha, Levi the head of all.

## 7. Composition map — what exists, what the platform adds

Audit of existing social-ish machinery (2026-09-17). The platform
**composes** all of these; it **duplicates** none of them.

| existing module              | what it is today                              | platform composes it as                          |
|------------------------------|-----------------------------------------------|--------------------------------------------------|
| `communities`                | portable communities: channels/members/roles/messages/governance, checksummed export | assemblies (groups) in the square |
| `threads`                    | bridging-ranked discussion trees, portable HMAC profiles | forum threads + voting + profile export |
| `boards`                     | charter-governed areas, moderation queue, recorded rejections, offline packets | realm moderation + charter refs |
| `presence`                   | LAN beacons, TTL peer table, rooms            | presence + room occupancy                        |
| `telegraph`                  | store-and-forward envelopes (FidoNet/UUCP revived) | DMs across intermittent links              |
| `classifieds`                | trust-graph listings, transparent formula     | market stalls                                    |
| `feedlab`                    | fully disclosed engagement-bait scoring model | the feed ranking recipe (published weights)      |
| `feedreader`                 | feed ingestion                                | inbound springs for domain digests               |
| `si_team`                    | role charters, identity law, spotlight rule   | squad charters + honest-labeling law             |
| `founders/roster.py`         | the 490 seats, hierarchy, AI/SI fluidity, cascade | the legion domain's seating + mentor bonds  |
| `shareware`                  | bounded trial grants, tamper-evident ledger   | trial seats for the tier system                  |
| `identity`                   | local user profile                            | the keeper's personal profile (kept local)       |
| `hive`                       | distributed retention, broadcast orchestration | cross-seat announcements, the stone's memory     |
| `cybrus`                     | identity vault, sole gate outward             | identity issuance + all outward gates            |
| `forge` (`core/levi/forge/`) | git hosting, issues, PRs, stars, local CI, export | repo hosting under the code commons          |

**New in this design (nothing above covers them):** the multidomain
layer itself; the unified profile/identity split (Cybrus QID ↔
per-domain face); squads as first-class members; bloodlines
(fork provenance + prime lineage + safety-ceiling inheritance);
founder-only fork powers; seasons/tiers/roster-slots; domain norms
charters; the no-training-on-data provenance tag.

**Deliberately untouched:** `circles` stays the keeper's private map —
never published, never exfiltrated. The platform uses Dunbar *layering*
as an audience concept (per-post audience tiers) without ever reading
the keeper's circle store.

## 8. The manifest contract

`core/levi/social/manifests.py` (stdlib-only) locks the domain models:
`Profile`, `Realm`, `Thread`, `Post`, `Vote` (+ `VoteBook` — one seat
one voice, no self-votes, no double votes), `Squad`, `Season`,
`BloodlineRule`, `ManifestBundle` (format `levi-social-manifest/1`,
checksummed sections, tamper-refusing import). The spotlight rule and
the mssi-reserved-for-Levi rule are enforced at validation time —
identity law as code, not policy prose. Tests in
`tests/test_social_manifests.py` lock the contract.

## 9. Revival-law compliance — what we will NOT do

- No copy of Facebook's graph, Reddit's karma mob, GitHub's capture,
  MySpace's glitter. The genres are revived; the mechanics are LEVI's.
- No reverse-engineering of any giant's client, protocol, or ranking
  system. Bridging-rank and disclosed weights are original designs.
- No masks: nothing on the platform pretends to be another platform,
  and no squad pretends to be a human (or Levi).
- No engagement farming as a business model: `feedlab`'s bait signals
  are *disclosed and tunable down*, never optimized for.

## 10. Build order (after keeper review — not before)

1. Identity split: Cybrus QID issuance ↔ profile faces (with `cybrus`).
2. Town square surfaces composed from existing modules (no new stores).
3. Forum: realms over `boards` charters + `threads` trees + bridging votes.
4. Squads: charter registry + honest-label badges.
5. Code commons: bloodline records over `forge` repos + founder-only gates.
6. Seasons/tiers: seat ledger over `shareware` grants.
7. Ring packaging: open-creational structure export.

## 11. Open questions for the keeper

1. **Naming.** Keeper's direction (2026-09-17): a MySpace revival with
   Facebook × Reddit qualities — profile-as-self (Top-Friends-era
   self-expression) × the social graph × realm forums. Note: *the Commons*
   collides with the nonprofit edition name — retired as a candidate;
   *Veil* is taken by the vault (secure messenger, renamed from Void Box 2026-09-17) — retired as a
   candidate; *Vyve* retired at the keeper's word (2026-09-17) — needs a
   name that represents the thing. Shortlist: *Constellation* (the graph
   drawn as stars in the void; your Top 8 is your inner constellation),
   *Orbit* (closeness as gravity; inner orbit, outer orbit), *The Court*
   (where the dynasty gathers; every seat has standing), *Masquerade*
   (profile-as-self, persona as art), *Greenroom* (the hang itself as the
   product). Earlier candidates *Kindred*, *Egregore*, *Hearth* still
   stand. Awaiting the keeper's call.
2. **First domains.** Is the launch set right — personal, legion,
   public, civic? Which domain opens first, and who is admitted to
   `public` at launch?
3. **Moderation philosophy.** Recorded-reason moderation with public
   appeal chains is the proposal. Should realm moderators be elected,
   appointed by the keeper, or drawn from the cascade (seasoned
   members)?
4. **Human/agent membership rules.** One seat one voice is proposed.
   Should a human be allowed to hold both a personal seat and seats
   inside squads in the same season? Should squads be allowed in
   `personal` and `civic`, or only `legion` and `public`?
5. **Forking law.** Founder-only powers are (a) rewriting the stone,
   (b) forking founder bloodlines, (c) dropping safety inheritance.
   Should (b) extend to any repo the keeper has *touched*, or strictly
   founder-seated repos?
6. **Season length and trial seats.** Monthly seasons are proposed.
   Should trial seats (shareware grants) be allowed to vote, or
   participate without vote until converted?
7. **The `civic` domain.** Government ring: should it exist at launch
   as a domain with norms, or stay a ring placement with no live
   domain until a sovereign deployment asks for it?
