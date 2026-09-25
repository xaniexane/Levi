# LEVI Master Inventory

**Ordered:** 2026-09-21 — Chauncey ("everything" cataloged; nothing left behind).
**Scope:** every product, capability, system, and in-flight build across the empire — repo + memory.
**Status key:** `live` = running/usable · `building` = code exists, incomplete · `spec` = designed, not built · `parked` = shelved, kept · `gated` = blocked on a named gate · `unverified` = could not confirm.
**Rule:** originals are never modified; hunt analyses never ship as rebuilds of a giant's feature — additions only.

---

## 1. Product lines

| # | Name | What it is | Status | Where | Gate |
|---|---|---|---|---|---|
| PL-01 | NeighborOS | LEVI's local-services workforce: dispatch-first OS for local services (photo job posts, estimates, trusted workers, living business/property records) | spec/building | `core/levi/neighbor/`, `core/levi/neighboros/`, `docs/NEIGHBOROS_SPEC.md` | NeighborPay/live money deferred — business/legal call; launch is his to execute |
| PL-02 | Hunts | The weakness hunt productized: dissect a target, deliver verified findings; deliverable is always an addition | building (research live; productization spec) | `core/levi/perpetual/`, `core/levi/bounty/`, `docs/PRODUCT_LINES.md` | Bounty payouts via Cybrus only (binding); public showcase launch on his word |
| PL-03 | Creation | Alpha creation lab as a product: prompt in → Echo blueprint → Alpha generators → real build dir + manifest | building | `core/levi/hub/`, `core/levi/revival/` | Honest labeling — scaffolds, not production apps |
| PL-04 | Operator Academy | Academy that trains operators on live organs; real learning science, defensive-only | spec/building | `core/levi/academy/`, `docs/PRODUCT_LINES.md` | No credential/accreditation claims |
| — | DemandPulse | Economic-intelligence engine: keyless ingestion → clustering → 5-factor scoring → heatmap + alerts; $6/mo customer product chosen | building | `core/levi/demand/` (engine, alerts, competition intel) | Standalone customer cut not built (zero internal refs required); payment/entitlement undesigned; 10 workflows install awaiting his word |
| — | Trio token | Hicomb/Acode plugin trio sold as a token (not NFT); buyer-facing copy converted 2026-09-21 | gated | `~/workspace/hicomb/trio/` | Payment destination, production key, terms details — all his |
| — | Alpha/Omega hub | The whole hub: orchestrator (Discover→Evaluate→Execute→Track→Optimize→Repeat), CLI + web console, jobs, creation lab, approvals — stdlib-only | building | `core/levi/hub/` (commit `157ecc3`, 211 tests green) | Localhost-only until he says otherwise; canon-doc mapping needs his word; Archive.zip + don't-touch folder unexamined |

## 2. Capabilities

| Capability | What it is | Status | Where | Gate |
|---|---|---|---|---|
| Cybrus | Security & Identity layer: accounts, credential factory, encrypted vault, token engine — Chauncey's own seat | live | `core/levi/cybrus/` | **BINDING: all money flows through Cybrus, no exceptions** |
| Veil (was Void Box) | Secure messenger: stdlib core, keeper-held key hierarchy, tamper-evident VB1 envelopes, device rotation/revocation, replay protection | building | `core/levi/cybrus/veil.py` | Hardening pending (AES-256-GCM + scrypt ratchet done 9-17; Android compile check outstanding); renamed from Void Box 2026-09-17 on his word |
| DemandPulse engine | 8 keyless sources, 12 industries, pain-language classification, clustering, corroboration, heatmap; OBSERVED/INFERENCE/HYPOTHESIS labels | live | `core/levi/demand/` (158 tests) | — |
| Competition intel | 6 rivals tracked (Trends, Exploding Topics, Crayon, Klue, 6sense, CB Insights); snapshots, diffs, gap analysis, upgrade recommender (advisory-only) | live | `core/levi/demand/competition.py` (22 tests) | — |
| Jobs engine | Keyless job search: Remotive, RemoteOK, Arbeitnow, Himalayas, Jobicy; stages to review buffer | live | `core/levi/jobs/`, `core/levi/hub/jobs.py` | Adzuna excluded (keyed) by design |
| Creation lab | Echo (keyword blueprint architect) → Alpha (47 generators) via Forge pipeline with human gates | live (organs) | `core/levi/revival/`, `core/levi/hub/alpha.py`, `core/levi/forge/` | — |
| Scout (tool agent) | Web fetch, notes, heartbeat, shell via real sandbox (bubblewrap/unshare); shell always needs HITL approval | live | `core/levi/hub/agent.py`, `core/levi/sandbox/` | No fake sandboxes — denylist "sandbox" cut |
| Browser automation | HTTP-level fetch + form POST only | building (honest cut) | `core/levi/hub/agent.py` | Full browser control deferred (was Playwright's job; not faked) |
| Daily hunts | Perpetual hunt, twice daily (~05:19, ~17:19 CT); rotates retired software, forgotten methods, giant patterns, fallen platforms | live | cron `levi-perpetual-hunt-daily`, `core/levi/perpetual/` | Findings become additions or are archived |
| Bounty hunter | Hunt-the-problem service abilities + public hunt showcase | spec | `core/levi/bounty/` | Money via Cybrus only; showcase launch on his word |
| Academy sessions | Boot Camp sessions with budgets; spaced repetition, Feynman drills, pressure drills, Socratic interrogation | live | `core/levi/academy/` | Defensive-only curriculum |
| Image generation | Creator-suite media generation | spec/building | `core/levi/media/`, media skill | unverified depth |
| Video generation | Photo/video generation, avatar creation (creator suite scope) | spec | `core/levi/media/`, memory 2026-09-21 | unverified |
| TTS / voice | Speech synthesis + read-back | live (skill) | tts skill, `core/levi/voice/` | — |
| Dating + creator services (PL-05) | Skip-the-games + OnlyFans + Telegram fused, but E2E-sealed and airtight — the non-conforming bet: adult creator space with real security | building (sealed design + SI/AI sides in repo, commit `c0b3b5d`, 38/38 tests) | `core/levi/creator/si/`, `core/levi/creator/ai/`, `core/levi/cybrus/veil.py`, `docs/PRODUCT_LINES.md` | SI-side launch needs his word + legal review; live money Cybrus-only pending business call; no explicit content in repo; tracks never merge (Plaiground gate) |
| Echoverse | Branching organ: explore space (SFW route) | live (organ) | `core/levi/` organs | — |
| Mandella | Branching organ: stake under fog, phantoms haunt | live (organ) | `core/levi/` organs | — |
| REIM / RIEM | Compost failure → compost-genome; matched twin-pair | live (organs) | `core/levi/` organs | Fit-gated pairing only |
| Site Lift | AI analysis + pricing uplift for business sites; first real use: Easy Touch Massage 2026-09-17 | live (pattern) | `docs/SITE_LIFT.md` | Owner-gated facts never fabricated |
| Social platform | Hub social design (town square, forum, code commons); advisor proposed name Swarm; counsel delivered legal musts | spec | `core/levi/social/`, `core/levi/hive/`, `docs/SOCIAL_PLATFORM_DESIGN.md` | Naming open (Vyve retired, Void Box pulled); every advisor/counsel call is his |
| VYVE messenger | Messenger app (Android) | building | `apps/vyve-messenger/` | Android build not recently run |
| LEVI Android app | Companion Android app | building | `apps/levi-android/` | — |
| Hicomb | From-scratch code editor (his Acode answer); Pollen formatter; trio + legion-hub plugins | building | `~/workspace/hicomb/` | — |
| Games league | Game systems league (bagatelle, deduction, hotseat, IF engine, daily puzzle, league) | building | `core/levi/games/` | Mixable material for the organism |
| LEGION NFTs | NFT apparatus (odd sets, assembler, license, money) | building | `core/levi/genesis/nft/` | **Lawyer before first real mint** (2026-09-18); 1,000/yr floor, Base chain |
| Universe (theme park) | Theme-park architecture: Alpha deliberation + Omega Nexus routing through real organs | building | `core/levi/universe/` | — |
| Dynasty | Bloodline: baby Levi (growth loop) → minds → LEVI → Nanobit → eleven originals | building | `core/levi/dynasty/`, `core/levi/growth/`, `core/levi/nursery/` | Dynasty materials eyes-only (Chauncey + Rex) |
| SOXI | Levi × XI crossbreed intelligence classification; LN router + 10 classes; offline-first | building | `core/levi/soxi/` (13 tests) | BT needs one-time `ollama pull phi3:mini` |
| Native brain | Tiny transformer trained from scratch (600 steps, loss 5.283→2.107); LEVI's own Ollama-style runner planned | building | `core/levi/brain/` | 600-step rerun approved; promote only on 0.02 held-out margin + better samples |
| Nine-teacher pipeline | Teacher intake, BPE tokenizer (8,192 vocab), persistent checkpoints, resume-after-kill | building | `core/levi/brain/train/` | Samples gibberish at 45 steps — no fluency claims |
| Cyber skills | 823 defensive blue-team playbooks (818 + phase-derived + omega) | live | `core/levi/skill/playbooks/cyber/` | Blue-team only; offensive never integrated |
| Finance | Market data, indicators, signals, portfolio; SimulatedBroker default | live (paper) | `core/levi/finance/` | **Paper/simulated only — live trading structurally refused** |
| King control plane | Orchestration over story fabric + model engine; CLI `levi king` | building | `core/levi/king/`, `docs/KING.md` | unverified current state |
| Fleet | Agent fleet categories incl. dispatch/compliance/fraud/coach/guardian | building | `core/levi/fleet/` | — |
| Growth loop | Harvest → reflect → consolidate → journal; baby book at `~/.levi/growth/` | live | `core/levi/growth/` | Writes growth-tagged memory only |
| Backup | Snapshots + integrity checks | live | `core/levi/backup/` | Daily verification alert fires; cloud upload state unchecked |
| Forge pipeline | echo → alpha → preview → permission → materialize → nexus → receipt | live | `core/levi/forge/` | — |
| Twins lattice | Echo, Alpha, Cybrus, Kai, Titan, Nexus, Aether — twin-pair agents | live | `core/levi/twins/` | — |
| UniForge | Original creation engine (Hybrid Pro / Prime Founder) | spec | Drive inventory only (`UniForge_Hybrid_Pro.py`) | Analyzed, not integrated |
| Nanobit | One of the eleven originals | memory only | lineage memory | — |
| Mesh tower | Off-grid mesh hardware review | parked | memory only | His word; hardware review pending |
| lwp interpenetration | Rebuild toward true interpenetration (fractal Alpha/Omega growth, not modules) | building | `core/levi/lwp/`, `core/levi/interpenetration/` | Coordinator dispatched; needs his direction at checkpoints |

## 3. In-flight builds (active work right now)

| Build | State | Where |
|---|---|---|
| Alpha/Omega hub shell | Built 2026-09-21, committed `157ecc3`; follow-ups open | `core/levi/hub/` |
| DemandPulse competition intel | Built + committed `4e6a66f` today; CLI wiring into `__main__.py` pending (sibling was in-flight) | `core/levi/demand/competition.py` |
| LEVI strengthen pass | Full-suite-from-zero + repo-wide ruff sweep running | background worker |
| Brain 600-step rerun | Approved; torch reinstall + persistent checkpoints every 50 steps | `core/levi/brain/` |
| BPE training resume | Checkpoint survived at step 25; resume demonstrated | `core/levi/brain/train/` |
| lwp interpenetration rebuild | Coordinator dispatched with full canon | `core/levi/lwp/` |
| Self-sufficiency learning loop | Scheduled live, daily ~04:19 CT | cron `levi-brain-learn-tick` |
| DemandPulse alert sweep | Live, every 30 min; 3 alerts fired today | cron `demandpulse-alert-sweep` |
| Daily hunts | Live, twice daily | crons `levi-perpetual-hunt-daily[-evening]` |
| Academy Boot Camp | Live sessions via cron | `core/levi/academy/` |
| Hicomb editor | Building; trio built for Hicomb + Acode fork | `~/workspace/hicomb/` |
| Games league | Building in repo | `core/levi/games/` |
| Social platform design | Awaiting his calls on advisor/counsel proposals | `docs/SOCIAL_PLATFORM_DESIGN.md` |
| VYVE messenger | Exists; Android build stale | `apps/vyve-messenger/` |

## 4. Hunt-derived assets (recycled, never deleted)

| Asset | What it is | Status | Where |
|---|---|---|---|
| Resurrected rigor candidates | Weakness-hunt outputs refined into rigor checks | building | hunt outputs; mixable material |
| GTPM scan-mind | Scan-mind from hunt pipeline | building | `core/levi/gtpm/` |
| Hunt methods catalog | Named methods extracted from hunts | live | `core/levi/methods/`, `docs/METHODS.md` |
| Software revivals | Originals preserved untouched; revivals rebuilt LEVI-native | building | originals in `~/workspace/drive-sweep/`; revivals in `core/levi/revival/` |
| Giant-pattern analyses | What giants built/refused/killed; sly-generosity trades | live (analyses) | hunt job outputs | 
| Additions (not rebuilds) | Every shippable hunt result is a new LEVI-native capability | rule | standing law |

## 5. Parked / gated (kept, not dropped)

| Item | Why it waits | Gate |
|---|---|---|
| Trio token release | Real money, real release | Payment destination, production key, terms details — his |
| LEGION first mint | Real NFT on Base | Lawyer before first mint (2026-09-18) |
| NeighborPay / live money | Money-transmitter + contractor-classification risk | Business/legal call — his |
| Bounty payouts | Real money movement | Cybrus-only flow; business/legal call |
| Free-core creed | Doctrine says free-core-forever; live law is paid-but-tiny | His word settles it |
| DemandPulse 10 workflows install | Defined, not installed | His explicit go-ahead |
| Hub localhost exposure | Binds 127.0.0.1 today | His call |
| Canon-doc architecture mapping | 4×4×4×∞ structure unmapped | His word before it constrains the build |
| Social platform name | Vyve retired, Void Box pulled | His call |
| Hunt showcase launch | Public track record | His word |
| Grok second-profile recovery | Full-scope (chats, library, automations) | His device tap |
| Contributor board climb | Acode PRs closed unmerged; Termux fix committed locally | His fresh token for the PR |
| Job applications | 8-job batch + NoGigiddy + Empower | Only when he asks |
| Mesh tower hardware | Off-grid review | His word |
| Dating service launch | Sealed design | His word |
| DemandPulse cron wording | Says "hourly", runs every 30 min | Trivial fix, unscheduled |
| Push/email alerts | Channels report not_configured | His device target / mail provider |
| OneDrive corpus | 13,008 files pulled 2026-09-16 | Authorization revoked — his re-auth to pull more |

---

## 6. Full module map — `core/levi/*`

One line each. "Organ" = organism subsystem. Entries marked *(unverified)* mean the purpose is inferred from the name only.

| Module | One line |
|---|---|
| academy | Boot Camp training sessions with budgets |
| advisor | Product advisor agent (filled Swarm's blanks) |
| affect | Affect/emotion modeling |
| agent | Agent runtime primitives |
| alpha | Alpha seat: creation-lab logic *(unverified depth)* |
| analog | Analog/continuity systems *(unverified)* |
| archive | Archive handling |
| attention | Attention-state tracking |
| automation | Recipes, workflows, macros, tap-shortcuts |
| backup | Snapshots + integrity checks |
| bloodstream | The shared organism bloodstream (inter-organ messaging) |
| boards | Boards (kanban-style tracking surfaces) *(unverified)* |
| bot | The Levi bot product surface |
| bounty | Bounty-hunter abilities + hunt showcase (spec) |
| brain | Native brain: training, weights, eval |
| bridging | Bridging between systems *(unverified)* |
| builder | Builder/creation utilities *(unverified)* |
| canvas | Canvas surfaces |
| capproto | Capability protocol *(unverified)* |
| capsule | Capsule packaging *(unverified)* |
| catalogue | Catalogs *(unverified)* |
| chain | Chain-of-custody / chain logic *(unverified)* |
| charters | Charters (governing documents) |
| ci | CI helpers |
| circles | Circles (groupings) *(unverified)* |
| classifieds | Classifieds listings |
| cli | CLI surfaces |
| cloud | Cloud tier interfaces |
| commitments | Commitment tracking |
| communities | Community structures |
| companion | Companion/adaptive intelligence (DNA strand 1) |
| connectors | External connectors |
| console | Console surfaces |
| control | Control plane primitives |
| convo | Conversation handling |
| copper | Copper layer *(unverified)* |
| cortex | Cortex (cognition layer) *(unverified)* |
| council | Counsel/advisor council (legal + product) |
| craft | Craft utilities *(unverified)* |
| creator | Creator-suite tooling |
| creed | Laws/creed (free-core-forever dispute lives here) |
| cyberpulse | CyberPulse heartbeat registry |
| cybrus | Security & Identity: vault, credentials, tokens — all money flows through here |
| daemon | Always-on OS layer (chat is a client of the daemon) |
| decisions | Decision ledger |
| demand | DemandPulse engine + alerts + competition intel |
| desk | Desk surface *(unverified)* |
| dials | Dials/tuning *(unverified)* |
| digest | Digests *(unverified)* |
| discover | Discovery engine |
| discovery | Discovery (research) *(unverified — sibling of discover)* |
| docs | Doc tooling |
| doors | Doors (there-and-ours pattern) *(unverified)* |
| dream | Dream/alignment synthesis |
| drift | Drift detection *(unverified)* |
| dual | Dual-key consent gates |
| dualkey | Standing-policy + per-action keys |
| dweller | Dweller *(unverified)* |
| dynasty | The dynasty bloodline program |
| editions | Editions/variants *(unverified)* |
| ei | Emotional intelligence (5D EI evaluation) |
| eli | ELI orchestrator (central logic router) |
| energy | Energy metering *(unverified)* |
| engagement | Engagement tracking *(unverified)* |
| engines | Engine registry |
| ephemera | Ephemera (short-lived artifacts) |
| eula | EULA/terms handling |
| exodus | Exodus (migration-out tooling) *(unverified)* |
| factory | LEVI's software factory (builds product lines) |
| fairtrade | Fair-trade economics *(unverified)* |
| feedlab | Feed generation lab |
| feedreader | Feed reading |
| finance | Paper-only finance (market, signals, portfolio, SimulatedBroker) |
| fleet | Agent fleet (dispatch, compliance, fraud, coach, guardian) |
| forge | Forge pipeline (echo→alpha→preview→permission→materialize→nexus→receipt) |
| founders | Founders roster (DemandPulse→Echo→Alpha+Omega→LEVI→Nanobit→eleven) |
| friction | Friction analysis *(unverified)* |
| galaxy | Service hub / Galaxy product surface |
| games | Games league |
| generosity | Sly-generosity pattern tracking *(unverified)* |
| genesis | Genesis: NFTs, licenses, money, odd sets |
| governor | Usage governor |
| graph | Graph structures |
| growth | Growth loop (baby Levi): harvest→reflect→consolidate→journal |
| gtpm | GTPM scan-mind (hunt-derived) |
| hive | Hive: builders' grouping inside Legion |
| honestsearch | Honest search |
| hub | Alpha/Omega hub shell (CLI, web console, orchestrator, jobs, auth, HITL) |
| hypercube | Hyper-Cube original form *(unverified)* |
| i18n | Internationalization |
| identity | Identity layer |
| inbox | Inbox (Vibe Chat) |
| income | Income tracking (batches A–E) |
| integrations | Third-party integrations |
| intelligence | Intelligence analysis |
| interop | Interop (cross-system) |
| interpenetration | True interpenetration rebuild target (fractal growth, not modules) |
| interruptions | Interruption handling |
| jobs | Job search engine + application tracker |
| king | King control plane |
| knowledge | Knowledge base (awesome-courses ingestion) |
| lab | Lab/experiment space *(unverified)* |
| legion | Legion intelligence universe (groupings of intelligence forms) |
| liberation | Liberation *(unverified)* |
| lifepack | Lifepack *(unverified)* |
| lwp | L.W.P. structural physics (DNA strand 2) + fusion kernel |
| mailtriage | Mail triage |
| marketplace | Agent/automation marketplace |
| mcp | MCP servers |
| media | Media generation (image/video/creator suite) |
| memory | Memory store + bank |
| mesh | Mesh networking (off-grid) |
| meta | Meta tooling *(unverified)* |
| methods | Hunt-derived methods catalog |
| model | Model management |
| monetize | Monetization logic |
| neighbor | Neighborhood surfaces (homepages, webrings) |
| neighboros | NeighborOS product-line organ |
| nexus | Nexus seat: research chat, provider routing |
| nursery | Nursery (raising new intelligences) |
| oath | Oath/promises *(unverified)* |
| observability | Observability |
| offline | Offline-first chain |
| omnipulse | OmniPulse original form *(unverified)* |
| operator | Operator tooling + operator skills |
| ops | Ops runbooks |
| oracle | Oracle (true-name) *(unverified)* |
| orchestration | Orchestration primitives |
| organs | Organ registry |
| packaging | Packaging |
| packs | Packs (specialized capability packs) |
| pdi | PDI *(unverified)* |
| perpetual | Perpetual hunt jobs |
| persona | Persona layer (lenses, not identities) |
| personas | Persona definitions |
| phase3 | Phase-3 artifacts *(unverified)* |
| pincards | Pin/scope/retire with provenance |
| plaiground | PL-06: NSFW companion chat + image generation service, Echoverse-backed (gate, companions, chat, photos, simulator, afterdark, depth, wellness, CLI — 50/50 tests) |
| plugins | Plugin system |
| policy | Policy engine |
| power | Power management *(unverified)* |
| premium | Premium tiers |
| premortem | Premortem analysis |
| presence | Presence *(unverified)* |
| project | Project management |
| promises | Promises tracking |
| provenance | Provenance records |
| pulse | Pulse/heartbeat |
| pwa | PWA surfaces |
| quickdial | Quick-dial *(unverified)* |
| rag | RAG retrieval |
| recap | Recaps |
| recommender | Recommender systems |
| rescue | Rescue & Remodel organ |
| research | Research crews |
| reveal | Reveal *(unverified)* |
| revival | Revival yard: Echo/Alpha/Nexus organs + software revivals |
| rewards | Rewards |
| runtime | Runtime |
| sandbox | Real sandbox backends (bubblewrap > unshare > subprocess) |
| security | Security layer |
| sentinel | Sentinel monitoring |
| ser18 | SER-18 Core original form *(unverified)* |
| serve | Serving layer |
| services | Services registry |
| shareware | Shareware *(unverified)* |
| shelf | Shelf (there-and-ours: their shelf for discovery) *(unverified)* |
| si_team | SI team *(unverified)* |
| sidewinder | Sidewinder *(unverified)* |
| signals | Signal ingestion |
| sim | Simulation (bounded) |
| skill | Skill registry |
| snapshots | Snapshots |
| social | Social platform organs |
| soxi | SOXI intelligence classification (Levi × XI) |
| strategy | Strategy |
| surgeon | Surgeon (code repair) |
| survivability | Survivability |
| sweeps | Sweep tooling (repo watch, drive-sweep) |
| synthesis | Synthesis |
| teach | Teaching |
| teachback | Teach-back verification |
| telegraph | Telegraph *(unverified)* |
| teletext | Teletext/videotex surfaces |
| threads | Threads integration |
| torch | Torch training infra |
| twins | Twin lattice agents (Echo, Alpha, Cybrus, Kai, Titan, Nexus, Aether) |
| uniforge | UniForge (original creation engine; analyzed, not integrated) |
| universe | Universe theme-park architecture |
| ux | UX shell (void theme) |
| vault | Vault (keeper-held) |
| vaults | Vaults (plural infra) *(unverified)* |
| vector | Vector search |
| verify | Verification |
| videotex | Videotex surfaces |
| voice | Voice/TTS |
| weblayer | Web layer |
| workflows | Workflow definitions (incl. 10 DemandPulse workflows) |
| workshop | Workshop *(unverified)* |
| worlds | Worlds |

---
## 7. apps/*

| App | One line | Status |
|---|---|---|
| levi-android | LEVI companion Android app (React Native/Expo build outputs present) | building |
| vyve-messenger | VYVE messenger Android app | building (stale build) |

## 8. docs/* (185 files — name-derived map)

One line each, derived from the filename. Read the doc itself for substance.

| Doc | Topic |
|---|---|
| ACADEMY.md | Academy |
| ACADEMY_DIFFERENTIATORS.md | Academy Differentiators |
| ACADEMY_EXPANSION.md | Academy Expansion |
| ACADEMY_ROLL_CALL.md | Academy Roll Call |
| ADVISOR.md | Advisor |
| AFFECT.md | Affect |
| AGENT.md | Agent |
| AGENT_PERSONA.md | Agent Persona |
| ANDROID_APP.md | Android App |
| ARCHITECTURE.md | Architecture |
| ARCHIVE.md | Archive |
| ASSISTANT_CORE.md | Assistant Core |
| ATLAS.md | Atlas |
| AUTOMATION_SAFETY.md | Automation Safety |
| BACKUP.md | Backup |
| BLOODSTREAM.md | Bloodstream |
| BLUEPRINT_GROUNDED.md | Blueprint Grounded |
| BOT.md | Bot |
| BOUNTY.md | Bounty |
| BRAIN_TRAINING.md | Brain Training |
| BRAIN_V2.md | Brain V2 |
| BREAK_THE_CODE_SWEEPS.md | Break The Code Sweeps |
| BRIDGING.md | Bridging |
| BUILDER.md | Builder |
| CANVAS.md | Canvas |
| CAPABILITIES.md | Capabilities |
| CAPPROTO.md | Capproto |
| CHAIN.md | Chain |
| CHARTERS.md | Charters |
| CHIPS.md | Chips |
| CLASSIFIEDS.md | Classifieds |
| CLEARANCE.md | Clearance |
| CLI.md | Cli |
| CLOUD_API.md | Cloud Api |
| COMMITMENTS.md | Commitments |
| COMMUNITIES.md | Communities |
| CONSOLE.md | Console |
| CONTROL_PLANE.md | Control Plane |
| CONVO.md | Convo |
| COUNCIL.md | Council |
| COURSES.md | Courses |
| CREATORLAB_REFERENCE.md | Creatorlab Reference |
| CREATOR_PLATFORM.md | Creator Platform |
| CREED.md | Creed |
| CURRICULUM.md | Curriculum |
| CUSTOMIZE.md | Customize |
| CYBRUS.md | Cybrus |
| CYBRUS_VAULT.md | Cybrus Vault |
| DAEMON.md | Daemon |
| DECISIONS.md | Decisions |
| DEEPWEB.md | Deepweb |
| DEMAND.md | Demand |
| DEMAND_AUTHORITY.md | Demand Authority |
| DIALS.md | Dials |
| DISCOVER.md | Discover |
| DOCUMENT_SKILLS.md | Document Skills |
| DREAM.md | Dream |
| DREAM_PRODUCTS.md | Dream Products |
| DRIFT.md | Drift |
| DUAL.md | Dual |
| DYNAMIC_UI.md | Dynamic Ui |
| ENERGY.md | Energy |
| ENGAGEMENT.md | Engagement |
| ENTERPRISE.md | Enterprise |
| ENTERPRISE_BLUEPRINT.md | Enterprise Blueprint |
| EPHEMERA.md | Ephemera |
| EULA.md | Eula |
| FEEDREADER.md | Feedreader |
| FINANCE.md | Finance |
| FLEET.md | Fleet |
| FLEET_FIVE.md | Fleet Five |
| FORGE.md | Forge |
| FORGE_DESIGN.md | Forge Design |
| FRICTION.md | Friction |
| GALAXY.md | Galaxy |
| GENESIS.md | Genesis |
| GROWTH.md | Growth |
| HEARTBEAT.md | Heartbeat |
| HOME_AUDIT.md | Home Audit |
| HONESTSEARCH.md | Honestsearch |
| HOSTING.md | Hosting |
| IDENTITY.md | Identity |
| INBOX.md | Inbox |
| INCOME.md | Income |
| INCOME_BATCH_A.md | Income Batch A |
| INCOME_BATCH_B.md | Income Batch B |
| INCOME_BATCH_C.md | Income Batch C |
| INCOME_BATCH_D.md | Income Batch D |
| INCOME_BATCH_E.md | Income Batch E |
| INTEGRATIONS.md | Integrations |
| INTEROP.md | Interop |
| INTEROP_FOLLOWUPS.md | Interop Followups |
| INTERPENETRATION.md | Interpenetration |
| INTERRUPTIONS.md | Interruptions |
| JOBS.md | Jobs |
| KING.md | King |
| KNOWLEDGE.md | Knowledge |
| KNOWLEDGE_PIPELINE.md | Knowledge Pipeline |
| LAB.md | Lab |
| LEARNING_SYNC.md | Learning Sync |
| LEARN_LOOP.md | Learn Loop |
| LEGION.md | Legion |
| LEXICON.md | Lexicon |
| LIFEPACK.md | Lifepack |
| LINUX_COMPUTER.md | Linux Computer |
| LWP.md | Lwp |
| MAILTRIAGE.md | Mailtriage |
| MASTER_INVENTORY.md | Master Inventory |
| MCP.md | Mcp |
| MCP_CATALOG.md | Mcp Catalog |
| MEDIA.md | Media |
| MEMORY.md | Memory |
| METHODS.md | Methods |
| MISSION.md | Mission |
| MODELS.md | Models |
| MONETIZATION.md | Monetization |
| MONETIZE.md | Monetize |
| MONEY_LAW.md | Money Law |
| NEIGHBOROS.md | Neighboros |
| NEIGHBOROS_DIFFERENTIATORS.md | Neighboros Differentiators |
| NEIGHBOROS_SPEC.md | Neighboros Spec |
| NEWS.md | News |
| NURSERY.md | Nursery |
| OATH.md | Oath |
| OBSERVABILITY.md | Observability |
| OPERATOR.md | Operator |
| OPERATOR_SKILLS.md | Operator Skills |
| ORGANS.md | Organs |
| PACKS.md | Packs |
| PERPETUAL.md | Perpetual |
| PERSONA.md | Persona |
| PERSONAS.md | Personas |
| PLAIGROUND.md | Plaiground |
| POWER.md | Power |
| PREMIUM_HYBRID.md | Premium Hybrid |
| PREMORTEM.md | Premortem |
| PRESENCE.md | Presence |
| PRODUCT_LINES.md | Product Lines |
| PROMISES.md | Promises |
| PWA.md | Pwa |
| RAG.md | Rag |
| RECAP.md | Recap |
| RECOMMENDER.md | Recommender |
| REFERENCES.md | References |
| REMIXSTUDIO.md | Remixstudio |
| RESCUE_REMODEL_DESIGN.md | Rescue Remodel Design |
| REVIVAL.md | Revival |
| REVIVAL_FORGE.md | Revival Forge |
| REWARDS.md | Rewards |
| RUNBOOK.md | Runbook |
| SECURITY.md | Security |
| SECURITY_INDEX.md | Security Index |
| SENTINEL.md | Sentinel |
| SERVICES.md | Services |
| SHIELD_SERVICE.md | Shield Service |
| SIGNALS.md | Signals |
| SIM.md | Sim |
| SITE_LIFT.md | Site Lift |
| SI_ADULT.md | Si Adult |
| SNAPSHOTS.md | Snapshots |
| SOCIAL_PLATFORM_DESIGN.md | Social Platform Design |
| SOUL.md | Soul |
| SOURCE_SYNC_PROTOCOL.md | Source Sync Protocol |
| STRATEGY.md | Strategy |
| SURVIVABILITY.md | Survivability |
| SWEEPS.md | Sweeps |
| SYNTHESIS.md | Synthesis |
| SYNTHESIS_ARCHITECTURE.md | Synthesis Architecture |
| TEACH.md | Teach |
| TEACHBACK.md | Teachback |
| THREADS.md | Threads |
| TORCH.md | Torch |
| TWINS_SER21.md | Twins Ser21 |
| UNIFORGE.md | Uniforge |
| UPLOADS_CONSOLIDATED.md | Uploads Consolidated |
| UPLOADS_OFFLINE_FIRST.md | Uploads Offline First |
| UPLOADS_SMALL.md | Uploads Small |
| UPLOADS_VEIL.md | Uploads Veil |
| UPLOADS_VYVE.md | Uploads Vyve |
| USAGE_GOVERNOR.md | Usage Governor |
| VAULT.md | Vault |
| VAULTS.md | Vaults |
| VIDEOTEX.md | Videotex |
| WAREHOUSES.md | Warehouses |
| WORLDS.md | Worlds |

---
*Inventory draft written 2026-09-21 by inventory sweep. Statuses marked live/building/spec reflect repo presence + memory, not a fresh test run. Anything marked unverified needs eyes-on confirmation. Nothing was built, modified, or committed for this inventory — the only new file is this one.*

