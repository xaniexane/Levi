---
skill_id: red_audio_video_capture_test
name: Audio/Video Capture Validation Test
description: Test audio/video capture capabilities to validate DLP and endpoint-monitoring controls.
risk: moderate
permissions: []
requires_confirmation: true
tags: [red-team, collection, audio, video]
version: 1.0.0
team: red
tests_blue: cyber_implementing_endpoint_dlp_controls
---
# Audio/Video Capture Validation Test

## Purpose

Audio and video capture turn a compromised host into a bug. This test validates — with
canary recordings only — whether capture APIs are monitored, whether DLP covers
multimedia, and whether the environment has any technical barrier to covert recording.

## When to use

- During collection phases, with explicit AV-capture authorization.
- To validate endpoint controls against covert recording.
- When the threat model includes espionage.

## Prerequisites

- Explicit authorization for audio/video capture testing; canary recordings only,
  immediately destroyed.
- User notification per the ROE where legally required.

## Procedure

1. Test microphone capture via standard APIs with a canary recording (seconds, destroyed
   immediately).
2. Test screen capture and webcam access the same way.
3. Record telemetry: did any EDR/DLP rule fire on capture-API use?
4. Check for technical barriers: are cameras/mics disabled by policy on sensitive hosts?
5. Verify all canary recordings are destroyed; log the destruction.
6. Deliver the AV-capture assessment with policy and monitoring recommendations.

## Expected outputs

- Capture-API detection results per modality.
- Policy-barrier inventory (disabled devices).
- Canary-recording destruction log.

## Pitfalls

- Real recordings of real people without consent — canary only, destroy immediately.
- Testing on hosts where recording is legally restricted without legal review.
- Forgetting that screen capture includes credentials on screen — canary desktops only.

## References

- MITRE ATT&CK: Audio Capture (T1123), Video Capture (T1125).

## Blue-team control under test

This playbook validates their endpoint posture against covert collection is under test —
unmonitored capture APIs are an espionage-readiness gap. Paired blue-team counterpart:
`cyber_implementing_endpoint_dlp_controls`.

> **Authorization guard.** This is adversary-emulation material. Every live action in this playbook requires explicit, scoped authorization with a defined time window, named targets, and a rollback/cleanup plan. Techniques marked MODERATE or higher require confirmation before execution. Nothing here executes on its own: invoking this skill only reads this playbook.
