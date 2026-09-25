# SYNTHESIS ARCHITECTURE — the unified offline intelligence

> **Status:** living sketch. Phase 1 built 2026-09-20/21. Element verdicts
> marked ⏳ are under deep re-research (Chauncey's law: no element is
> marked not-possible on a shallow look). Nothing is silently dropped:
> every inventoried element appears below with its phase and its
> keep / tweak / refine / replace / impossible / overlooked verdict.

## The one-page sketch

```
┌─────────────────────────────────────────────────────────────┐
│                    levi synthesis                           │
│              one front door, zero network                   │
│   ask · status · prove-offline · config                     │
│   run · delegate · schedule · tick · receipts               │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐   ┌───────────┐  ┌────────────┐
   │  MIND   │   │  AGENCY   │  │  VITALITY  │
   │         │   │           │  │            │
   │ native  │   │ perceive→ │  │ status     │
   │ brain   │   │ reason→   │  │ dashboard: │
   │ (heard, │   │ act→      │  │ brain,     │
   │ labeled)│   │ verify→   │  │ skills,    │
   │    +    │   │ receipt   │  │ growth,    │
   │ rules   │   │           │  │ L.W.P.,    │
   │ engine  │   │ tool loop │  │ finance,   │
   │(decides)│   │ (31 real  │  │ daemon     │
   │         │   │  tools,   │  │            │
   │substrate│   │  gated)   │  │ prove-     │
   │ honesty │   │           │  │ offline    │
   │ law     │   │ delegate  │  │            │
   └─────────┘   │ schedule  │  └────────────┘
                 └───────────┘
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐   ┌───────────┐  ┌────────────┐
   │ STRANDS │   │ CONTROL   │  │ KNOWLEDGE  │
   │ LEVI    │   │ daemon    │  │ courses    │
   │ L.W.P.  │   │ King      │  │ news pipe  │
   │ FACTORY │   │ twins     │  │ packs      │
   │         │   │ interop   │  │ atlas      │
   │         │   │ policy    │  │            │
   └─────────┘   └───────────┘  └────────────┘
```

**Read it bottom-up:** the organism's existing organs (strands, control,
knowledge) are untouched — synthesis adds no duplicate organs. The middle
layer is the new work: **Mind** (what it makes of things, honestly
labeled), **Agency** (doing things, with permission gates and receipts),
**Vitality** (how it is, proven offline). One CLI, one module
(`core/levi/synthesis/`), stdlib-only at import.

## Design pillars

### 1. Offline-first (enforced, not promised)

`OfflineGuard` disables socket creation, DNS, and connection helpers for
the guarded block. The agentic loop runs *inside* the guard:
network-shaped tools fail closed and the receipt says so. Static scan
pins the synthesis import closure free of network libraries
(`tests/test_synthesis_offline.py`). `prove-offline` is the runtime
demonstration, not a claim.

### 2. Agency as architecture, not a bolt-on

Every goal flows through **perceive → reason → act → verify → receipt**:

- *perceive*: memory recall, growth learnings, subsystem status (advisory).
- *reason*: the mind deliberates first; the verdict frames the work.
- *act*: the canonical `run_subtask` tool loop with the deterministic
  offline planner and the real sandboxed `ToolRegistry`. The deliberation
  rides as prior context — tools receive the clean goal.
- *verify*: transcript inspected; steps, calls, gates recorded.
- *receipt*: append-only JSONL. Every run leaves a trail.

**Permission law:** gated tools (`file_write`, `file_edit`, `shell_exec`,
`http_request`, …) require the explicit `--consent` flag — the flag IS the
Permission step of Plan → Preview → Permission → Execute → Verify →
Receipt. Without it the run ends at the gate (`ok=False`, block
recorded, nothing executed). The loop never retries a denied gate.
Delegation is fan-out to bounded sub-runs with one merged receipt;
scheduling is a local interval store + tick (copper/daemon for heavy
duty).

### 3. Substrate honesty

Every answer and every receipt carries `substrate` + `limits`. The native
brain is consulted first and heard as one labeled continuation; the rules
engine decides. Brain failures degrade to honest rules-only reports —
never exceptions, never silent fallbacks. No sentience claims, anywhere.

### 4. The signature look — a haunting of retired software

The system's look and feel is a design pillar: **brutalist,
gold-on-near-black, dark-first, editorial** — honoring RETIRED,
no-longer-used software. Not a timeline through today; a memorial to
dead systems and abandoned UI eras, carried forward as living law.

**Authoritative tokens** (evidenced from the L.W.P. Lattice Console OG
brief, `lwp-model.html`, and the G1 Wyrd-Rupture console — all three agree):

| Token | Value | Use |
|---|---|---|
| Void ground | `#0a0b0d` | page/console ground |
| Surfaces | `#12141a` / `#181b22` | panels, elevation |
| Warm paper | `#ECEAE4` | primary text |
| Muted | `#8E9088` | labels, metadata |
| **Signature gold** | `#C4A35A` | the *only* accent |
| Gold dim | `rgba(196,163,90,.28)` | hairlines, selections |
| Hairlines | `rgba(236,234,228,.1)` | all borders |

**Ghost-era set** (memorial accents, earned uses only): phosphor green
`#4ade80`, phosphor-mute `#7d9a74`, tape amber `#fcd34d`, warn/rust
`#c47a5a`, danger `#c45c4a`. **Hard bans:** no neon, no purple, no emoji.

**Typography:** serif display (Cormorant Garamond / Iowan Old Style /
Palatino — gold, uppercase, `.14em` tracking for brand lockups); sans
body (IBM Plex Sans / system); mono machine register (IBM Plex Mono /
system mono — stats, logs, hex dumps, kickers at `.68–.72rem`).

**Layout (brutalist):** fixed control rail (300–380px) + open work canvas;
flat rectangles, 1px hairlines; gold as structural trim (3px HUD accents,
hero-card hairlines, 2px left-rules); flat solid-gold primary buttons
with near-black text; immutability framing — locks, seals, ledgers,
`[IMMUTABLE RECORD]` in mono.

**Lineage narrative:** phosphor terminals (green-glow screens that no
longer boot) → punch-card/batch grids (the 20px lattice) → magnetic tape
ledgers (immutable sequential records) → dark OS chrome (console rails of
dead workstations) → the LEVI void today. Pressure resolves *into* the
ancient form — the Wyrd-Rupture rule. A memorial, not retro kitsch.

**Applications:** (a) *CLI/console* — warm-paper base, muted metadata,
gold headers/seals, phosphor green for committed records, tape amber
warnings; `[SYS]`/`[LAW]`/`[ROM]` sys-log register with timestamps;
graceful no-color degradation. (b) *Web* — dark-first void theme;
**realignment needed:** web accent `#e2a63d` → `#C4A35A`, drifted
silver/blue favicon → briefed gold diamond/lattice mark on near-black
(Phase 2 tweak; flagging to Chauncey whether the amber drift was
intentional). (c) *Documents* — editorial still-life register: dark
ground, thin gold lattice, serif display, uppercase kickers; the printed
page should feel torn from a dead system's manual.

### 5. Standing safety laws (inherited, binding)

Zero network · local commits only, never push · finance paper/simulated
only · cyber defensive-only · nothing publishes/posts/mints · dynasty /
canon / IP eyes-only (Chauncey + Rex) · originals preserved unchanged ·
L.W.P. = "Logan Wyrd Press, the literary tool, the prodigy" ·
proposed names are not canon (Chauncey renames).

## Element catalog — every inventoried design element, placed

Verdict tags: **KEEP** (local, working) · **TWEAK** (small adjustment) ·
**REFINE** (real adaptation work) · **REPLACE** (rebuild differently) ·
**IMPOSSIBLE** (earned, reason given) · **OVERLOOKED** (dormant potential
worth resurrecting) · **REFERENCE** (design heritage, not runtime) ·
⏳ (deep re-research in flight — verdict not yet earned).

### The three strands

| Element | Verdict | Phase | Evidence / note |
|---|---|---|---|
| LEVI companion / adaptive-intelligence strand | KEEP | 1 | Local: `core/levi/agent/`, `orchestration/`, `persona/`. The synthesis mind's rules deliberator (`levi.alpha.reason`) is this strand's reasoning core. |
| L.W.P. — Logan Wyrd Press, the literary tool, the prodigy | KEEP | 1 | Local: `core/levi/lwp/` (ContentMachine, press console, symbiosis). Surfaced in `synthesis status`. Never "structural physics." |
| FACTORY — constructive will | KEEP | 1 | Local: `core/levi/factory/`, `workshop/`. Reachable from synthesis via the agent tool `factory_status` / `workshop_dry_run`. No duplication. |

### Control and coordination

| Element | Verdict | Phase | Evidence / note |
|---|---|---|---|
| Daemon / always-on layer | KEEP | 1 | Local: `core/levi/daemon/` (supervisor, kernel, scheduler). Kernel state surfaced in `synthesis status`. |
| King control plane | KEEP | 1 | Local: `core/levi/king/` (status, ledger, D2→D5 ranks, `reim`). No synthesis duplication needed. |
| HITL gates | KEEP | 1 | Local: `levi.policy.gates.PolicyEngine` (risk 0–4, Plan→Preview→Permission→Execute→Verify→Receipt). The synthesis agent's `--consent` flag IS the Permission step; gated tools raise `ConfirmationRequired` otherwise. |
| Growth loop / baby Levi | KEEP | 1 | Local: `core/levi/growth/` (harvest→reflect→consolidate→journal). Journal count surfaced in status; learnings feed the agent loop via `growth_context`. |
| Twin behavior | KEEP | 1 | Local: `core/levi/twins/`. Standing rule: untouched unless Chauncey orders otherwise. Synthesis does not touch it. |
| Interop layer | KEEP | 1 | Local: `core/levi/interop/`. Connectors unwired = honest offline posture. Synthesis's OfflineGuard enforces the same law at runtime. |
| Automation threads + scheduled-run patterns | KEEP | 1 | Local: `core/levi/automation/`, `daemon` scheduler, `copper` scores. Synthesis adds the lightweight path: `schedule` + `tick`. |
| Offline-first adapters | KEEP | 1 | New: `core/levi/synthesis/offline.py` (`OfflineGuard`); existing interop transports stay unwired. |

### Sovereign Convergence Architecture elements (Grok lineage, 2026-08-21)

| Element | Verdict | Phase | Evidence / note |
|---|---|---|---|
| The named architecture itself | REFERENCE | — | Design heritage. Its elements are judged individually below; the name is not a runtime to import. |
| L.W.P. lattice console | KEEP (as design law) + TWEAK | 2 | The console *artifacts* (`lwp-model.html`, G1 Wyrd-Rupture console) are the evidenced source of the signature-look pillar (gold `#C4A35A`, ghost-era tokens, brutalist rail). Functionally superseded by local `core/levi/lwp/`. Phase 2 tweak: web accent/favicon realignment (see pillar 4). |
| G1 symbiosis spine | KEEP | 1 | Local: `core/levi/lwp/symbiosis.py`. Already the working spine. |
| REIM / RIEM | KEEP + REFINE | 1 / 2 | KEEP: local King `reim`, `model_engine.reim_forks()` (genuine generation), anomaly budget formula (local is better than the Grok version). REFINE (Phase 2): the **RIEM salvage loop** — negative-vault + salvage-pool + "salvaged intent" facet extraction — is pure local logic, MISSING from the local core (repo-wide grep confirms), extractable as `core/levi/lwp/riem.py` stdlib-only, wired into `deny_last()`/`reim_forks()`. Earned by full file read + diff. |
| `lwp_sovereign_backend.py` (FastAPI service) | REFINE (part) / leave-behind (part) | 2 | 194 lines read fully. REFINE: the `SovereignNodeState` persistence + RIEM vault/salvage semantics (see above). Leave behind: FastAPI/uvicorn/cloudflared shell, Pollinations art URL (external network), Bearer multi-client auth, unauthenticated `/v1/telemetry` (kept CLI/local-only if ever surfaced), dead revenue/words stubs, hardcoded quality literals. Lenses/budget/reim already ported or superseded locally — a blind import would duplicate. |
| SOURCE_REGISTRY | ⏳ | — | Deep grep of local core + recovered corpora in flight. |
| QID / causal universe | ⏳ | — | Local hit: `core/levi/identity/cycle.py` ("QID addressing"). Full reconstruction in flight. |

### Knowledge

| Element | Verdict | Phase | Evidence / note |
|---|---|---|---|
| Awesome-courses knowledge base | KEEP | 1 | Local: `core/levi/knowledge/` courses catalog. Agent tool `course_search` uses it. |
| Daily news pipeline + capability atlas | KEEP | 1 | Local: `core/levi/knowledge/news/`. Dated, queryable, deliberately OUT of training weights. |
| Knowledge-brain tier packs (`free-minimal`, `pro-capable`, `private-omniscient`) | REFINE / REPLACE + **OVERLOOKED** | 2 | Earned by full extraction + design-intent recovery. The zips are manifest-shells + 2 real L10 objects (von Neumann entropy, quantum computing basics) — the 84–86 L10 bodies were authored in the Grok chat and never captured as files (confirmed lost across all sweeps). The design is fully specified and already half-adopted in-repo (`docs/KNOWLEDGE_PIPELINE.md`, `core/levi/brain/seed_stage1.py` with 25 nano entries). **free-minimal → REFINE** (manifest schema, serial scheme `KB-DOMAIN-YYYY-ALPHA-INSTANCE-CHECK`, nano format, curation rules; rebuild = re-author 22 L10 bodies from open sources → Master Index). **pro-capable → REFINE** (same + its 2 L10 objects are the authoring template for the other 82; additive upgrade-path model is sound). **private-omniscient → REPLACE** (byte-identical payloads to pro + claims of schemas/algorithms that aren't in the zip; rebuild the *concept* honestly as a founder full-snapshot build artifact — not "omniscient" marketing, not founder-encrypted, since the content is open-source). **OVERLOOKED flag:** the first-pass triage dismissed these as "empty tier shells" — the emptiness at L0–L9 is *by design* (L10-canonical authoring, deterministic derivation downward), and `core/levi/packs/` is a different concept (scoped context assembly, no serials/derivation/tiers). Reviving overrules a recorded triage verdict → **Chauncey's call** (uncertainty rule). Nothing here is impossible — the barrier is authoring labor (~84 L10 objects), not blocked technology. |
| `LEVI_Smithsonian_Kit.zip` | TWEAK | 2 | Two reference markdowns (prompt kit + open knowledge sources). Not code; the open-sources list becomes a reference doc for the knowledge corpus (license notes intact). |
| `core/levi/packs/` (local scoped packs) | KEEP | 1 | Already the working pack system. |

### Lineage builds

| Element | Verdict | Phase | Evidence / note |
|---|---|---|---|
| wyrd builds (14 zips + G1 console HTML, 2026-08-19→24) | mostly REPLACE; 4 REFINE | 2 / 3 | Earned per-file: 29 artifacts extracted, diffed, grepped against the core. **REPLACE** (superseded by `core/levi/lwp/model_engine.py` or `core/levi/power/`): keys, alive, circuit, gain, power, immortal, master_road, trophy, gold, unicorn, ultimate, the G1 Wyrd-Rupture HTML (visual mockup; logic lives in `wyrd_rupture()`). **REFINE** (Phase 2, real gaps): (1) `wyrd_anomaly_trail` — lens vocabulary (`morrison_haunt`, `mccarthy_reduction`, `kafka_procedure`, …) + scarcity-gated attempt protocol (only `mccarthy` survives locally); (2) `wyrd_immersion` — body-site `AffectState`, 6 `IMMERSION_MODES`, mandatory `EIImmersionLock` on expand (core `affect/`/`ei/` are different, non-literary systems); (3) `wyrd_master_graph` — forms data (`dream_vision`, `dialogic`, `encyclopedic`, `menippean`, `autofiction`, `kenosis`, `unity_of_place`) + master-combo presets; (4) `wyrd_ultimate` variant-2 HELP text — the design documentation for the feared-arts port. **Honesty gap found (surfaced, not fixed — sibling-owned):** `model_engine.py`'s docstring claims a port of "modes, feared arts" but grep proves no MODES/FEARED dicts exist. |
| cascade builds (v6 761K, v7 1.58M) | REFINE | 2 | The richest un-ported design in the corpus: the **feared-arts subsystem** — 10 named arts (`reader_complicity`, `unreliable_system`, `active_silence`, `temporal_empathy`, `transmission_decay`, `sacred_profane_collapse`, `anti_climax_design`, `constraint_bind`, `generational_scar`, `confession_under_duress`, each with intensity/description/effect/risk/pairs) + `FearedArtsAdvisor` + `detect_feared()` + accept/reject/defer proposal workflow + 10 combo presets. **0 hits in `core/levi/`** for all 10 names. Also salvageable: six uniqueness systems (`master_style.py` — Consequence Density, Scar Typography, Reader Temperature, Lattice Metrics, Irreversibility Index, Voice Contamination Map — 0 hits), 24 interpenetration modes (only `causal_bleed` survives), anomaly×10 + lens×8 vocabularies (machinery is thin string lists; value is the vocabulary). |
| `LEVI_X_LWP_*` lineage builds | REPLACE (+1 flagged exception) / IMPOSSIBLE (1 item) | 3 | **G1 base + FULL_OWNER + HYPERDRIVE pack → REPLACE**: lineage superseded by the current organism. **Flagged exception (not overruled):** the merge-time rejection of `echoverse.py` dropped design the current organ lacks — causal `EventFingerprint`s, `converge()` branch collisions, the HITL gate taxonomy CANON‖PARALLEL CANON‖NON-CANON‖QUARANTINED, negative-page coordinates. Re-opening is Chauncey's call. **8 VYVE zips → REPLACE**: verified 26/26 packages have same-named counterparts in the current core — literally the current core's prior code state. **G1_GITHUB_SAFE protected data (`ssa_banks`, `bible_runtime`, `synaptic_patterns`) → IMPOSSIBLE (earned):** checked all trees and variants — the payloads were never in any recovered artifact. The engine logic is ported; the proprietary data cannot be salvaged from files that don't contain it. |
| `LWP_UNIFIED_COMPLETE.zip` | TWEAK (pending) | 2 | First pass: older broad L.W.P. assembly; local `core/levi/lwp/` cleaner and tested. Final verdict after the wyrd/cascade/LWP_X comparison completes. |
| Echo / DemandPulse / UniForge | REFERENCE | — | Architecture reference only, not new canon claims. Local organs exist (`organs/`, `demand/`, `uniforge/`); the corrected origin chain (DemandPulse → Echo → Alpha + Omega → LEVI → Nanobit → the eleven) is canon and untouched by this build. |

### Safety and money

| Element | Verdict | Phase | Evidence / note |
|---|---|---|---|
| Cyber defensive playbooks (823) | KEEP | 1 | Local: `core/levi/skill/playbooks/cyber/`. Defensive blue-team only. Not invoked by synthesis (out of scope for the mind/agent). |
| Finance, paper-only | KEEP | 1 | Local: `core/levi/finance/` (`PaperBroker`). Mode surfaced in status. Live trading structurally disabled; unchanged. |

### Web / UX

| Element | Verdict | Phase | Evidence / note |
|---|---|---|---|
| Void-theme web UX | KEEP + TWEAK | 1 / 2 | Local `web/` is dark-first and consistent — except the accent drift (`#e2a63d` vs signature `#C4A35A`) and the silver/blue favicon vs the briefed gold lattice mark. Phase 2 tweak, pending Chauncey's call on whether the drift was intentional. |
| wyrd HTML consoles | REFERENCE | — | Design ancestors of the signature look (see pillar 4). Not runtimes. |

### Overlooked potential — dormant, worth resurrecting

Distinct verdict category per Chauncey: retired/unused/overlooked elements
with REAL unrealized potential. Only strong candidates are listed.

1. **The Knowledge Brain tier system (OVERLOOKED, strong).** The largest
   paid-for, unbuilt asset in the corpus: a fully-specified tiered
   offline knowledge product (Free seed / Pro / Founder), L10-canonical
   authoring with deterministic L0 derivation, SHA-256 checksum chain,
   serial scheme, open-license-only curation — dismissed on a misread
   ("empty tier shells"; `core/levi/packs/` "already covers" it — it
   doesn't; different concept). Revival proposal: `core/levi/knowledge/canon/`
   with pack loader + `verify_derivation_chain` + tier gating; re-author
   the 84 L10 bodies from open sources using the 2 surviving objects as
   the template. **Caveat:** reviving overrules the recorded first-pass
   triage → Chauncey's call (uncertainty rule). Both verdicts presented
   side by side, his word settles it.
2. *(further candidates pending the full overlooked-potential report —
   dormant local modules and dead-software paradigms were still being
   ranked when this sketch was written.)*

### Phase 3: replacement or earned-impossible

| Element | Verdict | Phase | Earned reason |
|---|---|---|---|
| Native brain as the *decider* ("brain-primary") | REPLACE (gated) | 3 | Earned: weights verified live (`tiny-gpt.pt`, 3.27M params, 600 steps) generate garbled proof-of-learning text; the module's own docstring says it "cannot reason, converse, or replace a language model." Replacement needs a full retraining run on a real corpus + Chauncey's explicit call. Surfaced, not taken. Brain V2 stays stopped at `ckpt-005400.npz` per standing law. |
| (further Phase 3 items) | ⏳ | — | Filled in when the four in-flight researches report. |

## Phases

**Phase 1 — the well-built core (BUILT, pending suite + commit).**
`core/levi/synthesis/`: mind (`ask` + substrate honesty), offline
(`OfflineGuard` + `prove-offline`), status (one dashboard), config,
agentic loop (`run`/`delegate`/`schedule`/`tick`/`receipts` with
permission gates and append-only receipts), CLI wiring
(`levi synthesis` + `python -m levi.synthesis`), 39 tests, docs. Zero
network at runtime. One entry point. Agency first-class.

**Phase 2 — tweaking and refinement (each item bounded, Chauncey-gated
where noted).**
1. RIEM salvage-loop extraction (`core/levi/lwp/riem.py` + wiring into
   `deny_last()`/`reim_forks()`) — refinement, earned.
2. Feared-arts subsystem port (10 arts + advisor + proposal workflow) —
   refinement; the single richest un-ported design in the corpus.
3. L.W.P. immersion craft (body-site affect, 6 immersion modes,
   mandatory EI lock) — refinement; absent from the core.
4. Anomaly-trail lens vocabulary + scarcity protocol; master-graph forms
   data — refinement (vocabulary/data, thin machinery).
5. Knowledge Brain revival (canon pack loader, derivation verification,
   tier gating; re-author 84 L10 bodies) — refinement + OVERLOOKED;
   **needs Chauncey's overrule of the first-pass triage.**
6. Smithsonian open-sources list → knowledge-corpus reference doc — tweak.
7. Web accent `#e2a63d` → `#C4A35A` + gold-lattice favicon — tweak,
   pending Chauncey's call on the drift.
8. SOURCE_REGISTRY / QID follow-through per the in-flight verdict.
9. Further overlooked-potential revivals per the full hunt report (only
   strong candidates).

**Phase 3 — replacement or earned-impossible.**
Brain-as-decider (needs retraining + Chauncey's call); wyrd/cascade/
LEVI_X_LWP final verdicts; anything the deep research marks impossible,
with the earned reason written next to it. No dates on Phase 3 —
gated on decisions and research, not on effort.

## ETA — known vs estimated

**Known (measured this build):**
- Phase 1 core (mind/offline/status/config/CLI/docs/tests): ~1 focused hour.
- Agentic loop (agent.py, CLI commands, 8 tests, smoke tests): ~1 focused hour.
- Targeted synthesis tests: 31 passed + 1 skipped in ~3s (default python);
  ruff clean. Full suite from zero: in progress (3 pre-existing
  collection errors in sibling-owned `test_agents_wave_{a,c,d}.py` — they
  expect `/tmp/wave_*_updates.py` files that don't exist; unrelated to
  synthesis; rerun excluding them is underway).

**Estimated (labeled, not promised):**
- Commit + cleanup: <1 hour after the suite verdict lands.
- Phase 2 items 1–4 (RIEM, feared arts, immersion, vocabularies): ~6–12
  focused hours total — feared arts is the big one (new subsystem +
  proposal workflow + tests).
- Phase 2 item 5 (Knowledge Brain): ~10–20 focused hours, mostly
  authoring labor (84 L10 objects from open sources); the pipeline
  itself is half-built already.
- Phase 2 items 6–9: ~2–4 focused hours + research verdicts.
- Phase 3: no wall-clock estimate — gated on Chauncey's decisions
  (brain retraining authorization, triage overrule, naming,
  accent-drift call, EchoVerse re-open) and on research completion,
  not on build effort.

**Total honest shape:** Phase 1 is done and measured. Everything else is
estimated ranges above, each tagged. Nothing here is a promise of
wall-clock completion.
