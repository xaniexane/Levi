"""Focus-flow: the real music plugin for the "and more" lane.

What it is, honestly:
  - buzztunes (BuzzEngine) curates the focus QUEUE: search -> curate ->
    score -> ordered queue + receipts. Deterministic against the fake
    provider (no network, no audio) — the engine's own test double.
  - this module renders REAL PLAYABLE AUDIO for the session: a locally
    synthesized ambient pad (stdlib only, no network), written as a WAV
    the Hicomb cell plays through the browser's Web Audio path.
  - buzztunes does NOT render audio (its engine says so itself); the
    "playback" is the WAV + the browser audio. The receipt states both.

The cell (cells/focus-flow/cell.js) drives the browser-side playback:
start/stop/next over a WebSocket-free in-cell synth pad, plus WAV
playback. See plugins/README.md for the open lane ("and more").
"""

from __future__ import annotations

import hashlib
import math
import random
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..engine import SIEngine
from ..laws import LAWS  # noqa: F401

SAMPLE_RATE = 22050
MAX_RENDER_SECONDS = 600  # sessions render at most 10 min of pad

# midi numbers for the chord roots (triads built in code)
_CHORD_MIDI = {
    "Am": [57, 60, 64],  # A3 C4 E4
    "F": [53, 57, 60],   # F3 A3 C4
    "C": [48, 52, 55],   # C3 E3 G3
    "G": [55, 59, 62],   # G3 B3 D4
    "Dm": [50, 53, 57],  # D3 F3 A3
    "Bb": [58, 62, 65],  # Bb3 D4 F4
}


def midi_to_hz(m: int) -> float:
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


@dataclass
class FocusConfig:
    minutes: int = 25
    mood: str = "calm"
    seed: int = 7
    sample_rate: int = SAMPLE_RATE
    pad_level: float = 0.30
    noise_level: float = 0.08


class FocusSession:
    """One focus session: plan (SI + buzztunes queue) then render (WAV)."""

    def __init__(
        self,
        engine: Optional[SIEngine] = None,
        store_dir: Optional[str] = None,
    ) -> None:
        self._si = engine or SIEngine()
        self.store_dir = Path(
            store_dir or Path.home() / ".levi" / "si" / "focus-flow"
        ).resolve()
        self._buzz: Optional[object] = None

    # -- planning ------------------------------------------------------
    def _buzz_engine(self):  # lazy: buzztunes stays an optional import
        if self._buzz is None:
            from levi.buzztunes.engine import BuzzEngine
            from levi.buzztunes.providers import default_registry

            self._buzz = BuzzEngine(
                self.store_dir / "buzztunes", registry=default_registry()
            )
        return self._buzz

    def plan(self, minutes: int = 25, mood: str = "calm") -> Dict:
        """SI ambience params + the buzztunes focus queue.

        Returns params, queue (curated order, no audio), and an honest
        note about what the queue is.
        """
        pick = self._si.consult(
            "focus-pick", {"minutes": minutes, "mood": mood}
        )
        queue: List[Dict] = []
        queue_note = "buzztunes unavailable"
        try:
            buzz = self._buzz_engine()
            result = buzz.curate("", provider="fake")  # full catalog, deterministic
            for t in result.get("queue", [])[:8]:
                queue.append(
                    {
                        "id": t.id,
                        "title": t.title,
                        "artist": t.artist,
                        "duration": t.duration,
                        "provider": t.provider,
                    }
                )
            queue_note = (
                "curated order only — the fake provider renders no audio; "
                "the session's playable audio is the locally synthesized pad"
            )
        except Exception as exc:  # L3: plan survives a dead queue
            queue_note = f"queue unavailable ({exc.__class__.__name__}); pad still renders"
        return {
            "params": pick.data,
            "queue": queue,
            "queue_note": queue_note,
            "tier": pick.tier,
        }

    # -- rendering -----------------------------------------------------
    def render(
        self, path: str, config: Optional[FocusConfig] = None, *,
        seconds: Optional[int] = None,
    ) -> Dict:
        """Render the session pad to a 16-bit mono WAV. Deterministic for a
        fixed config (seeded RNG). ``seconds`` overrides the SI-picked
        duration (test hook). Returns a playback receipt."""
        cfg = config or FocusConfig()
        pick = self._si.consult(
            "focus-pick", {"minutes": cfg.minutes, "mood": cfg.mood}
        )
        params = pick.data
        picked = int(params["render_seconds"])
        seconds = picked if seconds is None else max(1, int(seconds))
        sr = cfg.sample_rate
        chords = params["chords"]
        n_chords = len(chords)
        chord_secs = seconds / n_chords
        rng = random.Random(cfg.seed)

        total = seconds * sr
        samples = [0.0] * total
        fade = int(6 * sr)  # 6s fades between chords

        for ci, name in enumerate(chords):
            freqs = [midi_to_hz(m) for m in _CHORD_MIDI[name]]
            start = int(ci * chord_secs * sr)
            length = int(chord_secs * sr)
            # slight detune pairs for warmth
            voices = [(f, f * 1.003) for f in freqs]
            for i in range(length):
                t = i / sr
                env = min(1.0, i / fade, (length - i) / fade)
                env = max(0.0, env)
                lfo = 0.85 + 0.15 * math.sin(2 * math.pi * 0.1 * t + ci)
                v = 0.0
                for f1, f2 in voices:
                    v += math.sin(2 * math.pi * f1 * t)
                    v += 0.6 * math.sin(2 * math.pi * f2 * t)
                v /= len(voices) * 1.6
                idx = start + i
                if idx < total:
                    samples[idx] += v * env * lfo * params["pad_level"]

        # brown-noise bed, one-pole lowpassed
        last = 0.0
        for i in range(total):
            white = rng.uniform(-1.0, 1.0)
            last = (last + 0.02 * white) / 1.02
            samples[i] += last * 3.0 * params["noise_level"]

        peak = max(abs(s) for s in samples) or 1.0
        norm = 0.89 / peak
        ints = [int(max(-1.0, min(1.0, s * norm)) * 32767) for s in samples]
        rms = math.sqrt(sum(s * s for s in samples) / total)

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(struct.pack(f"<{len(ints)}h", *ints))

        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        return {
            "wav_path": str(out),
            "duration_s": seconds,
            "sample_rate": sr,
            "peak": round(peak * norm, 4),
            "rms": round(rms * norm, 4),
            "sha256": digest,
            "synth": True,
            "note": (
                "locally synthesized ambient pad — playable audio, "
                "not licensed music; buzztunes provided queue/curation only"
            ),
        }


__all__ = ["FocusSession", "FocusConfig", "SAMPLE_RATE", "midi_to_hz"]
