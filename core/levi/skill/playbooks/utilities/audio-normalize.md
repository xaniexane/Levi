---
skill_id: utility.audio_normalize
name: Audio Normalize
description: Bring audio to a consistent loudness using the EBU R128 loudnorm filter.
risk: moderate
permissions: []
requires_confirmation: true
tags: [audio, normalize, loudness, ffmpeg]
version: 1.0.0
---

# Audio Normalize

Audio Normalize measures a file's loudness and adjusts it to a broadcast target (e.g. -16 LUFS for podcasts), so quiet and loud recordings play at the same perceived volume. Output is a new file.

## When to use

- Evening out podcast episode loudness.
- Matching voice memo levels before editing.
- Preparing audio for platforms with loudness standards.

## Steps

1. Measure first: run loudnorm in measurement mode and note integrated loudness.
2. Apply the two-pass loudnorm filter targeting your platform's LUFS value.
3. Write the normalized audio to a new file.
4. Listen to the result against the original - dynamics should feel even, not squashed.

## Honest limits

- Requires the ffmpeg command-line tool with the loudnorm filter.
- Normalization changes dynamics by design; keep the original for re-grading.
- One-pass mode is faster but less accurate - two-pass is the honest default.

Original work authored for LEVI - utilities pack.
