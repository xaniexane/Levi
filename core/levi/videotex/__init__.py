"""LEVI videotex — the Minitel-heritage terminal navigation layer.

REMIX DELTA: Minitel (France, 1982-2012, ~9M terminals at peak), Prestel
(UK), Bildschirmtext/BTX (Germany), and Telidon (Canada) put whole
nations on numbered-tree services: 40 columns x 25 rows, no mouse, no
images, no tracking. You typed a service number, pressed ENVOI, and the
tree walked you down. The giants killed this pattern twice: first the web
replaced numbered trees with hyperlinks, then the app era replaced every
dumb terminal with a surveillance surface that needs a GPU, a JS engine,
and your identity. With it died the only UI that works on *any*
terminal — a serial console, a screen reader, Termux on a phone with one
bar of signal, 1200 baud.

This module revives the tree, not the terminal:

- :mod:`levi.videotex.keys` — Minitel function-key semantics on plain
  ASCII: ``*`` = RETOUR (back), ``#`` = ENVOI (confirm), ``sommaire`` =
  contents/home, ``suite`` = next page, ``guide`` = help,
  ``annulation`` = cancel, ``repetition`` = redraw, ``correction`` =
  clear the input line.
- :mod:`levi.videotex.pages` — the page model. 40-column wrapped text,
  numbered choices, breadcrumb trail. Content adapters read the
  filesystem only (``docs/``, ``docs/WAREHOUSES.md``) and degrade
  honestly when a source is missing — never importing sibling packages.
- :mod:`levi.videotex.navigate` — the navigator state machine: history
  stack, choice chunking (8 per screen, ``suite`` for more), and a
  scriptable ``run_script()`` so every session is testable.

What it ADDS that the giants refuse:
- All of LEVI browsable from the dumbest terminal in the house. No JS,
  no GPU, no account, no telemetry, no engagement surface — attention
  that cannot be monetized is attention the giants will not serve.
- The passive-terminal law: videotex *shows*, it never *executes*.
  Every choice navigates to another page; nothing here runs commands,
  writes files, or spends money. A Minitel terminal was passive, and
  LEVI's stays passive — action happens in the CLI, behind
  Plan -> Preview -> Permission.

Safety boundaries: read-only by construction (choice targets are page
ids, never callables with side effects); adapters never execute file
content, only display wrapped text; no network, no credentials.

Run: ``python -m levi.videotex --help``
"""

from __future__ import annotations

__all__ = ["PAGE_WIDTH", "CHOICES_PER_SCREEN"]

PAGE_WIDTH = 40
CHOICES_PER_SCREEN = 8
