"""Offline speech-to-text (STT) for LEVI.

Nothing here links speech code or touches a network: the module drives a
whisper.cpp command-line binary (``whisper-cli`` / ``whisper``) over a
subprocess boundary with a hard timeout, and reports honestly when the
binary is missing. On a device with no STT engine, every entry point
returns an explicit "unavailable" state instead of raising.

On Termux the intended engine is the precompiled whisper.cpp binary
bundled with the ``termux-stt`` package (no from-source compile); the
tiny model transcribes faster than real time on a phone CPU.

Daemon callers must run these in a worker thread: the subprocess is
always bounded by ``timeout``, but a long clip can still take tens of
seconds, and this module must never stall the daemon.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

#: whisper.cpp CLI names, in preference order.
WHISPER_BINARIES = ("whisper-cli", "whisper")

#: Recorder commands that can produce a WAV file, in preference order.
RECORDER_BINARIES = ("termux-microphone-record",)

ENV_ENGINE = "LEVI_STT_ENGINE"
ENV_MODEL = "LEVI_STT_MODEL"
ENV_HOME = "LEVI_HOME"

DEFAULT_TIMEOUT_S = 120
DEFAULT_RECORD_SECONDS = 5

_SEGMENT_RE = re.compile(r"^\[.*?\]\s*(.*)$")


@dataclass(frozen=True)
class STTStatus:
    """Honest capability report for speech-to-text on this device."""

    available: bool
    engine: str | None
    binary: str | None
    model: str | None
    recorder: str | None
    detail: str


@dataclass(frozen=True)
class Transcription:
    """Result of one transcription attempt."""

    ok: bool
    text: str
    engine: str | None
    error: str | None


def find_stt_binary(preferred: str | None = None) -> str | None:
    """Return the path of a whisper binary, or None when none is on PATH."""
    names = (preferred,) if preferred else WHISPER_BINARIES
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def find_recorder() -> str | None:
    """Return the path of a microphone recorder, or None when absent."""
    for name in RECORDER_BINARIES:
        found = shutil.which(name)
        if found:
            return found
    return None


def resolve_model(model: str | None = None) -> str | None:
    """Explicit model path wins, then LEVI_STT_MODEL, else whisper's default."""
    if model:
        return model
    return os.environ.get(ENV_MODEL)


def check_stt(model: str | None = None, engine: str | None = None) -> STTStatus:
    """Report whether speech-to-text can run here. Never raises."""
    wanted = engine or os.environ.get(ENV_ENGINE) or None
    binary = find_stt_binary(wanted)
    recorder = find_recorder()
    model_path = resolve_model(model)
    if binary is None:
        why = f"no whisper binary on PATH (looked for: {wanted or ', '.join(WHISPER_BINARIES)})"
        return STTStatus(
            available=False,
            engine=None,
            binary=None,
            model=model_path,
            recorder=recorder,
            detail=f"STT unavailable: {why}",
        )
    name = Path(binary).name
    model_note = f"model {model_path}" if model_path else "whisper default model"
    return STTStatus(
        available=True,
        engine=name,
        binary=binary,
        model=model_path,
        recorder=recorder,
        detail=f"STT ready: {name} at {binary}; {model_note}",
    )


def _parse_whisper_stdout(stdout: str) -> str:
    """Pull spoken text out of whisper-cli's segment lines.

    Falls back to the raw stdout when no segment lines are present, so an
    unexpected-but-harmless format change degrades to noise rather than
    silence.
    """
    lines = []
    for raw in stdout.splitlines():
        match = _SEGMENT_RE.match(raw.strip())
        if match and match.group(1).strip():
            lines.append(match.group(1).strip())
    if lines:
        return " ".join(lines)
    return stdout.strip()


def transcribe(
    audio_path: str | Path,
    *,
    model: str | None = None,
    engine: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> Transcription:
    """Transcribe a WAV/audio file via the whisper binary. Never raises."""
    audio = Path(audio_path)
    if not audio.is_file():
        return Transcription(
            ok=False, text="", engine=None, error=f"audio file not found: {audio}"
        )
    binary = find_stt_binary(engine or os.environ.get(ENV_ENGINE))
    if binary is None:
        return Transcription(
            ok=False,
            text="",
            engine=None,
            error="STT unavailable on this device: no whisper binary on PATH",
        )
    name = Path(binary).name
    model_path = resolve_model(model)
    cmd = [binary, "--no-prints", "-f", str(audio)]
    if model_path:
        cmd[1:1] = ["--model", model_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return Transcription(
            ok=False,
            text="",
            engine=None,
            error="STT unavailable: whisper binary vanished at run time",
        )
    except subprocess.TimeoutExpired:
        return Transcription(
            ok=False,
            text="",
            engine=name,
            error=f"STT timed out after {timeout}s",
        )
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-500:] or "no stderr"
        return Transcription(
            ok=False,
            text="",
            engine=name,
            error=f"whisper failed (rc={proc.returncode}): {tail}",
        )
    return Transcription(
        ok=True,
        text=_parse_whisper_stdout(proc.stdout or ""),
        engine=name,
        error=None,
    )


def _voice_dir() -> Path:
    home = os.environ.get(ENV_HOME)
    base = Path(home) if home else Path.home() / ".levi"
    return base / "voice"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def record_and_transcribe(
    seconds: int = DEFAULT_RECORD_SECONDS,
    *,
    output_dir: str | Path | None = None,
    model: str | None = None,
    engine: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> Transcription:
    """Record from the microphone, then transcribe. Never raises.

    Recording only exists where ``termux-microphone-record`` is present
    (i.e. Termux with termux-api). Elsewhere this returns unavailable.
    """
    recorder = find_recorder()
    if recorder is None:
        return Transcription(
            ok=False,
            text="",
            engine=None,
            error="recording unavailable on this device: "
            "no termux-microphone-record on PATH",
        )
    out_dir = Path(output_dir) if output_dir else _voice_dir() / "in"
    out_dir.mkdir(parents=True, exist_ok=True)
    wav = out_dir / f"clip-{_stamp()}.wav"
    try:
        proc = subprocess.run(
            [recorder, "-f", str(wav), "-l", str(seconds)],
            capture_output=True,
            text=True,
            timeout=seconds + 30,
        )
    except FileNotFoundError:
        return Transcription(
            ok=False,
            text="",
            engine=None,
            error="recording unavailable: recorder binary vanished at run time",
        )
    except subprocess.TimeoutExpired:
        return Transcription(
            ok=False,
            text="",
            engine=None,
            error=f"recording timed out after {seconds + 30}s",
        )
    if proc.returncode != 0 or not wav.is_file():
        tail = (proc.stderr or "").strip()[-300:] or "no stderr"
        return Transcription(
            ok=False,
            text="",
            engine=None,
            error=f"recorder failed (rc={proc.returncode}): {tail}",
        )
    return transcribe(wav, model=model, engine=engine, timeout=timeout)
