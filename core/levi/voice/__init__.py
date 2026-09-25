"""LEVI voice loop — offline speech-to-text and text-to-speech.

``levi.voice.listen`` drives a whisper.cpp binary over a subprocess
boundary; ``levi.voice.speak`` prefers Piper, falls back to Android
system TTS, and otherwise reports unavailable honestly. Both degrade
cleanly on devices (like this sandbox) that have no voice binaries at
all: they return explicit "unavailable" states, never exceptions.
"""

from __future__ import annotations

from .listen import STTStatus, Transcription, check_stt, record_and_transcribe
from .listen import transcribe as transcribe_file
from .speak import Speech, TTSStatus, check_tts, speak

__all__ = [
    "STTStatus",
    "TTSStatus",
    "Speech",
    "Transcription",
    "check_stt",
    "check_tts",
    "record_and_transcribe",
    "speak",
    "transcribe_file",
]
