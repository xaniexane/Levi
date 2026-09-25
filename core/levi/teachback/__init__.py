"""Teach-back — LEVI explains back its model of the user's goals.

Alignment instrument: LEVI periodically renders what it *believes*
the user's goals are; the user corrects; corrections are logged with
timestamps and confidence moves honestly (down when corrected, up on
explicit affirmation or fresh evidence — never invented upward).

All state in ``<LEVI_HOME>/teachback/`` as local JSON.
"""

from .model import (
    TeachbackModel,
    model,
    render_brief,
    correct,
    affirm,
    note_evidence,
    add_statement,
)

__all__ = [
    "TeachbackModel",
    "model",
    "render_brief",
    "correct",
    "affirm",
    "note_evidence",
    "add_statement",
]
