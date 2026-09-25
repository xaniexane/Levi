---
skill_id: utility.audio_silence_remove
name: Audio Silence Remove
description: Cut silent stretches out of an audio file above a threshold you set.
risk: moderate
permissions: []
requires_confirmation: true
tags: [audio, silence, trim, ffmpeg]
version: 1.0.0
---

# Audio Silence Remove

Audio Silence Remove detects stretches quieter than your threshold and drops them, tightening pauses in recordings. It writes a new file and reports how much time was removed.

## When to use

- Tightening a rambling voice recording.
- Removing long pauses from a meeting capture.
- Cleaning dead air before transcription.

## Steps

1. Listen to a sample and pick a silence threshold (e.g. -40dB) and minimum duration (e.g. 0.8s).
2. Run ffmpeg's silenceremove filter on a COPY, writing to a new file.
3. Check the reported removed duration and listen to two or three cut points.
4. If speech sounds clipped, raise the threshold or the minimum duration and re-run.

## Honest limits

- Requires the ffmpeg command-line tool.
- Aggressive settings eat quiet speech and breaths - start gentle.
- This edits timing, not content; keep the original until the tightened cut is approved.

Original work authored for LEVI - utilities pack.
