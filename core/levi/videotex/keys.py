"""Minitel function-key semantics on plain ASCII.

The Minitel keyboard had dedicated keys: SOMMAIRE (contents), ANNULATION
(cancel), RETOUR (back), REPETITION (redraw), GUIDE (help), CORRECTION
(fix input), SUITE (next), ENVOI (send/confirm). This module maps them
onto characters any terminal can type, and parses one input line into
exactly one action.

Simplification, documented: on real hardware you typed a number and then
pressed ENVOI to confirm. Here a bare number selects immediately — the
confirm step is folded in, because a local terminal has no metered
connection to protect.
"""

from __future__ import annotations

from dataclasses import dataclass

# Minitel key -> ASCII mapping, in the spirit of the original layout.
KEY_RETOUR = "*"  # back one level
KEY_ENVOI = "#"  # confirm (folded into bare-number selection)
KEY_SOMMAIRE = "sommaire"  # contents / home
KEY_SUITE = "suite"  # next chunk of choices
KEY_GUIDE = "guide"  # help page
KEY_ANNULATION = "annulation"  # cancel / quit at root
KEY_REPETITION = "repetition"  # redraw current page
KEY_CORRECTION = "correction"  # clear pending input, redraw prompt

_ALIASES = {
    "home": KEY_SOMMAIRE,
    "index": KEY_SOMMAIRE,
    "som": KEY_SOMMAIRE,
    "next": KEY_SUITE,
    "help": KEY_GUIDE,
    "?": KEY_GUIDE,
    "quit": KEY_ANNULATION,
    "exit": KEY_ANNULATION,
    "q": KEY_ANNULATION,
    "back": KEY_RETOUR,
    "redraw": KEY_REPETITION,
    "clear": KEY_CORRECTION,
}


@dataclass(frozen=True)
class KeyAction:
    """One parsed input line."""

    kind: str  # choice | retour | envoi | sommaire | suite | guide |
    # annulation | repetition | correction | unknown
    number: int = 0  # for kind == "choice"
    raw: str = ""  # the original input, for unknown-input echoes


def parse(line: str) -> KeyAction:
    """Parse a single input line into a KeyAction. Never raises."""
    text = (line or "").strip().lower()
    if not text:
        return KeyAction(kind="unknown", raw=line or "")
    if text == KEY_RETOUR:
        return KeyAction(kind="retour", raw=text)
    if text == KEY_ENVOI:
        return KeyAction(kind="envoi", raw=text)
    if text in (
        KEY_SOMMAIRE,
        KEY_SUITE,
        KEY_GUIDE,
        KEY_ANNULATION,
        KEY_REPETITION,
        KEY_CORRECTION,
    ):
        return KeyAction(kind=text, raw=text)
    if text in _ALIASES:
        return KeyAction(kind=_ALIASES[text], raw=text)
    if text.isdigit():
        return KeyAction(kind="choice", number=int(text), raw=text)
    return KeyAction(kind="unknown", raw=(line or "").strip())


def guide_lines() -> list[str]:
    """The GUIDE page content: every key, in Minitel order."""
    return [
        "Touches du terminal :",
        "",
        "  1-8      choisir un service",
        "  *        RETOUR : page precedente",
        "  #        ENVOI : confirmer",
        "  sommaire : page d'accueil",
        "  suite    : choix suivants",
        "  guide    : cette aide",
        "  repetition : reafficher la page",
        "  correction : effacer la saisie",
        "  annulation : quitter (a l'accueil)",
        "",
        "Le terminal est passif : il montre,",
        "il n'execute rien.",
    ]
