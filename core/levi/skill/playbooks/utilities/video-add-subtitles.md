---
skill_id: utility.video_add_subtitles
name: Video Add Subtitles
description: Attach an SRT subtitle file to a video as soft subtitles or burned-in captions.
risk: moderate
permissions: []
requires_confirmation: true
tags: [video, subtitles, ffmpeg]
version: 1.0.0
---

# Video Add Subtitles

Video Add Subtitles takes your video and a timed .srt file and produces a new video with the subtitles included - either as a toggleable soft track or burned permanently into the picture.

## When to use

- Adding captions to a talk recording.
- Preparing a video with translations.
- Making content watchable with sound off.

## Steps

1. Prepare and proofread the .srt file; check its timing against the video first.
2. For soft subtitles (MP4): add the srt as a mov_text stream without re-encoding video.
3. For burned-in captions: use the subtitles video filter (this re-encodes).
4. Write to a new file and watch a subtitled minute to confirm sync and readability.

## Honest limits

- Requires the ffmpeg command-line tool.
- Burned-in captions are permanent; soft subtitles need a player that shows subtitle tracks.
- Badly timed SRTs produce badly timed captions - fix the timing file, not the video.

Original work authored for LEVI - utilities pack.
