"""Briefing renderer — Brand24's digests, our physics.

Renders a tiered briefing document into the file outbox:
  BREAKING   — ternary breakout states
  GATHERING  — ternary gathering states (the skipped third state, visible)
  WATCHING   — feed-tiered items that are neither
  QUIET      — the rest, summarized
  QUARANTINED — appendix: held back under the label law, never published
  LEGEND     — what OBSERVED / INFERENCE / HYPOTHESIS mean

The renderer produces the body an email WOULD carry — and stops there.
File outbox only. Nothing is emailed, pushed, or otherwise sent by this
module; the file carries a header that says so. Themes come from
levi.demandpulse.themes (validated packs, safe structured tokens).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence

from levi.demandpulse.ternary import BREAKOUT, DORMANT, GATHERING, TernarySignal
from levi.demandpulse.themes import get_theme, paint, rule_line

LEGEND = (
    "OBSERVED: fetched text, basis named.  "
    "INFERENCE: computed over observations, basis named.  "
    "HYPOTHESIS: scored opportunity — advisory, never a claim about real demand."
)

OUTBOX_NOTICE = (
    "FILE OUTBOX ONLY — this briefing was written to a file and sent nowhere. "
    "Email/push channels are not configured."
)


def _section(title: str, lines: List[str], theme: Mapping[str, str]) -> List[str]:
    out = [paint(theme, "accent", title), rule_line(theme)]
    out.extend(lines if lines else [paint(theme, "dim", "(none)")])
    out.append("")
    return out


def render_briefing(
    digest: Any,
    ternary_states: Sequence[TernarySignal] = (),
    theme: str = "void",
) -> str:
    """Render a briefing from a digest (levi.demand.feed.Digest or mapping)
    plus optional ternary states. Pure function — no I/O."""
    th = get_theme(theme)
    bullet = th["bullet"]

    if hasattr(digest, "to_record"):
        record = digest.to_record()
    else:
        record = dict(digest)

    items = list(record.get("items", []) or [])
    quarantined = list(record.get("quarantined", []) or [])
    digest_id = record.get("digest_id", "?")
    generated_at = record.get("generated_at", "?")

    breakout = [s for s in ternary_states if s.state == BREAKOUT]
    gathering = [s for s in ternary_states if s.state == GATHERING]
    dormant = [s for s in ternary_states if s.state == DORMANT]

    def sig_line(s: TernarySignal) -> str:
        return (
            f"{bullet} {s.subject} — {s.state} "
            f"(velocity {s.velocity:+d}; counts={s.counts}) "
            f"[{s.label}: {s.basis}]"
        )

    def item_line(item: Mapping[str, Any]) -> str:
        title = item.get("title") or item.get("opportunity_id") or "untitled"
        composite = item.get("composite")
        comp = (
            f" composite={composite:.2f}" if isinstance(composite, (int, float)) else ""
        )
        return f"{bullet} {title}{comp}"

    lines = [
        paint(th, "accent", "DemandPulse briefing"),
        paint(th, "dim", f"digest {digest_id} · generated {generated_at}"),
        paint(th, "dim", OUTBOX_NOTICE),
        "",
    ]
    lines += _section(
        "BREAKING (ternary: breakout)", [sig_line(s) for s in breakout], th
    )
    lines += _section(
        "GATHERING (ternary: the third state)", [sig_line(s) for s in gathering], th
    )
    watched = [i for i in items if i.get("watched")]
    rest = [i for i in items if not i.get("watched")]
    lines += _section("WATCHING", [item_line(i) for i in watched], th)
    lines += _section("QUIET", [item_line(i) for i in rest], th)
    lines += _section(
        "DORMANT signals",
        [sig_line(s) for s in dormant],
        th,
    )
    q_lines = [
        f"{bullet} {q.get('title', q.get('opportunity_id', '?'))}: "
        f"{q.get('reason', 'held by the label law')}"
        for q in quarantined
    ]
    lines += _section(
        "QUARANTINED (held back — honesty law, not published)", q_lines, th
    )
    lines += _section("LABEL LEGEND", [LEGEND], th)
    return "\n".join(lines).rstrip() + "\n"


def write_briefing(
    text: str,
    home: Optional[Path] = None,
    stamp: Optional[str] = None,
) -> Path:
    """Write a rendered briefing to the product's file outbox. Returns path."""
    from levi.demandpulse.quickstart import outbox_dir

    outbox = outbox_dir(home)
    outbox.mkdir(parents=True, exist_ok=True)
    stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = outbox / f"briefing-{stamp}.txt"
    # never overwrite an existing briefing — append a counter instead
    counter = 1
    while path.exists():
        counter += 1
        path = outbox / f"briefing-{stamp}-{counter}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def render_latest(
    home: Optional[Path] = None,
    theme: str = "void",
    ternary_states: Sequence[TernarySignal] = (),
) -> Optional[str]:
    """Render a briefing from the latest stored feed digest, if any."""
    from levi.demand.feed import levi_home, load_latest

    digest = load_latest(home=levi_home())
    if digest is None:
        return None
    return render_briefing(digest, ternary_states=ternary_states, theme=theme)
