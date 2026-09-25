# Local Remix Studio — ARCHIVED AS UNBUILDABLE (stdlib-only)

**Status: archived, not built.** This document is the deliverable. Per
the standing laws, an addition that cannot be meaningfully built
local-first stdlib-only is archived with reasons — no stubs,
no demos-that-pretend.

## What the addition would have been

**Remix delta (from TikTok):** TikTok's product is the behavioral
profile — the editor, effects, and distribution are free because your
watch behavior is the inventory it sells, and watermark lock-in keeps
the value on-platform. LEVI would invert it: template-based short-video
creation tools running fully on-device — cuts, captions, transitions,
and text overlays from local templates — with no behavioral profiling,
no upload requirement, no account, and no watermark lock-in. The output
file would be yours, in open formats, with the edit decision list
exportable as JSON (monopoly-minus-one: take your project anywhere).

That is a genuine addition the giant refuses: TikTok *cannot* ship an
editor that doesn't phone home, because the phone-home is the business.

## Why stdlib blocks it

1. **No video encode/decode in the standard library.** Python's stdlib
   can read and write *uncompressed* frames only with heroic manual
   effort — there is no H.264/VP9/AV1 encoder or decoder, no container
   muxer (MP4/WebM), nothing. Real short-video output requires a codec.
2. **No audio track handling either** (`wave` handles PCM WAV files;
   compressed audio needs a codec too).
3. **No media framework bindings.** No GStreamer/ffmpeg bindings, no
   platform media APIs — those are all third-party or OS-native.
4. **A storyboard-planner stub would violate the no-stubs rule.**
   Planning edit decisions without the ability to render them is a demo
   that pretends. The law says: archive the analysis and move on.

## What would unblock it

- A sanctioned **native helper boundary**: e.g. shelling out to a
  user-installed `ffmpeg` (not bundled, not a dependency — detected at
  runtime, with honest "not installed" errors), keeping all *decisions*
  (templates, timing, captions) in stdlib Python and delegating only the
  encode step. That preserves local-first and free-core; it just isn't
  stdlib-only, so it needs an explicit policy exception from Chauncey.
- Or a future pure-Python codec — not feasible at usable speed today.

## Preserved for later

If the ffmpeg-boundary exception is ever granted, the honest shape is:
`core/levi/remix/` owning templates, the edit decision list, caption
timing, and preview storyboards (all stdlib), with a single
`render.py` that execs `ffmpeg` if present and refuses honestly if not.
No behavioral profiling, no watermark, JSON edit-list export — the remix
delta above stands unchanged.

Until then: archived. Nothing was built, and nothing pretends otherwise.
