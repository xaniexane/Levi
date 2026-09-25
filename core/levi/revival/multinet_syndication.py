"""multinet_syndication — one backend, many networks.

Studied from: dead-networks-20260916/report.md (ZiffNet / PC MagNet:
one editorial backend publishing simultaneously to CompuServe,
Prodigy, AOL, AppleLink).

The load-bearing idea: authorship happens once, in one place; each
network gets its own adapter that reshapes the piece to that
network's constraints — line length, title caps, tag support — and
the same editorial unit lands everywhere simultaneously. The adapter
layer is the product.

LEVI's take: ``Article`` is the single source of truth.
``NetworkAdapter`` declares a network's constraints (title/body caps,
tag support, line width) and ``format`` renders a compliant
``Payload``. ``Syndicator.publish`` runs one article through any set
of adapters and reports per-network payloads plus what was trimmed.
This is an original, from-scratch implementation for LEVI.

Honest limits: this is a formatting/dispatch layer, not a network
client — ``publish`` returns payloads ready to hand to a transport,
it never sends anything (stdlib-only, local-first, no network).
Truncation is reported, never silent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

ORIGIN = "levi-revival/multinet-syndication"


@dataclass(frozen=True)
class Article:
    """The single editorial source of truth."""

    title: str
    body: str
    author: str = ""
    tags: tuple = ()


@dataclass(frozen=True)
class Payload:
    """A network-ready rendering of an article."""

    network: str
    title: str
    body: str
    tags: tuple
    title_trimmed: bool = False
    body_trimmed: bool = False
    tags_dropped: bool = False


def _trim(text: str, cap: Optional[int]) -> tuple:
    if cap is None or len(text) <= cap:
        return text, False
    cut = text[:cap].rstrip()
    return cut + "...", True


@dataclass
class NetworkAdapter:
    """One network's editorial constraints."""

    name: str
    title_cap: Optional[int] = None
    body_cap: Optional[int] = None
    supports_tags: bool = True
    line_width: Optional[int] = None
    prefix: str = ""

    def format(self, article: Article) -> Payload:
        title, t_trim = _trim(article.title.strip(), self.title_cap)
        body, b_trim = _trim(article.body.strip(), self.body_cap)
        tags: tuple = article.tags
        dropped = False
        if not self.supports_tags and tags:
            tags, dropped = (), True
        if self.prefix:
            body = self.prefix + body
        if self.line_width:
            body = "\n".join(
                _wrap(paragraph, self.line_width) for paragraph in body.split("\n")
            )
        return Payload(
            network=self.name,
            title=title,
            body=body,
            tags=tags,
            title_trimmed=t_trim,
            body_trimmed=b_trim,
            tags_dropped=dropped,
        )


def _wrap(paragraph: str, width: int) -> str:
    words, lines, current = paragraph.split(), [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return "\n".join(lines)


class Syndicator:
    """Publishes one article to many networks through their adapters."""

    def __init__(self, adapters: Optional[List[NetworkAdapter]] = None) -> None:
        self._adapters: Dict[str, NetworkAdapter] = {}
        for adapter in adapters or []:
            self.add(adapter)

    def add(self, adapter: NetworkAdapter) -> None:
        if not adapter.name.strip():
            raise ValueError("adapter name must be non-empty")
        self._adapters[adapter.name] = adapter

    def networks(self) -> List[str]:
        return sorted(self._adapters)

    def publish(
        self, article: Article, networks: Optional[List[str]] = None
    ) -> Dict[str, Payload]:
        """Render ``article`` for each chosen network (default: all)."""
        chosen = networks if networks is not None else self.networks()
        result: Dict[str, Payload] = {}
        for name in chosen:
            adapter = self._adapters.get(name)
            if adapter is None:
                raise KeyError(f"no adapter for network {name!r}")
            result[name] = adapter.format(article)
        return result


# Four example network profiles with distinct constraints.
CLASSIC_NETWORKS = [
    NetworkAdapter(name="CompuServe", title_cap=40, body_cap=2000, line_width=70),
    NetworkAdapter(name="Prodigy", title_cap=30, body_cap=800, supports_tags=False),
    NetworkAdapter(name="AOL", title_cap=60, body_cap=4000, line_width=72),
    NetworkAdapter(name="AppleLink", title_cap=24, body_cap=500, supports_tags=False),
]


def demo() -> dict:
    """Syndicate one article to the four classic networks."""
    syndicator = Syndicator(CLASSIC_NETWORKS)
    article = Article(
        title="Local-first synthetic intelligence goes offline for real",
        body=(
            "LEVI's native brain now trains on its own corpus with no "
            "cloud in the loop. The full pipeline — harvest, reflect, "
            "consolidate, journal — runs on-device, and the baby book "
            "records every learning."
        ),
        author="levi",
        tags=("synthetic-intelligence", "local-first"),
    )
    payloads = syndicator.publish(article)
    return {
        network: {
            "title": p.title,
            "body_chars": len(p.body),
            "trimmed": p.title_trimmed or p.body_trimmed or p.tags_dropped,
        }
        for network, p in sorted(payloads.items())
    }
