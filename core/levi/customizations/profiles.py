"""LEVI customizations — named runtime profiles a user can tune.

The first LEVI-native customizations surface: a small, file-backed profile
store. A profile names the machine's posture — quiet hours, daemon cadence
overrides, persona stance, briefing line budget, which daemons run — and
profiles are applied by name. Daemons read the active profile; nothing in
this package ever touches a daemon, it only writes the record.

Storage is local-first: ``~/.levi/customizations/active.json``. Everything
is deny-closed: unknown stances, out-of-range hours, empty names, and
unparseable profiles are refused with a named error, never coerced.

Usage::

    from levi.customizations import profiles

    p = profiles.build_profile("night-owl", quiet_hours=(23, 7),
                               cadence_overrides={"heartbeat": 120},
                               persona_stance="soft", brief_lines=10)
    profiles.activate(p)                    # writes active.json
    active = profiles.read_active()         # Profile | None

Run it: ``python -m levi.customizations.profiles list``
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

__all__ = [
    "ProfileError",
    "Profile",
    "STANCES",
    "DEFAULT_ROOT",
    "build_profile",
    "activate",
    "read_active",
    "deactivate",
    "list_profiles",
]


class ProfileError(ValueError):
    """Raised when a profile fails validation or the store misbehaves."""


#: Persona stances a profile may name. The persona lattice owns their
#: meaning; here they are opaque labels.
STANCES = ("soft", "plain", "sharp", "playful", "solemn", "mischief")

#: Where profiles live unless a caller says otherwise.
DEFAULT_ROOT = Path.home() / ".levi" / "customizations"

_ACTIVE_FILE = "active.json"


@dataclass(frozen=True)
class Profile:
    """One named posture for the machine."""

    name: str
    quiet_hours: Tuple[int, int] = (22, 7)  # (start_hour, end_hour) 0-23, wraps
    cadence_overrides: Dict[str, int] = field(default_factory=dict)
    persona_stance: str = "plain"
    brief_lines: int = 16
    daemons_enabled: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "quiet_hours": list(self.quiet_hours),
            "cadence_overrides": dict(self.cadence_overrides),
            "persona_stance": self.persona_stance,
            "brief_lines": self.brief_lines,
            "daemons_enabled": list(self.daemons_enabled),
        }

    @staticmethod
    def from_dict(data: dict) -> "Profile":
        return build_profile(
            data.get("name"),
            quiet_hours=tuple(data.get("quiet_hours", (22, 7))),
            cadence_overrides=data.get("cadence_overrides", {}),
            persona_stance=data.get("persona_stance", "plain"),
            brief_lines=data.get("brief_lines", 16),
            daemons_enabled=data.get("daemons_enabled", []),
        )


def _hour(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProfileError(f"{where}: hours must be ints 0-23, got {value!r}")
    if not 0 <= value <= 23:
        raise ProfileError(f"{where}: hours must be 0-23, got {value}")
    return value


def build_profile(
    name: object,
    quiet_hours: object = (22, 7),
    cadence_overrides: Optional[Dict[str, int]] = None,
    persona_stance: object = "plain",
    brief_lines: object = 16,
    daemons_enabled: Optional[List[str]] = None,
) -> Profile:
    """Validate everything and build an immutable Profile."""
    if not isinstance(name, str) or not name.strip():
        raise ProfileError(f"profile name must be a non-empty string, got {name!r}")
    if not name.replace("-", "").replace("_", "").isalnum():
        raise ProfileError(f"profile name must be [a-z0-9_-], got {name!r}")

    if not isinstance(quiet_hours, (tuple, list)) or len(quiet_hours) != 2:
        raise ProfileError(
            f"quiet_hours must be a (start, end) pair, got {quiet_hours!r}"
        )
    start, end = (
        _hour(quiet_hours[0], "quiet_hours.start"),
        _hour(quiet_hours[1], "quiet_hours.end"),
    )
    if start == end:
        raise ProfileError("quiet_hours start and end must differ")

    overrides = cadence_overrides or {}
    if not isinstance(overrides, dict):
        raise ProfileError(f"cadence_overrides must be a dict, got {overrides!r}")
    clean_overrides: Dict[str, int] = {}
    for daemon, minutes in overrides.items():
        if not isinstance(daemon, str) or not daemon.strip():
            raise ProfileError(
                f"cadence key must be a non-empty string, got {daemon!r}"
            )
        if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes < 1:
            raise ProfileError(
                f"cadence for {daemon!r} must be minutes >= 1, got {minutes!r}"
            )
        clean_overrides[daemon] = minutes

    if persona_stance not in STANCES:
        raise ProfileError(
            f"persona_stance must be one of {STANCES}, got {persona_stance!r}"
        )

    if isinstance(brief_lines, bool) or not isinstance(brief_lines, int):
        raise ProfileError(f"brief_lines must be an int, got {brief_lines!r}")
    if not 4 <= brief_lines <= 120:
        raise ProfileError(f"brief_lines must be 4-120, got {brief_lines}")

    enabled = daemons_enabled or []
    if not isinstance(enabled, (list, tuple)):
        raise ProfileError(f"daemons_enabled must be a list, got {enabled!r}")
    clean_enabled = []
    for daemon in enabled:
        if not isinstance(daemon, str) or not daemon.strip():
            raise ProfileError(
                f"daemons_enabled entries must be non-empty strings, got {daemon!r}"
            )
        clean_enabled.append(daemon)
    if len(set(clean_enabled)) != len(clean_enabled):
        raise ProfileError("daemons_enabled has duplicates")

    return Profile(
        name=name,
        quiet_hours=(start, end),
        cadence_overrides=clean_overrides,
        persona_stance=persona_stance,
        brief_lines=brief_lines,
        daemons_enabled=clean_enabled,
    )


def _root(path: Optional[Path]) -> Path:
    root = Path(path) if path is not None else DEFAULT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def activate(profile: Profile, root: Optional[Path] = None) -> Path:
    """Write the profile as the active one. Returns the file path."""
    if not isinstance(profile, Profile):
        raise ProfileError(f"activate expects a Profile, got {type(profile).__name__}")
    target = _root(root) / _ACTIVE_FILE
    tmp = target.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(profile.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    tmp.replace(target)
    return target


def read_active(root: Optional[Path] = None) -> Optional[Profile]:
    """Read the active profile; None when none is set. Corrupt = error, not None."""
    target = _root(root) / _ACTIVE_FILE
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProfileError(f"active profile is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError("active profile must be a JSON object")
    return Profile.from_dict(data)


def deactivate(root: Optional[Path] = None) -> bool:
    """Remove the active profile. Returns True if one was set."""
    target = _root(root) / _ACTIVE_FILE
    if not target.exists():
        return False
    target.unlink()
    return True


def list_profiles(root: Optional[Path] = None) -> List[str]:
    """Names of stored profiles (active plus any saved *.profile.json)."""
    base = _root(root)
    names = []
    active = base / _ACTIVE_FILE
    if active.exists():
        try:
            data = json.loads(active.read_text(encoding="utf-8"))
            names.append(data.get("name", "(unnamed)"))
        except (json.JSONDecodeError, AttributeError):
            names.append("(corrupt)")
    for path in sorted(base.glob("*.profile.json")):
        if path.name != _ACTIVE_FILE:
            names.append(path.stem.replace(".profile", ""))
    return names


def _cli(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="levi.customizations.profiles",
        description="Named runtime profiles for LEVI's posture.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="print the active profile")
    sub.add_parser("list", help="list known profile names")
    act = sub.add_parser("activate", help="activate a profile built from flags")
    act.add_argument("name")
    act.add_argument("--quiet", default="22-7", help="start-end hours, e.g. 22-7")
    act.add_argument("--stance", default="plain", choices=STANCES)
    act.add_argument("--brief-lines", type=int, default=16)
    act.add_argument(
        "--daemon", action="append", default=[], help="enable a daemon (repeatable)"
    )
    args = ap.parse_args(argv)

    if args.cmd == "list":
        for name in list_profiles():
            print(name)
        return 0
    if args.cmd == "show":
        active = read_active()
        if active is None:
            print("no active profile")
            return 1
        print(json.dumps(active.to_dict(), indent=2, sort_keys=True))
        return 0
    try:
        start_s, end_s = args.quiet.split("-", 1)
        profile = build_profile(
            args.name,
            quiet_hours=(int(start_s), int(end_s)),
            persona_stance=args.stance,
            brief_lines=args.brief_lines,
            daemons_enabled=args.daemon,
        )
    except (ValueError, ProfileError) as exc:
        ap.error(str(exc))
    path = activate(profile)
    print(f"activated {profile.name} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
