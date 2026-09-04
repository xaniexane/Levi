"""
Backwords story mode — Joyner Lucas–style first→last / last→first.

Method (not copyrighted lyrics): write start-to-finish, then the same units
from finish back to start. LEVI uses the same cascade / expand_paragraph
units both ways.
"""
from __future__ import annotations

from typing import List, Tuple
import re


def split_units(text: str) -> List[str]:
    """Split prose into reversible units (sentences)."""
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def reverse_units(units: List[str]) -> List[str]:
    """Last → first (backwords order)."""
    return list(reversed(units))


def dual_passage(forward_text: str) -> Tuple[str, str, List[str]]:
    units = split_units(forward_text)
    forward = " ".join(units)
    backwords = " ".join(reverse_units(units))
    return forward, backwords, units


def format_dual_block(title: str, forward_text: str) -> str:
    fwd, bak, units = dual_passage(forward_text)
    lines = [
        "### " + title,
        "",
        "**Forward** (first → last)",
        fwd,
        "",
        "**Backwords** (last → first — same units)",
        bak,
        "",
        "_units=" + str(len(units)) + "_",
        "",
    ]
    return "\n".join(lines)
