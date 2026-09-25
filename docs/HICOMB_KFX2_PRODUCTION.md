# HICOMB — KFX² teardown + production-phase plan

Date: 2026-09-21. Workstream: 8 of 13.
Product: Hicomb — a from-scratch code editor, our own house. Chauncey develops
on Android via Termux + Acode today; Hicomb is the editor he moves INTO, not
an app he visits. Mobile-first is the primary surface, not a port. The
differentiator: LEVI integration — the editor and the intelligence are one
organism. The file being edited knows the project; the project knows the
builder.

KFX² law (Chauncey, 2026-09-21): absorb the outside pattern — STRENGTHS as
well as weaknesses — → reverse it → improve it → return a version only we
could build. Unreplicable means: our architecture (local-first, deterministic,
gated) makes their cost structures and compromises unnecessary.
Frame docs: `PLAIGROUND_CRUSHON_KFX2.md` (absorb+reverse+improve+unreplicable),
`PLAIGROUND_GIANTS_KFX2.md` (strengths-amplified form, correction).

Nothing here authorizes code. This doc is strategy + production order only.

---

## (a) COMPETITOR TEARDOWN — Acode, Spck Editor

### Acode (Acode Foundation, MIT open source, Android 7.0+)

**Features (per official listing, verified from their store copy):**
- Syntax highlighting, 100+ languages; multi-file tabs; command palette
  (Ctrl+Shift+P); project-wide file search (Ctrl+P); keyboard shortcuts
- Code completion / IntelliSense via LSP **plugins** (not built-in)
- Emmet, interactive JS console, live HTML/Markdown preview, themes/fonts,
  large-file optimization
- Git: clone, commit, push, pull, branch management; GitHub integration
- SSH, FTP/SFTP file management
- Plugin Store: language servers, themes/icon packs, AI-assisted coding
  tools, build tools/formatters, framework support; plugins written in
  JS/TS
- Integrated terminal (one-time setup; AXS PTY, Alpine proot, no root
  required — per third-party comparison doc, secondary source)
- File recovery, in-app file browser

**Pricing:** Free tier with ads (confirmed: "The free version contains
ads"). Pro = in-app purchase (ad removal + premium themes; "In-app purchases
may vary by region"). **Could not verify:** exact Pro price in USD —
listing sites state removal-of-ads but no price surfaced in public search;
do not quote one.

**UX:** VS-Code-flavored: command palette, tabs, sidebar. Terminal via
proot-Alpine is genuinely capable for web dev (npm, etc.). Third-party
comparison (darkian-studio/acode.md, secondary/unverified by us) notes:
LSP only via plugins, debugging = JS console only, all-files search was
beta, no minimap, offline-capable.

**Sentiment — what mobile devs love:**
- The most capable free mobile code editor on Android; the terminal +
  Git + FTP stack makes it a real web-dev IDE on a phone
- MIT open source, community plugin store, F-Droid availability
- Genuine large-file handling (50,000+ lines cited in third-party listings)

**Sentiment — what they hate:**
- Ads in the free tier, inside a professional tool; Pro fix is paid
- Plugin ecosystem fragility: plugin updates/ads edge cases reported on
  their GitHub (e.g. PR fixing ads shown in Pro after plugin uninstall)
- Terminal setup friction ("one-time setup" of the proot environment)
- LSP as plugin means IntelliSense quality varies by plugin, not by the
  editor

**Could not verify:** download counts, rating trends, exact ad network /
privacy posture of the ad layer, Pro price. The recent "Terminal & AI
Coding" rebrand (AI-assisted coding plugins, external purchase flow,
login/auth flow changes per their repo PR #2110) suggests the AI monetization
lane is being actively built — treat as moving target.

### Spck Editor / Git Client (Leaf Stack Studio Ltd., Waterloo ON; released 2018)

**Features (per Google Play listing):**
- Git-first: clone public/private repos (GitHub/GitLab/Bitbucket, AWS
  CodeCommit, Azure DevOps), checkout/pull/push/commit/log, diff viewer
- TypeScript autocompletion + smart hints (JS/TS/TSX/JSX, CSS/LESS/SCSS,
  HTML+Emmet); syntax highlighting for many more languages
  (Python, Go, Rust, Java, Kotlin, PHP, C/C++, shell…)
- On-screen extra/keyboard snippets; CSS color selector; project & file
  search; auto-indentation; light/dark themes
- On-device HTML/Markdown preview; JS labs; zip export/import
- New: AI code completion and code explanations (per listing)
- Tiny: ~11 MB APK; the lightest credible mobile Git client + editor

**Pricing:** Free app ("Spck Editor Lite"). Pro = separate paid app,
"Spck Editor for NodeJS": Node Terminal access, create tasks/run Node
programs, npm/webpack on Android. **Could not verify:** Pro price, or
whether the AI features are paywalled/usage-metered. The NodeJS app
description mentions a "Daily free trial of 1 hour" — ambiguous whether
that's a Node-terminal daily allowance; do not state as fact. Mark:
could not verify pricing or AI metering.

**UX:** Compact, Git-client-first framing: the pitch is "make changes,
preview, push" — a phone as a commit machine. ~1M+ downloads, 4.16/5
from ~13K ratings (AppBrain, 2026). 66K downloads in last 30 days —
still actively installed.

**Sentiment — what mobile devs love:**
- Size and speed: under 11 MB, fast on low-end hardware — real
  mobile-first engineering, not a shrunken desktop
- The Git workflow from a phone actually works; diff viewer and
  multi-remote clone are the killer shape
- TypeScript smart completion is genuinely good for the JS front-end
  niche

**Sentiment — what they hate:**
- Private repos require app tokens — setup friction every Git user
  complains about
- **"Back up your projects before uninstalling the app, otherwise you
  will likely lose the data!"** — their own Play listing says this.
  Projects live in app-private storage with no safety net. This is the
  structural tell: your work is hostage to the app container.
- JS/web-centric; other languages are syntax-highlighting only
- No real terminal in Lite; Node terminal is the paid tier

**Could not verify:** privacy posture of the AI completion (cloud-routed?
whose model?), offline behavior, exact NodeJS-app price.

### The pattern both share

- Mobile code editors live or die on: (1) real Git, (2) real preview,
  (3) tolerable input (extra keyboard rows/snippets), (4) weight.
- Both are **editors-as-tools**: a file buffer, a Git client, a preview
  pane. Neither knows your project; neither knows you. The intelligence
  lane (Spck's new AI completion, Acode's AI plugins) is cloud-routed,
  metered, and rented — their architecture forces meter-per-message
  economics, so it shows up as trials, tiers, or tokens.

---

## (b) KFX² ON HICOMB

### ABSORB — the outside patterns worth taking

1. **Acode's plugin ecosystem shape.** A community Plugin Store with a JS
   API surface is the right extensibility model for a mobile editor —
   themes, language servers, formatters, build tools. We adopt the *shape*
   (store + JS plugin API), not the fragility: our plugin host is the
   daemon's own sandbox with capability gating, so a plugin cannot take
   the editor down and cannot phone home without permission.
2. **Spck's Git integration.** Clone→edit→diff→commit→push from the phone
   as one motion is the mobile killer workflow. We adopt the whole Git
   motion as first-class: project IS a repo; the editor never asks you
   to "set up Git," it finds the `.git` or offers init/clone on first
   open.
3. **Spck's weight discipline.** ~11 MB and fast on low-end hardware.
   That number is the target to beat, not match: Hicomb ships lean and
   stays lean. Bloat is a veto, not a roadmap.
4. **The command palette + project search shape.** Ctrl+P / Ctrl+Shift+P
   on a phone (with a command bar tuned for touch) is the navigation
   pattern every dev already knows. Adopt it; don't invent a new one.
5. **Extra keyboard rows / snippets.** The on-screen keyboard is the
   phone editor's real enemy. Adopt the snippet-row + bracket-pair row
   as core, not as an afterthought.

### REVERSE — their weaknesses, flipped into our strengths

| Their failure | Our reversal |
|---|---|
| Ads inside a professional tool (Acode free tier) | No ads. Ever. The editor is part of the organism, not an ad surface. Our economics (paid-but-tiny entry, volume) don't need the ad dollar, so the ad SDK never ships. |
| "Back up before uninstall or you lose your data" (Spck's own warning) | Projects live in the user's file tree, daemon-synced and journaled. Uninstall the UI, your code is still there. The app container holds zero hostage. |
| Private-repo app tokens as setup friction (Spck) | SSH keys / tokens managed once in the vault, reused by every project. First clone is a picker, not a config file. |
| LSP via plugin lottery; JS-console-only debugging (Acode) | Language intelligence is built in as the daemon's own analyzer, deterministic and offline — not a plugin you hope someone maintains. |
| Cloud-routed, metered AI (both, entering) | LEVI is local and already knows the project. No per-message meter exists in our architecture, so no trial, no tokens, no "daily free hour." |
| Desktop editors shrunk to phone | Hicomb is designed phone-first: touch command bar, snippet rows, preview that respects a 6-inch screen. Desktop companion (if ever) is the port, not the other way. |
| Cloud-sync lock-in for continuity | Local-first: the daemon is the sync. No account required to keep your work. |

### AMPLIFY — their strengths, made unreplicable

Their strength is **editor-as-tool**: a sharper buffer, a faster Git
client, a lighter APK. We amplify by changing the category:

**Editor-as-organ.** In Acode and Spck, the editor knows files. In
Hicomb, the file being edited knows the project, and the project knows
the builder — because LEVI is the bloodstream, not a plugin:

1. **The project knows itself.** Open any file and Hicomb already knows
   the repo's language, framework, test command, entry points, and
   recent changes — from the daemon's project model, not from a scan
   you waited for. Their "AI code completion" rents a cloud model per
   keystroke; ours reads a local ledger. UNREPLICABLE because their
   meter-per-message cost structure forbids always-on project awareness
   — they'd have to bill you for the editor *thinking*.
2. **The builder's memory, in the buffer.** LEVI's growth journal is the
   editor's memory: "you fixed this bug pattern twice last month,"
   "this file's last three commits were all yours at 2am — the test
   command is X." Spck shows you a diff; Hicomb shows you the diff plus
   why it matters to *you*. UNREPLICABLE: their data model is files;
   ours is the relationship between builder and codebase.
3. **Mobile-first as physics, not port.** Spck proved the phone can be
   the primary dev environment for a niche; we make it the primary
   environment, period. Chauncey builds LEVI itself on a phone — the
   editor's first user is its own maker, dogfooding daily. No desktop
   editor company can do this without cannibalizing the product their
   revenue comes from. Our revenue doesn't come from a desktop seat.
4. **Deterministic assistance, zero meter.** Refactors, renames,
   test-runs, commit-message drafts — executed by the daemon's own
   analyzers offline, confirmed by the builder, logged in the journal.
   Their AI lane is rented intelligence with a per-token meter;
   ours is owned capability with zero marginal cost. UNREPLICABLE:
   their pricing punishes use; ours has nothing to punish with.
5. **Continuity as the product.** Sessions, branches, stashes, and the
   builder's intent survive app kills, phone swaps, and reinstalls —
   because the daemon owns the state, not the UI process. Their state
   dies with the activity; ours is the organism's memory.

**Return to sender:** everything they gate behind tiers, trials, tokens,
or ads — always-on intelligence, project awareness, your own code's
safety — we ship as physics, because our physics made the scarcity
unnecessary.

### Positioning — the uproar doctrine (Chauncey, 2026-09-21)

Chauncey's positioning law: **we offer what they do, what they don't, and do
it even better, and for fraction of fractions.** Match the competitors
feature-for-feature plus what they don't offer, better built, at radically
lower prices. Dollar-scale entry, volume over margin.

**Competitor features → our parity.** Acode's editor core (syntax
highlighting across languages, multi-tab, command palette, project-wide
search, snippets/keyboard rows) is Phase 0; Spck's Git-native motion
(clone→edit→diff→commit→push as one phone motion) is Phase 1; live preview
and an integrated terminal are Phase 2; the JS plugin API + store shape is
Phase 3. Touch command bar, the extra-keyboard row, large-file handling,
themes — all matched, none invented beyond what the plan builds.

**Competitor gaps → our exclusives.** What neither editor can sell:
editor-as-organ — the file knows the project and the project knows the
builder, because LEVI is the bloodstream, not a plugin; language
intelligence built into the daemon, deterministic and offline, instead of
Acode's plugin-lottery LSP; unmetered assistance — no trials, no tokens, no
daily free hour — because there is no per-message meter in our architecture;
zero ads ever, with the ad SDK never entering the dependency tree; projects
living in the user's tree, journaled and daemon-synced, so uninstalling the
UI never threatens the code (the opposite of Spck's "back up or lose it"
warning); continuity that survives app kills and reinstalls; phone-first as
physics, not a port.

**Our price as a fraction of theirs.** Acode's Pro price and Spck's Pro
price/metering **could not be verified** — this document states no competitor
price: **competitor price not verified in this document.** Ours: the standing
law is no-free-core, paid-but-tiny entry, volume over margin; the exact
Hicomb price point is Chauncey's call (gated in the plan). What the plan
already fixes: no ads, no per-message meter, no hostage data — so whatever
the tiny entry is, it cannot be sliced into trials, tiers, or token packs.

### Honest limits

- We have not benchmarked real-world Android performance yet; the
  weight target (~11 MB class) is an aspiration until Chauncey tests
  on his Moto G.
- Git hosting auth (GitHub/SSH) still needs his one-time vault setup;
  we reduce the friction, we don't eliminate the credential.
- No store listing exists; any Play/F-Droid presence is his call.
- On-device language analysis scope starts narrow (the languages LEVI
  itself is built in) and widens by demand — no claims beyond that.

---

## (c) PRODUCTION-PHASE PLAN

Sequenced build order. Each phase is a working editor state, not a
spec — Chauncey dogfoods from Phase 1 onward on his phone.

**Phase 0 — Skeleton (editor core).**
Buffer engine: open/edit/save, multi-tab, syntax highlighting (core
languages first: Python, JS/TS, HTML/CSS, Markdown, shell), undo/redo,
find/replace incl. project search, file tree. Touch command bar
(Ctrl+P / Ctrl+Shift+P equivalent). Extra keyboard snippet row.
Target: genuinely usable for editing LEVI's own repo on the Moto G.

**Phase 1 — Git-native.**
Project IS a repo: open folder → detect `.git`, or offer init/clone.
Clone/push/pull/commit/branch/stash/diff viewer. Commit from the phone
as one motion. Vault-managed SSH/token auth (one-time setup, his
credentials, never stored in chat).

**Phase 2 — Preview + terminal.**
Live HTML/Markdown preview. Integrated terminal (proot-style Linux
userland, no root) so the editor can run the project's own toolchain.
Run-config per project remembered by the daemon.

**Phase 3 — Plugin store (Acode's shape, our sandbox).**
JS plugin API + in-app store: themes, formatters, language extras.
Capability-gated sandbox — plugins declare network/filesystem access,
the builder approves. No plugin ships with ads, ever.

**Phase 4 — LEVI woven in (the unreplicable layer).**
Project model in the daemon: language/framework/test/entry detection.
Builder-aware assistance: commit-message drafts from the diff, rename
refactors, "you've fixed this pattern before" recall from the growth
journal, session continuity across kills/reinstalls. All offline, all
unmetered, all logged.

**Phase 5 — Polish + weight war.**
Cold-start time, APK size, battery, large-file stress (50k+ lines),
low-storage behavior (his $5 phone is the floor, not the Moto G).
Ship criteria: beats Spck's weight class on his actual hardware.

### Milestones (concrete, testable)

- M1: Edit + save a file in `~/workspace/levi` from the phone, tabs +
  highlighting + project search working. (Phase 0)
- M2: Clone a repo, make a commit, push — entirely from the phone.
  (Phase 1)
- M3: Run the project's test suite from the in-editor terminal.
  (Phase 2)
- M4: Install a community theme + a formatter from the store without
  granting network access. (Phase 3)
- M5: Editor drafts a commit message from the diff; recalls a prior
  fix pattern from the journal — offline, no meter. (Phase 4)
- M6: Cold start < 2s, APK in Spck's weight class, 50k-line file
  smooth, on the Moto G. (Phase 5)

### Gated on Chauncey

- **Phone testing** — every milestone is verified on his real hardware
  (Moto G primary; the $5 phone as the floor). No milestone is "done"
  until he touches it.
- **Store listing** — Play and/or F-Droid presence, listing copy,
  screenshots: his five specifics per action (destination, scope,
  account, copy, media) before anything ships publicly.
- **Pricing/licensing decision** — the law is no-free-core, paid-but-tiny
  entry, volume over margin; the exact Hicomb price point is his call.
- **Git host credentials** — one-time vault setup for GitHub/SSH; he
  provides, we never persist outside the vault.
- **Plugin store moderation policy** — who can publish, what review
  bar: his word before the store opens to anyone but him.

### Hard nos

- **No ads.** Not in free, not in pro, not in plugins. The ad SDK never
  enters the dependency tree.
- **No cloud lock-in.** No account required; no project data leaves the
  device without his explicit act. Sync is the daemon's job, local-first.
- **No desktop-port thinking.** Phone-first design is the law; any
  desktop surface later is the port. No feature ships on desktop first.
- **No rented AI meter.** No per-message, per-token, or per-minute
  metering anywhere in the editor. Assistance is daemon-owned and
  unmetered by architecture.
- **No hostage data.** Uninstalling the UI never threatens the code.
  Projects live in the user's tree, journaled, recoverable.
- **No scope creep into IDE-bloat.** Debugging depth, remote dev
  servers, and cloud workspaces are roadmap, not Phase 0–5. The editor
  earns each layer by being excellent at the previous one.
