"""Voting — favorites and proposals, tagged by track.

The engagement layer spans AI and SI equally: every ballot carries a
track tag (``ai`` | ``si`` | ``both``), and results aggregate per track
back to the hub. The AI+SI pairing is the product; engagement treats
it as one.

Two ballot kinds:
- favorites: pick your favorite feature / agent / skill. One vote per
  ballot; recasting replaces (change your mind anytime).
- proposals: vote add / remove / change / integrate + free text. Each
  distinct proposal becomes weighted input on the request box
  (``/requests``) — open status, never auto-build.

Same rules as surveys: opt-in, skippable, local-first, metadata-only
analytics. No voter identity is ever stored — this is a single-user
organism; the tally is the vote.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

KINDS = ("favorites", "proposals")
TRACKS = ("ai", "si", "both")
VERBS = ("add", "remove", "change", "integrate")


@dataclass
class Ballot:
    id: str
    title: str
    tagline: str
    kind: str = "favorites"  # favorites | proposals
    track: str = "both"  # ai | si | both
    options: List[str] = field(default_factory=list)
    intro: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            self.kind = "favorites"
        if self.track not in TRACKS:
            self.track = "both"


BALLOTS: Dict[str, Ballot] = {}


def _reg(b: Ballot) -> Ballot:
    BALLOTS[b.id] = b
    return b


_reg(
    Ballot(
        id="hall-of-fame",
        title="Hall of Fame",
        tagline="which feature deserves immortality?",
        kind="favorites",
        track="both",
        intro=(
            "AI muscle and SI mind, one ballot. Pick the feature you'd "
            "enshrine — the hub weighs the crown."
        ),
        options=[
            "Cybrus vault (SI: your keys, home soil)",
            "DemandPulse authority (SI: senses, then acts)",
            "Oracle counsel (SI: which move — and why)",
            "bounty board (AI: hunts for hire)",
            "job search service (AI: the hunt, automated)",
            "income generators (AI: the portfolio)",
            "UniForge surgeon (AI: the code surgeon)",
        ],
    )
)

_reg(
    Ballot(
        id="agent-draft",
        title="Agent Draft",
        tagline="draft your starting lineup from the legion",
        kind="favorites",
        track="ai",
        intro=(
            "The AI track fields the agents. One pick — who's first off "
            "your bench?"
        ),
        options=[
            "Cybrus — the gatekeeper",
            "UniForge — the surgeon",
            "the King — the coordinator",
            "automation minions — the swarm",
            "the bounty hunter — the closer",
        ],
    )
)

_reg(
    Ballot(
        id="mind-meld",
        title="Mind Meld",
        tagline="which part of the SI mind do you trust most?",
        kind="favorites",
        track="si",
        intro=(
            "The SI track is the mind itself. Which faculty earns your "
            "trust?"
        ),
        options=[
            "the companion — the voice",
            "Oracle — the weighing mind",
            "DemandPulse — the sensing skin",
            "memory + growth — the raising",
            "the native brain — the dreaming weights",
        ],
    )
)

_reg(
    Ballot(
        id="ship-it",
        title="Ship It",
        tagline="vote what Levi should add, remove, change, or integrate",
        kind="proposals",
        track="both",
        intro=(
            "Your proposals land in the request box as weighted input — "
            "open for triage, never auto-built. Same proposal voted twice "
            "counts twice. Speak plainly; the hub is listening in aggregate."
        ),
    )
)


def get_ballot(ballot_id: str) -> Optional[Ballot]:
    return BALLOTS.get(ballot_id)


def cast_favorite(ballot: Ballot, pick: str, store: "EngagementStore | None" = None) -> Dict:
    """Cast a favorites vote. ``pick`` may be an option or its 1-based index."""
    text = (pick or "").strip()
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(ballot.options):
            text = ballot.options[idx]
    if text not in ballot.options:
        return {"ok": False, "error": f"pick one of the listed options (see: engage ballots)"}
    if store is not None:
        store.record_vote(ballot.id, text, "favorites")
        _report_ballot_to_hub(ballot, store)
    return {"ok": True, "ballot_id": ballot.id, "choice": text}


def cast_proposal(verb: str, text: str, store: "EngagementStore | None" = None) -> Dict:
    """Cast a proposal vote → weighted request-box input."""
    verb = (verb or "").strip().lower()
    if verb not in VERBS:
        return {"ok": False, "error": f"verb must be one of: {', '.join(VERBS)}"}
    if store is None:
        return {"ok": False, "error": "no store"}
    return store.upsert_proposal(verb, text)


def _report_ballot_to_hub(ballot: Ballot, store: "EngagementStore") -> None:
    """Per-track aggregate ballot signal → DemandPulse. Counts only."""
    try:
        from levi.demand.pulse import DemandPulse
    except Exception:
        return
    tallies = store.vote_tallies().get(ballot.id, {})
    if not tallies:
        return
    leaders = ", ".join(f"{opt[:40]}×{n}" for opt, n in sorted(tallies.items())[:3])
    try:
        DemandPulse().scan_seed(
            f"engagement: ballot '{ballot.id}' [{ballot.track}] — top: {leaders} (aggregate, local)",
            segment="engagement",
        )
    except Exception:
        pass


def run_ballot_interactive(ballot: Ballot, store: "EngagementStore | None" = None) -> Dict:
    """Interactive terminal run. 'skip' at any prompt backs out cleanly."""
    print(f"\n== {ballot.title} [{ballot.track}] ==")
    print(ballot.tagline)
    if ballot.intro:
        print(ballot.intro + "\n")
    if ballot.kind == "favorites":
        for i, opt in enumerate(ballot.options, 1):
            print(f"    {i}. {opt}")
        current = store.current_vote(ballot.id) if store else ""
        if current:
            print(f"  (current vote: {current} — voting again replaces it)")
        try:
            raw = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  (backed out — nothing recorded)")
            return {"ok": False, "skipped": True}
        if raw.lower() == "skip" or not raw:
            print("  (skipped — the ballot stays open)")
            return {"ok": False, "skipped": True}
        result = cast_favorite(ballot, raw, store)
        print("  vote counted." if result.get("ok") else f"  {result.get('error')}")
        return result
    # proposals
    print(f"  verbs: {', '.join(VERBS)}")
    try:
        verb = input("  verb > ").strip().lower()
        if verb == "skip" or not verb:
            print("  (skipped — the ballot stays open)")
            return {"ok": False, "skipped": True}
        text = input("  what > ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  (backed out — nothing recorded)")
        return {"ok": False, "skipped": True}
    if not text or text.lower() == "skip":
        print("  (skipped — the ballot stays open)")
        return {"ok": False, "skipped": True}
    result = cast_proposal(verb, text, store)
    if result.get("ok"):
        print(f"  proposal logged (weight ×{result['weight']}, request #{result['request_id']}).")
    else:
        print(f"  {result.get('error')}")
    return result
