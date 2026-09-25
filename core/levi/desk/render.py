"""Render the desk: each enabled tile in layout order, errors isolated.

A tile that throws, returns non-lines, or references nothing registered
renders a one-line honest placeholder — the desk itself never fails.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .layout import DeskLayout
from .registry import TileRegistry, register_builtin_tiles

_RULE = "-" * 40


def render_desk(registry: Optional[TileRegistry] = None,
               base: Optional[Path] = None) -> str:
    reg = registry or TileRegistry()
    if registry is None:
        register_builtin_tiles(reg)
    layout = DeskLayout(base=base)
    lines: List[str] = ["YOUR DESK", _RULE]
    shown = 0
    for entry in layout.entries():
        if not entry["enabled"]:
            continue
        name = entry["tile"]
        tile = reg.get(name)
        if tile is None:
            lines += ["[%s]" % name, "  (tile not registered — removed or renamed)",
                      _RULE]
            continue
        lines.append("[%s] %s" % (name, tile.title))
        prefs = dict(tile.default_prefs)
        prefs.update(entry["prefs"])
        try:
            rendered = tile.render(prefs)
            if not isinstance(rendered, list):
                lines.append("  (tile returned non-lines — refused)")
            elif not rendered:
                lines.append("  (nothing to show)")
            else:
                lines += ["  " + str(line) for line in rendered]
        except Exception as exc:  # a tile may never sink the desk
            lines.append("  (tile error: %s)" % exc.__class__.__name__)
        lines.append(_RULE)
        shown += 1
    if shown == 0:
        lines.append("(empty desk — add tiles with: python -m levi.desk add <name>)")
    return "\n".join(lines) + "\n"
