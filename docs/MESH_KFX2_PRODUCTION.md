# KFX² — Off-Grid Mesh Tower Hardware — absorb, reverse, amplify, return unreplicable

Date: 2026-09-21. Workstream 11 of 13.
Frame: Chauncey's KFX² law — absorb the outside pattern (strengths as well
as weaknesses) → reverse it → improve it → return a version only we could
build. Frame docs: `PLAIGROUND_CRUSHON_KFX2.md`, `PLAIGROUND_GIANTS_KFX2.md`.

Product: long-range, infrastructure-independent mesh communication nodes
for communities — the LEVI mesh tower. This doc covers capability design,
software/protocols, and the path to prototype. It ends at the gate.

**GATE STATUS (standing): any hardware purchase, any prototype build, and
any field test are GATED on Chauncey's explicit word. This document
authorizes none of them.**

---

## (a) Competitor teardown

Honesty rule throughout: every fact below comes from a public secondary
source named inline. Anything I could not verify is marked COULD-NOT-VERIFY.
Nothing is invented.

### Meshtastic

- **What it is (per its own docs, meshtastic.org):** an open-source (GPL)
  project that turns LoRa radio boards into a multi-hop messaging mesh.
  Firmware is flashed onto commodity boards; the phone pairs over
  Bluetooth and the board does the radio work.
- **Radio/protocol (as publicly stated):** LoRa, sub-GHz ISM bands —
  915 MHz in the US, 868 MHz in the EU, 26 regional variants cited by
  community docs. No license required to operate in the US on 915 MHz
  (per community guides; FCC Part 15 assumption). Multi-hop forwarding:
  messages between non-adjacent nodes are relayed by nodes in between.
- **Encryption (as publicly stated):** AES-256 for channel messages;
  Curve25519 + AES for direct messages (PKC). Public channels default to
  a well-known default key — i.e. public channels are effectively public.
- **Range (as publicly claimed):** typically 5–15 km per community guides;
  the claimed all-time record is 331 km (205 miles) under optimal
  conditions. Real-world user reports (Hacker News, forums) cluster at
  2–10 km, strongly dependent on elevation/line-of-sight.
- **Hardware/cost (community-sourced):** bare boards typically $25–60;
  starter kits $30–150 (antenna, USB cable, case included). Popular
  platforms: LILYGO T-Echo (~$50), Heltec WiFi LoRa 32 V3 (~$18),
  RAKwireless WisBlock (RAK4631/RAK3312 starter kits ~$27–40). Solar roof
  nodes are common DIY builds (~$83 in one documented build: panel,
  MPPT, battery, enclosure, antenna).
- **App UX:** Android, iOS/iPad/macOS, web, Python CLI/SDK clients exist.
  The recurring user complaint (thesecuredad.com guide, 2026; HN threads):
  the Android and iOS apps feel like different products — mapping,
  node discovery, and features are inconsistent between them. MQTT relay
  is useful but flaky (messages don't always arrive; DM-over-MQTT behavior
  varies). "Delivered" ticks don't reliably mean the human got the
  message. The honest summary from HN: think bidirectional pager, not
  sat-phone replacement — short texts, latency up to ~40–50 seconds.
- **Use cases users actually report:** hiking/hunting party comms, solar
  roof repeaters, disaster-response coordinating (one community account
  cites Meshtastic staying up during the April 2025 Portugal–Spain
  blackout — COULD-NOT-VERIFY from independent reporting).
- **User love:** no license, no fee, no account; power sipping (days to
  weeks per charge); maker-customizable; community-owned feel — running a
  node contributes to a shared mesh. Scale is real: community sources
  claim well into six figures of nodes deployed worldwide (COULD-NOT-VERIFY
  independently).
- **User hate (documented security findings):**
  - CVE-2025-52464 (CVSS v4 9.5, reported 2025): duplicated X25519 key
    pairs across production batches — vendors cloned a "golden image"
    after first-boot key generation, plus low-entropy key generation on
    some platforms. Enabled DM decryption and remote node hijack for
    affected batches. Patched in firmware 2.6.11.
  - DEF CON 2025 research (project's own blog): NodeInfo packets can be
    spoofed (name/metadata overwrite on others' node lists); PSK channels
    lack message verification, so anyone holding the PSK can inject
    messages that appear to come from other users.
  - A contributor comment thread on meshtastic.org's own encryption page:
    DM encryption has no forward secrecy, no big red box warning users
    that DMs are not E2E-private without key management discipline.
- **Structural weakness (our read):** it's a *device project* — the
  intelligence lives on the phone app, the radio is a dumb relay, and the
  security story depends on the weakest link in an open hardware supply
  chain. Range claims are honest only with elevation; most users get
  practical, not romantic, range.

### goTenna

- **What it was (consumer line):** goTenna Mesh — a 1-watt UHF device
  (~1.7 oz, wand form, BLE pairing to phone) that created a mesh for
  texts and GPS locations. Claimed up to 4 miles; realistic 1–3 miles
  point-to-point per retailer specs. Features: private 1:1, group chats,
  public emergency "Shout" broadcasts, free offline maps, stationary
  relays, end-to-end encryption claimed with no central data store.
- **Pricing (historical):** pre-order era ~$129/pair rising to $179/pair;
  current resale/clearance listings show ~$30 single units and ~$155
  pairs (COULD-NOT-VERIFY what these reflect — likely end-of-line or
  used stock). goTenna Plus was a $9.99/year subscription (topo maps,
  trip stats, SMS relays).
- **Where it went:** the company pivoted hard to public sector. goTenna
  Pro ($499) — 5-watt variable output, software-defined tunable VHF/UHF
  (142–175 MHz & 445–480 MHz), MILSPEC/IP68, 60+ hour battery, fleet
  management portal, integrations with Android Tactical Assault Kit —
  and the ProX line, selling to defense, public safety, wildland
  firefighting, NGOs. TechCrunch (2019): consumer was "a small part of
  our business compared to the public sector."
- **Status of the civilian line:** per an independent security research
  report (dollarhyde/gotenna_v1_and_mesh_vulnerabilities, 2025), the
  vendor discontinued the entire civilian market (v1 + Mesh) around the
  time the ICS advisory ICSA-24-270-04 released. COULD-NOT-VERIFY from
  an official goTenna announcement — treat as reported, not confirmed.
- **Security findings (that same report, CVE-2025-32888):** hardcoded
  verification token in the goTenna app for sending SMS through goTenna
  servers (reported to vendor 2017–2018, acknowledged); additional
  hard-coded credential issues on the Mesh firmware.
- **Structural weakness (our read):** proprietary, phone-tethered gadget
  sold as a pair; the company abandoned the consumer who bought into
  "your own network" when the margin moved to defense. The mesh only
  exists where other gadget-owners are. No continuity, no local
  intelligence — just a radio strapped to a smartphone.

### COULD-NOT-VERIFY list (open items, not claims)

- Meshtastic: exact node count worldwide; current official pricing of
  any specific kit; current maintainer roadmap post-2026; independent
  confirmation of the Portugal–Spain blackout account.
- goTenna: official confirmation of civilian-line discontinuation;
  current availability/support of Mesh app on app stores; Pro pricing
  beyond the $499 figure from older reporting.
- Neither: any official long-range tower-grade (mast-mounted,
  community-coverage) product — both sell/serve handset-adjacent devices.

---

## (b) KFX² — our return

### ABSORB — patterns worth taking

1. **Meshtastic's community-mesh physics.** Open firmware, multi-hop
   forwarding, license-free ISM operation, solar/battery sipping. The
   *mesh as commons* is the right physics — we adopt the shape.
2. **Meshtastic's roles model.** ROUTER/REPEATER role firmware — nodes
   that exist to serve, not just to talk. We adopt and extend: our
   tower nodes are infrastructure-first by design.
3. **goTenna's product thinking.** A wand you clip on and forget, BLE
   pairing that just works, offline maps bundled with the radio,
   "Shout" as a first-class emergency primitive. We adopt the
   *ergonomics of trust* — the thing must feel reliable before it is
   used in a crisis.
4. **goTenna Pro's lane discipline.** One product for consumers, one
   hardened product for institutions — each honest about what it is.
   We adopt the split: community tower (civil) and the hardened variant
   question stays parked until legal/security review says otherwise.
5. **Both's store-and-forward primitive.** The network works without
   contemporaneous connectivity. We adopt it as the foundation of
   everything below.

### REVERSE — their weaknesses, flipped

| Their failure | Our reversal |
|---|---|
| Range is romantic in marketing, practical (2–10 km) in the field | Towers, not pocket radios: elevated, high-gain, solar-fed mast nodes as the unit of coverage. Honest range math published per install, not a global claim |
| Phone-tethered apps: dead phone = dead node | The tower is the node. LEVI runs ON the tower — local intelligence, not an app accessory. A phone is a client, never a dependency |
| Meshtastic's open supply chain cloned keys across batches (CVE-2025-52464) | Deterministic, per-device key provisioning at first boot with a hardware-entropy gate — a tower that can't prove it generated its own keys doesn't join the mesh |
| No forward secrecy, no auth on PSK channels (Meshtastic); hard-coded tokens (goTenna) | Authenticated channels by default; identity-bound key exchange; spoofed nodeinfo rejected at the protocol layer, not the app layer |
| goTenna abandoned its civilian users for defense margins | Community-owned infrastructure: the towers belong to the neighborhood that raises them. No pivot is possible — the ownership is the architecture |
| Android/iOS app fragmentation (Meshtastic) | One client contract: the tower exposes a single protocol; clients are thin renderers. Fragmentation dies where the intelligence is centralized on-node |
| Gadget sales as the business model | Towers as infrastructure: sold/installed once, owned locally, no subscription to keep talking (goTenna Plus's $9.99/yr is the exact anti-pattern) |

### AMPLIFY — their strengths, made unreplicable

1. **Their device-as-radio → our tower-as-organ.** Meshtastic's radio is
   dumb; the phone is the brain. We invert it: the tower carries LEVI's
   local intelligence. Store-and-forward with on-node smarts — message
   triage, priority queuing (emergency beats chatter), delay-tolerant
   routing decisions, local directory services — executed on the tower,
   with no cloud relay anywhere in the loop. UNREPLICABLE: their cost
   structure assumes a cloud/app backend; our architecture has no
   backend to pay for, so we have no per-message, per-seat, or
   per-feature scarcity to monetize.
2. **Their mesh-as-gadget-network → our mesh-as-commons.** Meshtastic
   proved people will run infrastructure for each other. AMPLIFY: the
   tower is community property by design — neighborhood-owned, with
   local governance of channels and keys (the "who runs the tower" is a
   social question our design answers, not a support ticket). UNREPLICABLE:
   goTenna's model required abandoning consumers when defense paid more;
   a commons can't be pivoted away from its owners.
3. **Their emergency use-case → our emergency-first doctrine.**
   goTenna's "Shout" and Meshtastic's disaster-response reputation are
   the proof that off-grid comms earn trust in crises. AMPLIFY: the
   tower's firmware treats emergency broadcast as a first-class
   protocol primitive with reserved airtime — not a feature in an app,
   but physics in the radio. UNREPLICABLE: proprietary silos can't
   interoperate in a real disaster; an open protocol with authenticated
   priority channels can.
4. **Their maker energy → our honest hardware story.** The DIY solar
   roof node is already the community's favorite object. AMPLIFY: we
   publish the full tower reference design (enclosure, power budget,
   antenna, mounting) — the tower is inspectable, repairable, and
   rebuildable by its owners. UNREPLICABLE: a sealed gadget's margin
   depends on you not opening it; our margin (such as it is) depends on
   you understanding it.
5. **Their "no license, no fee" promise → our no-rent permanence.**
   Meshtastic's appeal is no carrier, no SIM, no bill. AMPLIFY: no
   subscription, no account, no cloud — the tower talks because physics
   allows it, and nothing can be switched off remotely. UNREPLICABLE:
   any competitor with a server bill must eventually charge rent; we
   have no server, so the rent is zero forever.

**Return-to-sender line:** everything they ration — range (by device
form factor), intelligence (by phone app), trust (by vendor continuity),
and access (by subscription) — we ship as physics of the tower, because
our architecture made their scarcities unnecessary.

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: we offer what they do, what they don't, and
do it even better — at a fraction of their fraction. The slate matches
every competitor feature-for-feature PLUS what they never offered,
built better, at radically lower prices. Dollar-scale entry, volume
over margin.

**Competitor features → our parity (drawn from the teardown above):**
multi-hop mesh forwarding, license-free ISM operation (915 MHz US /
868 MHz EU as the documented baseline), solar/battery-sipping nodes,
router/repeater role nodes that exist to serve, store-and-forward for
disconnected operation, the emergency broadcast primitive (their
"Shout"), BLE pairing ergonomics and the feel of a thing you clip on
and trust, end-to-end encryption on channels and DMs. The mesh-as-
commons physics they proved — we adopt the shape, not the gadget.

**Competitor gaps → our exclusives:** the tower is the node — LEVI
runs ON the tower, so a dead phone never kills the network (their
intelligence lives in a tethered app); community-owned infrastructure
by design, so no goTenna-style pivot away from the civilians who built
it; per-device key provisioning with a hardware-entropy gate and
forward secrecy, written against CVE-2025-52464 and the DEF CON
findings as explicit threat models (their keying broke across cloned
batches); emergency as a first-class protocol primitive with reserved
airtime, not an app feature; honest range math published per install,
never a global romantic claim; one thin-client contract so
Android/iOS/web can't fragment; and the full tower reference design
published and repairable — their margin depends on a sealed gadget,
ours depends on you understanding it.

**Our price as a fraction of theirs:** no price anchor is set in this
document — NO purchase, prototype, or field test is authorized; every
dollar spends at Gate 1 on Chauncey's word only. Theirs — Meshtastic
bare boards typically $25–60, starter kits $30–150 (community-sourced),
a documented DIY solar roof node at ~$83; goTenna Mesh $129/pair
pre-order rising to $179/pair (historical), clearance/resale listings
~$30 single / ~$155 pair (COULD-NOT-VERIFY what those reflect), goTenna
Plus $9.99/yr (the exact anti-pattern), goTenna Pro $499
(public-sector, observed — the defense lane is not entered). The
doctrine's binding law for this lane: no rent, ever — no subscription,
no account, no cloud, no per-message — because the tower talks by
physics, and nothing can be switched off remotely.

---

## (c) PRODUCTION-PHASE PLAN — sequenced, gated

Everything below is docs and design until a gate opens. NO code yet
(docs-only workstream); NO commits in this workstream.

### Phase 0 — Protocol & software design (ungated design work)
- Milestone 0.1: Mesh protocol spec — packet format, addressing, hop
  budget, priority classes (emergency reserved airtime), authenticated
  channel handshake, nodeinfo attestation. Interop note: decide the
  Meshtastic-compatibility question explicitly (speak their protocol on
  shared channels? or clean-slate?) — Chauncey's word settles it.
- Milestone 0.2: On-tower intelligence spec — what LEVI runs locally:
  store-and-forward queue policy, delay-tolerant routing, priority
  triage, local directory, power-aware duty cycling. Deterministic,
  stdlib-only, offline-first — same laws as the core.
- Milestone 0.3: Key provisioning & identity spec — per-device keygen
  with hardware-entropy gate, no golden images, forward secrecy design,
  channel auth. Written against the Meshtastic CVE-2025-52464 and
  DEF CON findings as explicit threat models.
- Milestone 0.4: Client contract — one thin-client protocol; reference
  client behavior defined so Android/iOS/web can't fragment.
- Milestone 0.5: Power & RF budget model — honest range math per tower
  class (mast height, antenna gain, TX power within legal limits),
  solar/battery sizing. No romantic numbers; publish the spreadsheet.

### Phase 1 — Hardware evaluation (design + comparison; NO purchase)
- Milestone 1.1: Reference-design shortlist — evaluate commodity LoRa
  modules (Semtech SX1262-class), MCU platforms (ESP32-S3 / nRF52840
  class), solar/MPPT/battery chains, enclosures, mast hardware.
  Paper comparison only.
- Milestone 1.2: Spectrum & legal survey — ISM band rules per target
  region (US 915 MHz Part 15 as baseline), TX power and duty-cycle
  limits, antenna regulations. **Licensing is an OPEN LEGAL QUESTION —
  flagged for counsel before any transmit hardware is selected.**
- Milestone 1.3: Tower reference design document — the full inspectable
  build: BOM, power budget, mounting, weatherproofing. Still paper.
- **GATE 1 → 2:** Chauncey's explicit approval required to spend a
  dollar on parts OR to assemble anything that transmits.

### Phase 2 — Prototype path (ALL GATED)
- Milestone 2.1 (gated): parts procurement — per the approved BOM only.
- Milestone 2.2 (gated): bench prototype — one tower, lab testing,
  protocol conformance against the Phase 0 spec, key-provisioning
  ceremony validated.
- Milestone 2.3 (gated): two-tower field test — controlled range/power
  validation against the honest-math model from 0.5. Licensed-spectrum
  compliance verified BEFORE first transmission.
- Milestone 2.4 (gated): community pilot design — the governance
  question (who owns/maintains a tower) answered on paper before any
  community sees hardware.

### HARD NOS (standing, no exceptions without his word)
- No spectrum-law violations, ever. If a design needs more power or a
  different band than license-exempt rules allow, it stops at the legal
  question — it does not transmit and hope.
- No customer deployment, no "beta in the neighborhood," no
  pre-orders, no crowdfunding — until the legal, safety, and his-five-
  specifics gates all clear.
- No proprietary lock-in on the protocol: the mesh protocol stays open;
  the unreplicable part is our architecture, not a secret radio format.
- No cloud relay in the data path — ever. The day a tower needs our
  server to deliver a message, the design has failed.
- No defense/law-enforcement variant work without a separate,
  explicit authorization (the goTenna-Pro lane is observed, not entered).

### Open questions for Chauncey (not decisions)
1. Meshtastic-protocol compatibility vs clean-slate protocol?
2. First target region for the spectrum survey (US 915 MHz assumed)?
3. Civil-community lane only, or keep a hardened institutional variant
   on the roadmap?
4. Tower ownership/governance model — neighborhood co-op shape, or
   another form?

---

## Honest limits of this document
- All competitor facts are public-secondary-source as of 2026-09-21;
  specs, pricing, and status marked COULD-NOT-VERIFY where I could not
  confirm them. Nothing invented.
- No hardware has been selected, priced firm, or purchased. No code
  written. No prototype exists.
- RF regulatory treatment is a legal question, not an engineering
  assumption — counsel before transmission hardware.
- The tower is a design on paper until Gate 1 opens.
