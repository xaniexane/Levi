"""LEVI attention — addressed wake-signaling, clean-room revived.

SELCAL (1957) let ground stations call one aircraft over a shared radio
channel: every receiver heard every transmission, but only the aircraft
whose two-pair tone code matched woke up with a chime. 99% silence, one
chime when it matters — attention economics at the signaling layer.

This module is the anti-notification: local services subscribe with a
two-part wake code; the AttentionBus stays silent by default and wakes
only the addressed subscriber. Every signal, matched or ignored, lands in
an auditable wake ledger.

The Bell 103 answer-tone ritual (``ritual.py``) is the pairing ceremony:
probe -> answer -> confirm, capability intersection or honest abort.
"""

from __future__ import annotations

__all__ = ["signal", "ritual"]
