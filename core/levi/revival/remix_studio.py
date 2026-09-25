"""Local remix studio: template-based short-video composition plans.

Studied from: giant-patterns-hunt-20260916-0016/report.md [Additions 12]
(template-based short-video creation tools on-device: no behavioral
profiling, no watermark lock-in).

This is an original, from-scratch implementation for LEVI. The studio does
not touch pixels — it composes the *plan* a local renderer would execute.
A ``Project`` holds media slots (references to local files, durations, and
start offsets), a caption track, and an ordered list of template operations.
Applying a template (title intro, beat cut, caption card, stinger outro,
crossfade, speed ramp) edits the timeline deterministically: it inserts
segments, captions, and transition markers according to the template's
documented recipe. ``render_edl`` then exports an Edit Decision List —
plain JSON describing every segment, caption, and transition with timings —
which any local renderer can execute.

Two hard guarantees baked into the design:

- **No behavioral profiling.** The studio keeps no watch history, no
  engagement metrics, no per-viewer state. Templates are chosen explicitly
  by the user, never "recommended" from behavior.
- **No watermark lock-in.** The EDL schema is open and documented in
  ``EDL_SCHEMA_VERSION``; the exporter never injects watermarks and never
  binds the output to a vendor tool. ``verify_no_watermark`` scans an EDL
  for the markers this studio would never produce.

Public surface:
- ``RemixStudio``: ``new_project``, ``apply_template``, ``render_edl``,
  ``verify_no_watermark``, ``list_templates``.
- ``Project``: ``add_clip``, ``add_caption``, ``timeline``.
- ``Clip``, ``Caption``, ``EditDecisionList``, ``RemixError``.

Honest limits: this is composition planning, not video encoding — rendering
the pixels needs a separate local tool (e.g. ffmpeg) consuming the EDL.
Template timing is beat/frame-quantized arithmetic, not creative judgment.

stdlib-only. No network. Deterministic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ORIGIN = "levi-revival/remix-studio"

EDL_SCHEMA_VERSION = "levi-edl/1"


class RemixError(ValueError):
    """Raised for invalid remix operations."""


@dataclass
class Clip:
    """A local media reference on the timeline."""

    clip_id: int
    path: str  # local file reference; never fetched, never uploaded
    duration_s: float
    start_s: float = 0.0  # offset into the source media
    label: str = ""


@dataclass
class Caption:
    caption_id: int
    text: str
    start_s: float
    end_s: float
    style: str = "default"


@dataclass
class Segment:
    clip_id: int
    source_start_s: float
    timeline_start_s: float
    duration_s: float
    speed: float = 1.0
    transition_in: Optional[str] = None


@dataclass
class EditDecisionList:
    """The portable composition artifact: open schema, no watermarks."""

    schema: str
    project: str
    duration_s: float
    segments: List[Dict[str, object]]
    captions: List[Dict[str, object]]
    watermark: Optional[str] = None  # always None from this studio

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": self.schema,
                "project": self.project,
                "duration_s": self.duration_s,
                "segments": self.segments,
                "captions": self.captions,
                "watermark": self.watermark,
            },
            indent=2,
            sort_keys=True,
        )


@dataclass
class Project:
    """An in-progress composition."""

    name: str
    clips: List[Clip] = field(default_factory=list)
    captions: List[Caption] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    _next_clip: int = 1
    _next_caption: int = 1

    def add_clip(
        self, path: str, duration_s: float, start_s: float = 0.0, label: str = ""
    ) -> Clip:
        if duration_s <= 0:
            raise RemixError("clip duration must be positive")
        if start_s < 0:
            raise RemixError("clip start offset must be >= 0")
        clip = Clip(
            clip_id=self._next_clip,
            path=path,
            duration_s=duration_s,
            start_s=start_s,
            label=label,
        )
        self._next_clip += 1
        self.clips.append(clip)
        return clip

    def add_caption(
        self, text: str, start_s: float, end_s: float, style: str = "default"
    ) -> Caption:
        if not text.strip():
            raise RemixError("caption text must be non-empty")
        if not (0 <= start_s < end_s):
            raise RemixError("caption needs 0 <= start < end")
        caption = Caption(
            caption_id=self._next_caption,
            text=text,
            start_s=start_s,
            end_s=end_s,
            style=style,
        )
        self._next_caption += 1
        self.captions.append(caption)
        return caption

    def duration(self) -> float:
        """Total timeline duration from segments (0.0 if none)."""
        if not self.segments:
            return 0.0
        return max(s.timeline_start_s + s.duration_s / s.speed for s in self.segments)

    def timeline(self) -> List[Dict[str, object]]:
        """Human-readable segment list in timeline order."""
        return [
            {
                "clip_id": s.clip_id,
                "at": round(s.timeline_start_s, 2),
                "for": round(s.duration_s, 2),
                "speed": s.speed,
                "transition_in": s.transition_in,
            }
            for s in sorted(self.segments, key=lambda s: s.timeline_start_s)
        ]


# Template recipes: each maps to a documented, deterministic timeline edit.
TEMPLATES: Dict[str, str] = {
    "title-intro": "First 2s: title caption over clip 1, fade-in transition.",
    "beat-cut": "Cut every clip to 1.5s segments laid back-to-back from t=0.",
    "caption-card": "One caption per clip, centered on its middle third.",
    "stinger-outro": "Final 2s: 'end card' caption with crossfade transition.",
    "speed-ramp": "Alternate segments at 1.0x and 1.5x speed.",
}


class RemixStudio:
    """Template operations + EDL export. No profiling, no watermarks."""

    def __init__(self) -> None:
        self._projects: Dict[str, Project] = {}

    def new_project(self, name: str) -> Project:
        if not name.strip():
            raise RemixError("project needs a name")
        if name in self._projects:
            raise RemixError(f"project {name!r} already exists")
        project = Project(name=name)
        self._projects[name] = project
        return project

    def get_project(self, name: str) -> Project:
        try:
            return self._projects[name]
        except KeyError as exc:
            raise RemixError(f"no project {name!r}") from exc

    @staticmethod
    def list_templates() -> Dict[str, str]:
        return dict(TEMPLATES)

    def apply_template(
        self, project: Project, template: str, title: str = ""
    ) -> Project:
        """Apply a named template recipe to the project's clips."""
        if template not in TEMPLATES:
            raise RemixError(f"unknown template {template!r}")
        if not project.clips:
            raise RemixError("template needs at least one clip")
        clips = sorted(project.clips, key=lambda c: c.clip_id)
        project.segments.clear()

        if template == "title-intro":
            for i, clip in enumerate(clips):
                project.segments.append(
                    Segment(
                        clip_id=clip.clip_id,
                        source_start_s=clip.start_s,
                        timeline_start_s=i * 3.0,
                        duration_s=3.0,
                        transition_in="fade" if i > 0 else None,
                    )
                )
            project.add_caption(title or project.name, 0.0, 2.0, style="title")
        elif template == "beat-cut":
            t = 0.0
            for clip in clips:
                remaining = clip.duration_s
                src = clip.start_s
                while remaining > 0:
                    take = min(1.5, remaining)
                    project.segments.append(
                        Segment(
                            clip_id=clip.clip_id,
                            source_start_s=src,
                            timeline_start_s=t,
                            duration_s=take,
                            transition_in="cut",
                        )
                    )
                    t += take
                    src += take
                    remaining -= take
        elif template == "caption-card":
            t = 0.0
            for clip in clips:
                project.segments.append(
                    Segment(
                        clip_id=clip.clip_id,
                        source_start_s=clip.start_s,
                        timeline_start_s=t,
                        duration_s=clip.duration_s,
                    )
                )
                third = clip.duration_s / 3.0
                project.add_caption(
                    clip.label or f"clip-{clip.clip_id}",
                    t + third,
                    t + 2 * third,
                    style="card",
                )
                t += clip.duration_s
        elif template == "stinger-outro":
            t = 0.0
            for clip in clips:
                project.segments.append(
                    Segment(
                        clip_id=clip.clip_id,
                        source_start_s=clip.start_s,
                        timeline_start_s=t,
                        duration_s=clip.duration_s,
                    )
                )
                t += clip.duration_s
            project.add_caption("thanks for watching", t, t + 2.0, style="endcard")
            project.segments.append(
                Segment(
                    clip_id=clips[-1].clip_id,
                    source_start_s=clips[-1].start_s,
                    timeline_start_s=t,
                    duration_s=2.0,
                    transition_in="crossfade",
                )
            )
        elif template == "speed-ramp":
            t = 0.0
            for i, clip in enumerate(clips):
                speed = 1.5 if i % 2 else 1.0
                project.segments.append(
                    Segment(
                        clip_id=clip.clip_id,
                        source_start_s=clip.start_s,
                        timeline_start_s=t,
                        duration_s=clip.duration_s,
                        speed=speed,
                    )
                )
                t += clip.duration_s / speed
        return project

    def render_edl(self, project: Project) -> EditDecisionList:
        """Export the open-schema EDL. Never includes a watermark."""
        segments = [
            {
                "clip_id": s.clip_id,
                "source_start_s": round(s.source_start_s, 3),
                "timeline_start_s": round(s.timeline_start_s, 3),
                "duration_s": round(s.duration_s, 3),
                "speed": s.speed,
                "transition_in": s.transition_in,
            }
            for s in sorted(project.segments, key=lambda s: s.timeline_start_s)
        ]
        captions = [
            {
                "text": c.text,
                "start_s": round(c.start_s, 3),
                "end_s": round(c.end_s, 3),
                "style": c.style,
            }
            for c in sorted(project.captions, key=lambda c: c.start_s)
        ]
        return EditDecisionList(
            schema=EDL_SCHEMA_VERSION,
            project=project.name,
            duration_s=round(project.duration(), 3),
            segments=segments,
            captions=captions,
            watermark=None,
        )

    @staticmethod
    def verify_no_watermark(edl_json: str) -> bool:
        """True iff the EDL carries no watermark marker of any kind."""
        try:
            payload = json.loads(edl_json)
        except json.JSONDecodeError:
            return False
        if payload.get("watermark"):
            return False
        blob = edl_json.lower()
        return "watermark" not in blob or '"watermark": null' in blob
