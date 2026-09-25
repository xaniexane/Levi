# KFX² — AI app-builder brands: teardown + our production plan

Date: 2026-09-21. Chauncey ordered: look up and analyze Emergent, run the
signature on the other top builder brands, move planning into production.
Public secondary sources only. Pricing/features below are third-party
reported and change often — verify against live pages before acting.

## 1. EMERGENT (emergent.sh) — deep dive

**What it is.** YC-backed AI full-stack app builder ("vibe coding" platform).
You describe an app in plain English; autonomous multi-agent systems
(frontend, backend, design, testing, deployment agents) build a working
web app and deploy it. Reported backers include Lightspeed, Together Fund,
Prosus (claimed, YouTube). Reported scale: 6M+ founders, $15M ARR in 90
days, 180+ countries (claimed — treat as marketing).

**What it actually builds.** Full-stack web apps (React/Next.js frontend,
FastAPI/Node backend, Supabase database), auth, Stripe/PayPal payments,
hosting, custom domains — all inside one AI-driven workflow. Also builds
mobile apps via Expo/React Native from the same conversation (camera,
location, push notifications, sensors); no Flutter/native Swift/Kotlin.
10k+ community custom agents claimed. MCP Connector lets you drive
projects from ChatGPT or Claude. 1M-token context window on Pro; editable
system prompts and custom agent creation on Pro.

**Workflow.** Describe → agents plan/build/test → refine by chatting →
deploy. Notable: it asks clarifying questions when confused (forces the
user to sharpen requirements); has per-project credit budgets in Advanced
Controls to cap runaway consumption.

**Pricing (third-party reported).** Free: ~10 credits/mo. Standard:
$20/mo, ~100 credits, private hosting, GitHub integration, extra credit
purchases. Pro: $200/mo, 750 credits, premium integrations (Stripe), beta
access, priority support, more powerful machine. Enterprise: custom. A
deployed app consumes ~50 credits/month on their managed infrastructure —
so a Standard plan's 100 credits gets tight when you're both hosting live
and still building.

**Strengths.** Fastest credible prompt→live-app for full-stack; real,
ownable code (GitHub sync, VS Code server access); backend/auth/payments
handled, not left as homework; mobile from the same conversation; asks
clarifying questions; multi-agent planning handles complex structures
better than single-shot generators.

**Where it bleeds.** The #1 complaint everywhere: **credits burn faster
than expected, especially in debugging loops** — the AI keeps consuming
credits on every failed attempt to fix its own mistakes ("paying for a
system that gets worse the more you use it"; one user: 110 credits gone in
a day with no working app). Paying for changes reported "done" that weren't
implemented; unforgiving refund policy once credits are spent; data-loss
reports (entire projects disappearing, weak support recovery — back up to
GitHub immediately); support quality inconsistent; unpredictable
generation; not enterprise-grade reliability.

**Moat assessment.** Speed + full-stack-in-one-flow + GitHub ownership.
No structural moat: it rents frontier models, marks up inference as
credits, and hosts your runtime. Its margin problem is visible in the
pricing — deployed apps are a monthly credit tax.

## 2. The other five, tighter

### Lovable (lovable.dev)
Formerly GPT Engineer. Design-led web-app builder: prompt → React +
TypeScript + Tailwind + shadcn/ui, Supabase backend, one-click deploy,
GitHub sync, visual editing, Figma import. Reported: $20M ARR in 2 months
(claimed, fastest in European startup history). Pricing reported: Free
5/day (30/mo cap, public projects), Pro $25/mo (~100 credits), Teams
$30/mo shared pool, Business $50/mo (SSO, privacy controls), Enterprise
custom. Strengths: easiest start for non-coders, clean modern stack,
predictable-ish pricing vs Emergent. Bleeds: credit-based debugging loops
("wasting credits fixing its own mistakes"); changes break existing
functionality; non-technical users can't maintain output without code
knowledge; web-only; Trustpilot carries a consumer alert for removed fake
reviews. G2 4.4/5.

### v0 by Vercel (v0.app)
AI UI-component generator: prompt → production-ready React/shadcn/Tailwind,
trained on Vercel's design system; v0-1.5-lg with up to 512K context;
AutoFix streaming post-processor; one-click deploy to Vercel. Pricing
reported: free ~$5 credits/mo; former $20 Premium gone for new users —
collaborative paid access starts ~$30/user/mo. Strengths: best-in-class UI
code quality, design-system aware, fastest mockup engine. Bleeds: the
"pay-per-mistake" model is the community's top complaint (charged for every
prompt including retries of the AI's own errors; credits "disappearing in
hours"); small changes cause unintended rewrites; loops/claims of applied
updates that weren't; V0 watermark complaints; Next.js/Vercel-only gravity;
no real backend story.

### Bolt.new (StackBlitz)
Prompt → full app in the browser: live WebContainer runtime, multi-framework
(React/Vue/Svelte/Astro), file-level visibility + terminal, ZIP export,
Expo mobile targeting. Open-source core (bolt.diy). Reported: $40M ARR in
6 months (claimed). Pricing reported: token-based — Free 1M tokens/mo
(300K daily cap), Pro $25/mo ~10–13M tokens, tokens roll over one month.
Strengths: best in-browser dev environment, framework flexibility, code
transparency, open-source escape hatch. Bleeds: token costs spike during
debugging; no built-in auth (backend setup is yours); preview instability
on complex builds; hands you a project, not a finished product.

### Replit Agent (Replit)
Not an agent that emits code — a full browser IDE with an agent inside it:
PostgreSQL/Neon, key-value storage, Deployments hosting, real-time
collaboration. Pricing: effort-based — Core $25/mo ($20 annual) includes
$25 usage credits; Pro $100/mo; Agent checkpoints ~$0.06 simple to $1+
complex (reported July 2026). Strengths: most capable for API-heavy/backend
work; zero local setup; end-to-end build-test-deploy. Bleeds: the
Agent 3 + effort-based pricing backlash — cost unknowable before the task
runs, charged on failure ("pricing casino"); The Register documented users
hitting ~$1,000/week; agent refactors code it wasn't asked to touch;
real lock-in to Replit infra; online-only, no offline mode; support and
billing-dispute complaints; Trustpilot horror stories (agents "lying,"
changing things unasked).

### Base44 (Wix)
Prompt → hosted full-stack web app in under a minute: built-in database,
auth, hosting, no external setup. Wix acquired June 2025 — reported $80M,
Wix's filing says $92.158M total consideration ($18.058M cash + $74.1M
contingent). Reported scale: 2M+ users, ~$150M ARR as of May 2026
(claimed). Pricing reported: Free 25 message credits/mo (5/day); annual
plans $16/40/80/160 mo (Starter/Builder/Pro/Elite); message credits +
integration credits. Strengths: fastest speed-to-live, everything included,
design quality, SOC 2 Type II/ISO 27001. Bleeds: **backend stays on Base44
infrastructure** — GitHub sync (Builder+, Dec 2025) exports frontend only;
replacing the backend is a separate engineering project (the runtime you
don't own); Trustpilot ~2.2/5 on credit consumption and reliability; Wix's
own filing warns AI infra costs are "substantial" and LLM-developer
competition could limit monetization — the margin problem, admitted in
print. Founder response: building "Base 1," their own domain model, to own
the stack and the margin.

## 3. The pattern underneath

**What they all get right (the absorb list).**
- Prompt→working-app is real and the demo moment converts: minutes from
  idea to live URL.
- Conversational iteration beats re-scaffolding: refine-by-chatting is the
  core loop.
- Full-stack-in-one-flow (auth + DB + deploy handled) is what separates
  builders from UI toys.
- Code you can take with you (GitHub sync/export) is now table stakes —
  the market punishes lock-in rhetorically even when it practices it.
- Clarifying questions and scoped prompts stretch every budget — the best
  UX innovation is making the user think before spending.

**Where they all bleed (the reversal surface).**
1. **Credit/token metering with misaligned incentives.** Every vendor
   profits from your debugging loops — including loops caused by their own
   errors. Users pay per mistake, including the AI's. This is the single
   most hated pattern in the category.
2. **Unpredictable cost.** You cannot know the price before the task runs
   (Replit's effort-based pricing is the extreme); credits vanish in
   debugging spirals; top-up economics punish iteration — the exact phase
   where a builder should be cheapest.
3. **The runtime you don't own.** Base44 keeps your backend; Replit keeps
   your infra; Emergent taxes deployed apps monthly. Export exists, but
   the live thing stays theirs.
4. **Code quality on large builds.** All of them degrade past a complexity
   threshold: unintended rewrites, loops, claimed-but-not-applied changes,
   context loss. Nobody has solved "big app stays coherent."
5. **No offline story.** Every one is cloud-only. No building on a plane,
   no building where connectivity is thin or surveilled.
6. **Amnesia between sessions.** The builder forgets you. No relationship,
   no accumulated knowledge of your project, your taste, your patterns.

## 4. KFX² — strengths amplified to unreplicable

Our physics: local-first, deterministic, no per-unit metering games. Every
move below is something their cost structure forbids.

1. **Kill the credit meter on generation.** Their margin problem (Wix's
   filing admits it) is renting frontier inference and reselling it by the
   drop. Ours runs on LEVI's own offline brain + local toolchain: the cost
   of a build is compute you already own. No credits, no tokens, no
   "pricing casino." They cannot follow without abandoning their revenue
   model.
2. **Never charge for our own mistakes — the honest retry law.** Bounded,
   deterministic verify loop: generated code must pass build + tests before
   it's shown; retries inside the bound are free by construction (there is
   no meter to charge). "I broke it, I'm fixing it free" as architecture,
   not policy. Their incentives make this impossible; ours make it
   automatic.
3. **You own the runtime, not just the code.** Local-first means the built
   app runs on your machine and your phone — no monthly credit tax to keep
   it alive, no backend held hostage (Base44's exact trap), no infra
   lock-in (Replit's). Export isn't a feature; there's nothing to escape
   from.
4. **Offline-capable building.** None of the six works offline. Ours does:
   on-device brain, local templates, local toolchain. Build on a plane,
   in a dead zone, under surveillance. A whole geography of users they
   structurally cannot serve.
5. **The builder remembers you.** Their builders have amnesia; ours is an
   organ of LEVI — journal, growth loop, accumulated knowledge of your
   projects, your taste, your patterns. The tenth app you build starts
   where the ninth left off. Unreplicable without the organism.
6. **We take a cut when you win, not when you type.** Marketplace economics
   (Chauncey's law: 12% on digital products created and monetized on our
   platform) replace credit rent. Our incentive is your app succeeding;
   theirs is your debugging loop never ending. Alignment as moat.
7. **Deterministic honesty in output.** Generated apps ship with provenance
   (what the builder made vs what you wrote), a security baseline pass,
   and no fake claims — the same honesty discipline as the rest of the
   platform. They ship "it works (probably)"; we ship "here's exactly what
   it is."

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: **we offer what they do, what they don't, and do
it even better, and for fraction of fractions.** Match every builder
feature-for-feature plus what they don't offer, better built, at radically
lower prices. Dollar-scale entry, volume over margin.

**Competitor features → our parity.** Prompt→working-app is the scaffold
engine (Phase 1); conversational refine-by-chatting is the refine loop
(Phase 3), with change-scoped diffs that cure the v0 "unintended rewrite"
disease; full-stack-in-one-flow (auth + DB + packaging handled) matches
Emergent's one-flow promise without the cloud; code you take with you is
absolute — it's local, so there's nothing to export *from*; clarifying
questions and scoped prompts are absorbed as the cost-free UX innovation
they are; one-tap packaging to web bundle + Android APK on your own machine
(Phase 4).

**Competitor gaps → our exclusives.** What none of the six can sell without
abandoning their revenue model: no credit/token meter, ever — builds run on
LEVI's own offline brain and compute you already own, so the category's #1
complaint (paying for their AI's debugging loops) has no meter to bill
through; the honest retry law — generated code passes build + tests before
it's shown, retries free by construction; you own the runtime, not just the
code — no monthly credit tax to keep a deployed app alive, no Base44-style
hostage backend; offline-capable building (none of the six works offline);
and a builder that remembers you — journal, growth loop, the tenth app
starting where the ninth left off, against their universal amnesia.

**Our price as a fraction of theirs.** Third-party reported competitor
pricing (per this doc's own caveat: verify against live pages before
acting): Emergent $20/mo Standard, $200/mo Pro; Lovable $25/mo Pro;
v0 ~$30/user/mo paid access; Bolt $25/mo Pro; Replit $25/mo Core; Base44
$16–160/mo — every one a meter that profits from your debugging loops.
Ours: zero build meter. We take 12% on digital products you monetize on our
marketplace (Chauncey's law) — a cut when you win, not when you type.
Dollar-scale entry, volume over margin; entry mechanics gated on his
per-action approval.

## 5. Production-phase plan — our builder play

**Product home (gated on Chauncey): Hicomb-embedded, recommended.**
The builder should live inside Hicomb (our from-scratch code editor) as a
"describe → scaffold → refine" mode — prompt builds the project, the same
editor refines it, no handoff between tools. Standalone only if he wants a
separate brand. (Links to HICOMB_KFX2_PRODUCTION.md in the main program —
this doc covers the builder competitive set; that doc covers the editor.)

**Sequenced build order.**
- **Phase 1 — Scaffold engine.** Prompt → project skeleton from LEVI's
  deterministic templates (stdlib-first stacks, local toolchain). No
  model needed for structure; the brain fills logic. Milestone: "describe
  a CRUD app, get a running local project."
- **Phase 2 — Verify loop.** Generated code must build + pass generated
  smoke tests before presentation; bounded retry budget, free by
  construction. Milestone: zero "it looked done but wasn't" deliveries.
- **Phase 3 — Refine loop.** Conversational iteration inside Hicomb, local
  model assist, change-scoped diffs (no unintended rewrites — the v0
  disease, cured by determinism). Milestone: tenth iteration as coherent
  as the first.
- **Phase 4 — Package.** One-tap local packaging: web bundle + Android
  APK via the existing toolchain notes; runs on-device, offline.
  Milestone: prompt → installed app on the phone, no cloud touched.
- **Phase 5 — Marketplace hookup.** Publish built apps to our marketplace;
  12% house cut on monetized digital products. GATED: payments, legal
  review, customer release — all need Chauncey's explicit per-action
  approval.

**Gated on Chauncey:** product home (Hicomb-embedded vs standalone),
marketplace launch, any payment wiring, any customer-facing release.
**Hard nos:** no credit/token metering ever; no cloud-held runtime; no
shipping generated code without the verify loop passing.

## Honest limits
- All competitor pricing/features are third-party reported (Sept 2026
  sources); verify live before quoting.
- Emergent's scale/backer/ARR figures are marketing-claimed, not audited.
- Base44's $150M ARR / 2M users and Bolt's $40M ARR are claimed figures.
- No hands-on testing was performed on any of the six; sentiment is drawn
  from reviews, Reddit threads, and press.
