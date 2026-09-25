# Retired software with load-bearing ideas — hunt 2026-09-23

Theme (a): retired software whose honesty or ahead-of-its-time mechanism the
winners never absorbed. Four finds, none previously covered (Improv, HyperCard,
HotSync, Sidekick are all absent from the pending waves and build queue;
Lotus Agenda+Ecco and Director were already queued and therefore excluded).

## Finds

1. **Lotus Improv (1991-1996)** — the cube spreadsheet: dimensions first,
   formulas on named members instead of cell addresses, views as projections.
   Killed by IBM's acquisition, its own company's immune response, Excel
   bundling, and in-memory cubes on 1990s hardware. → BUILDING NOW as
   `core/levi/cube/`, a stdlib dimension-first pivot engine.

2. **HyperCard (1987-2004)** — shipped free with every Mac; the tool and the
   artifact were the same thing; HyperTalk inspired JavaScript; Myst was built
   in it. Killed by neglect (no color, no web, 3.0 stalled, Jobs reassigned
   the team in 2000, sales ceased 2004). → QUEUED: native stack-authoring
   primitive (cards as live scriptable documents), larger build.

3. **Palm HotSync (1996-2009)** — one-button local sync via open conduit
   plugins; your computer was the server, no cloud, no account. Killed by the
   smartphone/cloud recentralization (Apple dropped the conduit in Snow
   Leopard, 2009). The local-only sync capability is still cited as missing
   on modern platforms. → QUEUED: `core/levi/conduit/` honest local sync.

4. **Borland Sidekick (1984-1999)** — TSR resident PIM: Ctrl-Alt from any
   program, tools popped up, work untouched underneath; 1M+ copies at $49.95.
   Killed by protected-mode multitasking making the hack unnecessary; the
   idea was re-absorbed into trays and notification shades that serve the
   platform. → ARCHIVED as inspiration (resident quick-capture; LEVI's
   quickdial/daemon partly cover the ground).

## Skepticism ledger

- Improv was genuinely harder to learn; Spolsky's generality critique stands.
- HyperCard's ceiling (1-bit, slow) was real; FileMaker outgrew it honestly.
- HotSync could duplicate records; the conduit contract is the living part.
- Sidekick's TSRs crashed machines; ambient residency is the living part.

## Sources

Two per find, recorded in findings.jsonl: Wikipedia pages for all four,
plus instadeq (Improv), eclecticlight (HyperCard), AppleInsider + TechSpot
(HotSync), eWeek (Sidekick).
