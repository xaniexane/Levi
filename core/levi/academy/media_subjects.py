"""Academy media-production subject catalog — the M track.

Six subjects teaching LEVI's real media stack: the offline procedural
photo generator (:mod:`levi.media.local`), backend selection across
local / Pollinations / SD, prompt craft, ffmpeg video fx
(:mod:`levi.media.video`), vertical-format production, and
thumbnail/poster design for social.

Shaped exactly like :mod:`levi.academy.subjects` day entries —
``{title, objectives, key_questions, exercise_type}`` — so the catalog
slots into the syllabus/ladder/lesson machinery via :func:`as_track`
and :func:`merge_into` (which copies, never mutates, the syllabus).

Every objective uses a measurable Bloom's-taxonomy (revised) verb —
remember/define, understand/explain, apply/execute, analyze/deconstruct,
evaluate/critique, create/design — so each one is assessable.

Honesty law for this track: procedural art is always labeled procedural,
never passed off as photography; every render and every video op carries
a receipt; no likeness of a real person is ever synthesized.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

TRACK_KEY = "M"
TRACK_NAME = "Media Production"


def _subject(
    subject_id: str,
    title: str,
    description: str,
    objectives: List[str],
    key_questions: List[str],
    exercise_type: str,
    defense_note: str,
    requires_authorization: bool = False,
) -> Dict[str, Any]:
    assert len(objectives) == 3, "three objectives per subject"
    assert len(key_questions) == 3, "three key questions per subject"
    return {
        "id": subject_id,
        "title": title,
        "description": description,
        "objectives": list(objectives),
        "key_questions": list(key_questions),
        "exercise_type": exercise_type,
        "defense_note": defense_note,
        "requires_authorization": requires_authorization,
    }


SUBJECTS: List[Dict[str, Any]] = [
    _subject(
        "procedural-photo",
        "Procedural Photo Generation",
        "Generate deterministic thumbnail backgrounds, plates, and product-mockup layouts with the offline procedural engine — no network, no weights, same seed means same pixels.",
        [
            "Generate a deterministic composition with a fixed seed and verify byte-identical output across two runs",
            "Evaluate which local styles suit text overlays versus product shots, and justify the choice from the style's properties",
            "Design a product-mockup composition with a text-safe zone for a given brief, then render it",
        ],
        [
            "What does 'deterministic' buy you that a cloud image API cannot?",
            "When is procedural art the honest choice, and when is it a lie by omission?",
            "How does a text-safe zone change what a thumbnail is allowed to promise?",
        ],
        "media-photo",
        "Procedural art is labeled procedural — always. It is a layout plate "
        "and background engine, never a fake photograph. The seed is the "
        "receipt: same seed, same pixels, no surprises.",
    ),
    _subject(
        "backend-selection",
        "Backend Selection: Local vs Pollinations vs SD",
        "Three backends, one dispatcher: know exactly when each is the honest tool — offline procedural, free keyless photoreal reference, or hardware-gated local diffusion.",
        [
            "Distinguish the three backends by availability, cost, and honesty guarantees",
            "Select the correct backend for a brief — offline phone, photoreal reference, local GPU — and defend the choice",
            "Explain why the dispatcher defaults to local, and name the cases where 'auto' is the wrong answer",
        ],
        [
            "What breaks when the network is gone — and which backend survives?",
            "Why is the Pollinations output labeled 'external reference, never LEVI'?",
            "What has to be true before the SD scaffold is allowed to run?",
        ],
        "media-backend",
        "The dispatcher defaults to local because local-first is the law. "
        "External pixels are references, not ours — labeled at the border, "
        "every time.",
    ),
    _subject(
        "prompt-craft",
        "Prompt Craft for Image Generation",
        "Prompts are specifications: subject, style, composition, and constraints — written so the render is reviewable against the words that asked for it.",
        [
            "Write a prompt with subject, style, composition, and negative constraints for a thumbnail brief",
            "Deconstruct a failed generation into concrete prompt fixes: what to add, what to remove",
            "Build a reusable prompt template for a content series with slots for the variable parts",
        ],
        [
            "What makes a prompt reviewable — how do you check the render against the words?",
            "Why do negative constraints matter more than adjectives?",
            "When does a template help, and when does it make every thumbnail look the same?",
        ],
        "media-prompt",
        "Craft serves clarity: a prompt is a contract with the viewer. No "
        "prompt may ask for a real person's likeness — the engine refuses "
        "what the morals refuse.",
    ),
    _subject(
        "ffmpeg-fundamentals",
        "FFmpeg Video FX Fundamentals",
        "Mechanical video transforms with receipts: trim, cut, concat, caption burn-in, Ken Burns, crossfade, loudness work — every op hashed in, hashed out.",
        [
            "Execute trim, concat, and caption burn-in on real clips and read the receipts back",
            "Explain the re-encode versus stream-copy trade-off and choose correctly for a deadline",
            "Diagnose a failed ffmpeg run from its stderr tail and state the fix",
        ],
        [
            "Why does every op return a receipt — what does the hash prove?",
            "When is stream copy the right call, and what does it cost you?",
            "What does 'fail-closed' mean when ffmpeg is missing?",
        ],
        "media-video",
        "Receipts on every render: input hashes, op, params, output hash. "
        "A transform you cannot reproduce is a rumor — the receipt is the "
        "proof.",
    ),
    _subject(
        "vertical-production",
        "Vertical-Format Production",
        "The 9:16 pipeline for TikTok, Reels, and Shorts: reformat without stretching, animate stills with Ken Burns, and ship captioned vertical clips end to end.",
        [
            "Reformat a landscape clip to 9:16 with scale-to-cover and center crop — no stretching, subject kept",
            "Produce a Ken Burns clip from a still image with a chosen zoom direction and pan",
            "Assemble a captioned vertical clip end to end: reformat, burn captions, extract a thumbnail",
        ],
        [
            "Why scale-to-cover plus crop instead of stretch — what does each do to the subject?",
            "What makes a Ken Burns move feel intentional versus seasick?",
            "Where do captions have to sit so a phone's UI chrome doesn't eat them?",
        ],
        "media-vertical",
        "Vertical is the native format of the phone in Chauncey's pocket. "
        "Captions burn into the safe zone — legibility is a requirement, "
        "not a style.",
    ),
    _subject(
        "thumbnail-design",
        "Thumbnail & Poster Design for Social",
        "Thumbnails are promises: contrast, safe zones, and honesty — the click must be payable by the content behind it.",
        [
            "Design a thumbnail with a text-safe zone that stays readable at small sizes",
            "Critique a thumbnail for contrast, clutter, and honesty: does the content pay off the click",
            "Produce a poster and thumbnail pair for one piece of content from a single brief",
        ],
        [
            "What survives at 120 pixels wide — and what dies?",
            "Where is the line between a strong thumbnail and a dishonest one?",
            "Why does the poster and the thumbnail need to be designed together?",
        ],
        "media-thumbnail",
        "A thumbnail is a promise the content must keep. Clickbait the "
        "content cannot pay off is a lie with good kerning — never shipped.",
    ),
]

_SUBJECTS_BY_ID = {s["id"]: s for s in SUBJECTS}


def get_subject(subject_id: str) -> Dict[str, Any]:
    """Fetch one subject by id. Raises KeyError when unknown."""
    try:
        return _SUBJECTS_BY_ID[subject_id]
    except KeyError:
        raise KeyError(f"unknown media subject {subject_id!r}") from None


def subject_ids() -> List[str]:
    return [s["id"] for s in SUBJECTS]


def syllabus_entries() -> List[Tuple[str, Dict[str, Any]]]:
    """(subject_id, day-entry) pairs shaped exactly like syllabus day entries."""
    return [
        (
            s["id"],
            {
                "title": s["title"],
                "objectives": list(s["objectives"]),
                "key_questions": list(s["key_questions"]),
                "exercise_type": s["exercise_type"],
            },
        )
        for s in SUBJECTS
    ]


def as_track() -> Dict[str, Any]:
    """The catalog as a syllabus track, ready to merge."""
    return {
        "name": TRACK_NAME,
        "days": {str(i + 1): entry for i, (_, entry) in enumerate(syllabus_entries())},
    }


def merge_into(syllabus: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``syllabus`` with this catalog merged as a new track.

    Copies, never mutates — the caller's syllabus dict is untouched.
    Raises ValueError if the track key is already taken.
    """
    merged = copy.deepcopy(syllabus)
    tracks = merged.setdefault("tracks", {})
    if TRACK_KEY in tracks:
        raise ValueError(
            f"syllabus already has track {TRACK_KEY!r} — refusing to overwrite"
        )
    tracks[TRACK_KEY] = as_track()
    names = merged.setdefault("track_names", {})
    names[TRACK_KEY] = TRACK_NAME
    return merged
