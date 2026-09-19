"""Tests for the LEVI voice loop (STT + TTS).

Hermetic: no voice binaries are required. ``shutil.which`` and
``subprocess.run`` are faked; audio files live in tmp_path; LEVI_HOME is
redirected to tmp_path so no user HOME is touched.
"""

from __future__ import annotations

import subprocess

import pytest

from levi.voice import (
    check_stt,
    check_tts,
    record_and_transcribe,
    speak,
    transcribe_file,
)
from levi.voice import listen
from levi.voice.speak import PIPER_BINARY, TERMUX_TTS_BINARY


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("LEVI_HOME", str(tmp_path))
    return tmp_path


def _fake_which(mapping):
    def fake(name):
        return mapping.get(name)

    return fake


def _completed(cmd, stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=cmd, returncode=returncode, stdout=stdout, stderr=stderr
    )


# ---------------------------------------------------------------- STT


def test_stt_unavailable_without_binary(monkeypatch, home):
    monkeypatch.setattr("shutil.which", _fake_which({}))
    status = check_stt()
    assert status.available is False
    assert status.engine is None
    assert "unavailable" in status.detail.lower()
    result = transcribe_file(home / "clip.wav")
    assert result.ok is False
    assert "unavailable" in result.error.lower()


def test_stt_transcribe_parses_segment_lines(monkeypatch, home):
    monkeypatch.setattr(
        "shutil.which", _fake_which({"whisper-cli": "/usr/bin/whisper-cli"})
    )
    stdout = (
        "[00:00:00.000 --> 00:00:02.000]  hello world\n"
        "[00:00:02.000 --> 00:00:04.000]  this is a test\n"
    )
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _completed(cmd, stdout=stdout)

    monkeypatch.setattr("subprocess.run", fake_run)
    audio = home / "clip.wav"
    audio.write_bytes(b"fake-wav")
    result = transcribe_file(audio, model="/models/tiny.bin", timeout=30)
    assert result.ok is True
    assert result.text == "hello world this is a test"
    assert result.engine == "whisper-cli"
    assert "--model" in calls[0]
    assert "/models/tiny.bin" in calls[0]


def test_stt_transcribe_falls_back_to_raw_stdout(monkeypatch, home):
    monkeypatch.setattr("shutil.which", _fake_which({"whisper": "/usr/bin/whisper"}))
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **kw: _completed(cmd, stdout="plain output text\n"),
    )
    audio = home / "clip.wav"
    audio.write_bytes(b"fake-wav")
    result = transcribe_file(audio)
    assert result.ok is True
    assert result.text == "plain output text"


def test_stt_missing_audio_refused_before_subprocess(monkeypatch, home):
    monkeypatch.setattr(
        "shutil.which", _fake_which({"whisper-cli": "/usr/bin/whisper-cli"})
    )

    def boom(cmd, **kwargs):
        raise AssertionError("subprocess must not be called")

    monkeypatch.setattr("subprocess.run", boom)
    result = transcribe_file(home / "missing.wav")
    assert result.ok is False
    assert "not found" in result.error


def test_stt_timeout_reports_honestly(monkeypatch, home):
    monkeypatch.setattr(
        "shutil.which", _fake_which({"whisper-cli": "/usr/bin/whisper-cli"})
    )

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 30)

    monkeypatch.setattr("subprocess.run", fake_run)
    audio = home / "clip.wav"
    audio.write_bytes(b"fake-wav")
    result = transcribe_file(audio, timeout=30)
    assert result.ok is False
    assert "timed out" in result.error
    assert result.engine == "whisper-cli"


def test_stt_binary_vanishing_at_run_time(monkeypatch, home):
    monkeypatch.setattr(
        "shutil.which", _fake_which({"whisper-cli": "/usr/bin/whisper-cli"})
    )

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr("subprocess.run", fake_run)
    audio = home / "clip.wav"
    audio.write_bytes(b"fake-wav")
    result = transcribe_file(audio)
    assert result.ok is False
    assert "unavailable" in result.error.lower()


def test_stt_failed_returncode_reports_stderr(monkeypatch, home):
    monkeypatch.setattr(
        "shutil.which", _fake_which({"whisper-cli": "/usr/bin/whisper-cli"})
    )
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **kw: _completed(cmd, stderr="bad model", returncode=1),
    )
    audio = home / "clip.wav"
    audio.write_bytes(b"fake-wav")
    result = transcribe_file(audio, model="/models/nope.bin")
    assert result.ok is False
    assert "rc=1" in result.error
    assert "bad model" in result.error


def test_stt_env_overrides(monkeypatch, home):
    monkeypatch.setattr("shutil.which", _fake_which({}))
    monkeypatch.setenv("LEVI_STT_MODEL", "/models/from-env.bin")
    status = check_stt()
    assert status.model == "/models/from-env.bin"
    monkeypatch.setenv("LEVI_STT_ENGINE", "whisper-cli")
    status = check_stt()
    assert status.available is False
    assert "whisper-cli" in status.detail


def test_record_unavailable_without_recorder(monkeypatch, home):
    monkeypatch.setattr("shutil.which", _fake_which({}))
    result = record_and_transcribe(3)
    assert result.ok is False
    assert "unavailable" in result.error.lower()


def test_record_then_transcribe(monkeypatch, home):
    mapping = {
        "termux-microphone-record": "/usr/bin/termux-microphone-record",
        "whisper-cli": "/usr/bin/whisper-cli",
    }
    monkeypatch.setattr("shutil.which", _fake_which(mapping))

    def fake_run(cmd, **kwargs):
        if cmd[0].endswith("termux-microphone-record"):
            idx = cmd.index("-f")
            with open(cmd[idx + 1], "wb") as fh:
                fh.write(b"fake-wav")
            return _completed(cmd)
        return _completed(cmd, stdout="[00:00:00.000 --> 00:00:01.000]  yo\n")

    monkeypatch.setattr("subprocess.run", fake_run)
    result = record_and_transcribe(2)
    assert result.ok is True
    assert result.text == "yo"
    assert result.engine == "whisper-cli"


# ---------------------------------------------------------------- TTS


def test_tts_unavailable_without_any_engine(monkeypatch, home):
    monkeypatch.setattr("shutil.which", _fake_which({}))
    status = check_tts()
    assert status.available is False
    assert "unavailable" in status.detail.lower()
    result = speak("hello")
    assert result.ok is False
    assert "unavailable" in result.error.lower()


def test_speak_empty_text_refused(monkeypatch, home):
    monkeypatch.setattr(
        "shutil.which",
        _fake_which({"termux-tts-speak": "/usr/bin/termux-tts-speak"}),
    )

    def boom(cmd, **kwargs):
        raise AssertionError("subprocess must not be called")

    monkeypatch.setattr("subprocess.run", boom)
    result = speak("   ")
    assert result.ok is False
    assert "refused" in result.error


def test_speak_piper_then_play(monkeypatch, home):
    voice_model = home / "en.onnx"
    voice_model.write_bytes(b"fake-onnx")
    mapping = {
        "piper": "/usr/bin/piper",
        "termux-media-player": "/usr/bin/termux-media-player",
    }
    monkeypatch.setattr("shutil.which", _fake_which(mapping))
    monkeypatch.setenv("LEVI_TTS_VOICE", str(voice_model))
    calls = []
    seen_inputs = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if "input" in kwargs:
            seen_inputs.append(kwargs["input"])
        if "--output_file" in cmd:
            idx = cmd.index("--output_file")
            with open(cmd[idx + 1], "wb") as fh:
                fh.write(b"fake-wav")
        return _completed(cmd)

    monkeypatch.setattr("subprocess.run", fake_run)
    result = speak("hello there")
    assert result.ok is True
    assert result.engine == "piper"
    assert result.output_path is not None
    assert result.output_path.startswith(str(home))
    assert "played" in result.detail
    assert seen_inputs == ["hello there"]
    assert calls[0][0] == "/usr/bin/piper"
    assert calls[1][0] == "/usr/bin/termux-media-player"


def test_speak_piper_keeps_wav_when_no_player(monkeypatch, home):
    voice_model = home / "en.onnx"
    voice_model.write_bytes(b"fake-onnx")
    monkeypatch.setattr("shutil.which", _fake_which({"piper": "/usr/bin/piper"}))

    def fake_run(cmd, **kwargs):
        if "--output_file" in cmd:
            idx = cmd.index("--output_file")
            with open(cmd[idx + 1], "wb") as fh:
                fh.write(b"fake-wav")
        return _completed(cmd)

    monkeypatch.setattr("subprocess.run", fake_run)
    result = speak("hello", voice=str(voice_model))
    assert result.ok is True
    assert result.engine == "piper"
    assert "no media player" in result.detail.lower()
    assert result.output_path is not None


def test_speak_piper_needs_voice_model_file(monkeypatch, home):
    # piper binary present but the ONNX file is missing: piper must NOT win.
    monkeypatch.setattr(
        "shutil.which",
        _fake_which(
            {
                "piper": "/usr/bin/piper",
                "termux-tts-speak": "/usr/bin/termux-tts-speak",
            }
        ),
    )
    status = check_tts(voice=str(home / "missing.onnx"))
    assert status.available is True
    assert status.engine == "termux-tts-speak"
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: _completed(cmd))
    result = speak("hello", voice=str(home / "missing.onnx"))
    assert result.ok is True
    assert result.engine == "termux-tts-speak"


def test_speak_termux_tts_failure(monkeypatch, home):
    monkeypatch.setattr(
        "shutil.which",
        _fake_which({"termux-tts-speak": "/usr/bin/termux-tts-speak"}),
    )
    monkeypatch.setattr(
        "subprocess.run",
        lambda cmd, **kw: _completed(cmd, stderr="speaker busy", returncode=2),
    )
    result = speak("hello")
    assert result.ok is False
    assert "rc=2" in result.error


def test_speak_explicit_engine_missing_reports(monkeypatch, home):
    monkeypatch.setattr("shutil.which", _fake_which({}))
    result = speak("hello", engine="piper")
    assert result.ok is False
    assert "piper" in result.error


def test_speak_piper_timeout(monkeypatch, home):
    voice_model = home / "en.onnx"
    voice_model.write_bytes(b"fake-onnx")
    monkeypatch.setattr("shutil.which", _fake_which({"piper": "/usr/bin/piper"}))

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 60)

    monkeypatch.setattr("subprocess.run", fake_run)
    result = speak("hello", voice=str(voice_model))
    assert result.ok is False
    assert "timed out" in result.error


def test_voice_modules_import_cleanly():
    assert listen.WHISPER_BINARIES == ("whisper-cli", "whisper")
    assert PIPER_BINARY == "piper"
    assert TERMUX_TTS_BINARY == "termux-tts-speak"
