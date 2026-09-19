# Small Uploads — Study & Evaluation

Worker: uploads-small (2026-09-17). Four keeper materials, studied from copies in
`~/workspace/uploads-work/small/`. Originals in `~/workspace/user/files/` untouched.

## Item 1 — `archive3/index.html` (from `archive__3.zip`)

**What it is:** Complete, production-quality single-file website for
**Easy Touch Massage LLC** — independent massage/facial/waxing business,
Springfield, IL, therapist Jontae' Williams-Davis, LMT (practicing since 2015).
653 lines, no external JS (Google Fonts only). Working: full priced service
menu (massage/facials/body treatments/waxing) in accessible accordions, Square
booking + gift-card links, sticky mobile call/book bar, message-us modal
(validated, honeypot anti-spam, focus trap, Esc-close, opens visitor's own email
app), schema.org `HealthAndBeautyBusiness` JSON-LD, canonical + OG meta.

**State: WORKING, pre-launch.** Genuinely shippable; blocked only on owner input.

**Gaps found and fixed (in the improved copy):**
- Favicon was a `data:,` stub → inline SVG "ET" monogram in brand plum (#6B2D8B).
- No og:image → generated branded 1200×630 `og-image.png` (PIL) and wired
  `og:image` / `twitter:image` / JSON-LD `image`. Note: it's a generated graphic,
  not a real photo — owner may prefer real imagery (intake question 4 covers photos).
- HTML comments referenced a README / "build notes" that were NOT in the zip →
  wrote `README.md`: launch checklist, pricing/verification notes, post-launch steps.
- Dangling "see build notes" references → pointed at `README.md`.

**Gaps deliberately NOT filled** (owner-only, per revival honesty rules):
- The 3 review placeholders stay placeholders — no invented quotes.
  The intake docx names 7 real reviewers; exact wording must come from the owner.
- ZIP 62702 vs 62704 conflict stays flagged; hours stay flagged as directory-sourced.
- Square booking/gift-card links were carried over from the old site — unverified.

## Item 2 — `Information_Needed_From_Jontae.docx` (from `archive__3.zip`)

**What it is:** A client intake questionnaire, not a build asset. NOT acted on —
read and reported only. It asks Jontae' for six things before the site goes live:
1. **Reviews** — pick 3 of 7 named real clients and give their exact quoted words.
2. **Address** — confirm ZIP 62702 vs 62704 (Birdeye shows 62704).
3. **Business hours** — confirm the public-listing hours table (Mon–Fri 9–9,
   Sat 10–8, Sun 11–6) or correct them.
4. **Photos** — 3–5 real photos of the space/work/products + how they'll be sent.
5. **Logo** — square version for the browser tab, or text logo is fine.
6. **Anything else** — open changes (wording, colors, services, prices).

Study note: this docx is the instrument the HTML's launch TODOs were written
against. It pairs 1:1 with the gaps above. Archived with the improved copy.

## Item 3 — `lumen-grid.html`

**What it is:** Tiny interactive grid widget (1.4KB). **State: WORKING but
toy-grade.** Bugs found: "Clear" reset to 1 cell instead of emptying (mislabeled);
cells had no identity, no persistence, no deletion.

**Improved:** Clear now empties (with an empty-state message); cells are
click-to-rename (contenteditable, Enter to commit), each has a remove button,
"Reset" restores defaults, and the grid persists to localStorage (with graceful
degradation if storage is unavailable). Accessibility added (list/listitem roles,
aria-live, labeled controls). Kept the minimalist black-cell aesthetic.

## Item 4 — `nexora-studio.html` + `nexora-spark.html`

**What they are:** Two static landing-page prototypes for a "Nexora kit" profile
product — Studio edition ($54/mo) and Spark edition (free). Same design-token
system (`:root` custom properties, serif "mark" eyebrows, rounded cards).
**State: STUBS** — static mockups, placeholder copy ("You / Digital creator"),
and each one's "This kit includes" list promised features that did not exist:
Spark listed 3 project cards, mood widget, public profile URL; Studio listed
"Full UI Studio, all layouts, Swiss + mosaic" — none rendered.

**Completed (working copies in `~/workspace/uploads-work/small/`):**
- **Spark:** live demo room — 3 project cards, working mood widget (4 moods,
  toggle, persists), public profile URL that derives from the display name with
  a copy button (clipboard + manual fallback). Editable name/role, persisted.
- **Studio:** layout studio — Swiss grid ↔ mosaic switcher over a live tile
  preview; full **token editor** (color pickers for all 5 theme colors, radius
  slider) that restyles the page in place, renders the `:root` block, copies it
  to clipboard, and resets — completing the "Edit the :root block" promise.
  Editable name/role, persisted. All JS passes `node --check`; HTML tag-balanced.

## Console/UX evaluation for LEVI

The prototypes are product mockups, not LEVI code — nothing was copied into the
repo (per instructions: describe, don't build; keeper's call on recreation).

**Patterns worth a LEVI-native recreation (keeper's decision):**
1. **Token-driven theming with a live editor** (Studio). The `:root` custom
   property block as a user-editable theme contract is a clean mechanism. A
   LEVI-native version could be the console's theme/personalization surface —
   user-tunable tokens with contrast guardrails, persisted per operator room.
2. **The "room" model** (Spark). Editable identity, mood widget, profile URL —
   maps naturally onto LEVI operator rooms / roster identity cards, but LEVI's
   version would read/write the LEVI memory store, not localStorage.
3. **Craft details from the massage site** (quality reference only): accordion
   menus, focus-trapped modal, sticky action bar, honeypot form. Generic web
   patterns — recreate freely if the console ever needs them; nothing LEVI-specific.

**Do NOT carry over:** the "Nexora" brand, edition names, and pricing ($54/mo /
Free). If any pattern is recreated LEVI-native, it gets LEVI's name and LEVI's
twist per the revival laws.

**Verdict:** Spark and Studio are now honest demos of what their kit lists
promise. The token editor is the one pattern with real LEVI-console value.

## Provenance & honesty notes

- Improved copies live at `~/workspace/uploads-work/small/` — outside the repo,
  per the one-study instruction. Originals unmodified.
- Interactive behavior validated by code review, `node --check` on all scripts,
  and HTML tag-balance checks only — **no live browser run** was available to
  this worker, so click-through behavior is not browser-verified. Flag as the
  one gap before these touch any user-facing surface.
- No owner data was fabricated anywhere: reviews, hours, ZIP, and photos remain
  explicitly owner-gated. The docx was read, summarized, and left untouched.
- Ready for keeper review. No keeper review is claimed.

## Keeper's call (2026-09-17)

**Easy Touch: declined — no further work.** The keeper said "no Easy Touch":
the massage-site track is dropped. Materials stay untouched where they are;
nothing from it is applied LEVI-native and nothing further is built on it.
