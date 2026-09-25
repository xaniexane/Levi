"""hub.themes: Myspace-style system-wide theming — safe structured themes.

The Hub absorbs Myspace's soul: the interface is personal everywhere.
But Myspace let users inject raw HTML/JS (the XSS era); the Hub keeps the
soul and reverses the compromise: **themes are structured data only** —
validated tokens, never raw markup or scripts. A theme pack is a JSON
document a member installs, tunes, and carries — and, in a later
marketplace milestone, buys and sells. Nothing in this module wires
payments: see the owner gate note on ``PLATFORM_CUT``.

What it does:

- ``ThemePack`` — immutable, strictly validated theme-pack format:
  named colors (hex only), font stacks from an allowlist, radius and
  density presets from allowlists. Unknown keys, URLs, raw CSS, and
  HTML/JS are rejected at validation time, not render time.
- ``THEME_SURFACES`` — every surface the Hub will ever have receives the
  same active pack: feed, communities, discovery, creation, profile,
  marketplace, messages, the LEVI tab, settings. Theming is applied
  THROUGHOUT, on one code path, so it works on mobile too.
- ``css_variables(pack)`` — one ``:root{...}`` block every surface
  embeds. CSS variables do the work; no per-surface CSS duplication.
- ``ThemeStore`` — local-first JSON store (~/.levi/hub-social/themes):
  install, list, activate, deactivate, export, import. The member's
  themes are portable data, not platform assets.
- ``PLATFORM_CUT = 0.12`` — PL-05 doctrine: the platform's stated cut on
  digital products created and monetized on-platform (theme packs are
  future marketplace products). Named constant, never magic numbers.
  ``creator_net`` / ``stated_price_for_net`` do the pure arithmetic —
  no processor wiring, no charges; real payment collection is OWNER-GATED
  (see ``GATED`` below).
- Ternary: ``density`` is three states — ``compact``, ``comfortable``,
  ``airy`` — the third state the giants' binary cozy/roomy switches skip.
- Paired mind: ``validate()`` proposes, ``sanitize()`` verifies — every
  pack is checked by two independent passes (the verifier never trusts
  the proposer's say-so).

Hard limits:

- No advertising hooks, no analytics tokens, no telemetry fields.
- No network calls. Local-only by construction.
- Physical-goods economics: not in this module, no cut assumed, per plan.

GATED ON CHAUNCEY: actual theme-pack sales / payment collection; the
8-vs-12 bottom-nav tab map (this module serves CSS to every surface but
does not decide the map); any network exposure beyond 127.0.0.1; any
customer release.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------
# Doctrines as constants
# --------------------------------------------------------------------------

#: PL-05: platform cut on digital products created and monetized on-platform.
#: Stated once, published, stable — never hardcoded as a magic number.
PLATFORM_CUT = 0.12

#: Currency unit for the cut math: integer cents, no floats in money paths.
CENTS = 100

# --------------------------------------------------------------------------
# Safe-by-construction token space
# --------------------------------------------------------------------------

_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

#: Colors are hex only. No URLs, no functions, no raw CSS.
COLOR_TOKENS = (
    "bg",
    "bg2",
    "line",
    "fg",
    "dim",
    "accent",
    "ok",
    "warn",
    "danger",
)

#: Fonts come from named system stacks only. No @font-face URLs, no webfonts.
FONT_STACKS = {
    "system": "system-ui, -apple-system, 'Segoe UI', sans-serif",
    "serif": "Georgia, 'Times New Roman', serif",
    "mono": "ui-monospace, 'SF Mono', Menlo, monospace",
    "rounded": "'Trebuchet MS', 'Segoe UI', system-ui, sans-serif",
}

RADIUS_VALUES = {"sm": "6px", "md": "10px", "lg": "16px"}

#: The ternary: density is THREE states, not the binary cozy/roomy.
DENSITY_VALUES = {"compact", "comfortable", "airy"}
DENSITY_PAD = {"compact": "6px", "comfortable": "12px", "airy": "20px"}

KNOWN_TOP_KEYS = {"name", "author", "version", "description", "tokens"}
KNOWN_TOKEN_KEYS = set(COLOR_TOKENS) | {"font", "radius", "density"}

#: Every surface the Hub will ever have gets the same active pack —
#: theming is THROUGHOUT, one code path, mobile included.
THEME_SURFACES = (
    "feed",
    "communities",
    "discovery",
    "creation",
    "profile",
    "marketplace",
    "messages",
    "levi-tab",
    "settings",
)


class ThemeError(ValueError):
    """Raised when a theme pack fails validation."""


def _propose(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Pass 1 (proposer): structural shape check on a raw pack dict."""
    if not isinstance(raw, dict):
        raise ThemeError("theme pack must be a JSON object")
    unknown = set(raw) - KNOWN_TOP_KEYS
    if unknown:
        raise ThemeError(f"unknown theme-pack keys: {sorted(unknown)}")
    tokens = raw.get("tokens")
    if not isinstance(tokens, dict):
        raise ThemeError("theme pack needs a 'tokens' object")
    bad = set(tokens) - KNOWN_TOKEN_KEYS
    if bad:
        raise ThemeError(f"unknown tokens: {sorted(bad)}")
    return raw


def _verify(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Pass 2 (verifier): value safety check. Never trusts pass 1."""
    tokens = raw["tokens"]
    out: Dict[str, Any] = {}
    for key in COLOR_TOKENS:
        value = tokens.get(key, "")
        if not isinstance(value, str) or not _HEX_COLOR.match(value):
            raise ThemeError(f"token '{key}' must be a hex color like #0d1117")
        # A verifier does not trust the proposer's regex alone: normalize.
        out[key] = value.lower()
    font = tokens.get("font", "system")
    if font not in FONT_STACKS:
        raise ThemeError(f"font must be one of {sorted(FONT_STACKS)}")
    out["font"] = font
    radius = tokens.get("radius", "md")
    if radius not in RADIUS_VALUES:
        raise ThemeError(f"radius must be one of {sorted(RADIUS_VALUES)}")
    out["radius"] = radius
    density = tokens.get("density", "comfortable")
    if density not in DENSITY_VALUES:
        raise ThemeError(f"density must be one of {sorted(DENSITY_VALUES)}")
    out["density"] = density
    # Meta fields: length-bounded, no markup allowed through.
    meta: Dict[str, Any] = {}
    for key in ("name", "author", "description"):
        value = raw.get(key, "")
        if not isinstance(value, str):
            raise ThemeError(f"'{key}' must be a string")
        if len(value) > 200:
            raise ThemeError(f"'{key}' exceeds 200 characters")
        if "<" in value or ">" in value:
            raise ThemeError(f"'{key}' must be plain text (no markup)")
        meta[key] = value
    version = raw.get("version", "1.0.0")
    if not isinstance(version, str) or not re.match(r"^\d+\.\d+\.\d+$", version):
        raise ThemeError("version must be semver like 1.0.0")
    meta["version"] = version
    return {"meta": meta, "tokens": out}


@dataclass(frozen=True)
class ThemePack:
    """An immutable, validated theme pack — structured data only.

    Construct only via :meth:`from_dict` / :meth:`from_json` so every
    instance has passed both validation passes.
    """

    name: str
    author: str
    version: str
    description: str
    tokens: Dict[str, str] = field(repr=False)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ThemePack":
        shaped = _propose(copy.deepcopy(raw))  # proposer pass
        clean = _verify(shaped)  # verifier pass (independent)
        return cls(tokens=clean["tokens"], **clean["meta"])

    @classmethod
    def from_json(cls, text: str) -> "ThemePack":
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ThemeError(f"invalid JSON: {exc}") from exc
        return cls.from_dict(raw)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "author": self.author,
            "version": self.version,
            "description": self.description,
            "tokens": dict(self.tokens),
        }

    def to_json(self) -> str:
        """Portable export: the member's pack travels with the member."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def derive(self, **overrides: Any) -> "ThemePack":
        """A new pack with token overrides — still passes both passes."""
        raw = self.to_dict()
        raw["tokens"] = {**raw["tokens"], **overrides}
        return ThemePack.from_dict(raw)


def css_variables(pack: ThemePack) -> str:
    """The one CSS block every surface embeds. Pure CSS variables —
    mobile-safe, no per-surface styles to keep in sync.
    """
    t = pack.tokens
    lines = [":root{"]
    for key in COLOR_TOKENS:
        lines.append(f"--hub-{key}:{t[key]};")
    lines.append(f"--hub-font:{FONT_STACKS[t['font']]};")
    lines.append(f"--hub-radius:{RADIUS_VALUES[t['radius']]};")
    lines.append(f"--hub-pad:{DENSITY_PAD[t['density']]};")
    lines.append(f"--hub-density:{t['density']};")
    lines.append("}")
    return "".join(lines)


# --------------------------------------------------------------------------
# Built-in packs (safe defaults; ship with the product)
# --------------------------------------------------------------------------


def _builtin(name: str, author: str, description: str, **tokens: str) -> ThemePack:
    return ThemePack.from_dict(
        {
            "name": name,
            "author": author,
            "version": "1.0.0",
            "description": description,
            "tokens": tokens,
        }
    )


def void_pack() -> ThemePack:
    """Void — dark default. The calm baseline."""
    return _builtin(
        "Void",
        "Hub",
        "The dark default — calm, high-contrast, phone-first.",
        bg="#0d1117",
        bg2="#161b22",
        line="#30363d",
        fg="#e6edf3",
        dim="#8b949e",
        accent="#58a6ff",
        ok="#3fb950",
        warn="#d29922",
        danger="#f85149",
        font="system",
        radius="md",
        density="comfortable",
    )


def paper_pack() -> ThemePack:
    """Paper — light reading theme."""
    return _builtin(
        "Paper",
        "Hub",
        "A light theme for daylight reading.",
        bg="#ffffff",
        bg2="#f6f8fa",
        line="#d0d7de",
        fg="#1f2328",
        dim="#59636e",
        accent="#0969da",
        ok="#1a7f37",
        warn="#9a6700",
        danger="#d1242f",
        font="system",
        radius="md",
        density="airy",
    )


def dusk_pack() -> ThemePack:
    """Dusk — warm night theme."""
    return _builtin(
        "Dusk",
        "Hub",
        "Warm night tones for late scrolling.",
        bg="#1a1410",
        bg2="#241c15",
        line="#4a3a2c",
        fg="#f5e8d8",
        dim="#a8927a",
        accent="#ffb86b",
        ok="#7bc96f",
        warn="#e5a93d",
        danger="#ef6461",
        font="rounded",
        radius="lg",
        density="comfortable",
    )


BUILTIN_PACKS = {"void": void_pack, "paper": paper_pack, "dusk": dusk_pack}


# --------------------------------------------------------------------------
# Local-first store
# --------------------------------------------------------------------------


def _data_dir() -> Path:
    root = os.environ.get("LEVI_HUB_SOCIAL_DIR") or os.path.join(
        os.path.expanduser("~"), ".levi", "hub-social"
    )
    return Path(root) / "themes"


class ThemeStore:
    """Local-first theme store. JSON files under the data dir; nothing
    leaves the device. One active pack applies to EVERY surface.
    """

    ACTIVE_FILE = "active.json"

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else _data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # -- packs ------------------------------------------------------------
    def _path(self, name: str) -> Path:
        safe = re.sub(r"[^a-z0-9_-]", "", name.lower().replace(" ", "-"))
        if not safe:
            raise ThemeError("pack name is empty after sanitizing")
        return self.data_dir / f"{safe}.theme.json"

    def install(self, pack: ThemePack) -> None:
        """Install a validated pack. Builtin names are protected — installing
        over 'Void'/'Paper'/'Dusk' would shadow the deterministic defaults."""
        if pack.name.lower() in BUILTIN_PACKS:
            raise ThemeError(f"builtin pack '{pack.name}' is protected")
        target = self._path(pack.name)
        target.write_text(pack.to_json(), encoding="utf-8")

    def list(self) -> List[str]:
        names = sorted(BUILTIN_PACKS)
        for path in sorted(self.data_dir.glob("*.theme.json")):
            try:
                names.append(ThemePack.from_json(path.read_text("utf-8")).name)
            except (ThemeError, OSError):
                continue  # a corrupt file never breaks the list
        return names

    def get(self, name: str) -> ThemePack:
        key = name.lower()
        if key in BUILTIN_PACKS:
            return BUILTIN_PACKS[key]()
        return ThemePack.from_json(self._path(name).read_text(encoding="utf-8"))

    # -- activation --------------------------------------------------------
    def activate(self, name: str) -> ThemePack:
        pack = self.get(name)  # raises if unknown/corrupt — fail loud here
        (self.data_dir / self.ACTIVE_FILE).write_text(
            json.dumps({"active": pack.name}), encoding="utf-8"
        )
        return pack

    def deactivate(self) -> ThemePack:
        (self.data_dir / self.ACTIVE_FILE).unlink(missing_ok=True)
        return void_pack()

    def active(self) -> ThemePack:
        path = self.data_dir / self.ACTIVE_FILE
        if path.exists():
            try:
                name = json.loads(path.read_text("utf-8")).get("active", "")
                return self.get(name)
            except (ThemeError, OSError, json.JSONDecodeError, KeyError):
                pass
        return void_pack()

    def active_css(self) -> str:
        """The CSS block every surface embeds — theming THROUGHOUT."""
        return css_variables(self.active())

    def css_for_surface(self, surface: str) -> str:
        """Same pack, any surface. A wrong surface name is a bug — say so."""
        if surface not in THEME_SURFACES:
            raise ThemeError(
                f"unknown surface '{surface}'; expected one of {THEME_SURFACES}"
            )
        return self.active_css()


# --------------------------------------------------------------------------
# PL-05 economics: the stated 12% cut — pure math, no processor wiring.
# Real payment collection is OWNER-GATED. These functions only answer
# "what would the numbers be" so creators see the deal up front.
# --------------------------------------------------------------------------


def creator_net(gross_cents: int) -> int:
    """Cents the creator keeps after the stated platform cut."""
    if gross_cents < 0:
        raise ValueError("gross_cents must be >= 0")
    return int(gross_cents * (1 - PLATFORM_CUT))


def platform_cut_cents(gross_cents: int) -> int:
    """Cents the platform takes at the stated cut."""
    if gross_cents < 0:
        raise ValueError("gross_cents must be >= 0")
    return int(round(gross_cents * PLATFORM_CUT))


def stated_price_for_net(net_cents: int) -> int:
    """Gross list price (cents) that leaves the creator with net_cents."""
    if net_cents < 0:
        raise ValueError("net_cents must be >= 0")
    return int(round(net_cents / (1 - PLATFORM_CUT)))


def cut_disclosure() -> str:
    """The published deal, in plain words — no stacked layers, no surprises."""
    pct = int(PLATFORM_CUT * 100)
    return (
        f"One number, stated up front: the platform takes {pct}% on digital "
        "products sold on-platform. No listing fees, no stacked layers. "
        "Physical-goods economics are not decided — no cut assumed."
    )
