---
skill_id: utility.video_trim
name: Video Trim
description: Cut a video down to a start/end time range without re-encoding when possible.
risk: moderate
permissions: []
requires_confirmation: true
tags: [video, trim, ffmpeg]
version: 1.0.0
---

# Video Trim

Video Trim extracts the segment between your start and end times. By default it copies the streams untouched (fast, lossless); frame-accurate cuts opt into re-encoding.

## When to use

- Cutting a clip out of a longer recording.
- Removing dead air from the start or end of a video.
- Extracting a highlight segment for sharing.

## Steps

1. Pick start and end times (HH:MM:SS) and preview them in a player first.
2. Run ffmpeg with -ss before -i for speed, -to for the end, and -c copy for a lossless stream copy.
3. Write to a new file; verify duration and that audio stays in sync.
4. If the cut lands mid-scene awkwardly, re-run with re-encoding for frame accuracy.

## Honest limits

- Requires the ffmpeg command-line tool installed on the machine.
- Stream copy cuts on keyframes, so the cut point can shift by a second or so - re-encode when precision matters.
- Always write to a new file; trimming in place risks the only copy.

Original work authored for LEVI - utilities pack.
