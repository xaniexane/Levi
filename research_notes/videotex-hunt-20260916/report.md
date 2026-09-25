# Hunt report — wave-017: dead protocols, deeper vein

Theme: **Dead protocols** (second pass — beyond Chappe semaphore,
prosigns/prowords, Q-codes, telegraph codebooks, already covered).
Vein: **videotex / numbered-tree terminal services** — Minitel, Prestel,
Bildschirmtext, Telidon, and the function-key ritual.

## Pattern analysis

**What was built.** France put a free Minitel terminal in millions of
homes (1982) and numbered the nation's services: 3615 codes, typed a
number, pressed ENVOI. ~9M terminals at peak; train times, chat,
banking, all on 40×25 text at 1200/75 baud. The UK (Prestel), Germany
(Bildschirmtext/BTX), and Canada (Telidon) ran the same playbook with
local variations.

**What was refused.** Every constraint that made it work: 40 columns,
no images, no mouse, no tracking, no engagement metrics, no identity
beyond the phone line. The giants' business is monetizable attention;
a UI that cannot show ads or harvest behavior is a UI they will not
build — then or now.

**What was killed.** The web's hyperlink model killed the numbered tree;
the app era killed the dumb terminal as a first-class citizen. The
Minitel network shut down 30 June 2012.

**The sly-generosity trade.** Free terminals to sell metered services —
give away the endpoint, meter the usage. The direct ancestor of the
modern free-hardware / free-tier-for-metered-billing playbook (app
stores, cloud free tiers, subsidized phones).

**Romanticism flags.** Minitel nostalgia often forgets the metered
billing that made 3615 codes a small fortune, and the state-monopoly
context (France Télécom) that made universal rollout possible. Neither
is revived here.

## The addition: LEVI videotex

`core/levi/videotex/` — a Minitel-heritage navigation layer for LEVI.
Numbered trees over the warehouse inventory and the full docs library,
Minitel function-key semantics on plain ASCII (`*` RETOUR, `#` ENVOI,
`sommaire`, `suite`, `guide`, `annulation`, `repetition`,
`correction`), 40-column homage wrapping, and the passive-terminal law:
it shows, it never executes — choice targets are page ids,
structurally incapable of side effects.

Why the giants refuse it: it works on a serial console, a screen
reader, and Termux on one bar of signal — with zero telemetry, zero
ads, zero engagement surface. LEVI ships it because where there isn't
a way, LEVI creates one — including no-GUI, no-bandwidth ways in.

## Findings (ArchiveRecords in findings.jsonl)

1. Minitel system (1982–2012) — load-bearing
2. Numbered-tree service navigation — load-bearing
3. ENVOI/RETOUR/SOMMAIRE function-key ritual — useful-pattern
4. 3615 metered service codes — useful-pattern (the trade, not the billing)
5. Prestel (UK) — inspirational
6. Telidon (Canada) — inspirational
