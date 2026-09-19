"""The honest Web layer — LEVI's native answer to Fireworks' murder.

Macromedia Fireworks (1998-2013) died with Adobe for 'overlap': a web-first
hybrid canvas where slices became HTML elements and hotspots became
hyperlinks. LEVI takes the load-bearing pattern — regions of a canvas that
carry their own behavior — and adds it natively: define hotspot regions on
a canvas, attach local links, export to tracking-free HTML image-maps and
interactive SVG. No editor rebuild, no subscription, no toll.

Born from the murdered-creatives hunt (evening-20260918-creatives).
Stdlib-only, local-first, clean-room — the hard route.
"""

from .model import Canvas, Hotspot
from .export import to_html, to_svg

__all__ = ["Canvas", "Hotspot", "to_html", "to_svg"]
