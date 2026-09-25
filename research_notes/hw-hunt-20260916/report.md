# Abandoned-hardware hunt — wave-004 (2026-09-16)

Dead machines, consoles, handhelds, and peripherals — and the tricks their
constraints forced. Four finds, all web-verified today; no guesses in the
mechanisms below (cycle counts and dates come from the cited sources).

## 1. Atari 2600: racing the beam — the kernel under a hard slice budget

- **What/when:** Atari VCS/2600 (1977). No video frame buffer; the TIA
  paints whatever its registers say at the exact pixel the electron beam
  touches. ~76 CPU cycles per scanline; NTSC 262 scanlines per frame
  (3 VSYNC + 37 VBLANK + 192 kernel + 30 overscan).
- **Mechanism:** Mid-scanline register writes change the picture in
  lockstep with the beam; the ~22-cycle horizontal blank is the only safe
  setup window. One cycle late = wrong color in the wrong place, so
  programmers hand-counted cycles like drummers.
- **Why it died:** Cost-cut design became a liability once framebuffer
  consoles (NES era) arrived; the 1983 crash finished it. Survives in
  homebrew/demoscene (Stella debugger still counts scanlines).
- **Revival recipe:** Frame-as-kernel execution — slice work into
  fixed-cost quanta with a hard per-slice budget and an inviolable
  reserved slice (the heartbeat) that always gets serviced.
- **LEVI application:** Daemon supervision executor: automation runs
  sliced into bounded budgets so a runaway task can never starve the
  heartbeat tick. Same for bounded simulation budgets.
- **Rating:** load-bearing. Status: technique-alive.

## 2. Amiga Copper: timed choreography as a 3-instruction scored list

- **What/when:** Commodore Amiga (1985). A display-synchronized
  co-processor running lists of just 3 instructions: MOVE (write a
  hardware register), WAIT (stall until the beam reaches x,y), SKIP (skip
  the next MOVE if a condition holds). Lists restart at each VBLANK.
- **Mechanism:** `WAIT (0,64); MOVE COLOR00 $0f0; WAIT (0,128); MOVE
  COLOR00 $00f` draws two color zones with no CPU and no interrupts.
  A final WAIT for an impossible position parks the Copper until restart.
- **Why it died:** Amiga's commercial death + commodity GPUs absorbing
  the pattern (raster interrupts, shaders). It didn't lose technically —
  its platform died.
- **Revival recipe:** Scored choreography: declarative WAIT/EXEC/SKIP
  lists against a real or simulated clock, producing a receipt of what
  ran and when. No timers, no callbacks — the list IS the program.
- **LEVI application:** `core/levi/copper/` — built this wave under the
  standing approval. Supervision recovery sequences and automation
  routines as scores; FakeClock gives deterministic replay for tests
  and bounded simulation.
- **Rating:** load-bearing. Status: absorbed.

## 3. Palm Graffiti: narrow the input, gain reliability

- **What/when:** Palm Computing's Graffiti (1994), shipped in the Pilot
  (1996). Single-stroke shorthand alphabet users learn (~20 minutes to
  competence; Palm claimed near-100% accuracy and >30 wpm).
- **Mechanism:** Constrain the input space instead of expanding the
  recognizer: one prescribed stroke per character; stroke end = commit.
  Palm made the human adapt a little so the machine could be exact —
  where Newton tried to recognize natural handwriting and failed.
- **Why it died:** Capacitive multitouch killed stylus PDAs; survives as
  a third-party Android keyboard. The principle died with the platform,
  not on its merits.
- **Revival recipe:** For high-stakes agent actions, define a closed set
  of unambiguous command forms instead of parsing free text. Narrow the
  channel where reliability matters rather than widening the model.
- **LEVI application:** Consequential-action confirmations get a
  closed, exact-match command vocabulary for approve/deny/abort —
  no fuzzy intent parsing at the permission gate.
- **Rating:** useful-pattern. Status: technique-alive.

## 4. ZX Spectrum multicolor: exploit the hardware's re-read moment

- **What/when:** ZX Spectrum (1982), £125 target. 256×192 bitmap plus a
  32×24 attribute grid (one byte per 8×8 cell: ink/paper/bright/flash —
  borrowed from Teletext). Infamous attribute clash.
- **Mechanism:** The ULA re-reads attribute RAM every scanline, so
  writing a new value during horizontal blank yields 8×1 'multicolor/
  hicolour' over ~20 columns (CPU too slow for full width), or 8×2 over
  the full width (Nirvana+ engine). The impossible becomes possible by
  piggybacking the hardware's natural re-read moment.
- **Why it died:** Price-point compromise outcompeted by better cheap
  graphics; survives in demoscene folklore.
- **Revival recipe:** Schedule state mutations at the system's natural
  re-read boundaries rather than adding new machinery.
- **LEVI application:** Growth-loop bookkeeping piggybacks journal
  compaction on heartbeat boundaries instead of running a separate
  timer — "write in the blank": bounded, predictable, zero new timers.
- **Rating:** useful-pattern. Status: technique-alive.

## Honest skepticism

- Cycle counts (76/scanline) are NTSC-specific; PAL machines differ.
- Palm's "100% accuracy / 30 wpm" claims are vendor claims from 1994
  press materials — plausible directionally, not independently verified
  here.
- The LEVI applications are analyses, not measured results; the copper
  executor is built and tested, the rest are recipes.
