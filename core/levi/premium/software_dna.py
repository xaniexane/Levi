"""
Classic × modern software DNA — 20 retired + 20 modern, interpenetrating into LEVI.

Not nostalgia cosplay: each pair teaches an operator trait LEVI absorbs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class DnaPair:
    retired: str
    modern: str
    levi_trait: str
    surface: str


PAIRS: List[DnaPair] = [
    DnaPair("Norton Commander / DOS dual-pane", "VS Code / JetBrains split editors", "Dual-context work without losing place", "condensed console tabs"),
    DnaPair("HyperCard stacks", "Notion / local markdown wikis", "Self-contained project packs", "levi export / import"),
    DnaPair("Palm Desktop / Newton", "Local-first apps (Ink & Switch lineage)", "Offline-complete core", "levi go"),
    DnaPair("WinHelp / man pages", "In-product docs + offline man-style CLI", "Help that works on a plane", "levi cognition / si"),
    DnaPair("Excel macros / AutoHotkey", "Zapier-like automation under approval", "Macros with HITL", "levi daemon / agent"),
    DnaPair("BBSes / fidonet", "Discord/Slack + self-hosted chat", "Session continuity + community optional", "levi chat sessions"),
    DnaPair("Storyspace / early hypertext fiction", "Twine / Ink", "Literary physics as engine", "levi story / model"),
    DnaPair("PGP / early offline crypto", "Signal-style ratchet designs", "Local CMK · cloud never owns keys", "levi cloud crypto"),
    DnaPair("TrueCrypt / local vaults", "Password managers + sealed blobs", "Sealed ~/.levi posture", "Phase B design"),
    DnaPair("Lotus Notes (local replicas)", "CRDT sync / encrypted backup", "Optional sync without surrender", "Phase B/C map"),
    DnaPair("Classic Mac / NeXT Interface Builder", "SwiftUI / modern design systems", "Craft UI · glass condensed console", "levi serve-ui"),
    DnaPair("Turbo Pascal / Delphi RAD", "Next.js / fast app scaffolds", "Ship thin vertical slices", "levi builder / KAI builder"),
    DnaPair("Emacs / Vim depth", "Command palette power users", "Keyboard-first CLI parity", "levi --help"),
    DnaPair("Desk accessories (Apple)", "Today widgets / quick tools", "Morning + continue loops", "levi morning"),
    DnaPair("Claris FileMaker", "Airtable / local SQLite apps", "Structured local memory", "corpus / ~/.levi"),
    DnaPair("Infocom / interactive fiction", "AI dungeon-likes (with care)", "Agency + constraint narrative", "L.W.P. cascade"),
    DnaPair("Symantec/Norton Utilities diagnostics", "Observability stacks", "Scorecard + stress harness", "levi scorecard / stress"),
    DnaPair("FirstClass / FirstClass BBS", "Modern community platforms", "SYSOP HITL culture", "silence ≠ approve"),
    DnaPair("AppleScript / Apple Events", "Shortcuts / IPC bridges", "Agent tools under approval", "levi agent"),
    DnaPair("ICQ / early presence", "Modern presence + focus modes", "Nervous system routing", "persona matrix"),
]


def format_dna() -> str:
    lines = [
        "══ Software DNA · 20 retired × 20 modern → LEVI ══",
        f"pairs={len(PAIRS)}",
        "Interpenetrating: each pair becomes a trait, not a skin.",
        "",
    ]
    for i, p in enumerate(PAIRS, 1):
        lines.append(f"{i:2}. {p.retired}")
        lines.append(f"    × {p.modern}")
        lines.append(f"    → {p.levi_trait}")
        lines.append(f"    surface: {p.surface}")
        lines.append("")
    return "\n".join(lines)
