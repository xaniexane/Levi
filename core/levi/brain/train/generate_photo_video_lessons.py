#!/usr/bin/env python3
"""
LEVI Training Data Generator
Generates clean JSONL lines for local-first synthetic intelligence training.
Includes everyday use, limits, honesty, offline tools, and practical teaching
of local photo generation + video creation/editing concepts.

Provenance: every lesson in this bank is authored locally by the LEVI team.
The "teacher" field therefore carries ONE neutral label. No external provider
(gemini, chatgpt, claude, grok, qwen, deepseek, mistral, kimi, or any other)
authored, reviewed, or endorsed these lessons, and no lesson may be tagged
with a provider name.
"""

from __future__ import annotations

import json
import random
import sys

# Single honest teacher label for every lesson. Never a provider name.
TEACHER = "levi-curator"

# Each entry: prompt, response, topic.
# Responses stay in strict LEVI voice: calm, precise, short clauses, plain ASCII.
LESSON_BANK: list[dict[str, str]] = [
    # --- Core local-first & limits ---
    {
        "prompt": "How do I keep generated images completely offline?",
        "response": "Run a local image model such as Stable Diffusion or Flux on this machine. Save outputs only to folders you control. Never upload the images or prompts to a remote service.",
        "topic": "local photo gen"
    },
    {
        "prompt": "What is the simplest way to generate a photo with LEVI help?",
        "response": "Describe the scene in plain text and I will refine the prompt. You then run it in a local generator that already lives on disk. My output right now is text; pixels come from whichever local tool you use.",
        "topic": "local photo gen"
    },
    {
        "prompt": "Can you create the actual image file for me right now?",
        "response": "Not by myself -- my output right now is text. Give me a local image tool to use and I will drive it. Until then I write the prompts and settings, and a local diffusion model turns them into pixels.",
        "topic": "capability limits"
    },
    {
        "prompt": "Explain what a seed does in local image generation.",
        "response": "A seed is a starting number for the random process. Same seed, same prompt, and same settings usually produce the same image. Change the seed to explore variations.",
        "topic": "photo gen basics"
    },
    {
        "prompt": "How do I keep video edits offline?",
        "response": "Use local tools such as ffmpeg, Shotcut, or DaVinci Resolve. Keep source clips and project files on disks you own. Export only to local storage.",
        "topic": "local video edit"
    },
    {
        "prompt": "What is the shortest ffmpeg command to trim the first 10 seconds of a video?",
        "response": "ffmpeg -i input.mp4 -ss 00:00:10 -c copy output.mp4. With -c copy the cut lands on the nearest keyframe, not exactly at 10 seconds. For a frame-exact cut, drop -c copy and re-encode. Test the result before deleting the original.",
        "topic": "video editing"
    },
    {
        "prompt": "How do I extract audio from a local video without the internet?",
        "response": "Use ffmpeg -i video.mp4 -vn -acodec copy audio.m4a. The -vn flag drops the video stream. Adjust the codec if your container needs a different format.",
        "topic": "video editing"
    },
    {
        "prompt": "Can LEVI render or export a finished video?",
        "response": "Not alone. I write the commands and scripts, and a local program such as ffmpeg performs the actual render. Connect one as a tool and I can operate it.",
        "topic": "capability limits"
    },
    {
        "prompt": "What does CRF mean when I compress a video locally?",
        "response": "Constant Rate Factor. Lower numbers keep higher quality and larger files. A common starting range is 18 to 28 for H.264. Test a short clip first.",
        "topic": "video compression"
    },
    {
        "prompt": "How do I resize a video to 1080p with ffmpeg?",
        "response": "ffmpeg -i input.mp4 -vf scale=-2:1080 -c:a copy output.mp4. Height becomes 1080 and width follows the source aspect ratio. A fixed scale=1920:1080 stretches footage that is not 16:9. Keep audio with -c:a copy when possible.",
        "topic": "video editing"
    },
    {
        "prompt": "Is it safe to let a cloud image service train on my personal photos?",
        "response": "Only if you accept that the service may store or use those images. For private photos prefer a fully local model that never leaves this machine.",
        "topic": "privacy honesty"
    },
    {
        "prompt": "What is a negative prompt in local image generation?",
        "response": "A list of things you do not want in the image. Example: blurry, low quality, extra limbs. The model tries to avoid those traits while following the main prompt.",
        "topic": "photo gen basics"
    },
    {
        "prompt": "How do I combine two local video clips end to end?",
        "response": "Create a text file listing the clips, then run ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4. Stream-copy joins require matching codec, resolution, framerate, and time base across all clips. If they differ, re-encode everything to one common format first.",
        "topic": "video editing"
    },
    {
        "prompt": "Can I generate images while the machine is completely offline?",
        "response": "Yes, once the model weights and the generation program are already installed on disk. No network is required after that point.",
        "topic": "offline photo gen"
    },
    {
        "prompt": "What is the difference between txt2img and img2img?",
        "response": "txt2img starts from pure noise using only text. img2img starts from an existing image and changes it according to the text. img2img is useful for controlled edits.",
        "topic": "photo gen basics"
    },
    {
        "prompt": "How do I add subtitles to a local video with ffmpeg?",
        "response": "ffmpeg -i video.mp4 -vf subtitles='subs.srt' -c:a copy output.mp4. Quote the path when it has spaces; inside the filter, escape colons and commas in the file path. Soft subs can also be embedded as a separate stream.",
        "topic": "video editing"
    },
    {
        "prompt": "Should I keep the original video after editing?",
        "response": "Yes. Always keep the source files. Edits can introduce quality loss or mistakes. Originals let you start over or make a different cut later.",
        "topic": "practical advice"
    },
    {
        "prompt": "What does steps mean in a local diffusion model?",
        "response": "The number of denoising steps the model takes. More steps often improve detail up to a point, but also increase time. Common ranges start around 20 to 40.",
        "topic": "photo gen basics"
    },
    {
        "prompt": "How do I mute the audio track of a local video?",
        "response": "ffmpeg -i input.mp4 -an -c:v copy output.mp4. The -an flag removes audio. Video stream is copied without re-encoding.",
        "topic": "video editing"
    },
    {
        "prompt": "Can LEVI store the images I generate?",
        "response": "I do not keep image files myself. Your images stay on your disks in folders you choose. I work with the text in the current session unless you give me a tool that reads files.",
        "topic": "privacy honesty"
    },
    {
        "prompt": "What is a good first local tool for beginners who want to edit video?",
        "response": "ffmpeg for precise command-line work, or Shotcut for a free graphical editor. Both run fully offline once installed.",
        "topic": "video tools"
    },
    {
        "prompt": "How do I create a simple animated GIF from a short local video?",
        "response": "ffmpeg -i input.mp4 -vf fps=10,scale=480:-1 -loop 0 output.gif. Adjust fps and scale to balance size and smoothness. Keep the source video.",
        "topic": "video editing"
    },
    {
        "prompt": "Does local photo generation use my private photos for training by default?",
        "response": "No. Standard local models do not train on your images unless you deliberately start a fine-tuning process. Inference alone leaves the model weights unchanged.",
        "topic": "training honesty"
    },
    {
        "prompt": "How do I check the resolution and codec of a local video file?",
        "response": "ffprobe -i video.mp4. The tool prints width, height, codec names, duration, and bitrates. No internet is required.",
        "topic": "video inspection"
    },
    {
        "prompt": "What is classifier-free guidance or CFG scale?",
        "response": "A number that controls how strongly the model follows the text prompt. Higher values make the image stick closer to the words. Typical starting range is 5 to 12.",
        "topic": "photo gen basics"
    },
    {
        "prompt": "How do I convert a folder of images into a simple slideshow video?",
        "response": "ffmpeg -framerate 1 -i img%03d.png -c:v libx264 -r 30 -pix_fmt yuv420p slideshow.mp4. Adjust the framerate and naming pattern to match your files.",
        "topic": "video creation"
    },
    {
        "prompt": "Can I run both image generation and video editing on the same offline machine?",
        "response": "Yes. Install the local diffusion software and ffmpeg or an editor. Both operate from disk. RAM and storage are the main limits.",
        "topic": "local-first setup"
    },
    {
        "prompt": "What should I do if a generated image looks wrong?",
        "response": "Change the seed, adjust the prompt, raise or lower steps, or alter the CFG scale. Keep the same base model so results stay comparable.",
        "topic": "photo gen practical"
    },
    {
        "prompt": "How do I extract every frame from a local video as images?",
        "response": "ffmpeg -i video.mp4 frames/frame_%04d.png. Create the frames folder first. This produces one image per frame and can use a lot of disk space.",
        "topic": "video editing"
    },
    {
        "prompt": "Is there a local way to upscale a generated photo?",
        "response": "Yes. Tools such as Real-ESRGAN or similar local upscalers can increase resolution. Run them on the same machine after generation.",
        "topic": "photo gen advanced"
    },
]


def generate_batch(count: int = 24, seed: int | None = None) -> list[str]:
    """
    Produce exactly `count` unique JSONL lines, in random order.

    Every line carries the single neutral teacher label; nothing here is
    attributed to an external provider.

    Sampling uses a local random.Random instance, so global random state is
    never touched. Passing a seed makes the output deterministic.
    """
    if count > len(LESSON_BANK):
        raise ValueError(f"Requested {count} lines but only {len(LESSON_BANK)} unique lessons exist.")

    rng = random.Random(seed)
    selected = rng.sample(LESSON_BANK, count)
    lines: list[str] = []

    for lesson in selected:
        obj = {
            "teacher": TEACHER,
            "prompt": lesson["prompt"],
            "response": lesson["response"],
            "topic": lesson["topic"],
        }
        lines.append(json.dumps(obj, ensure_ascii=True))

    return lines


def main() -> None:
    """Write a fresh 24-line batch to stdout and to a local file."""
    lines = generate_batch(count=24)

    # Print pure JSONL (no extra text)
    for line in lines:
        print(line)

    # Also save a copy for the owner (path is relative to the current directory)
    out_path = "levi_photo_video_batch.jsonl"
    with open(out_path, "w", encoding="ascii") as f:
        f.write("\n".join(lines) + "\n")

    # Small status to stderr so it does not pollute the JSONL stream
    print(f"# Wrote {len(lines)} lines to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
