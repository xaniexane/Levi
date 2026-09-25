---
skill_id: utility.video_compress
name: Video Compress
description: Re-encode a video to a much smaller file at a chosen quality level.
risk: moderate
permissions: []
requires_confirmation: true
tags: [video, compress, ffmpeg]
version: 1.0.0
---

# Video Compress

Video Compress re-encodes video with H.264 (or H.265) at a quality setting you choose, typically shrinking files dramatically. The original is preserved; the compressed copy is the deliverable.

## When to use

- Shrinking a screen recording for upload.
- Fitting videos under an attachment size limit.
- Archiving footage at a smaller footprint.

## Steps

1. Probe the source (resolution, codec, duration) with ffprobe.
2. Choose a CRF value: 23 is a sane default, higher numbers mean smaller files and lower quality.
3. Encode to a new file (preset medium balances speed and size).
4. Compare sizes and watch a minute of the result for artifacts before deleting anything.

## Honest limits

- Requires the ffmpeg command-line tool.
- Compression is lossy by design - keep the original until the compressed copy is verified.
- Diminishing returns past CRF ~28 for most content; smaller is not always better.

Original work authored for LEVI - utilities pack.
