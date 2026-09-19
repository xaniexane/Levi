"""MySpace-era profile customization engine — data + validation only.

STATUS: AWAITING KEEPER REVIEW. This module implements the customization
canon from ``docs/SOCIAL_PLATFORM_DESIGN.md`` (§1a): the profile is a
*canvas*, not a template — theme tokens, reorderable layouts, a profile
song, animated UI descriptors, and interactive widget descriptors, all
member-controlled, all inside binding guardrails.

What this is: shapes and rules. Theme tokens are named, validated
design values. Layouts are ordered section lists. Animations and widgets
are *descriptors as data* — the engine validates them; it never executes
code. Member content (custom blocks, guestbook entries) is structured
data, never raw markup.

Binding guardrails (the keeper's law):
- Contrast floors hold on every theme: unreadable text/background pairs
  are auto-repaired (or refused in strict mode) — full expression, never
  at the cost of readability.
- ``prefers-reduced-motion`` is honored: animations degrade to static.
- No autoplay, ever: a profile song with ``autoplay=True`` is refused.
- Entrance motion must settle at the natural position — animation never
  strands text off-canvas or otherwise breaks readability.
- Everything member-supplied is sandboxed as data: no markup execution,
  URLs scheme-validated (http/https only).

Stdlib only. No network, no storage backends — the caller persists the
sealed dicts however it persists anything else.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

CUSTOMIZE_FORMAT = "levi-social-customize"
CUSTOMIZE_VERSION = 1

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CustomizeError(Exception):
    """Any customization refusal: bad token, bad layout, broken guardrail."""


# ---------------------------------------------------------------------------
# Theme tokens
# ---------------------------------------------------------------------------

# Token names the engine understands. Colors pair with backgrounds for the
# contrast floor; fonts/radii/spacing/backgrounds are structural.
TOKEN_COLORS = (
    "color.text",
    "color.heading",
    "color.accent",
    "color.link",
    "color.muted",
)
TOKEN_BACKGROUNDS = ("bg.page", "bg.panel", "bg.accent")
TOKEN_FONTS = ("font.display", "font.body")
TOKEN_RADII = ("radius.panel", "radius.widget")
TOKEN_SPACING = ("spacing.gap", "spacing.pad")
TOKEN_ALL = (
    TOKEN_COLORS + TOKEN_BACKGROUNDS + TOKEN_FONTS + TOKEN_RADII + TOKEN_SPACING
)

_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")
_LENGTH_RE = re.compile(r"\d+(?:\.\d+)?(?:px|rem|em|%)\Z")
# Fonts: generic families are always safe; named families must be simple
# identifiers (no url(), no quotes tricks — stored as data, rendered by a
# renderer that treats them as plain strings).
_FONT_RE = re.compile(r"[A-Za-z][A-Za-z0-9 \-]{0,63}\Z")
_GENERIC_FONTS = ("serif", "sans-serif", "monospace", "cursive", "fantasy")
_URL_RE = re.compile(r"https?://[^\s<>\"]{1,2048}\Z", re.IGNORECASE)

# WCAG AA floor for normal text. The platform's promise: expression never
# costs readability.
CONTRAST_FLOOR = 4.5


def _check_color(value: str, what: str) -> str:
    if not isinstance(value, str) or not _COLOR_RE.match(value):
        raise CustomizeError(
            "bad %s %r: must be #rgb or #rrggbb" % (what, value)
        )
    return value.lower()


def _check_length(value: str, what: str) -> str:
    if not isinstance(value, str) or not _LENGTH_RE.match(value):
        raise CustomizeError(
            "bad %s %r: must be a non-negative length like 8px, 1.5rem, 50%%"
            % (what, value)
        )
    return value


def _check_font(value: str, what: str) -> str:
    if not isinstance(value, str) or not _FONT_RE.match(value.lower()):
        raise CustomizeError("bad %s %r: simple font name only" % (what, value))
    return value


def _check_url(value: str, what: str) -> str:
    if not isinstance(value, str) or not _URL_RE.match(value):
        raise CustomizeError(
            "bad %s: must be an http(s) URL, no markup" % what
        )
    if re.search(r"javascript\s*:", value, re.IGNORECASE):
        raise CustomizeError("bad %s: javascript: URLs refused" % what)
    return value


def _hex_to_rgb(value: str) -> Tuple[float, float, float]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def _luminance(value: str) -> float:
    """Relative luminance per WCAG 2.x (sRGB)."""

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _hex_to_rgb(value)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two hex colors; 1.0 (none) .. 21.0 (max)."""
    l1 = _luminance(_check_color(fg, "fg"))
    l2 = _luminance(_check_color(bg, "bg"))
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


def _best_text_color(bg: str) -> str:
    """Pick the readable extreme (black or white) with the better ratio."""
    black = contrast_ratio("#000000", bg)
    white = contrast_ratio("#ffffff", bg)
    return "#000000" if black >= white else "#ffffff"


@dataclass
class ThemeToken:
    """One named design value. ``kind`` decides validation."""

    name: str
    value: Any
    kind: str  # "color" | "font" | "length" | "background"

    def validate(self) -> "ThemeToken":
        if self.name not in TOKEN_ALL:
            raise CustomizeError("unknown token %r" % (self.name,))
        if self.kind == "color":
            _check_color(self.value, self.name)
        elif self.kind == "font":
            _check_font(self.value, self.name)
        elif self.kind == "length":
            _check_length(self.value, self.name)
        elif self.kind == "background":
            self._validate_background()
        else:
            raise CustomizeError("bad token kind %r" % (self.kind,))
        return self

    def _validate_background(self) -> None:
        v = self.value
        if isinstance(v, str):
            _check_color(v, self.name)  # solid color background
            return
        if isinstance(v, dict):
            kind = v.get("type")
            if kind == "gradient":
                stops = v.get("stops")
                if not isinstance(stops, list) or len(stops) < 2:
                    raise CustomizeError(
                        "bad %s: gradient needs >= 2 color stops" % self.name
                    )
                for stop in stops:
                    _check_color(stop, self.name + ".stop")
                return
            if kind == "image":
                _check_url(v.get("url", ""), self.name + ".url")
                return
        raise CustomizeError(
            "bad %s: background must be a color, {type: gradient, stops: [...]}, "
            "or {type: image, url: ...}" % self.name
        )


# Which text colors are checked against which backgrounds for the floor.
CONTRAST_PAIRS = (
    ("color.text", "bg.page"),
    ("color.heading", "bg.page"),
    ("color.text", "bg.panel"),
    ("color.link", "bg.page"),
    ("color.accent", "bg.accent"),
)


@dataclass
class ProfileTheme:
    """A profile's full token set. Missing tokens fall back to defaults."""

    tokens: Dict[str, ThemeToken] = field(default_factory=dict)

    def set(self, token: ThemeToken) -> "ProfileTheme":
        token.validate()
        self.tokens[token.name] = token
        return self

    def get(self, name: str) -> Optional[ThemeToken]:
        return self.tokens.get(name)

    def colors(self) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for name in TOKEN_COLORS + TOKEN_BACKGROUNDS:
            tok = self.tokens.get(name)
            if tok is not None and tok.kind in ("color", "background"):
                v = tok.value
                out[name] = v if isinstance(v, str) else "#000000"
        return out


DEFAULT_THEME = ProfileTheme(
    tokens={
        name: ThemeToken(name=name, value=value, kind="color")
        for name, value in {
            "color.text": "#e8e4da",
            "color.heading": "#f5f1e6",
            "color.accent": "#c9a227",
            "color.link": "#7fb3d5",
            "color.muted": "#8a8578",
            "bg.page": "#0d0b08",
            "bg.panel": "#1a1611",
            "bg.accent": "#2a2118",
        }.items()
    }
)


def enforce_contrast(
    theme: ProfileTheme, *, strict: bool = False
) -> Tuple[ProfileTheme, List[str]]:
    """Enforce the contrast floor on every text/background pair.

    Default mode auto-repairs: an unreadable text color is replaced with
    the readable extreme (black or white, whichever scores better) and
    the repair is reported. ``strict=True`` refuses instead of repairing.
    Returns (theme, repairs); in strict mode returns ([], []) on success.
    """
    colors = theme.colors()
    repaired: "ProfileTheme" = ProfileTheme(
        tokens=dict(theme.tokens)
    )
    repairs: List[str] = []
    for fg_name, bg_name in CONTRAST_PAIRS:
        fg = colors.get(fg_name)
        bg = colors.get(bg_name)
        if fg is None or bg is None:
            continue  # token not set: renderer falls back to DEFAULT_THEME
        ratio = contrast_ratio(fg, bg)
        if ratio >= CONTRAST_FLOOR:
            continue
        if strict:
            raise CustomizeError(
                "contrast refusal: %s on %s scores %.2f, floor is %.1f"
                % (fg_name, bg_name, ratio, CONTRAST_FLOOR)
            )
        fixed = _best_text_color(bg)
        repaired.tokens[fg_name] = ThemeToken(
            name=fg_name, value=fixed, kind="color"
        )
        colors[fg_name] = fixed
        repairs.append(
            "%s on %s scored %.2f (< %.1f): repaired to %s"
            % (fg_name, bg_name, ratio, CONTRAST_FLOOR, fixed)
        )
    return repaired, repairs


# ---------------------------------------------------------------------------
# Layouts — MySpace-era reorderable sections
# ---------------------------------------------------------------------------

# Built-in section kinds. "custom" blocks are member-authored structured
# blocks (see CustomBlock) — never raw markup.
SECTION_KINDS = (
    "bio",
    "song",
    "friends",
    "posts",
    "guestbook",
    "mood",
    "custom",
)

_DEFAULT_SECTION_ORDER = ("bio", "song", "friends", "posts", "guestbook", "mood")


@dataclass
class Section:
    """One arrangeable block on the profile canvas."""

    id: str
    kind: str
    title: str = ""
    visible: bool = True

    def validate(self) -> "Section":
        if not isinstance(self.id, str) or not re.match(
            r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z", self.id
        ):
            raise CustomizeError("bad section id %r" % (self.id,))
        if self.kind not in SECTION_KINDS:
            raise CustomizeError(
                "bad section kind %r: must be one of %s"
                % (self.kind, ", ".join(SECTION_KINDS))
            )
        if len(self.title) > 120:
            raise CustomizeError("section title too long (max 120)")
        return self


@dataclass
class Layout:
    """The canvas arrangement: an ordered list of section ids."""

    sections: List[Section] = field(default_factory=list)

    def __post_init__(self) -> None:
        for s in self.sections:
            s.validate()
        ids = [s.id for s in self.sections]
        if len(set(ids)) != len(ids):
            raise CustomizeError("duplicate section ids in layout")

    def reorder(self, order: List[str]) -> "Layout":
        """MySpace-era drag-to-arrange: the member sets the full order.

        The order must name every section exactly once — nothing dropped,
        nothing invented. Hiding is ``visible=False``, not omission.
        """
        known = {s.id for s in self.sections}
        if set(order) != known or len(order) != len(known):
            raise CustomizeError(
                "bad reorder: must name every section id exactly once "
                "(known: %s)" % sorted(known)
            )
        by_id = {s.id: s for s in self.sections}
        self.sections = [by_id[i] for i in order]
        return self

    def order(self) -> List[str]:
        return [s.id for s in self.sections]

    @classmethod
    def default(cls) -> "Layout":
        return cls(
            sections=[
                Section(id=kind, kind=kind, title=kind.title())
                for kind in _DEFAULT_SECTION_ORDER
            ]
        )


# ---------------------------------------------------------------------------
# Custom blocks — member content as structured data, never raw markup
# ---------------------------------------------------------------------------

BLOCK_KINDS = ("heading", "text", "quote", "link", "image", "divider")
_MAX_BLOCK_TEXT = 2000


@dataclass
class CustomBlock:
    """A member-authored block. Plain text and validated URLs only —
    there is no markup channel to smuggle scripts through."""

    kind: str
    text: str = ""
    url: str = ""
    label: str = ""

    def validate(self) -> "CustomBlock":
        if self.kind not in BLOCK_KINDS:
            raise CustomizeError(
                "bad block kind %r: must be one of %s"
                % (self.kind, ", ".join(BLOCK_KINDS))
            )
        if len(self.text) > _MAX_BLOCK_TEXT:
            raise CustomizeError("block text too long (max %d)" % _MAX_BLOCK_TEXT)
        if len(self.label) > 120:
            raise CustomizeError("block label too long (max 120)")
        # Plain-text discipline: no angle brackets, no control chars.
        for what, value in (("text", self.text), ("label", self.label)):
            if "<" in value or ">" in value:
                raise CustomizeError(
                    "bad block %s: markup refused — plain text only" % what
                )
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
                raise CustomizeError("bad block %s: control chars refused" % what)
        if self.kind in ("link", "image"):
            if not self.url:
                raise CustomizeError("block kind %r needs a url" % self.kind)
            _check_url(self.url, "block.url")
        elif self.url:
            _check_url(self.url, "block.url")
        return self


# ---------------------------------------------------------------------------
# Profile song — an anthem, never an ambush
# ---------------------------------------------------------------------------


@dataclass
class ProfileSong:
    """The profile anthem. A reference (URL or platform track id), plus
    display metadata. Playback is always member-initiated: ``autoplay``
    defaults False and True is refused at construction."""

    ref: str
    title: str = ""
    artist: str = ""
    autoplay: bool = False

    def __post_init__(self) -> None:
        if self.autoplay:
            raise CustomizeError(
                "autoplay refused: profile songs never autoplay"
            )
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise CustomizeError("song ref must be a non-empty string")
        if self.ref.startswith("http"):
            _check_url(self.ref, "song.ref")
        elif not re.match(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z", self.ref):
            raise CustomizeError(
                "bad song ref %r: URL or simple track identifier" % (self.ref,)
            )
        if len(self.title) > 200 or len(self.artist) > 200:
            raise CustomizeError("song title/artist too long (max 200)")


# ---------------------------------------------------------------------------
# Animated UI — descriptors as data, validated, degradable
# ---------------------------------------------------------------------------

ANIMATION_TARGETS = ("background", "entrance", "section", "widget", "text")
EASINGS = ("linear", "ease", "ease-in", "ease-out", "ease-in-out")
_MIN_DURATION_MS = 50
_MAX_DURATION_MS = 5000
# Per-target property allowlist: the descriptor names CSS-ish properties,
# but the engine only validates names — the renderer owns the pixels.
_ANIMATION_PROPS = {
    "background": ("opacity", "background-position", "filter"),
    "entrance": ("opacity", "transform"),
    "section": ("opacity", "transform", "max-height"),
    "widget": ("opacity", "transform"),
    "text": ("opacity", "color", "letter-spacing"),
}


@dataclass
class Animation:
    """One animation descriptor: name, target, duration, easing.

    Entrance motion must settle at the natural position (``ends_neutral``)
    — animation never strands content off-canvas or breaks readability.
    """

    name: str
    target: str
    duration_ms: int
    easing: str = "ease"
    properties: Tuple[str, ...] = ()
    ends_neutral: bool = True

    def validate(self) -> "Animation":
        if not isinstance(self.name, str) or not re.match(
            r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z", self.name
        ):
            raise CustomizeError("bad animation name %r" % (self.name,))
        if self.target not in ANIMATION_TARGETS:
            raise CustomizeError(
                "bad animation target %r: must be one of %s"
                % (self.target, ", ".join(ANIMATION_TARGETS))
            )
        if not isinstance(self.duration_ms, int) or not (
            _MIN_DURATION_MS <= self.duration_ms <= _MAX_DURATION_MS
        ):
            raise CustomizeError(
                "bad duration %r: %d–%d ms"
                % (self.duration_ms, _MIN_DURATION_MS, _MAX_DURATION_MS)
            )
        if self.easing not in EASINGS:
            raise CustomizeError(
                "bad easing %r: must be one of %s"
                % (self.easing, ", ".join(EASINGS))
            )
        allowed = _ANIMATION_PROPS[self.target]
        for prop in self.properties:
            if prop not in allowed:
                raise CustomizeError(
                    "bad property %r for target %r: must be one of %s"
                    % (prop, self.target, ", ".join(allowed))
                )
        if self.target == "entrance" and not self.ends_neutral:
            raise CustomizeError(
                "entrance animation %r must end neutral: animation never "
                "breaks readability" % (self.name,)
            )
        return self

    def degraded(self) -> Dict[str, Any]:
        """The reduced-motion form: static. Same identity, no movement."""
        return {"name": self.name, "target": self.target, "motion": "static"}

    def spec(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "target": self.target,
            "duration_ms": self.duration_ms,
            "easing": self.easing,
            "properties": list(self.properties),
            "ends_neutral": self.ends_neutral,
        }


# ---------------------------------------------------------------------------
# Interactive widgets — registry of descriptors, never executed code
# ---------------------------------------------------------------------------

# The registry: name -> {description, params}. Params are validated by key;
# values are plain data. A renderer elsewhere turns descriptors into UI.
WIDGET_REGISTRY: Dict[str, Dict[str, Any]] = {
    "song_player": {
        "description": "Plays the profile anthem. Member-initiated only.",
        "params": ("show_title", "compact"),
    },
    "mood_status": {
        "description": "Current mood/status line with an emoji-free text field.",
        "params": ("default_text",),
    },
    "guestbook": {
        "description": "Visitors leave signed plain-text notes; owner moderates.",
        "params": ("moderated", "max_entries"),
    },
    "draggable_arrange": {
        "description": "Declares the layout reorderable by drag in the renderer.",
        "params": ("axis",),
    },
    "live_preview": {
        "description": "Live theme preview pane while editing tokens.",
        "params": ("show_contrast",),
    },
}


@dataclass
class Widget:
    """One placed widget: a registry name plus validated params."""

    name: str
    params: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> "Widget":
        entry = WIDGET_REGISTRY.get(self.name)
        if entry is None:
            raise CustomizeError(
                "unknown widget %r: registry holds %s"
                % (self.name, ", ".join(sorted(WIDGET_REGISTRY)))
            )
        allowed = entry["params"]
        for key in self.params:
            if key not in allowed:
                raise CustomizeError(
                    "bad param %r for widget %r: allowed %s"
                    % (key, self.name, ", ".join(allowed))
                )
        for key, value in self.params.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if key == "max_entries" and not (1 <= value <= 1000):
                    raise CustomizeError("max_entries must be 1–1000")
                continue
            if isinstance(value, str):
                if len(value) > 200 or "<" in value or ">" in value:
                    raise CustomizeError(
                        "bad param value for %r: plain text, max 200" % key
                    )
                continue
            raise CustomizeError(
                "bad param value for %r: bool, number, or plain string" % key
            )
        return self


@dataclass
class GuestbookEntry:
    """A signed plain-text note. Structured data; the renderer escapes."""

    author: str
    text: str

    def validate(self) -> "GuestbookEntry":
        if not isinstance(self.author, str) or not re.match(
            r"[A-Za-z0-9][A-Za-z0-9 _-]{0,31}\Z", self.author
        ):
            raise CustomizeError("bad guestbook author %r" % (self.author,))
        if not isinstance(self.text, str) or not self.text.strip():
            raise CustomizeError("guestbook text must be non-empty")
        if len(self.text) > 500:
            raise CustomizeError("guestbook text too long (max 500)")
        if "<" in self.text or ">" in self.text:
            raise CustomizeError("guestbook text: markup refused, plain text only")
        return self


# ---------------------------------------------------------------------------
# The whole canvas — one profile's customization, sealed and portable
# ---------------------------------------------------------------------------


@dataclass
class ProfileCustomization:
    """Everything a member controls about their face: theme, layout,
    blocks, song, animations, widgets. Owner-only state; the profile id
    ties it to the seat (identity lives in Cybrus, never here)."""

    profile_id: str
    theme: ProfileTheme = field(default_factory=ProfileTheme)
    layout: Layout = field(default_factory=Layout.default)
    blocks: List[CustomBlock] = field(default_factory=list)
    song: Optional[ProfileSong] = None
    animations: List[Animation] = field(default_factory=list)
    widgets: List[Widget] = field(default_factory=list)
    repairs: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not re.match(
            r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z", self.profile_id
        ):
            raise CustomizeError("bad profile_id %r" % (self.profile_id,))
        for b in self.blocks:
            b.validate()
        for a in self.animations:
            a.validate()
        for w in self.widgets:
            w.validate()
        names = [a.name for a in self.animations]
        if len(set(names)) != len(names):
            raise CustomizeError("duplicate animation names")
        wnames = [w.name for w in self.widgets]
        if len(set(wnames)) != len(wnames):
            raise CustomizeError("duplicate widget names")

    def apply_guardrails(self, *, strict: bool = False) -> "ProfileCustomization":
        """Run the binding guardrails: contrast floor on the theme.

        Repairs are recorded on ``self.repairs`` so the member sees what
        the platform fixed and why. Strict mode refuses instead.
        """
        repaired_theme, repairs = enforce_contrast(self.theme, strict=strict)
        self.theme = repaired_theme
        self.repairs.extend(repairs)
        return self

    def render(self, *, reduced_motion: bool = False) -> Dict[str, Any]:
        """The renderer-ready spec. With ``reduced_motion=True`` every
        animation degrades to its static form — same identity, no movement.
        """
        if reduced_motion:
            animations = [a.degraded() for a in self.animations]
        else:
            animations = [a.spec() for a in self.animations]
        return {
            "profile_id": self.profile_id,
            "theme": {
                name: (tok.value if not isinstance(tok.value, dict) else tok.value)
                for name, tok in self.theme.tokens.items()
            },
            "layout": self.layout.order(),
            "sections": [asdict(s) for s in self.layout.sections],
            "blocks": [asdict(b) for b in self.blocks],
            "song": asdict(self.song) if self.song else None,
            "animations": animations,
            "widgets": [
                {"name": w.name, "params": dict(w.params)} for w in self.widgets
            ],
            "repairs": list(self.repairs),
            "reduced_motion": reduced_motion,
        }

    # -- portable sealed form (mirrors the manifests bundle discipline) --

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "format": CUSTOMIZE_FORMAT,
            "version": CUSTOMIZE_VERSION,
            "profile_id": self.profile_id,
            "theme": {
                name: {"value": tok.value, "kind": tok.kind}
                for name, tok in self.theme.tokens.items()
            },
            "layout": [asdict(s) for s in self.layout.sections],
            "blocks": [asdict(b) for b in self.blocks],
            "song": asdict(self.song) if self.song else None,
            "animations": [
                {
                    "name": a.name,
                    "target": a.target,
                    "duration_ms": a.duration_ms,
                    "easing": a.easing,
                    "properties": list(a.properties),
                    "ends_neutral": a.ends_neutral,
                }
                for a in self.animations
            ],
            "widgets": [
                {"name": w.name, "params": dict(w.params)} for w in self.widgets
            ],
            "repairs": list(self.repairs),
        }
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        data["checksum"] = hashlib.sha256(canonical.encode()).hexdigest()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfileCustomization":
        if data.get("format") != CUSTOMIZE_FORMAT:
            raise CustomizeError("bad bundle format %r" % (data.get("format"),))
        if data.get("version") != CUSTOMIZE_VERSION:
            raise CustomizeError("bad bundle version %r" % (data.get("version"),))
        expect = data.get("checksum", "")
        body = {k: v for k, v in data.items() if k != "checksum"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        if hashlib.sha256(canonical.encode()).hexdigest() != expect:
            raise CustomizeError("checksum mismatch: tampered bundle refused")
        theme = ProfileTheme()
        for name, tok in body.get("theme", {}).items():
            theme.set(
                ThemeToken(name=name, value=tok["value"], kind=tok["kind"])
            )
        song_data = body.get("song")
        return cls(
            profile_id=body["profile_id"],
            theme=theme,
            layout=Layout(
                sections=[Section(**s) for s in body.get("layout", [])]
            ),
            blocks=[CustomBlock(**b) for b in body.get("blocks", [])],
            song=ProfileSong(**song_data) if song_data else None,
            animations=[
                Animation(
                    name=a["name"],
                    target=a["target"],
                    duration_ms=a["duration_ms"],
                    easing=a.get("easing", "ease"),
                    properties=tuple(a.get("properties", ())),
                    ends_neutral=a.get("ends_neutral", True),
                )
                for a in body.get("animations", [])
            ],
            widgets=[
                Widget(name=w["name"], params=dict(w.get("params", {})))
                for w in body.get("widgets", [])
            ],
            repairs=list(body.get("repairs", [])),
        )
