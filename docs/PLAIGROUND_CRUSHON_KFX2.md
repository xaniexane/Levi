# KFX² on CrushOn.AI — absorb, reverse, improve, return unreplicable

Date: 2026-09-21. Target: crushon.ai (web-first NSFW character-chat platform,
~700K+ APK downloads off-Play, 6-tier pricing $0–$199.99/mo).
Order: "keep our core but use our kfx2 signature on them… I want it a lot
like that."

Our core is untouchable: the gate (PIN + on/off + minor hard-lock), the
bounds law, depth (journal + earned rapport + recall), local-first
stdlib-only architecture, the Echoverse simulator, stories, wellness.
What we take from them is the *surface richness* — rebuilt on our physics.

## ABSORB — their patterns worth taking

1. **Character cards + discovery.** Profile card, tags, intro text, greeting
   (first message), example conversations for steering. We adopt this as
   Companion Schema v2: name, traits, boundaries (existing) + greeting,
   example dialogue, tags, avatar seed. Difference: ours are private by
   default; publishing to any library is an explicit owner act, never the
   default.
2. **Multi-character / group chat.** They gate it behind Premium+. We adopt
   the *capability* — ensemble scenes with 2+ companions — because our
   simulator already thinks in scenes. No tier wall: it's a scene, not a
   upsell.
3. **Memory pins.** User-pinned memories with priority recall. We absorb
   pins into depth: pinned entries outrank journal recall, still local,
   still never wiped by a backend update (there is no backend update).
4. **Scene Cards / Target Play.** Custom emotional scripts and memory logic
   for steering narrative mid-chat. Maps directly onto our stories engine +
   simulator: user-authored scene frames, saved and replayable.
5. **Inspiration Replies.** AI-suggested user responses when stuck. Ours:
   deterministic suggestion lines derived from companion traits and scene
   state — no model call, no cost, no refusal risk.
6. **Hidden Images / keyword-triggered unlocks.** Gamified image reveals
   tied to story beats. Our photos backend is procedural-local; we adopt
   the *mechanic* (beat-triggered generative art reveals) with honest
   scope — no photorealism claims, no blurred-tier teasing.
7. **Creator economy.** Publish → followers → tips. We adopt the shape but
   route it through PL-05 creator services with Cybrus money flows and
   Chauncey's stated 12% platform cut — contract-grade economics, not
   opaque diamonds with reversible settlements.

## REVERSE — their weaknesses, flipped into our strengths

| Their failure | Our reversal |
|---|---|
| Memory wipes after backend updates; context collapse | Journal + earned rapport + recall, local files, nothing to wipe — continuity is the product |
| Credits vs coins vs diamonds vs packs confusion | One honest price, stated plainly; deterministic engine has no marginal message cost |
| Server-side chats, ad-data sharing, no encryption | Local-first 0600 storage, no ads, no analytics; Veil sealing for anything that leaves the device |
| "Unfiltered" breaks when a routed model refuses | Deterministic engine + bounds law in code — consistent, no mid-chat refusals from a stranger's model |
| Bot replies count against message caps | No per-message metering exists in our architecture |
| NSFW images blurred below ~$50/mo | Procedural art has no tiers — same honest scope for everyone |
| Quiet re-filtering of once-explicit characters | Bounds law is public, in code, and does not move under users |
| No verifiable age gate | PIN + affirmation + minor hard-lock, documented and tested |

## IMPROVE — what "a lot like that" actually ships as

Build order (all behind the existing gate, all local-first):

1. **Companion Schema v2** — greeting, example dialogue, tags, avatar seed.
   Extends `companions.py`; old definitions keep working.
2. **Ensemble scenes** — `chat.py` grows multi-companion sessions; the
   simulator already stages scenes, so group chat is a scene with turns.
3. **Memory pins** — `depth.py` grows pinned entries with recall priority.
4. **Scene frames** — `stories.py`/`simulator.py` grow savable,
   replayable scene cards (their Target Play, our engine).
5. **Beat-triggered art** — `photos.py` grows keyword/beat-triggered
   procedural reveals (their Hidden Images, our honest scope).
6. **Creator publishing** — companions publishable to the PL-05 creator
   layer by explicit owner choice, with the 12% cut and Cybrus settlement.
   Private by default, always.

## UNREPLICABLE — the signature only we can sign

- **Echoverse branching simulator.** Taken / not-taken / wild scenario
  engine. They have chat; we have *scenes that branch*. Nothing in their
  stack does this.
- **Earned rapport.** Depth as an instrument that reads the record instead
  of flattering the owner — not a longer context window, a relationship
  ledger.
- **The gate itself.** PIN + on/off + minor hard-lock + fail-closed
  disable. No competitor ships adult mode as a physical-feeling switch.
- **Deterministic + local.** No model roulette, no server, no per-message
  meter, no 17-permission manifest. Their whole cost structure (caps,
  tiers, blurred images) exists to pay for *their* architecture. Ours
  doesn't have those costs, so it doesn't have those punishments.
- **Return to sender:** everything they monetize through scarcity
  (memory, group chat, images, unfiltered consistency) we ship as
  physics — because our physics made scarcity unnecessary.

## Honest limits

- Voice slots / voice messages: roadmap, not now. No third-party voice
  service enters the pipeline without Chauncey's word.
- Photorealistic image synthesis: not our procedural backend's scope, and
  we don't claim it. The owned-backend question stays open.
- No external model routing, ever — "only our stuff" forbids renting
  their brains to power our product.
- Creator payouts, live payments, and any customer release remain gated
  (legal review, his five specifics per action).
