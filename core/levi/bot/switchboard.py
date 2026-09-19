"""Switchboard — the inbound router bot for LEVI.

Switchboard hears an incoming request and routes it: it scores the request
text against every module's declared capabilities in the interop manifest
and returns ranked routing candidates with receipts. Deterministic,
keyword-based, explainable — and honest: when nothing matches, it returns
an ``unrouted`` receipt instead of guessing.

Switchboard computes; it never acts. The chosen module's own CLI or API is
what actually runs.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from levi.interop.manifest import DECLARATIONS

_WORD = re.compile(r"[a-z0-9]+")

#: Tokens too generic to route on.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "my",
        "me",
        "i",
        "you",
        "it",
        "is",
        "are",
        "do",
        "does",
        "did",
        "what",
        "how",
        "why",
        "when",
        "where",
        "please",
        "can",
        "could",
        "should",
        "would",
        "will",
        "be",
        "this",
        "that",
        "there",
        "here",
        "get",
        "set",
        "make",
        "show",
        "list",
        "run",
        "now",
    }
)

#: Extra signal words wired to modules, because capability names are terse.
_SIGNAL_HINTS: Dict[str, List[str]] = {
    "daemon": ["daemon", "background", "always", "supervisor", "restart", "uptime"],
    "perpetual": ["forever", "never", "hunt", "cron", "periodic"],
    "automation": ["automate", "schedule", "routine", "minion", "workflow"],
    "memory-store": ["remember", "recall", "memory", "forget"],
    "rag": ["question", "answer", "cite", "document"],
    "archive": ["history", "record", "find", "lost", "forgotten"],
    "finance": ["stock", "market", "price", "trade", "portfolio"],
    "king": ["king", "post", "social", "publish"],
    "academy": ["learn", "course", "teach", "lesson"],
    "cyber-skills": ["security", "hardening", "threat", "defense", "detection"],
    "bot-services": ["service", "research", "brief"],
    "growth": ["grow", "reflect", "journal", "baby"],
    "factory": ["build", "generate", "code", "scaffold"],
    "integrations": ["termux", "android", "phone", "device", "battery"],
}


@dataclass
class Route:
    """One routing candidate with its evidence."""

    module: str
    matched: List[str] = field(default_factory=list)
    score: int = 0
    confidence: float = 0.0

    @property
    def routed(self) -> bool:
        return self.module != "unrouted"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def tokenize(text: str) -> List[str]:
    """Lowercase word tokens with stopwords removed."""
    return [t for t in _WORD.findall(text.lower()) if t not in _STOPWORDS]


def _cap_tokens(capability: str) -> List[str]:
    return [t for t in re.split(r"[.\-_]", capability.lower()) if t]


def score_module(module: str, tokens: List[str]) -> Route:
    """Score one manifest module against request tokens."""
    declaration = DECLARATIONS.get(module, {})
    provides = declaration.get("provides", [])
    token_set = set(tokens)
    matched: List[str] = []
    score = 0
    for cap in provides:
        cap_toks = _cap_tokens(cap)
        hits = [t for t in cap_toks if t in token_set and t not in _STOPWORDS]
        if hits:
            matched.append(cap)
            score += len(hits)
    hint_hits = sum(1 for h in _SIGNAL_HINTS.get(module, []) if h in token_set)
    score += hint_hits
    if hint_hits:
        matched.append(f"signal:{module}")
    confidence = min(1.0, score / 4.0)
    return Route(module=module, matched=matched, score=score, confidence=confidence)


def route(text: str, *, top_n: int = 3, min_score: int = 1) -> List[Route]:
    """Route ``text`` to manifest modules, best-first.

    Returns ranked :class:`Route` candidates with at least ``min_score``.
    When nothing scores, returns a single ``unrouted`` receipt — never a
    guess.
    """
    tokens = tokenize(text)
    if not tokens:
        return [Route(module="unrouted", score=0, confidence=0.0)]
    scored = [score_module(m, tokens) for m in DECLARATIONS]
    ranked = sorted(
        (r for r in scored if r.score >= min_score),
        key=lambda r: (r.score, r.module),
        reverse=True,
    )
    if not ranked:
        return [Route(module="unrouted", score=0, confidence=0.0)]
    return ranked[: max(1, top_n)]


def route_summary(routes: List[Route]) -> str:
    """One-line-per-route human summary of a routing."""
    lines = []
    for r in routes:
        if not r.routed:
            lines.append("unrouted: nothing in the manifest matched — no guess made")
            continue
        matched = ", ".join(r.matched[:3])
        lines.append(
            f"{r.module} (score={r.score}, conf={r.confidence:.2f}): {matched}"
        )
    return "\n".join(lines)


def _cli(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="levi.bot.switchboard",
        description="Route an incoming request to LEVI manifest modules.",
    )
    ap.add_argument("text", nargs="?", default="", help="request text to route")
    ap.add_argument("--top", type=int, default=3, help="max candidates to show")
    ap.add_argument("--repl", action="store_true", help="interactive routing REPL")
    args = ap.parse_args(argv)

    if args.repl:
        print("switchboard — type a request, blank line quits")
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                break
            print(route_summary(route(line, top_n=args.top)))
        return 0
    if not args.text:
        ap.error("request text is required (or --repl)")
    print(route_summary(route(args.text, top_n=args.top)))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
