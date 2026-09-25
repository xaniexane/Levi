"""LEVI pdi — Picture Description Instructions, an ASCII vector-graphics opcode stream.

REMIX DELTA: NAPLPS (1982, born of Canada's Telidon videotex program)
encoded vector graphics as compact *binary* Picture Description
Instructions — opcodes for lines, arcs, and fills that flew over
broadcast teletext and rendered on anything from a TV to a workstation.
Videotex died in the 90s, and with it died the only mainstream
resolution-independent graphics language that *wasn't* a bitmap. This
module revives the idea, not the wire format:

- :mod:`levi.pdi.pdi` — a human-readable, one-opcode-per-line ASCII
  stream (``L``, ``R``, ``E``, ``T``, ``P``, ``K``, ``C``) parsed into a
  Picture and rendered to well-formed SVG or a terminal ASCII-art
  preview. Device-independent 0..100 coordinate space; LEVI's own
  8-color palette.
- CLI: ``python -m levi.pdi render|validate``

EXPLICITLY NOT NAPLPS-COMPATIBLE: different coordinate model
(0..100 device space vs NAPLPS pixel units), ASCII vs binary opcodes,
LEVI's own palette — a remix, not a replica.

What it ADDS that the giants refuse:
- Diagrams as version-controllable, diffable plain text — grep-able,
  hand-editable, sendable over any wire.
- Offline SVG + ASCII previews with zero dependencies (stdlib only).

Research: perpetual-hunt wave-008, slug ``dead-networks-20260916``.

Stateless: this module keeps NO data directory — parsing and rendering
are pure functions; use tmp files only for CLI file-input plumbing.

Run: ``python -m levi.pdi --help``
"""

from __future__ import annotations

__all__ = [
    "SHELF",
]

SHELF = {
    "name": "pdi diagrams",
    "summary": (
        "Compact ASCII opcode streams for vector graphics, remixed from "
        "NAPLPS/Telidon Picture Description Instructions: one-opcode-per-line "
        "PDI streams parse into Pictures and render to well-formed SVG or "
        "terminal ASCII-art previews. Device-independent 0..100 coordinate "
        "space, LEVI's own 8-color palette, stdlib only."
    ),
    "items": [
        "pdi: parse() PDI streams into Picture (line-numbered PDIError)",
        "pdi: validate() non-raising check returning error strings",
        "pdi: render_svg() well-formed SVG, K palette 0-7, escaped text",
        "pdi: render_ascii() Bresenham lines, rect outlines, parametric "
        "ellipses, clipped text stamps",
        "CLI: python -m levi.pdi render [--svg|--ascii] | validate",
    ],
}
