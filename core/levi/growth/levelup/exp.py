"""EXP scoring for replies and questions (L5).

Two inputs, honestly separated:

- attention (0..10): how much the reply paid attention — relevance,
  focus, remembering what the user actually said.
- interaction (0..10): how much the exchange moved the bond forward —
  warmth, curiosity, the Tamagotchi spark.

These inputs are the CALLER's judgment (the trainer's read on the
exchange); this module turns them into EXP deterministically. It does
not derive attention/interaction from text — that is a separate,
harder problem, and this module will not pretend to solve it.

Math:
    base  = 2 * attention + 3 * interaction        (0..50)
    award = round(base * intensity_multiplier(intensity))

A perfect 10/10 exchange at intensity 5 is 50 * 3.0 = 150 EXP.
"""

from __future__ import annotations

from . import intensity as _intensity
from .receipts import award_exp


def _bounded(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("%s must be an int in 0..10, got %r" % (name, value))
    if value < 0 or value > 10:
        raise ValueError("%s must be an int in 0..10, got %r" % (name, value))
    return value


def score_reply(attention: int, interaction: int) -> int:
    """Base EXP for one scored reply: 2*attention + 3*interaction (L5)."""
    a = _bounded(attention, "attention")
    i = _bounded(interaction, "interaction")
    return 2 * a + 3 * i


def reply_exp(attention: int, interaction: int, intensity_level: int = 1) -> int:
    """Full EXP for a reply, intensity multiplier applied."""
    base = score_reply(attention, interaction)
    return int(round(base * _intensity.multiplier(intensity_level)))


def award_reply(
    entity: str,
    attention: int,
    interaction: int,
    intensity_level: int = 1,
    meta: dict | None = None,
) -> dict:
    """Score one reply and append the EXP receipt. Returns the receipt."""
    exp = reply_exp(attention, interaction, intensity_level)
    m = dict(meta or {})
    m.update(
        {
            "attention": attention,
            "interaction": interaction,
            "intensity": intensity_level,
            "intensity_name": _intensity.name(intensity_level),
        }
    )
    return award_exp(entity, "reply", exp, m)
