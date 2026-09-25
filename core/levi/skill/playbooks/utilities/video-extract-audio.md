---
skill_id: utility.video_extract_audio
name: Video Extract Audio
description: Pull the audio track out of a video file into a standalone audio file.
risk: moderate
permissions: []
requires_confirmation: true
tags: [video, audio, extract, ffmpeg]
version: 1.0.0
---

# Video Extract Audio

Video Extract Audio demuxes the audio stream from a video into its own file - either copied untouched or converted to MP3/AAC - without altering the video.

## When to use

- Getting the soundtrack from a recorded talk.
- Extracting audio for transcription.
- Saving a music track out of a video file.

## Steps

1. Probe the video to see what audio streams it carries.
2. For identical quality, copy the audio stream as-is (-vn -c:a copy) into a matching container.
3. To convert (e.g. to MP3), choose a bitrate (192k is a safe default) and encode.
4. Play the first seconds of the output to confirm it is the right track.

## Honest limits

- Requires the ffmpeg command-line tool.
- Stream copy preserves quality exactly; conversion always loses a little.
- Multi-audio videos: pick the stream deliberately with -map, or you may get the commentary track.

Original work authored for LEVI - utilities pack.
