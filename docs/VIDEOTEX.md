# LEVI Videotex — the Minitel-heritage terminal layer

`python -m levi.videotex` — browse LEVI from any terminal, Minitel-style.

## What it is

A numbered-tree navigation layer in the spirit of Minitel (France,
1982–2012), Prestel, and Bildschirmtext: 40-column pages, numbered
services, function keys on plain ASCII. The whole LEVI docs library and
warehouse inventory, readable from the dumbest terminal in the house —
a serial console, a screen reader, Termux on a phone with one bar of
signal.

## Keys

| Key | Minitel original | Does |
|---|---|---|
| `1`–`8` | number + ENVOI | choose a service |
| `*` | RETOUR | back one level (`*` at root hangs up) |
| `#` | ENVOI | confirm (folded into bare numbers) |
| `sommaire` | SOMMAIRE | contents / home |
| `suite` | SUITE | next chunk of choices |
| `guide` | GUIDE | key help |
| `repetition` | REPETITION | redraw the page |
| `correction` | CORRECTION | clear input, redraw |
| `annulation` | ANNULATION | back (`annulation` at root quits) |

## The passive-terminal law

Videotex **shows, never executes**. Every choice navigates to another
page — choice targets are page ids, structurally incapable of carrying
side effects. Action happens in the CLI, behind Plan → Preview →
Permission. A Minitel terminal was passive, and LEVI's stays passive.

## Pattern analysis (why this is an addition, not a rebuild)

- **Built:** Minitel put ~9M terminals in French homes; Prestel, BTX,
  and Telidon ran the same playbook elsewhere. Numbered trees, metered
  3615 service codes, ENVOI-to-confirm.
- **Refused:** the giants refused every constraint that made it work —
  40×25 text, no images, no tracking, no engagement metrics. Attention
  that cannot be monetized is attention they will not serve.
- **Killed:** the web's hyperlink model, then the app era's
  surveillance surfaces, killed the dumb terminal as a first-class UI.
- **Sly-generosity trade:** free Minitel terminals to sell metered
  services — the ancestor of today's free-hardware-for-metered-billing
  playbook (app stores, cloud free tiers).
- **LEVI's addition:** nobody sells a text-tree interface in 2026
  because it can't show ads or harvest behavior. LEVI ships one because
  "where there isn't a way, LEVI creates one" — including no-GUI,
  no-bandwidth, no-sight ways in.

## Honest limits

- Reading and navigation only; no command execution, no writes.
- Adapters read the filesystem (`docs/`, `docs/WAREHOUSES.md`) and say
  so when a source is missing — they never import sibling packages.
- 40-column wrap is an homage, not a real Videotex protocol
  implementation; this is not wire-compatible with Minitel hardware.
