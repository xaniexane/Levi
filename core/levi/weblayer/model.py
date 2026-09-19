"""Hotspot model — the Web layer's load-bearing primitive.

A canvas carries hotspots: regions (rectangles, ellipses, polygons) that
each know what they are for on the web — a link, a label, an action.
Clean-room take on the pattern Macromedia Fireworks died with: design
regions that carry their own behavior.

Everything is stdlib-only, local-first. Validation is deny-closed:
malformed hotspots are refused, never half-built.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_SHAPES = ("rect", "ellipse", "polygon")
_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError("weblayer: %s" % msg)


@dataclass
class Hotspot:
    """One clickable region on a canvas."""

    id: str
    shape: str
    coords: List[float]
    href: str
    label: str = ""
    alt: str = ""

    def validate(self, width: float, height: float) -> None:
        _need(bool(_ID_RE.fullmatch(self.id)), "bad hotspot id %r" % self.id)
        _need(self.shape in _SHAPES, "shape must be one of %s" % (_SHAPES,))
        _need(self.coords and all(isinstance(c, (int, float)) for c in self.coords),
              "coords must be a non-empty number list")
        if self.shape == "rect":
            _need(len(self.coords) == 4, "rect needs 4 coords (x,y,w,h)")
            x, y, w, h = self.coords
            _need(w > 0 and h > 0, "rect must have positive size")
            _need(x >= 0 and y >= 0 and x + w <= width and y + h <= height,
                  "rect %r exceeds canvas %sx%s" % (self.id, width, height))
        elif self.shape == "ellipse":
            _need(len(self.coords) == 4, "ellipse needs 4 coords (cx,cy,rx,ry)")
            cx, cy, rx, ry = self.coords
            _need(rx > 0 and ry > 0, "ellipse must have positive radii")
            _need(cx - rx >= 0 and cy - ry >= 0 and cx + rx <= width and cy + ry <= height,
                  "ellipse %r exceeds canvas %sx%s" % (self.id, width, height))
        else:  # polygon
            _need(len(self.coords) >= 6 and len(self.coords) % 2 == 0,
                  "polygon needs >=3 (x,y) pairs")
            xs = self.coords[0::2]
            ys = self.coords[1::2]
            _need(all(0 <= x <= width for x in xs) and all(0 <= y <= height for y in ys),
                  "polygon %r exceeds canvas %sx%s" % (self.id, width, height))
        _need(isinstance(self.href, str) and self.href.strip(), "href is required")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "shape": self.shape, "coords": list(self.coords),
            "href": self.href, "label": self.label, "alt": self.alt,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Hotspot":
        try:
            return cls(id=d["id"], shape=d["shape"], coords=list(d["coords"]),
                       href=d["href"], label=d.get("label", ""), alt=d.get("alt", ""))
        except (KeyError, TypeError) as exc:
            raise ValueError("weblayer: malformed hotspot dict: %s" % exc)


@dataclass
class Canvas:
    """A canvas with a Web layer of hotspots."""

    width: int
    height: int
    title: str = "weblayer canvas"
    image: Optional[str] = None  # local image path the map sits over
    hotspots: List[Hotspot] = field(default_factory=list)

    def validate(self) -> None:
        _need(isinstance(self.width, int) and isinstance(self.height, int)
              and self.width > 0 and self.height > 0, "canvas needs positive int size")
        seen = set()
        for h in self.hotspots:
            _need(h.id not in seen, "duplicate hotspot id %r" % h.id)
            seen.add(h.id)
            h.validate(self.width, self.height)

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {"width": self.width, "height": self.height, "title": self.title,
                "image": self.image, "hotspots": [h.to_dict() for h in self.hotspots]}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Canvas":
        try:
            c = cls(width=d["width"], height=d["height"], title=d.get("title", "weblayer canvas"),
                    image=d.get("image"), hotspots=[Hotspot.from_dict(h) for h in d.get("hotspots", [])])
        except (KeyError, TypeError) as exc:
            raise ValueError("weblayer: malformed canvas dict: %s" % exc)
        c.validate()
        return c
