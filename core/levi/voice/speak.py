"""Offline text-to-speech (TTS) for LEVI.

Engine selection, in order, all subprocess-bounded with a hard timeout:

1. Piper (``piper`` binary + an ONNX voice model file) — neural VITS
   voices, CPU real time, no network. The WAV is kept under
   ``$LEVI_HOME/voice/out/`` and played with ``termux-media-player`` when
   that exists; when it does not, the WAV is still produced and the
   result says so honestly.
2. ``termux-tts-speak`` — Android system TTS, the zero-install fallback
   already on the phone.
3. Nothing — an explicit "voice output unavailable on this device"
   result, never an exception and never silence mislabeled as speech.

The result always names the engine that actually spoke, per the honest
labeling rule. Daemon callers must run these in a worker thread.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PIPER_BINARY = "piper"
TERMUX_TTS_BINARY = "termux-tts-speak"
TERMUX_PLAYER_BINARY = "termux-media-player"

ENV_ENGINE = "LEVI_TTS_ENGINE"
ENV_VOICE = "LEVI_TTS_VOICE"
ENV_HOME = "LEVI_HOME"

DEFAULT_TIMEOUT_S = 60


@dataclass(frozen=True)
class TTSStatus:
    """Honest capability report for voice output on this device."""

    available: bool
    engine: str | None
    binary: str | None
    voice: str | None
    player: str | None
    detail: str


@dataclass(frozen=True)
class Speech:
    """Result of one speak attempt. ``output_path`` is the WAV for piper."""

    ok: bool
    engine: str | None
    output_path: str | None
    detail: str
    error: str | None


def check_tts(voice: str | None = None, engine: str | None = None) -> TTSStatus:
    """Report whether text-to-speech can run here. Never raises."""
    wanted = (engine or os.environ.get(ENV_ENGINE) or "").strip().lower() or None
    piper_bin = shutil.which(PIPER_BINARY)
    tts_bin = shutil.which(TERMUX_TTS_BINARY)
    player = shutil.which(TERMUX_PLAYER_BINARY)
    voice_path = voice or os.environ.get(ENV_VOICE)

    def _piper_status() -> TTSStatus:
        if piper_bin is None:
            return TTSStatus(
                available=False,
                engine=None,
                binary=None,
                voice=voice_path,
                player=player,
                detail="piper requested but no piper binary on PATH",
            )
        if not voice_path or not Path(voice_path).is_file():
            return TTSStatus(
                available=False,
                engine=None,
                binary=piper_bin,
                voice=voice_path,
                player=player,
                detail="piper found but no voice model file "
                f"(looked for: {voice_path or 'LEVI_TTS_VOICE'})",
            )
        player_note = (
            f"; playback via {player}" if player else "; no media player, WAV kept"
        )
        return TTSStatus(
            available=True,
            engine="piper",
            binary=piper_bin,
            voice=voice_path,
            player=player,
            detail=f"TTS ready: piper at {piper_bin} with {voice_path}{player_note}",
        )

    def _termux_status() -> TTSStatus:
        if tts_bin is None:
            return TTSStatus(
                available=False,
                engine=None,
                binary=None,
                voice=None,
                player=player,
                detail="termux-tts-speak requested but not on PATH",
            )
        return TTSStatus(
            available=True,
            engine="termux-tts-speak",
            binary=tts_bin,
            voice=None,
            player=player,
            detail=f"TTS ready: termux-tts-speak at {tts_bin}",
        )

    if wanted == "piper":
        return _piper_status()
    if wanted == "termux-tts-speak":
        return _termux_status()
    # Default: best available engine wins — piper needs binary AND voice.
    if piper_bin and voice_path and Path(voice_path).is_file():
        return _piper_status()
    if tts_bin:
        return _termux_status()
    detail = (
        "no TTS engine on this device (need piper + voice model, or termux-tts-speak)"
    )
    if piper_bin and not (voice_path and Path(voice_path).is_file()):
        detail += "; piper binary present but no voice model file"
    return TTSStatus(
        available=False,
        engine=None,
        binary=None,
        voice=voice_path,
        player=player,
        detail=f"TTS unavailable: {detail}",
    )


def _voice_dir() -> Path:
    home = os.environ.get(ENV_HOME)
    base = Path(home) if home else Path.home() / ".levi"
    return base / "voice"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def speak(
    text: str,
    *,
    voice: str | None = None,
    engine: str | None = None,
    output_dir: str | Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> Speech:
    """Speak ``text`` with the best available engine. Never raises."""
    if not text or not text.strip():
        return Speech(
            ok=False,
            engine=None,
            output_path=None,
            detail="refused: empty text",
            error="refused: empty text",
        )
    status = check_tts(voice=voice, engine=engine)
    if not status.available or status.engine is None:
        return Speech(
            ok=False,
            engine=None,
            output_path=None,
            detail=status.detail,
            error=f"voice output unavailable on this device: {status.detail}",
        )
    if status.engine == "piper":
        return _speak_piper(text, status, output_dir=output_dir, timeout=timeout)
    return _speak_termux_tts(text, status, timeout=timeout)


def _speak_piper(
    text: str,
    status: TTSStatus,
    *,
    output_dir: str | Path | None,
    timeout: int,
) -> Speech:
    out_dir = Path(output_dir) if output_dir else _voice_dir() / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"speech-{_stamp()}.wav"
    try:
        proc = subprocess.run(
            [status.binary, "--model", status.voice, "--output_file", str(wav)],
            input=text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return Speech(
            ok=False,
            engine=None,
            output_path=None,
            detail="piper binary vanished at run time",
            error="voice output unavailable: piper binary vanished at run time",
        )
    except subprocess.TimeoutExpired:
        return Speech(
            ok=False,
            engine="piper",
            output_path=None,
            detail=f"piper timed out after {timeout}s",
            error=f"piper timed out after {timeout}s",
        )
    if proc.returncode != 0 or not wav.is_file():
        tail = (proc.stderr or "").strip()[-500:] or "no stderr"
        return Speech(
            ok=False,
            engine="piper",
            output_path=None,
            detail=f"piper failed (rc={proc.returncode}): {tail}",
            error=f"piper failed (rc={proc.returncode}): {tail}",
        )
    if status.player:
        try:
            play = subprocess.run(
                [status.player, "play", str(wav)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            play = None
        if play is not None and play.returncode == 0:
            return Speech(
                ok=True,
                engine="piper",
                output_path=str(wav),
                detail=f"spoken by piper; played via {status.player}",
                error=None,
            )
        return Speech(
            ok=True,
            engine="piper",
            output_path=str(wav),
            detail=f"spoken by piper; WAV kept at {wav} (playback failed)",
            error=None,
        )
    return Speech(
        ok=True,
        engine="piper",
        output_path=str(wav),
        detail=f"spoken by piper; WAV kept at {wav} (no media player)",
        error=None,
    )


def _speak_termux_tts(text: str, status: TTSStatus, *, timeout: int) -> Speech:
    try:
        proc = subprocess.run(
            [status.binary, text],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return Speech(
            ok=False,
            engine=None,
            output_path=None,
            detail="termux-tts-speak vanished at run time",
            error="voice output unavailable: termux-tts-speak vanished at run time",
        )
    except subprocess.TimeoutExpired:
        return Speech(
            ok=False,
            engine="termux-tts-speak",
            output_path=None,
            detail=f"termux-tts-speak timed out after {timeout}s",
            error=f"termux-tts-speak timed out after {timeout}s",
        )
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-300:] or "no stderr"
        return Speech(
            ok=False,
            engine="termux-tts-speak",
            output_path=None,
            detail=f"termux-tts-speak failed (rc={proc.returncode}): {tail}",
            error=f"termux-tts-speak failed (rc={proc.returncode}): {tail}",
        )
    return Speech(
        ok=True,
        engine="termux-tts-speak",
        output_path=None,
        detail="spoken by termux-tts-speak",
        error=None,
    )
