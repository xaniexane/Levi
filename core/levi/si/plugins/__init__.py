"""levi.si.plugins — the "and more" lane.

Shipped kinds:
  music  — focus-flow: buzztunes-backed focus audio, real local playback.
  google — google-drive: Drive IO for code files via the connected
           hatch_gws_cli session; the cell stages, the engine transfers.
The lane stays open: any future plugin kind lives here as its own
module + tricombs cell under cells/.

See README.md in this directory for the lane contract.
"""

from .focus_flow import FocusConfig, FocusSession, SAMPLE_RATE, midi_to_hz
from .google_drive import (
    CODE_QUERY,
    MAX_TEXT_BYTES,
    DriveError,
    DriveReceipt,
    DriveSession,
)

__all__ = [
    "FocusSession",
    "FocusConfig",
    "SAMPLE_RATE",
    "midi_to_hz",
    "DriveSession",
    "DriveReceipt",
    "DriveError",
    "CODE_QUERY",
    "MAX_TEXT_BYTES",
]
