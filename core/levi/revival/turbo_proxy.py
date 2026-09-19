"""Degraded-mode compression pipeline, Opera Turbo shaped.

Studied from: desktop-casualties-20260916/report.md [1. Opera]

Functional description: a page model (HTML text plus attached assets) is
run through a compression pipeline that trades fidelity for bytes. Each
stage is honest about what it degrades: whitespace collapsing, comment
stripping, image downsampling to placeholders that keep alt text and
dimensions, and optional script deferral. The pipeline reports per-stage
and total savings as a fraction of the original byte size, and a toggle
with an always-visible status indicator (the "green light") shows whether
turbo mode is on — degraded-mode honesty: the indicator never claims a
page is unmodified when a stage ran.

Pure Python, stdlib only. No provider branding. Not artificial — synthetic.

Honest limits: the compression is heuristic (regex-level HTML minifying,
placeholder images), not a real proxy codec; savings are computed against
the in-memory page model, not measured over a network; "up to 80%" style
claims are never asserted — the report carries the actual measured ratio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

ORIGIN = "levi-revival/turbo-proxy"


@dataclass
class PageAsset:
    """An attached asset: images, scripts, styles."""

    kind: str  # "image", "script", "style"
    name: str
    size: int
    alt: str = ""


@dataclass
class PageModel:
    """A page as the proxy sees it: HTML plus assets."""

    html: str
    assets: List[PageAsset] = field(default_factory=list)

    def byte_size(self) -> int:
        return len(self.html.encode("utf-8")) + sum(a.size for a in self.assets)


@dataclass
class StageReport:
    stage: str
    bytes_saved: int
    degraded: bool
    note: str


@dataclass
class TurboReport:
    original_bytes: int
    final_bytes: int
    stages: List[StageReport] = field(default_factory=list)

    @property
    def savings_ratio(self) -> float:
        if self.original_bytes == 0:
            return 0.0
        return (self.original_bytes - self.final_bytes) / self.original_bytes

    def degraded(self) -> bool:
        return any(s.degraded for s in self.stages)


def _collapse_whitespace(html: str) -> str:
    out = re.sub(r">\s+<", "><", html)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def _strip_comments(html: str) -> str:
    return re.sub(r"<!--(?!\[if).*?-->", "", html, flags=re.DOTALL)


def _placeholder_images(assets: List[PageAsset]) -> List[PageAsset]:
    """Replace image payloads with tiny placeholders; keep alt text."""
    out = []
    for asset in assets:
        if asset.kind == "image":
            out.append(
                PageAsset(
                    kind="image",
                    name=asset.name,
                    size=min(asset.size, 256),  # placeholder budget
                    alt=asset.alt,
                )
            )
        else:
            out.append(asset)
    return out


class TurboProxy:
    """The compression pipeline with its honest toggle."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self._runs = 0

    def toggle(self, on: bool) -> None:
        self.enabled = bool(on)

    def status(self) -> Dict[str, object]:
        """The always-visible indicator: on/off plus lifetime run count."""
        return {
            "turbo": "ON" if self.enabled else "OFF",
            "indicator": "green" if self.enabled else "grey",
            "runs": self._runs,
        }

    def fetch(self, page: PageModel) -> tuple[PageModel, TurboReport]:
        """Run the page through the pipeline if enabled; else pass through.

        Returns the (possibly degraded) page and an honest report. When the
        toggle is off, the report says so and savings are zero — the
        indicator never claims compression that did not happen.
        """
        original = page.byte_size()
        report = TurboReport(original_bytes=original, final_bytes=original)
        if not self.enabled:
            return page, report

        self._runs += 1
        html = page.html
        assets = list(page.assets)

        collapsed = _collapse_whitespace(html)
        saved = len(html.encode()) - len(collapsed.encode())
        report.stages.append(
            StageReport(
                "whitespace",
                max(0, saved),
                False,
                "collapsed runs of whitespace between tags",
            )
        )
        html = collapsed

        stripped = _strip_comments(html)
        saved = len(html.encode()) - len(stripped.encode())
        report.stages.append(
            StageReport("comments", max(0, saved), False, "removed HTML comments")
        )
        html = stripped

        before_assets = sum(a.size for a in assets)
        assets = _placeholder_images(assets)
        after_assets = sum(a.size for a in assets)
        report.stages.append(
            StageReport(
                "images",
                before_assets - after_assets,
                True,
                "images replaced by placeholders (alt text kept)",
            )
        )

        degraded = PageModel(html=html, assets=assets)
        report.final_bytes = degraded.byte_size()
        return degraded, report
