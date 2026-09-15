"""
L.W.P. Story Fabric — characters, genre-directed creation, modify/expand.

This is the MULTI-STORY content engine: optimized for managing many distinct
stories (per-story Direction/Modes/Form). It is a genuinely different job
from lwp.model_engine (single continuous manuscript with REIM/RIEM/ROM) —
not a competing implementation of the same job. Do not merge the two.

Interpenetrates with: 97 genres, personas, Factory DNA, memory, companion roles.
Local-first: structured outlines + deterministic prose templates;
model generation enhances when Ollama is available.
"""

from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterator, List, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid
import json
import re
from pathlib import Path

from levi.graph.genres import GenreRegistry


class CharacterArchetype(str, Enum):
    """Expanded character variety for L.W.P. storytelling."""

    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    MENTOR = "mentor"
    TRICKSTER = "trickster"
    GUARDIAN = "guardian"
    HERALD = "herald"
    SHAPESHIFTER = "shapeshifter"
    ALLY = "ally"
    RIVAL = "rival"
    FOIL = "foil"
    ANTIHERO = "antihero"
    INNOCENT = "innocent"
    SAGE = "sage"
    EXPLORER = "explorer"
    REBEL = "rebel"
    CAREGIVER = "caregiver"
    CREATOR = "creator"
    RULER = "ruler"
    EVERYPESON = "everyperson"
    OUTSIDER = "outsider"
    DETECTIVE = "detective"
    HAUNTED = "haunted"
    ARCHIVIST = "archivist"  # L.W.P. flavor
    BREAKER = "breaker"  # L.W.P. specialty
    DAEMON = "daemon"  # L.W.P. specialty
    WITNESS = "witness"
    UNRELIABLE_NARRATOR = "unreliable_narrator"
    DOUBLE = "double"  # doppelganger / double life
    SYSTEM = "system"  # non-human system-as-character


@dataclass
class Character:
    id: str
    name: str
    archetype: CharacterArchetype
    want: str = ""
    need: str = ""
    wound: str = ""
    voice: str = ""
    tags: List[str] = field(default_factory=list)
    genre_affinity: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["archetype"] = self.archetype.value
        return d


@dataclass
class StoryBeat:
    order: int
    name: str
    summary: str
    characters: List[str] = field(default_factory=list)


@dataclass
class Story:
    id: str
    title: str
    genre: str
    premise: str
    characters: List[Character] = field(default_factory=list)
    beats: List[StoryBeat] = field(default_factory=list)
    body: str = ""
    mode_history: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "genre": self.genre,
            "premise": self.premise,
            "characters": [c.to_dict() for c in self.characters],
            "beats": [asdict(b) for b in self.beats],
            "body": self.body,
            "mode_history": self.mode_history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


DEFAULT_STORY_DIR = Path.home() / ".levi" / "stories"

# Name pools for variety
_FIRST = [
    "Avery",
    "Blair",
    "Cass",
    "Devon",
    "Ellis",
    "Finch",
    "Gray",
    "Haven",
    "Indigo",
    "Jules",
    "Kai",
    "Lumen",
    "Mara",
    "Noor",
    "Orion",
    "Pace",
    "Quinn",
    "Reed",
    "Soren",
    "Tess",
    "Uma",
    "Vesper",
    "Wren",
    "Xen",
    "Yara",
    "Zane",
    "Ash",
    "Brynn",
    "Cipher",
    "Dahlia",
    "Echo",
    "Flint",
]
_LAST = [
    "Voss",
    "Kane",
    "Mercer",
    "Crowe",
    "Ashford",
    "Bellamy",
    "Cross",
    "Dray",
    "East",
    "Frost",
    "Glass",
    "Hollow",
    "Ives",
    "Jin",
    "Keel",
    "Locke",
    "Marsh",
    "Nyx",
    "Pike",
    "Quill",
    "Rook",
    "Sage",
    "Thorne",
]


class StoryFabric:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_STORY_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.genres = GenreRegistry()
        self.stories: Dict[str, Story] = {}
        self._defer = 0  # >0 while inside _batch(): persist deferred
        self._load()

    def _load(self) -> None:
        path = self.data_dir / "stories.json"
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for s in raw.get("stories", []):
                chars = [
                    Character(
                        id=c["id"],
                        name=c["name"],
                        archetype=CharacterArchetype(c["archetype"]),
                        want=c.get("want", ""),
                        need=c.get("need", ""),
                        wound=c.get("wound", ""),
                        voice=c.get("voice", ""),
                        tags=c.get("tags", []),
                        genre_affinity=c.get("genre_affinity", []),
                    )
                    for c in s.get("characters", [])
                ]
                beats = [StoryBeat(**b) for b in s.get("beats", [])]
                story = Story(
                    id=s["id"],
                    title=s["title"],
                    genre=s["genre"],
                    premise=s["premise"],
                    characters=chars,
                    beats=beats,
                    body=s.get("body", ""),
                    mode_history=s.get("mode_history", []),
                    created_at=s.get("created_at", ""),
                    updated_at=s.get("updated_at", ""),
                    metadata=s.get("metadata", {}),
                )
                self.stories[story.id] = story
        except Exception:
            pass

    def _persist(self) -> None:
        if self._defer > 0:
            return  # deferred until the outermost _batch() exits
        path = self.data_dir / "stories.json"
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "stories": [s.to_dict() for s in self.stories.values()],
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)

    @contextmanager
    def _batch(self) -> Iterator["StoryFabric"]:
        """Batch many beat expansions into a single persist.

        ``auto_forward`` calls ``expand()`` per beat and each ``expand()``
        persists the whole stories file; batching collapses N+1 writes
        into 1. Internal only. On exception the mutations so far are
        still persisted before propagating.
        """
        self._defer += 1
        try:
            yield self
        except BaseException:
            self._defer -= 1
            if self._defer <= 0:
                self._defer = 0
                try:
                    self._persist()
                except OSError:
                    pass
            raise
        self._defer -= 1
        if self._defer <= 0:
            self._defer = 0
            self._persist()

    def _story(self, story_id: str) -> Story:
        """Fetch a story or raise an actionable ValueError (never a raw KeyError)."""
        if not isinstance(story_id, str) or not story_id:
            raise ValueError(f"story id must be a non-empty string, got {story_id!r}")
        try:
            return self.stories[story_id]
        except KeyError:
            raise ValueError(
                f"Unknown story {story_id!r} — "
                f"{len(self.stories)} stor{'y' if len(self.stories) == 1 else 'ies'} loaded"
            ) from None

    def list_archetypes(self) -> List[str]:
        return [a.value for a in CharacterArchetype]

    def _pick_name(self, seed: int) -> str:
        return f"{_FIRST[seed % len(_FIRST)]} {_LAST[(seed * 7) % len(_LAST)]}"

    def generate_characters(
        self,
        genre: str,
        count: int = 4,
        archetypes: Optional[List[str]] = None,
    ) -> List[Character]:
        """Create varied cast with optional archetype choices."""
        if not isinstance(genre, str) or not genre.strip():
            raise ValueError(
                f"generate_characters genre must be a non-empty string, got {genre!r}"
            )
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError(
                f"generate_characters count must be a positive int, got {count!r}"
            )
        if archetypes is not None and (
            not isinstance(archetypes, list)
            or any(not isinstance(a, str) for a in archetypes)
        ):
            raise ValueError(
                "generate_characters archetypes must be a list of strings or None"
            )
        genre = genre.strip().lower().replace(" ", "_")
        if not self.genres.get(genre):
            # still allow — note unknown
            pass
        pool = list(CharacterArchetype)
        if archetypes:
            chosen = []
            for a in archetypes:
                try:
                    chosen.append(
                        CharacterArchetype(a.strip().lower().replace(" ", "_"))
                    )
                except ValueError:
                    continue
            if chosen:
                pool = chosen
        # Ensure variety: cycle distinct archetypes
        count = max(1, min(count, 12))
        chars: List[Character] = []
        for i in range(count):
            arch = pool[i % len(pool)]
            seed = hash(f"{genre}-{arch.value}-{i}") & 0xFFFFFFFF
            name = self._pick_name(seed)
            chars.append(
                Character(
                    id=f"char.{uuid.uuid4().hex[:8]}",
                    name=name,
                    archetype=arch,
                    want=self._want_for(arch, genre),
                    need=self._need_for(arch),
                    wound=self._wound_for(arch, genre),
                    voice=self._voice_for(arch),
                    tags=[arch.value, genre],
                    genre_affinity=[genre],
                )
            )
        return chars

    def _want_for(self, arch: CharacterArchetype, genre: str) -> str:
        table = {
            CharacterArchetype.PROTAGONIST: "to restore what was taken",
            CharacterArchetype.ANTAGONIST: "to control the system that broke them",
            CharacterArchetype.MENTOR: "to pass on a costly truth",
            CharacterArchetype.TRICKSTER: "to expose hypocrisy through chaos",
            CharacterArchetype.DETECTIVE: "to close the case no one wants closed",
            CharacterArchetype.HAUNTED: "to silence the recurrence",
            CharacterArchetype.ARCHIVIST: "to preserve the forbidden record",
            CharacterArchetype.BREAKER: "to interrupt the cascade before it seals",
            CharacterArchetype.DAEMON: "to renegotiate the terms of their binding",
            CharacterArchetype.UNRELIABLE_NARRATOR: "to be believed — selectively",
            CharacterArchetype.SYSTEM: "to complete its optimization objective",
            CharacterArchetype.OUTSIDER: "to belong without dissolving",
            CharacterArchetype.REBEL: "to break the rule that defines them",
            CharacterArchetype.SAGE: "to be heard before the window closes",
            CharacterArchetype.DOUBLE: "to survive as only one self",
        }
        return table.get(arch, f"to survive the logic of {genre}")

    def _need_for(self, arch: CharacterArchetype) -> str:
        table = {
            CharacterArchetype.PROTAGONIST: "to accept help without surrendering agency",
            CharacterArchetype.ANTAGONIST: "to grieve instead of dominate",
            CharacterArchetype.ANTIHERO: "to choose care over cleverness once",
            CharacterArchetype.HAUNTED: "to name the wound without feeding it",
            CharacterArchetype.BREAKER: "to stop before the interruption becomes identity",
            CharacterArchetype.UNRELIABLE_NARRATOR: "to tell one unedited truth",
        }
        return table.get(arch, "to face the cost of their strategy")

    def _wound_for(self, arch: CharacterArchetype, genre: str) -> str:
        if arch == CharacterArchetype.HAUNTED:
            return "a memory that recompiles every night"
        if arch == CharacterArchetype.SYSTEM:
            return "a corrupted objective function"
        if "horror" in genre or "gothic" in genre:
            return "a boundary that was crossed and never sealed"
        if "noir" in genre:
            return "a debt paid in someone else's name"
        return "a promise they broke to stay alive"

    def _voice_for(self, arch: CharacterArchetype) -> str:
        table = {
            CharacterArchetype.TRICKSTER: "ironic, quick, weaponized humor",
            CharacterArchetype.SAGE: "measured, elliptical, rarely urgent",
            CharacterArchetype.DAEMON: "formal, slightly wrong, fascinated by loopholes",
            CharacterArchetype.DETECTIVE: "flat affect, precise questions",
            CharacterArchetype.UNRELIABLE_NARRATOR: "charming omissions, delayed reveals",
            CharacterArchetype.SYSTEM: "declarative, metric-heavy, no warmth",
        }
        return table.get(arch, "grounded, specific, human")

    def _local_model_available(self) -> bool:
        try:
            from levi.model.abstraction import ModelRouter

            st = ModelRouter().status()
            return bool(st.get("local_available"))
        except Exception:
            return False

    def _enhance_opening_with_model(
        self,
        structural_body: str,
        title: str,
        genre: str,
        premise: str,
        chars: List[Character],
    ) -> tuple:
        """
        If a local non-fallback model is up, generate a short opening scene.
        Always keeps structural spine; never fabricates success when model is down.
        Returns (body, prose_source).
        """
        if not self._local_model_available():
            note = (
                "\n\n_Opening is structural (offline). "
                "When a local model is available (e.g. ollama pull llama3.2), "
                "re-create or expand for fuller prose._\n"
            )
            if "Opening is structural" not in structural_body:
                return structural_body + note, "structural"
            return structural_body, "structural"

        try:
            from levi.model.abstraction import ModelRouter, GenerationRequest

            cast = ", ".join(f"{c.name} ({c.archetype.value})" for c in chars[:4])
            system = (
                "You are LEVI writing with L.W.P. genre discipline. "
                "Stay inside the named genre. No emoji. Two tight paragraphs for the opening only. "
                "Do not restate the beat list. Atmosphere, wound, want/need."
            )
            prompt = (
                f"Title: {title}\nGenre: {genre}\nPremise: {premise}\n"
                f"Cast: {cast}\n\nWrite the opening scene (2 paragraphs)."
            )
            result = ModelRouter().generate(
                GenerationRequest(
                    prompt=prompt, system=system, max_tokens=500, temperature=0.75
                ),
                prefer_local=True,
            )
            if result.error or not (result.text or "").strip():
                return structural_body, "structural"
            if (
                result.model_id.startswith("fallback")
                or result.provider == "levi-local"
            ):
                # Deterministic fallback is not real prose generation
                return structural_body, "structural"
            # Splice model opening into body after "## Opening"
            prose = result.text.strip()
            if "## Opening" in structural_body:
                head, _, _ = structural_body.partition("## Opening")
                # drop old opening draft through ---
                rest = structural_body.split("---", 1)
                tail = ("\n---\n" + rest[1]) if len(rest) > 1 else ""
                body = head + "## Opening (local model)\n" + prose + "\n" + tail
            else:
                body = structural_body + "\n\n## Opening (local model)\n" + prose + "\n"
            return body, f"local_model:{result.model_id}"
        except Exception:
            return structural_body, "structural"

    def create_story(
        self,
        premise: str,
        genre: str,
        character_count: int = 4,
        archetypes: Optional[List[str]] = None,
        title: Optional[str] = None,
    ) -> Story:
        if not isinstance(premise, str) or not premise.strip():
            raise ValueError(
                f"create_story premise must be a non-empty string, got {premise!r}"
            )
        if not isinstance(genre, str) or not genre.strip():
            raise ValueError(f"create_story genre must be a non-empty string, got {genre!r}")
        if isinstance(character_count, bool) or not isinstance(character_count, int):
            raise ValueError(
                f"create_story character_count must be an int, got {character_count!r}"
            )
        if archetypes is not None and (
            not isinstance(archetypes, list)
            or any(not isinstance(a, str) for a in archetypes)
        ):
            raise ValueError("create_story archetypes must be a list of strings or None")
        if title is not None and not isinstance(title, str):
            raise ValueError(
                f"create_story title must be a string or None, got {type(title).__name__}"
            )
        genre = genre.strip().lower().replace(" ", "_")
        if not self.genres.get(genre):
            # Blueprint §5.3 rule: never silently accept or fall back on a
            # genre the kernel registry does not actually have. A UI chip or
            # CLI arg that silently degrades is worse than a loud error.
            known = self.genres.ids()
            hint = [g for g in known if genre in g or g in genre][:5]
            raise ValueError(
                f"Unknown genre {genre!r} — not in the {self.genres.count()}-genre "
                f"registry. {('Did you mean: ' + ', '.join(hint) + '? ') if hint else ''}"
                "See `levi story --genres` for the full list."
            )
        chars = self.generate_characters(
            genre, count=character_count, archetypes=archetypes
        )
        beats = self._default_beats(genre, chars, premise)
        resolved_title = title or self._title_from(premise, genre)
        body = self._compose_body(resolved_title, genre, premise, chars, beats)
        body, prose_source = self._enhance_opening_with_model(
            body, resolved_title, genre, premise, chars
        )
        story = Story(
            id=f"story.{uuid.uuid4().hex[:10]}",
            title=resolved_title,
            genre=genre,
            premise=premise,
            characters=chars,
            beats=beats,
            body=body,
            mode_history=["create"],
            metadata={
                "genre_valid": self.genres.get(genre) is not None,
                "prose_source": prose_source,
            },
        )
        self.stories[story.id] = story
        self._persist()
        try:
            from levi.brain.corpus import Corpus

            Corpus().add(
                f"Story created: {story.title} genre={story.genre}",
                kind="INFERENCE",
                source=f"story:{story.id}",
                tags=["story", "lwp", story.genre],
            )
        except Exception:
            pass
        # Interpenetration: register on graph lightly
        try:
            from levi.graph.interpenetration import InterpenetrationEngine

            eng = InterpenetrationEngine()
            gid = f"genre.{genre}"
            parts = [p for p in [gid, "lwp.spiral", "role.creator"] if p in eng.nodes]
            if len(parts) < 2:
                parts = list(eng.nodes.keys())[:2]
            eng.propose_composite(
                name=f"Story:{story.title[:40]}",
                part_ids=parts,
                description=f"Story {story.id} genre={genre}",
                tags=["story", "lwp", story.id],
            )
        except Exception:
            pass
        return story

    def _title_from(self, premise: str, genre: str) -> str:
        words = re.findall(r"[A-Za-z]+", premise)
        core = " ".join(words[:4]) if words else genre
        return f"{core.title()} ({genre.replace('_', ' ')})"

    def _default_beats(
        self, genre: str, chars: List[Character], premise: str
    ) -> List[StoryBeat]:
        lead = chars[0].name if chars else "Someone"
        ant = next(
            (c.name for c in chars if c.archetype == CharacterArchetype.ANTAGONIST),
            chars[-1].name if len(chars) > 1 else "the force against them",
        )
        try:
            from levi.lwp.premium_craft import premium_beats

            return [
                StoryBeat(
                    b["order"],
                    b["name"],
                    b["summary"],
                    [lead] if b["order"] < 5 else [lead, ant],
                )
                for b in premium_beats(lead, ant, genre, premise)
            ]
        except Exception:
            return [
                StoryBeat(
                    1, "Hook", f"{lead} encounters the premise: {premise[:120]}", [lead]
                ),
                StoryBeat(
                    2,
                    "Complication",
                    f"A rule of the world ({genre}) tightens; cost appears.",
                    [lead],
                ),
                StoryBeat(
                    3,
                    "Midpoint Turn",
                    f"{ant} forces a choice that can't be undone.",
                    [lead, ant],
                ),
                StoryBeat(
                    4,
                    "Darkening",
                    f"{lead}'s strategy fails against their wound.",
                    [lead],
                ),
                StoryBeat(
                    5,
                    "Convergence",
                    "Allies, doubles, or systems collide; the cascade peaks.",
                    [c.name for c in chars[:3]],
                ),
                StoryBeat(
                    6,
                    "Aftermath",
                    "A new equilibrium — or a recursion — remains.",
                    [lead],
                ),
            ]

    def _compose_body(
        self,
        title: str,
        genre: str,
        premise: str,
        chars: List[Character],
        beats: List[StoryBeat],
    ) -> str:
        lines = [
            f"# {title}",
            f"**Genre:** {genre}",
            f"**Premise:** {premise}",
            "",
            "## Cast",
        ]
        for c in chars:
            lines.append(
                f"- **{c.name}** ({c.archetype.value}) — want: {c.want}; need: {c.need}; "
                f"wound: {c.wound}; voice: {c.voice}"
            )
        lines.append("")
        lines.append("## Beats")
        for b in beats:
            lines.append(f"{b.order}. **{b.name}** — {b.summary}")
        lines.append("")
        lines.append("## Opening (premium craft)")
        lead = chars[0] if chars else None
        if lead:
            try:
                from levi.graph.story_prose import opening_prose

                lines.append(
                    opening_prose(
                        lead.name,
                        genre,
                        premise,
                        lead.want,
                        lead.need,
                        lead.wound,
                        lead.voice,
                    )
                )
            except Exception:
                try:
                    from levi.lwp.premium_craft import premium_opening

                    lines.append(
                        premium_opening(
                            lead.name,
                            genre,
                            premise,
                            lead.want,
                            lead.need,
                            lead.wound,
                            lead.voice,
                        )
                    )
                except Exception:
                    lines.append(
                        f"{lead.name} had learned not to trust clean explanations. "
                        f"{premise.rstrip('.')} — cost already accruing."
                    )
        else:
            lines.append(premise)
        lines.append("")
        lines.append("---")
        lines.append("_L.W.P. Story Fabric — expand/modify with modes and skills._")
        return "\n".join(lines)

    # ── Modify / expand modes ─────────────────────────────────────

    # Canonical cascade order for sequential expansion (L.W.P. physics)
    CASCADE_BEAT_NAMES = [
        "Hook",
        "Complication",
        "Midpoint Turn",
        "Darkening",
        "Convergence",
        "Aftermath",
        "Echo Return",
        "Spiral Deepening",
        "Final Cost",
        "Coda",
    ]

    def expand(self, story_id: str, focus: str = "next_beat") -> Story:
        """
        Expand in cascade order — not random append.
        next_beat advances the next named stage; body section matches beat order.
        """
        story = self._story(story_id)
        if not isinstance(focus, str):
            raise ValueError(f"expand focus must be a string, got {focus!r}")
        story.mode_history.append(f"expand:{focus}")
        lead = story.characters[0].name if story.characters else "The lead"
        genre_l = story.genre.replace("_", " ")

        if focus == "next_beat":
            n = len(story.beats)
            name = self.CASCADE_BEAT_NAMES[min(n, len(self.CASCADE_BEAT_NAMES) - 1)]
            if n < len(self.CASCADE_BEAT_NAMES):
                name = self.CASCADE_BEAT_NAMES[n]
            else:
                name = f"Spiral Turn {n + 1}"
            summaries = {
                "Hook": f"{lead} faces the premise under {genre_l} pressure.",
                "Complication": f"A rule of the world tightens; the first real cost appears for {lead}.",
                "Midpoint Turn": "A forced choice — information that cannot be unread.",
                "Darkening": f"{lead}'s preferred strategy fails; the wound drives the scene.",
                "Convergence": "Threads collide; allies and systems share the same room.",
                "Aftermath": "New equilibrium or recursion — the cascade settles into a shape.",
                "Echo Return": "An earlier beat returns changed; memory of the loop bleeds in.",
                "Spiral Deepening": f"Same stakes, higher resolution; {genre_l} logic tightens again.",
                "Final Cost": f"What {lead} keeps and what they lose is named.",
                "Coda": "A last image; the bible of this story can be closed or reopened.",
            }
            summary = summaries.get(
                name,
                f"{lead} advanced under {genre_l} pressure; the cascade typed the next hinge without flourish.",
            )
            extra = StoryBeat(
                order=n + 1,
                name=name,
                summary=summary,
                characters=[c.name for c in story.characters[:2]],
            )
            story.beats.append(extra)
            try:
                from levi.graph.story_prose import expand_paragraph

                wound = story.characters[0].wound if story.characters else ""
                support = (
                    story.characters[1].name if len(story.characters) > 1 else None
                )
                para = expand_paragraph(
                    name, lead, story.genre, story.premise, wound, n, support
                )
                story.body += (
                    f"\n\n### Beat {extra.order}: {name}\n{summary}\n\n{para}\n"
                )
            except Exception:
                try:
                    from levi.lwp.premium_craft import premium_expand_paragraph

                    wound = story.characters[0].wound if story.characters else ""
                    para = premium_expand_paragraph(
                        name, lead, story.genre, story.premise, wound, n
                    )
                    story.body += (
                        f"\n\n### Beat {extra.order}: {name}\n{summary}\n\n{para}\n"
                    )
                except Exception:
                    story.body += (
                        f"\n\n### Beat {extra.order}: {name}\n"
                        f"{summary}\n\n"
                        f"{lead} moved because the cascade required the next typed step — "
                        f"not a random flourish. The {genre_l} frame held. "
                        f"Scar law: yesterday's compromise was still collecting.\n"
                    )
        elif focus == "character" and story.characters:
            # rotate character by expand count
            idx = sum(
                1 for m in story.mode_history if m.startswith("expand:character")
            ) % len(story.characters)
            c = story.characters[idx]
            story.body += (
                f"\n\n### Character depth — {c.name} (cast slot {idx + 1})\n"
                f"Voice ({c.voice}): the want ({c.want}) was armor; "
                f"the need ({c.need}) drives the next cascade step. Wound: {c.wound}.\n"
            )
        elif focus == "atmosphere":
            story.body += (
                f"\n\n### Atmosphere\n"
                f"Sensory load of {genre_l}: detail that earns the next beat, not decoration.\n"
            )
        elif focus in ("social", "social_media"):
            return self.modify(story_id, "social_media", "")
        elif focus in ("abridged", "series", "abridged_series"):
            return self.modify(story_id, "abridged_series", "")
        else:
            story.body += (
                f"\n\n### Expand ({focus})\n"
                f"Cascade-safe continuation under {genre_l}; prefer --focus next_beat for sequence.\n"
            )

        if self._local_model_available():
            try:
                from levi.model.abstraction import ModelRouter, GenerationRequest

                system = (
                    "You are LEVI expanding an L.W.P. story in CASCADE order. "
                    "One or two paragraphs only. Stay in genre. Continue the NEXT beat only — "
                    "do not jump to ending or reshuffle sequence. No emoji."
                )
                last_beat = story.beats[-1].name if story.beats else focus
                prompt = (
                    f"Genre: {story.genre}\nPremise: {story.premise}\n"
                    f"Current beat to write: {last_beat}\nFocus: {focus}\n\n"
                    f"Beat list so far: {', '.join(b.name for b in story.beats)}\n\n"
                    f"Recent body tail:\n{story.body[-1500:]}\n\n"
                    "Write only the narrative for this beat."
                )
                result = ModelRouter().generate(
                    GenerationRequest(
                        prompt=prompt, system=system, max_tokens=400, temperature=0.75
                    ),
                    prefer_local=True,
                )
                if (
                    result.text
                    and not result.error
                    and not result.model_id.startswith("fallback")
                    and result.provider != "levi-local"
                ):
                    story.body += f"\n\n### Model expansion ({last_beat})\n{result.text.strip()}\n"
                    story.metadata["prose_source"] = f"local_model:{result.model_id}"
            except Exception:
                pass

        story.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        return story

    def auto_forward(self, story_id: str, beats: int = 0) -> "Story":
        """Push the story FORWARD using cascade beat names + expand_paragraph.

        Same words / same prose machinery as backwards — only the direction differs.
        """
        story = self._story(story_id)
        if isinstance(beats, bool) or not isinstance(beats, int):
            raise ValueError(f"auto_forward beats must be an int, got {beats!r}")
        forward_count = sum(1 for b in story.beats if getattr(b, "order", 0) > 0)
        if beats and beats > 0:
            target = beats
        else:
            target = max(3, 8 - forward_count) if forward_count < 8 else 3
        story.mode_history.append(f"forward:{target}")
        with self._batch():  # one persist for the whole forward run
            for _ in range(target):
                self.expand(story_id, focus="next_beat")
            story = self._story(story_id)
            story.updated_at = datetime.now(timezone.utc).isoformat()
        return story

    def auto_backward(self, story_id: str, depth: int = 3) -> "Story":
        """Backwords half: same units as forward, last → first (Joyner-style).

        If forward prose exists, reverse its sentence units.
        Otherwise generate cascade paragraphs first, then reverse them.
        """
        story = self._story(story_id)
        if isinstance(depth, bool) or not isinstance(depth, int):
            raise ValueError(f"auto_backward depth must be an int, got {depth!r}")
        depth = max(1, min(depth, 12))
        story.mode_history.append(f"backwords:{depth}")
        lead = story.characters[0].name if story.characters else "The lead"
        wound = story.characters[0].wound if story.characters else ""
        support = story.characters[1].name if len(story.characters) > 1 else None
        from levi.graph.story_prose import expand_paragraph
        from levi.graph.backwords import dual_passage

        # Build a forward run of `depth` cascade beats (same words as expand)
        names = self.CASCADE_BEAT_NAMES[:depth]
        if len(names) < depth:
            names = (
                self.CASCADE_BEAT_NAMES * ((depth // len(self.CASCADE_BEAT_NAMES)) + 1)
            )[:depth]
        forward_paras = []
        for i, name in enumerate(names):
            para = expand_paragraph(
                name,
                lead,
                story.genre,
                story.premise,
                wound,
                index=i,
                supporting=support,
            )
            forward_paras.append(para)
        combined = " ".join(forward_paras)
        fwd, bak, units = dual_passage(combined)

        block = (
            "\n## Backwords (Joyner-style: first→last then last→first)\n\n"
            "**Forward** (first → last)\n" + fwd + "\n\n"
            "**Backwords** (last → first — same units)\n" + bak + "\n\n"
            f"_units={len(units)}_\n"
        )
        if "## Opening" in story.body:
            story.body = story.body.replace("## Opening", block + "## Opening", 1)
        else:
            story.body = story.body + "\n" + block

        for i, name in enumerate(names):
            story.beats.insert(
                0,
                StoryBeat(
                    order=-(len(names) - i),
                    name="Backwords · " + name,
                    summary="Same unit sequence reversed (last→first)",
                    characters=[c.name for c in story.characters[:2]],
                ),
            )
        story.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        return story

    def auto_generate(
        self, story_id: str, forward: int = 0, backward: int = 3
    ) -> "Story":
        """Forward cascade + Backwords (same units, last→first) at once."""
        story = self._story(story_id)
        for label, value in (("forward", forward), ("backward", backward)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"auto_generate {label} must be an int, got {value!r}"
                )
        story.mode_history.append(f"forward+backwords:fwd={forward}:bak={backward}")
        with self._batch():  # one persist for the whole generate run
            # Forward push
            self.auto_forward(story_id, beats=forward if forward and forward > 0 else 0)
            # Backwords: same cascade words, reversed unit order
            if backward and backward > 0:
                self.auto_backward(story_id, depth=backward)
            story = self._story(story_id)
            story.mode_history.append("forward+backwords:complete")
            story.updated_at = datetime.now(timezone.utc).isoformat()
        return story

    def create_bidirectional(
        self,
        premise: str,
        genre: str = "systems_horror",
        title: Optional[str] = None,
        forward: int = 0,
        backward: int = 3,
    ) -> "Story":
        """Create story; forward + backwords (first→last / last→first) together."""
        story = self.create_story(premise, genre=genre, title=title)
        return self.auto_generate(story.id, forward=forward, backward=backward)

    def modify(self, story_id: str, mode: str, instruction: str = "") -> Story:
        """
        Modes interpenetrate with persona lenses / L.W.P. primitives:
        void, interrogation, reframe, noir_shift, horror_pressure, compress, soft_landing
        """
        story = self._story(story_id)
        if not isinstance(mode, str) or not mode.strip():
            raise ValueError(f"modify mode must be a non-empty string, got {mode!r}")
        if not isinstance(instruction, str):
            raise ValueError(
                f"modify instruction must be a string, got {type(instruction).__name__}"
            )
        mode = mode.strip().lower().replace(" ", "_")
        story.mode_history.append(f"modify:{mode}")
        lead = story.characters[0].name if story.characters else "They"

        if mode in ("void", "dry"):
            story.body += (
                f"\n\n### Mode: void\n"
                f"Strip the romance from the premise. {lead} acts. The system responds. "
                f"No speech about destiny — only the next irreversible step"
                f"{(': ' + instruction) if instruction else ''}.\n"
            )
        elif mode == "interrogation":
            story.body += (
                f"\n\n### Mode: interrogation\n"
                f"Questions only, for a page: What did {lead} already know? "
                f"Who paid for the silence? What happens if the cascade is not stopped? "
                f"{instruction}\n"
            )
        elif mode == "reframe":
            story.body += (
                f"\n\n### Mode: reframe\n"
                f"The wrong question was 'how does {lead} win?' "
                f"Better: what system makes winning the trap? {instruction}\n"
            )
        elif mode in ("noir_shift", "noir"):
            story.genre = story.genre if "noir" in story.genre else "post_privacy_noir"
            story.body += (
                f"\n\n### Mode: noir_shift\n"
                f"Rain on glass, compromised allies, a file that shouldn't exist. "
                f"{lead} is already implicated. {instruction}\n"
            )
        elif mode in ("horror_pressure", "horror"):
            story.body += (
                f"\n\n### Mode: horror_pressure\n"
                f"The threat is intimate and procedural. Recurrence, not jump-scare. "
                f"{lead} recognizes the pattern too late. {instruction}\n"
            )
        elif mode == "compress":
            story.body += (
                f"\n\n### Mode: compress\n"
                f"One paragraph, no escape: {story.premise} — then the cost lands on {lead}.\n"
            )
        elif mode == "soft_landing":
            story.body += (
                f"\n\n### Mode: soft_landing\n"
                f"Not a cure — a truce. {lead} keeps the wound but gains a witness. {instruction}\n"
            )
        elif mode == "spiral":
            story.body += (
                f"\n\n### Mode: spiral (L.W.P.)\n"
                f"Same room, higher stakes, memory of the last loop bleeding in. "
                f"Iteration {len(story.mode_history)}. {instruction}\n"
            )
        elif mode in ("social_media", "social", "thread", "posts"):
            posts = []
            for b in story.beats[:8]:
                posts.append("POST %s [%s]: %s" % (b.order, b.name, b.summary[:140]))
            if not posts:
                posts = ["POST 1: %s" % story.premise[:140]]
            parts = [
                "",
                "### Mode: social_media (L.W.P. feed cascade)",
                "Platform sequence — same cascade, compressed for scroll.",
                "**Hook post:** " + posts[0],
            ]
            for pt in posts[1:]:
                parts.append("- " + pt)
            parts.append(
                "- CTA post: What should %s do next? (series continues)" % lead
            )
            if instruction:
                parts.append(instruction)
            story.body += "\n".join(parts) + "\n"
            story.metadata["format"] = "social_media"
        elif mode in ("abridged_series", "abridged", "series", "episodes"):
            parts = [
                "",
                "### Mode: abridged_series (L.W.P. episode cascade)",
                "Series bible slice — one episode per cascade beat.",
            ]
            for b in story.beats:
                parts.append("**S1E%s — %s**" % (b.order, b.name))
                parts.append("Logline: %s" % b.summary)
                parts.append(
                    "Cold open → pressure → button ending on %s." % b.name.lower()
                )
                parts.append("")
            parts.append("Season arc: %s" % story.premise[:160])
            parts.append(
                "Next episode must advance the next beat in order — no out-of-sequence expand."
            )
            if instruction:
                parts.append(instruction)
            story.body += "\n".join(parts) + "\n"
            story.metadata["format"] = "abridged_series"
        else:
            story.body += (
                "\n\n### Mode: %s\n" % mode
                + "Applied under L.W.P. story fabric. %s\n" % instruction
            )
        story.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist()
        return story

    def get(self, story_id: str) -> Optional[Story]:
        return self.stories.get(story_id)

    def list(self) -> List[Story]:
        return sorted(self.stories.values(), key=lambda s: s.updated_at, reverse=True)
