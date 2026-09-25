"""Engine detection for video learning — presence checks, never pretenders.

Each engine entry: {"available": bool, "kind": ..., "hint": ...}.
Missing engines are BLOCKED capabilities with install hints, not silent
gaps. Transcription engines are never assumed present (law 1).
"""

from __future__ import annotations

import os
import shutil
from typing import Dict

_WHISPER_HINT = (
    "pip install openai-whisper  (needs torch; heavy) "
    "or faster-whisper for a lighter route"
)
_VOSK_HINT = (
    "pip install vosk  and point LEVI_VOSK_MODEL at a downloaded model dir "
    "(e.g. vosk-model-small-en-us-0.15)"
)
_YTDLP_HINT = "pip install yt-dlp  (also unlocks platform captions + full metadata)"


def _module_present(name: str) -> bool:
    try:
        __import__(name)
    except Exception:
        return False
    return True


def detect() -> Dict[str, Dict[str, object]]:
    """Return availability info for every optional engine."""
    whisper_avail = _module_present("whisper") or shutil.which("whisper") is not None
    vosk_model = os.environ.get("LEVI_VOSK_MODEL", "")
    vosk_avail = _module_present("vosk") and bool(vosk_model) and os.path.isdir(vosk_model)
    ytdlp_avail = shutil.which("yt-dlp") is not None or _module_present("yt_dlp")
    ffmpeg_avail = shutil.which("ffmpeg") is not None
    return {
        "yt_dlp": {
            "available": ytdlp_avail,
            "kind": "binary-or-module",
            "role": "video metadata + platform captions (transcription source)",
            "hint": None if ytdlp_avail else _YTDLP_HINT,
        },
        "whisper": {
            "available": whisper_avail,
            "kind": "module-or-binary",
            "role": "local speech-to-text transcription (needs audio + ffmpeg)",
            "hint": None if whisper_avail else _WHISPER_HINT,
        },
        "vosk": {
            "available": vosk_avail,
            "kind": "module-plus-model",
            "role": "offline speech-to-text transcription (needs audio + ffmpeg)",
            "hint": None if vosk_avail else _VOSK_HINT,
        },
        "oembed": {
            "available": True,
            "kind": "stdlib-urllib",
            "role": "degraded metadata fallback: title + author only, no description",
            "hint": None,
        },
        "html_meta": {
            "available": True,
            "kind": "stdlib-urllib-html.parser",
            "role": "last-resort metadata: the page's own og:/twitter: meta tags",
            "hint": None,
        },
        "ffmpeg": {
            "available": ffmpeg_avail,
            "kind": "binary",
            "role": "audio extraction for local transcription engines",
            "hint": None if ffmpeg_avail else "install ffmpeg (media/video.py has the hints)",
        },
    }


def transcription_available() -> bool:
    """True only if a real transcription engine is present (law 1)."""
    d = detect()
    return bool(
        d["yt_dlp"]["available"] or d["whisper"]["available"] or d["vosk"]["available"]
    )
