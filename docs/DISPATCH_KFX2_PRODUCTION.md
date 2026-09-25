# KFX² on the transportation/dispatch lane — SuperDispatch, Motive, Samsara: absorb, reverse, amplify, return unreplicable

Date: 2026-09-21. Workstream 10 of 13.
Product: LEVI Transportation/Dispatch Edition — a thin vertical edition of
LEVI for truck-driver dispatch: load matching, driver communication,
scheduling, paperwork (bills of lading, invoicing), compliance reminders
(hours-of-service awareness). A working tool, not a demo, built on LEVI's
engine. Local-first: the dispatcher's data stays in-house.

Frame docs: `docs/PLAIGROUND_CRUSHON_KFX2.md` (frame v1: strengths absorbed,
weaknesses reversed) and `docs/PLAIGROUND_GIANTS_KFX2.md` (corrected frame:
STRENGTHS amplified into the unreplicable signature, not only weaknesses
reversed). This doc runs the corrected frame on three dispatch-lane
incumbents.

Sources: public secondary sources only (vendor pages, vendor support
articles, comparison sites, review aggregators, trade press). Every pricing
and feature claim below is either sourced or explicitly marked. NOTHING
in this doc was verified firsthand; no product was purchased, no demo was
booked, no sales rep was contacted.

---

## PART A — COMPETITOR TEARDOWN

### 1. SuperDispatch (founded 2013 — auto/vehicle transport TMS)

The closest comp to our lane: a purpose-built vertical for moving vehicles,
with both carrier and shipper sides.

**Core features (per their own site/support pages, 2026):**
- Carrier TMS + Shipper TMS (web dashboard), dedicated Driver App
  (iOS/Android), free Lite plan (loadboard access, driver app basics)
- Super Loadboard — carrier/broker/shipper load matching, with Private
  Loadboard for direct bookings to preferred carrier networks
- eBOL (electronic bill of lading) + digital photo/video inspections
- GPS load tracking, ETA updates, status notifications
- Automated price negotiation; Pricing Insights / Pricing Insights Pro —
  lane-level price ranges, lane volume, 90-day price trends built from
  their marketplace's millions of vehicle moves; also a per-request
  Pricing Insights API
- Billing management, factoring support, QuickBooks integration,
  PDF import + Chrome extension, reporting/analytics dashboard
- Carrier ratings/reviews, verified-carrier monitoring (active
  authority, cargo insurance)
- OEM/EDI integration + AIAG inspections (announced 2026), AutoIMS
  integration for auction customers (announced 2026), Bulk Order tool
  (announced 2026)
- Announced for 2026, not confirmed shipped: anti-fraud scoring engine
  (FMCSA data), "virtual agents" for routine comms, carrier credit card
  with fuel discounts + IFTA reporting, embedded carrier payroll

**Pricing (per their own support/pricing pages — VERIFIED from source):**
- Carrier TMS Pro: SEAT-BASED. First seat $55/month, each additional seat
  $50/month (seat = one active driver or dispatcher). Lite plan free.
- Shipper Pro: starts at $159/month (includes 2 seats).
- Pricing Insights Pro: metered per insight — Tier 1 $50/mo for 20
  insights, up to Tier 7 $2,000/mo for 10,000 insights; shippers get
  3 free lane insights/month, then paywall.
- Pricing Insights API: $0.05–$0.15 per request after a small free tier.

**Hardware requirements:** NONE. Pure cloud + mobile apps. This is their
structural advantage over the telematics giants — but note the trade:
they have no independent vehicle telemetry; GPS tracking is app-based.

**What users love/hate:** Could not verify firsthand sentiment. Comparison
sites position them as the default for auto transport ("THE MARKET IS
MOVING TO SUPER" — their own 2026 announcement; they claim 10M+ vehicles
moved in 2025, UNVERIFIED beyond their own press). Recurring criticism in
third-party comparisons: per-seat costs compound as you add drivers and
dispatchers; lane-price intelligence (their best data asset) sits behind
a metered upsell, so the value of their own network's data is
pay-per-look for the people generating it.

**What this teaches us:** The vertical-focus model works — deep workflow
fit (inspections → eBOL → billing) beats generic TMS. The flip side: their
pricing taxes exactly the growth it enables (more drivers = more seats),
and the dispatcher's own operational data (rates, lanes, carriers) is
harvested into their marketplace's pricing-data business, then sold back
to the dispatcher per insight.

### 2. Motive (formerly KeepTruckin — fleet management / ELD)

**Core features (per third-party fleet guides and review-aggregator
comparison pages, 2026):**
- ELD compliance: HOS logging, automated logbook entries, DVIR,
  DOT roadside-inspection mode, IFTA fuel-tax reporting
- AI dashcams (road-facing + in-cab) with incident detection, driver
  scorecards, automated safety-coaching workflows
- Real-time GPS tracking, geofencing, asset/trailer tracking,
  vehicle diagnostics, idle-time and fuel tracking
- Built-in messaging center: dispatch chats, broadcasts, read receipts
- Smart Load Board — custom load lists by equipment type + location
- In-cab WiFi hotspot, open API + developer portal, app marketplace
- Claimed scale (2021-era, from cost-guide writeups; could not re-verify
  for 2026): 100,000+ companies, 400,000+ connected vehicles

**Pricing (Motive does NOT publish pricing — all figures below are
third-party estimates, UNVERIFIED by Motive itself):**
- Starter ~$25/vehicle/month (ELD basics, HOS, GPS, DVIR, messaging)
- Pro ~$40/vehicle/month (adds scorecards, asset tracking, IFTA,
  analytics) — recommended for 20+ vehicles
- Enterprise ~$50/vehicle/month (200+ vehicles)
- Hardware: ~$150/vehicle gateway upfront; dashcam $100+ upfront plus
  ~$40/month per camera software fee. 10-truck fleet: ~$2,500+ upfront
  hardware before month one.
- Contracts: annual standard; long-term contract cited as a con.
- A 2026 comparison noted a "3-year commitment totals $9,720+" for one
  ELD bundle — illustrative of the lock-in shape, not a Motive quote.

**Hardware requirements:** Mandatory. Every vehicle needs their gateway
dongle; full value needs their dashcam. Bring-your-own-device is not the
model.

**Sentiment (review aggregators, trade press — consistent across
sources):**
- LOVE: interface simplicity — frequently called the most user-friendly
  ELD; driver app easy to learn; quick installation; geofencing + fuel
  monitoring; 24/7 support praised in some reviews; FreightWaves'
  Checkpoint (Aug 2026) named Motive ELD its overall pick for
  owner-operators.
- HATE: connection problems and software glitches interrupting daily
  operations; customer support "unresponsive at times" / "hard to reach";
  contract and sales-team complaints; editing ELD log errors is
  "cumbersome"; per-vehicle monthly pricing "adds up quickly as your
  fleet grows"; advanced features only on pricier plans.

**What this teaches us:** Motive wins on driver-facing UX simplicity — the
person in the cab can actually use it. Its weakness is the hardware-tax +
contract-tax model: the per-vehicle meter punishes fleet growth, and the
annual lock-in converts a tool into an obligation. Data harvest is
structural: cameras, diagnostics, and location stream to Motive's cloud
and feed the AI coaching/marketplace features — the fleet pays Motive,
then Motive monetizes the fleet's data back into product it sells.

### 3. Samsara (publicly traded — enterprise fleet telematics)

**Core features (per review-aggregator comparisons and trade press, 2026):**
- AI dashcams (HD, night vision) flagging distracted driving, tailgating,
  harsh braking, crashes; driver exoneration footage
- Real-time operations dashboards; exception/alert management
- ELD compliance (HOS, DVIR, IFTA) in the same platform
- Sensor ecosystem: trailers, reefers, powered/non-powered equipment
- Vehicle-health telemetry: engine faults, low oil, failing batteries
- Deep integration catalog (ServiceTitan, Fleetio, Oracle Field Service,
  etc.); publicly-traded enterprise posture, sold into trucking,
  construction, field services, government
- Market research of their own (Jan 2026, businesswire): 98% of public-
  sector dashcam users reported insurance-premium decreases — their
  flagship proof point

**Pricing (Samsara does NOT publish pricing — third-party 2026 estimates,
UNVERIFIED by Samsara):**
- Core telematics typically ~$27–$39/vehicle/month on 36-month terms;
  camera licenses extra; hardware ~$150–$350/vehicle upfront (when not
  bundled). A 10-truck fleet with dashcams: ~$4,000–$5,480 upfront before
  the first subscription payment (per a 2026 comparison — arithmetic is
  theirs, mark as unverified).
- Premium tiers (AI dashcam, coaching) cited at $40–$50+/vehicle/month
  by a market overview. SelectHub lists $27/vehicle/month as a starting
  figure.
- Contracts: 36-month terms are "almost always" the model (per a 2026
  buyer-data writeup). Quote-based sales; budgeting requires a sales
  cycle.

**Hardware requirements:** Mandatory and expensive. Vehicle gateways plus
separate AI dashcams per vehicle, self-installed or professionally.

**Sentiment (G2, SelectHub, review aggregators — consistent):**
- LOVE: "transformative" safety results; fewer accidents; insurance
  savings; exoneration footage resolving claims in days not weeks;
  intuitive dashboard; quick initial setup; strong AI-innovation pace
  (analyst score 77/100, highest of the comps seen).
- HATE: "pricing runs high for small fleets that don't need the full
  feature set"; 36-month lock-in; technical support "slow to respond and
  often unhelpful"; frequent updates disrupt settled workflows; reporting
  lags/crashes on heavy data volumes; driver discomfort with in-cab AI
  cameras ("can take time to build trust"); alert overload if not
  carefully configured.

**What this teaches us:** Samsara sells outcomes (fewer crashes, lower
insurance, settled claims) — not software. That's the strongest move in
the lane. But the price of admission is total surveillance economics:
upfront hardware in every cab, per-vehicle meters, three-year contracts,
and the fleet's video/telemetry/location corpus living on Samsara's
cloud — feeding the very AI that justifies the next upsell. Note the
2024 Reuters/Bloomberg Law lawsuit in which Samsara accused Motive of
industrial espionage over its AI dashcam tech — the giants' moat is
proprietary cloud AI trained on customer fleets. That sentence is the
whole opening.

---

## PART B — KFX²

### ABSORB — their patterns, worth taking

1. **eBOL + digital inspections** (SuperDispatch). The dispatch workflow
   is documents: inspection photos → bill of lading → invoice →
   factoring. We absorb the document chain as a first-class local
   pipeline — paper generated on the dispatcher's own machine, stored in
   their own files, printable and emailable. Our version never leaves
   the building; there is no cloud copy to subpoena, leak, or monetize.
2. **Load matching by lane** (SuperDispatch loadboard, Motive Smart
   Load Board). We absorb lane-aware load lists: loads matched to
   equipment type, deadhead distance, and driver preference. Difference:
   our matching runs against the dispatcher's OWN book — their drivers,
   their lanes, their history — plus whatever public boards the owner
   points it at. Nobody else's algorithm sits between a dispatcher and
   their freight.
3. **Driver messaging with receipts** (Motive). Dispatch chats,
   broadcasts, read receipts — absorbed as the driver-comms channel, but
   local-first: the conversation history is the dispatcher's record,
   not a cloud vendor's training data.
4. **HOS awareness** (Motive, Samsara ELD). We absorb the reminder
   shape: hours-of-service awareness that warns before a violation, not
   after. Built on driver self-logging + the dispatcher's own rules,
   NOT a certified ELD device. (Hard-no boundary: see Part C.)
5. **Safety-outcome thinking** (Samsara). They sell fewer crashes and
   cheaper insurance, not dashboards. We absorb the outcome posture:
   the edition's pitch is "fewer deadhead miles, fewer paperwork
   errors, fewer missed pickups" — measurable dispatch outcomes, with
   the ledger to prove them.
6. **Driver-exoneration evidence** (Samsara). We absorb the incident-
   evidence shape: timestamped, structured incident notes + documents
   stored locally. Their cameras watch the driver FOR the company; our
   records defend the driver ON the driver's side.

### REVERSE — their weaknesses, flipped into our strengths

| Their failure | Our reversal |
|---|---|
| Per-seat (SuperDispatch) / per-vehicle (Motive, Samsara) metering taxes growth: more drivers = more bill | No per-seat or per-vehicle meter exists in our architecture. Deterministic local engine — the marginal cost of the 50th driver is ~zero, so there is no 50th-driver tax. One honest price, stated plainly (Chauncey's dollar-scale-entry law: entry is paid-but-tiny, volume over margin) |
| Hardware lock-in: $150–$350 gateways + $100–$400 cams per vehicle, thousands upfront (Motive, Samsara) | No hardware required. Runs on the dispatcher's existing office machine + the driver's existing phone. Hardware integration (ELD dongles, OEM APIs) is a Chauncey-gated future option, never a day-one requirement |
| Annual and 36-month contracts; quote-based opaque pricing (Motive, Samsara) | No contracts, no sales cycle, no quote. Buy the edition, run it. The pricing page is one line |
| Fleet data harvested to the vendor's cloud: your video, location, and rates train THEIR AI and price THEIR data products (all three) | Local-first is the anti-harvest: the fleet's data never leaves the office. We literally cannot build their AI-on-your-data business because we never hold your data — the compromise is structurally impossible for us |
| The dispatcher pays for their own network's intelligence back per insight (SuperDispatch Pricing Insights meter) | Your lane history is YOUR ledger. Rate memory, carrier reliability, lane seasonality — computed locally from your own records, unlimited, no meter |
| Driver discomfort with in-cab surveillance; alert overload (Samsara); glitchy connections interrupting work (Motive) | No always-on surveillance stream, no alert firehose. Reminders and checks are dispatcher-configured thresholds on local data, tuned to one operation, not one platform's defaults |
| Support is slow/unreachable across all three (consistent complaint) | Support is the dispatcher themselves: offline-first, documented, deterministic. No ticket queue to a vendor who already locked you in for 36 months |

### AMPLIFY — their strengths, made unreplicable

Chauncey's correction (2026-09-21): the signature runs on their STRENGTHS
too — amplified, not just weaknesses reversed. This is the main event.

1. **SuperDispatch: vertical workflow depth.** Their strength is the
   end-to-end auto-transport chain — load → inspect → eBOL → track →
   bill → factor — purpose-built, not generic TMS. AMPLIFY: we go one
   layer deeper than a vertical — a DISPATCH LEDGER. Not just documents,
   but the operation's memory: which driver runs which lanes well, which
   shippers pay on time, which lanes die in February, which broker's
   "hot load" always pays cold. Their vertical is a workflow; ours is
   a relationship ledger with the workflow on top. UNREPLICABLE: their
   memory lives in their cloud and serves their marketplace; ours lives
   in the dispatcher's office and serves the dispatcher. They cannot
   build an un-harvestable memory without destroying how they eat.
2. **Motive: the driver can actually use it.** Their strength is
   driver-facing simplicity — the cab-side UX is famously learnable.
   AMPLIFY: LEVI-as-dispatcher that KNOWS the drivers — names, home
   time needs, preferred lanes, equipment, document status — because the
   ledger remembers. The dispatcher asks "who can cover the Tuesday
   Dallas run?" and gets an answer grounded in their own operation's
   record, not a filtered driver list. UNREPLICABLE: their driver
   knowledge is compliance data flowing uphill to the fleet manager's
   dashboard; ours is relationship data staying lateral with the
   dispatcher who earned it.
3. **Samsara: selling outcomes, not software.** Their strength is the
   ROI story — 98% of surveyed public-sector users saw insurance drops;
   incidents resolved in days. AMPLIFY by inversion: we sell the same
   outcome posture — fewer deadhead miles, zero lost paperwork, on-
   time pickups as the measurable promise — but the evidence is the
   owner's own ledger, not a vendor's research report. And the cost of
   the outcome is one honest price with no hardware, no meters, no
   contracts. UNREPLICABLE: their outcomes require their cameras, their
   cloud, their contract. Our outcomes require a laptop and a ledger.
   They cannot sell the outcome without the surveillance; we don't
   need the surveillance to keep the books.

### THE UNREPLICABLE SIGNATURE — only we could build this

- **The local-first dispatch board.** Their fleet cloud vs our office
  ledger: the fleet's data never leaves the building. Their whole cost
  structure (seats, vehicles, cameras, meters, 36-month terms) exists
  to pay for THEIR architecture. Ours doesn't have those costs, so it
  doesn't have those punishments. Return to sender: everything they
  meter through scarcity (seats, insights, cameras, support tiers) we
  ship as physics — because our physics made scarcity unnecessary.
- **LEVI-as-dispatcher.** Not a dashboard — an operator that knows the
  drivers, the lanes, and the paperwork. Memory ledger per driver
  (preferences, home-time, reliability), per lane (rates, seasonality,
  deadhead traps), per shipper (payment behavior). Ask in plain speech,
  get answers from your own records. Their AI coaches drivers for the
  fleet; ours dispatches with the dispatcher.
- **Paperwork as a local pipeline.** eBOL, invoices, inspection records —
  generated, stored, and archived on the owner's machine. Deterministic
  templates (no model roulette on legal documents), versioned, exportable
  to PDF, integrable with their accountant's tools — never uploaded to
  a vendor's cloud to be mined.
- **HOS awareness without the ELD trap.** Reminders grounded in the
  driver's own logged hours and the dispatcher's rules. Honest scope:
  this is AWARENESS, not certified compliance — the legal line is drawn
  in code and in the docs, and it does not move.

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: we offer what they do, what they don't, and
do it even better, for a fraction of their fractions. We match the
dispatch lane's core workflows feature-for-feature, add the capabilities
their architecture forbids them to build, and charge dollar-scale entry
instead of taxing the dispatcher's growth — volume over margin.

**Competitor features → our parity.** Load matching by lane
(SuperDispatch loadboard, Motive Smart Load Board); electronic bills of
lading and digital inspection records (SuperDispatch eBOL); driver
messaging with read receipts (Motive); hours-of-service awareness and
DVIR-style checklist prompts (Motive, Samsara ELD); and the outcome-grade
posture — fewer deadhead miles, zero lost paperwork, on-time pickups —
in Samsara's own idiom of selling results, not dashboards.

**Competitor gaps → our exclusives.** What they don't offer: the
dispatch ledger — per-driver, per-lane, per-shipper relationship memory
the dispatcher keeps, against SuperDispatch's metered Pricing Insights
that sells the dispatcher's own network data back per look; LEVI-as-
dispatcher — plain-speech answers grounded in the operation's own
record, not a filtered driver list; HOS awareness with the ELD trap
removed — warnings before a violation, never a compliance claim; the
anti-harvest guarantee — the fleet's data never leaves the office,
structurally, so their AI-on-your-data business is impossible for us;
and zero metering, zero hardware requirement, zero contracts.

**Our price as a fraction of theirs.** The edition's price is one honest
line under the dollar-scale-entry law (paid-but-tiny entry, volume over
margin) — the exact figure is not yet set in this document and is gated
on Chauncey's word. Against SuperDispatch's carrier pricing of
$55/month for the first seat and $50/month per additional seat (verified
from their own pages), Motive's ~$25–$50/vehicle/month plus ~$150
hardware per vehicle (third-party estimates, unverified by Motive), and
Samsara's ~$27–$39/vehicle/month on 36-month terms plus $150–$350
hardware per vehicle (third-party 2026 estimates, unverified by
Samsara), the fraction is decisive on structure, not just dollars: no
per-seat, per-vehicle, or per-insight meter means the 50th driver's
marginal cost is ~zero, with thousands in upfront hardware eliminated.
Their cloud-plus-hardware physics cannot follow us into that price.

---

## PART C — PRODUCTION-PHASE PLAN

Sequenced build order for the Dispatch Edition as a real product surface
on LEVI's engine. Each phase names its concrete milestone and its gates.

### Phase 1 — The Board (dispatch operations core)
Build: local dispatch board — loads, drivers, trucks as entities in a
SQLite ledger; drag-and-drop scheduling (board UI), status lifecycle
(booked → dispatched → picked up → in transit → delivered → invoiced).
Milestone: a dispatcher can run a full week of loads for a 5-truck
operation end-to-end offline, with the ledger as the single source of
truth.
Gate: none (pure local software).

### Phase 2 — Driver Comms
Build: driver messaging channel — dispatches, broadcasts, read receipts,
status check-ins — with full history in the local ledger. Driver side
runs on the driver's own phone (existing device, no new hardware).
Milestone: dispatcher ↔ driver conversation, load offers accepted in-
thread, all of it archived locally.
Gate: none for local/SMS-style transport. Any third-party messaging
provider (Twilio-class) integration is GATED on Chauncey.

### Phase 3 — Paperwork Pipeline
Build: deterministic document templates — bill of lading, invoice,
inspection checklist, rate confirmation — generated from ledger data,
exported to PDF, versioned and archived locally. QuickBooks-class export
format for the accountant.
Milestone: a delivered load produces a correct invoice in one action;
the full document set for a load is reproducible from the ledger a year
later.
Gate: none. Templates are deterministic (no model generation on legal
documents — hard rule).

### Phase 4 — LEVI-as-Dispatcher (the ledger comes alive)
Build: the memory ledger — per-driver profiles (lanes, preferences,
home-time, reliability), per-lane rate/seasonality memory, per-shipper
payment behavior — queryable in plain speech by the dispatcher.
Load-matching suggestions grounded in the operation's own record.
Milestone: "who should cover the Tuesday Dallas run, and what should we
charge?" answered from the ledger with cited records.
Gate: none for local suggestion. This is ADVISORY — the dispatcher
decides, the ledger informs. No autonomous dispatching claims, ever.

### Phase 5 — Compliance Awareness
Build: HOS awareness — driver self-logged hours + dispatcher rules →
warn-before-violation reminders; DVIR-style pre-trip checklist prompts;
IFTA-relevant mileage summaries from the ledger for the accountant.
Milestone: a driver approaching their hours limit gets a reminder before
it becomes a violation.
Gate: LEGAL REVIEW before any claim resembling ELD compliance, DOT
compliance, or "compliant with FMCSA" language. The edition NEVER claims
to be an ELD. Marketing and UI copy for this phase is reviewed line by
line.

### Phase 6 — Customer Pilot (Chauncey-gated)
Build: pilot packaging — installer, onboarding guide, one-page honest-
limits sheet (what it does, what it doesn't, the ELD line).
Milestone: one real dispatch operation running the edition for 30 days
with a feedback loop.
GATES (all on Chauncey): customer selection, pilot terms, support
commitment, and the five specifics per action for anything external.

### Deferred / Chauncey-gated future
- Any hardware integration (ELD dongles, OBD-II/J1939, OEM telematics
  APIs, dashcams). The edition's value proposition does not require
  them; adding them requires his explicit word and a re-audit of the
  no-harvest posture.
- Any load-board aggregation beyond the dispatcher's own book (public
  boards the owner points it at). No scraping; only owner-authorized
  feeds/APIs.
- Any cloud sync or multi-office feature: the local-first law holds —
  sync, if ever, is owner-controlled and encrypted, never a vendor cloud.

### HARD NOS (standing, non-negotiable)
1. NO ELD compliance claims without legal review. The edition is not an
   ELD, does not connect to the ECM, and no UI copy, marketing, or
   response may imply FMCSA/DOT compliance. The line is drawn in code
   and docs and does not move.
2. NO customer data leaves the building. No telemetry, no analytics
   callbacks, no "anonymous usage stats," no cloud backup by default.
   The anti-harvest posture is the product.
3. NO per-seat / per-vehicle / per-insight metering. The pricing law
   (paid-but-tiny entry, volume over margin) is structural: the engine
   has no marginal cost to meter.
4. NO model-generated legal documents. Paperwork templates are
   deterministic; a language model never fills in a bill of lading.
5. NO autonomous dispatching. LEVI advises; the dispatcher decides.
   Liability for the load stays with the licensed human operation.
6. NO hardware upsell as the growth path. The edition must be complete
   and valuable with zero hardware beyond a computer and phones.

---

## HONEST LIMITS OF THIS DOC

- All competitor pricing for Motive and Samsara is third-party estimated;
  neither publishes pricing, and nothing here was confirmed with either
  company. SuperDispatch's carrier/shipper pricing is from their own
  public pages (stronger), but plans change.
- No firsthand sentiment was gathered — no reviews were solicited, no
  drivers or dispatchers interviewed. Sentiment claims rest on public
  aggregators (G2, SelectHub, trade press).
- The 2024 Samsara-vs-Motive espionage lawsuit is a matter of public
  record (Reuters, Bloomberg Law); its outcome and merits are beyond
  this doc's scope.
- This is a planning document. No code exists, no pilot is scheduled,
  and every gate named above is real.
