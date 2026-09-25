"""methods: forgotten human techniques reborn as original LEVI works.

Pre-digital memory, retrieval, and organizing systems — the art of memory,
punched-card retrieval, faceted classification, intellectual bookkeeping —
reimplemented from scratch as LEVI's own stdlib-only, local-first code.
Defensive and deny-closed throughout: corrupt stores are quarantined, never
silently absorbed; nothing here phones home.

- ``loci``: method-of-loci memory palaces — rooms, loci, recall walkthroughs.
- ``llull``: Llull's combinatorial art — exhaustive idea generation from a
  primitive alphabet.
- ``bruno``: Bruno's memory wheels — rotating ring combinatorics bound to
  vivid image-seeds.
- ``pinakes``: Callimachus's Pinakes — author/subject catalog with critical
  judgment and authenticity notes.
- ``tironian``: Tironian shorthand — personal abbreviation expander with
  compounding rules.
- ``commonplace``: commonplace books + Locke's alphabetical index.
- ``florilegia``: thematic excerpt anthologies with provenance chains.
- ``triplebook``: Paciolian triple-book — intellectual double-entry
  (memoriale / giornale / quaderno) with trial-balance error detection.
- ``edgenotch``: edge-notched (McBee) cards — needle-sort boolean retrieval
  (notch = bitmask).
- ``optical``: optical-coincidence ("peek-a-boo") cards — inverted term cards
  with a light-table view.
- ``uniterm``: Uniterm coordinate indexing — post-coordinate boolean search
  with an inspectable coordination trace.
- ``colon``: Ranganathan colon classification — PMEST faceted synthesis.
- ``mundaneum``: Otlet's Mundaneum/UDC — relational notation sketch
  (INSPIRATIONAL: a faithful sketch, not a working world-brain).
- ``kardex``: Kardex visible records — one-card-per-entity ambient
  dashboard store.
- ``tickler``: the 43-folder tickler file — scheduled follow-up engine.
- ``ivylee``: Ivy Lee's six-task method — total-order daily planning.
- ``franklin``: Franklin's moral-perfection ledger — virtue/habit tracking.
- ``ach``: Analysis of Competing Hypotheses — disconfirmation-ranked
  hypothesis×evidence matrix.
- ``repertory``: Kelly's repertory grid — triadic construct elicitation.
- ``morphological``: Zwicky's morphological box — exhaustive combination
  enumeration with consistency pruning.
- ``triz``: the TRIZ contradiction matrix — curated classic pairs mapped to
  inventive principles (coverage() reports exactly what's encoded).
- ``waterlogic``: de Bono's water logic — flowscape perception mapping.
- ``vsm``: Beer's Viable System Model — S1–S5 viability diagnostic.
- ``opsroom``: the Cybersyn opsroom method — variety-attenuating decision
  room (INSPIRATIONAL: faithful protocol, honest about limits).
- ``deming``: Deming's System of Profound Knowledge — four-lens diagnostic.
- ``trivium``: the trivium & quadrivium — gated staged-learning protocol.
- ``ratio``: the Jesuit Ratio Studiorum — repetition-cycle study regimen.
- ``monitorial``: monitorial instruction — peer teach-back protocol
  (INSPIRATIONAL: recursion revived, regimentation not).
- ``pecia``: the pecia system — checksummed parallel-verification
  discipline for splitting work across agents.
- ``duplex``: Nautical Almanac duplex verification — N-version agreement
  primitive; disagreement quarantines.
- ``t5``: Los Alamos T-5 hand-computing pipeline — staged execution with
  per-stage verification.
- ``therbligs``: therblig motion-study analysis — workflow analyzer for
  agent plans.
- ``pneumatic``: pneumatic dispatch routing — information-diet router
  (INSPIRATIONAL).
- ``codebook``: commercial telegraph codebooks — compressed agent
  signaling with edition control.
- ``qcodes``: Q-codes & prosigns — terse status vocabulary.
- ``prowords``: radiotelephony prowords — consequential-instruction
  protocol.
- ``chappe``: the Chappe semaphore codebook — dense phrase→signal
  compression.
- ``quipu``: the quipu — tamper-evident tally cords (INSPIRATIONAL).
- ``kriegsspiel``: Kriegsspiel — umpired adversarial red-team harness.
- ``randgame``: RAND political-military gaming — scenario comparator.
- ``concatenative``: Stackscript — LEVI's own bounded stack machine
  (Forth's concatenative core remixed: deny-closed bounds, receipts,
  pure compute, no I/O words).
- ``delphi``: the Delphi method (RAND, 1950s) — iterative anonymous
  expert rounds with median/IQR feedback and a convergence exit rule.
- ``ngt``: Nominal Group Technique (Delbecq & Van de Ven) — silent
  generation → round-robin → clarification → private rank → Borda tally,
  enforced as a state machine.
- ``crawford``: the Crawford slip method (C. C. Crawford, 1925) —
  anonymous one-idea-per-slip rounds; collection before display.
- ``futuresearch``: Future Search (Weisbord & Janoff) — AREIN-gated,
  ordered past→present→future→common-ground→action planning arc.
- ``indenture``: the craft indenture — bonded training contract with
  master liability and staged sign-off milestones.
- ``masterpiece``: the chef-d'oeuvre — peer-judged masterwork gate whose
  admitted pieces become the quality reference corpus.
- ``compagnon``: the Compagnonnage Tour de France — forced-mobility
  rotation across workshops with a shared symbolic vocabulary.
- ``mystery``: the guild "mystery" — tiered knowledge disclosure, secrets
  after proven loyalty.
- ``hallmark``: hallmarks and assay offices — struck tripartite provenance
  (maker + independent assay + date), the tester accountable too.
- ``zunftlade``: the guild chest — multi-key institutional memory with
  auditable skill lineage.
- ``sloyd``: Sloyd — graded single-new-variable craft curriculum,
  individualized pacing.
- ``kontor``: the Kontor years — total-immersion foreign posting inside
  the commercial network.
- ``fleet``: the capped five-agent delegation fleet — five fixed roles,
  one task lock, one folded report, then terminated.
- ``tiers``: three-tier memory — core/recall/archival with promotion and
  demotion rules, file-portable form.
- ``daemons``: named daemon archetypes — the owns/wake/visible contract,
  no cross-domain leaks.
- ``graffiti``: Palm Graffiti — a constrained input alphabet where
  exactness replaces guessing.
- ``piemenu``: pie and marking menus — one radial gesture path for novice
  and expert alike.
- ``chord``: Engelbart's chorded keyset — five keys, binary chords,
  release-register strokes; the alphabet with no hand travel.
- ``folksonomy``: Delicious folksonomy — bottom-up tag index ranked by
  real use, not algorithm.
- ``cap``: Path's cap — bounded spaces where the hard membership cap is
  enforced by architecture.
- ``splitscreen``: split-screen local multiplayer — N viewports on one
  shared state, no servers.
- ``mason``: the Mason's Word and marks — membership-token authentication
  separated from competence proof, with piece-rate pay marks.
- ``worksong``: work songs — rhythm-chunked procedure encoding, metered
  verses as coordination protocol and memory vessel.
- ``measures``: historical measure systems — unit-conversion ladders for
  ten dead systems (cubit, barleycorn, pes, chain, ell, toise, arshin,
  talent, hogshead, braccio) with metric cross-conversion.
- ``blobber``: grid dungeon crawlers — discrete step/turn exploration with
  tile line-of-sight, player mapping, and attrition budgets.
- ``rtscampaign``: single-player RTS campaigns — trigger-scripted missions,
  tech-tree progression, and a seeded offline AI opponent.
- ``harvard``: the Harvard Observatory computers — piece-rate distributed
  classification pipeline with a compressible living taxonomy.
- ``eniac``: the Moore School human computers — blueprint-first adoption,
  porting operator procedures to a new substrate.
- ``greenwich``: Greenwich/HMNAO — post-publication audit by independent
  re-derivation with varied assumptions.
- ``bletchley``: Bletchley Park — the human+machine staged pipeline with
  hard isolation between stages.
- ``actuarial``: insurance actuarial departments — cohort experience
  tables with accumulation and reserves.
- ``forecast``: Richardson's Forecast Factory — cellular parallel
  computation with neighbor message passing and broadcast barrier sync.
- ``claytablet``: Mesopotamian clay-tablet accounting — tamper-evident
  sealed records with staged 3D→2D abstraction.
- ``writegates``: memory write gates — writes pass named gates only;
  background auto-writes are refused.
- ``naplps``: NAPLPS — 7-bit-safe vector opcode stream with macros and
  downloadable character sets.
- ``csnet``: CSNET — the adapter pattern at national scale: tunneling and
  session multiplexing across heterogeneous transports.
- ``x25``: X.25 — virtual circuits with in-order, error-corrected
  delivery; the network keeps its promise so endpoints stay dumb.
- ``cyclades``: CYCLADES — pure datagrams plus the end-to-end principle;
  reliability lives at the hosts.
- ``fidonet``: FidoNet echomail — federated moderation by charter and
  social enforcement, store-and-forward.
- ``sysop``: SysOp culture — ownership-as-stewardship: published norms,
  admission rites, contribution ratios.
- ``hollerith``: the Hollerith punched-card pipeline — schema, keypunch,
  reader, counters, sorter; the 1890 ETL separation.
- ``nomography``: nomography — computation compiled into lookup charts;
  the straightedge as instant evaluation.

Remix law: faithful preservation belongs in the Archive; these modules are
LEVI-native realizations — the load-bearing mechanism taken, improved, and
made ours — not clones of dead systems.

Deliberately no package-level exports: import the module you need.
"""
